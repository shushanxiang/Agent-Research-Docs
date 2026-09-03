"""检索模块冒烟测试 — 验证知识库查询是否正常工作"""
import httpx, json, sys, time

BASE = "http://localhost:8000"
client = httpx.Client(timeout=30)

# ═══ 1. 索引状态 ═══
print("=" * 60)
print("  检索模块冒烟测试")
print("=" * 60)

r = client.get(f"{BASE}/api/v1/documents/stats")
stats = r.json()
total_chunks = stats["total_chunks"]
total_docs = stats["total_documents"]
print(f"\n索引状态: {total_chunks} chunks / {total_docs} docs")
if total_chunks == 0:
    print("  ❌ 索引为空，请先上传文档")
    sys.exit(1)

# ═══ 2. 文档列表 ═══
r = client.get(f"{BASE}/api/v1/documents/")
docs = r.json()
print(f"\n已入库文档 ({docs['total']}):")
for d in docs["items"]:
    kb = "KB" if d["file_size"] < 10000 else "MB"
    size = d["file_size"] / 1024 if kb == "KB" else d["file_size"] / (1024 * 1024)
    print(f"  [{d['category']}] {d['filename']} ({size:.1f}{kb})")
    if d.get("metadata", {}).get("keywords"):
        print(f"       keywords: {d['metadata']['keywords']}")

# ═══ 3. 多条查询测试 ═══
queries = [
    ("疏散走道宽度要求", "GB 50222-2022", "4.1"),
    ("外墙保温材料燃烧性能等级", "GB 50222-2022", None),
    ("高层建筑高宽比不应超过多少", "JGJ 3-2010", "5.1"),
    ("消火栓被装饰物遮掩", "GB 50222-2022", "4.3.1"),
    ("框架剪力墙双向抗侧力", "JGJ 3-2010", "7.1.1"),
    ("住宅消防安全保障措施", None, None),  # 查真实 PDF
]

print(f"\n检索测试 ({len(queries)} 条):")
print("-" * 60)

pass_count = 0
fail_count = 0

for q, expected_code, expected_clause in queries:
    t0 = time.time()
    r = client.post(f"{BASE}/api/v1/search/regulations",
                    json={"query": q, "top_k": 3})
    elapsed = time.time() - t0
    d = r.json()

    top = d["results"][0] if d["results"] else None
    if not top:
        print(f'  ❌ "{q}" -> 无结果')
        fail_count += 1
        continue

    code_match = (expected_code is None) or (top["standard_code"] == expected_code)
    clause_match = (expected_clause is None) or (expected_clause in (top["clause_id"] or ""))

    if code_match:
        pass_count += 1
        print(f'  ✅ [{top["clause_id"]}] {top["standard_code"]} score={top["score"]:.3f} | {top["content"][:55]}')
        print(f'     查询: "{q}"  ({elapsed:.3f}s)')
    else:
        fail_count += 1
        print(f'  ❌ 期望 {expected_code} 实际 {top["standard_code"]}')
        print(f'     查询: "{q}"  ({elapsed:.3f}s)')

# ═══ 4. 图集检索 ═══
print(f"\n图集检索测试:")
r = client.post(f"{BASE}/api/v1/search/atlas",
                json={"query": "屋面防水上人屋面"})
d = r.json()
if d["total"] > 0:
    pass_count += 1
    top = d["results"][0]
    print(f'  ✅ [{top["node_id"]}] {top["node_name"]} score={top["similarity_score"]:.3f}')
else:
    print(f'  ⚠ 图集索引为空（需上传图集文档）')

# ═══ 汇总 ═══
total = pass_count + fail_count
client.close()
print(f"\n{'='*60}")
print(f"  结果: {pass_count}/{total} 通过, {fail_count} 失败")
print(f"{'='*60}")
if fail_count:
    sys.exit(1)
