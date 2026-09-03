"""
排查脚本：一键诊断当前服务状态并定位乱码来源
用法: python debug_garbage.py
"""
import httpx, re

BASE = "http://localhost:8000"
c = httpx.Client(timeout=30)
issues = []

# ═══ 1. 索引状态 ═══
stats = c.get(f"{BASE}/api/v1/documents/stats").json()
print(f"[1] 索引: {stats['total_chunks']} chunks / {stats['total_documents']} docs")
if stats["total_chunks"] == 0:
    print("    -> 索引为空，无乱码风险")

# ═══ 2. 逐文档检查 ═══
docs = c.get(f"{BASE}/api/v1/documents/").json()
print(f"\n[2] 文档列表 ({docs['total']} 个):")
for d in docs.get("items", []):
    parser = d.get("parser", "未知")
    raw = d.get("raw_text", "")
    raw_preview = raw[:60]

    # 检测 PDF 二进制
    is_binary = (
        raw.startswith("%PDF") or
        "JVBERi0" in raw_preview or
        raw.startswith("\x25\x50\x44\x46")
    )

    # 检测乱码比例
    total = len(raw)
    cjk = sum(1 for ch in raw if '\u4e00' <= ch <= '\u9fff' or '\u3400' <= ch <= '\u4dbf')
    garbage = sum(1 for ch in raw if ord(ch) > 127 and not (
        '\u4e00' <= ch <= '\u9fff' or
        '\u3400' <= ch <= '\u4dbf' or
        ch in '，。、；：？！""''【】（）《》—…×≤≥㎡①②③④⑤⑥⑦⑧⑨⑩'
    ))
    ratio = garbage / max(total, 1)

    status = "✅"
    if is_binary:
        status = "❌ PDF二进制误入"
        issues.append(f"文档 {d['filename']} 包含 PDF 二进制内容")
    elif ratio > 0.3:
        status = f"⚠ 乱码比例 {ratio:.0%}"
        issues.append(f"文档 {d['filename']} 乱码比例 {ratio:.0%}")

    print(f"  [{parser}] {d['filename']} ({d['file_size']}B)")
    print(f"    raw: {repr(raw_preview)}")
    print(f"    CJK={cjk} 垃圾字符={garbage}  ({status})")

# ═══ 3. 检索测试 ═══
if docs["total"] > 0:
    print(f"\n[3] 检索测试:")
    queries = ["疏散走道", "防火", "建筑"]
    for q in queries:
        r = c.post(f"{BASE}/api/v1/search/regulations", json={"query": q, "top_k": 1})
        d = r.json()
        if d["results"]:
            content = d["results"][0]["content"]
            has_cjk = any('\u4e00' <= ch <= '\u9fff' for ch in content)
            print(f"  '{q}': has_CJK={has_cjk}  top={content[:50]}...")
            if not has_cjk and len(content) > 10:
                issues.append(f"检索结果无中文字符: query='{q}' content='{content[:30]}'")

# ═══ 汇总 ═══
print()
if issues:
    print(f"发现 {len(issues)} 个问题:")
    for i, iss in enumerate(issues, 1):
        print(f"  {i}. {iss}")
    print(f"\n修复步骤:")
    print(f"  1. 浏览器访问 POST {BASE}/api/v1/documents/reset")
    print(f"  2. 重新上传文档（确保 parser 字段不是 'rejected'）")
    print(f"  3. 如果是 PDF 未正确解析，检查 MINERU_API_TOKEN 或安装 PyMuPDF")
    print(f"  uvicorn 日志位置: stdout (终端输出)")
    print(f"  关键日志搜索: 'ParseService' / 'MinerU' / 'rejected'")
else:
    print("未发现乱码问题 ✅")
    print(f"如需详细日志，重启 uvicorn 时加 --log-level debug:")
    print(f"  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level debug")

c.close()
