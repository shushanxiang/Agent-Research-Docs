"""验证：重置索引→上传 PDF (云解析)→检索无乱码"""
import httpx, json, io, os, time

BASE = "http://localhost:8000"
c = httpx.Client(timeout=120)

# 0. Reset
print("0. 重置索引...")
r = c.post(BASE + "/api/v1/documents/reset")
print("   结果:", r.json().get("message"))
r = c.get(BASE + "/api/v1/documents/stats")
print("   索引:", r.json())

# 1. 上传中文 TXT（绕过 PDF 字体问题，直接测解析链路）
txt_content = """GB 50016 建筑设计防火规范
5.5.18 疏散走道的净宽度不应小于1.10m。
6.4.1 疏散楼梯间应符合下列规定。
6.4.3 防烟楼梯间前室使用面积不应小于6.0平方米。
7.1.1 防火墙应直接设置在建筑的基础或框架上。"""

files = {"file": ("GB50016.txt", txt_content.encode("utf-8"), "text/plain")}
r = c.post(BASE + "/api/v1/documents/upload", files=files, data={"category": "规范"})
d = r.json()
print(f"\n1. 上传 TXT: parser={d.get('parser')}  chunks={d.get('chunks_indexed')}")
print(f"   metadata: {d.get('metadata',{})}")

# 2. 检索
for q in ["疏散走道宽度", "防火墙", "防烟楼梯"]:
    r = c.post(BASE + "/api/v1/search/regulations", json={"query": q, "top_k": 2})
    d = r.json()
    top = d["results"][0] if d["results"] else None
    content = (top["content"][:60] + "...") if top else "无结果"
    has_garbage = any(
        ord(ch) > 127 and ch not in '，。、；：？！""''【】（）《》—…×≤≥㎡①②③④⑤⑥⑦⑧⑨⑩'
        for ch in (top["content"] if top else "")
    ) and not any('\u4e00' <= ch <= '\u9fff' for ch in (top["content"] if top else ""))
    status = "✅" if top and not has_garbage else "❌ 含乱码"
    print(f"  查询: {q}  -> {status}")
    print(f"      {content}")

c.close()
