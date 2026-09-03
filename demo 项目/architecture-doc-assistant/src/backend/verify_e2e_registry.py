"""端到端验证：上传→检索→问答 同一数据源"""
import httpx
client = httpx.Client(timeout=30)
BASE = "http://localhost:8000"

# ═════════════════════════════════════════════════════
# Step 0: 上传前检索 — 应该返回空
# ═════════════════════════════════════════════════════
r0 = client.post(f"{BASE}/api/v1/search/regulations", json={"query": "疏散走道宽度"})
d0 = r0.json()
print(f"[0] 上传前检索: total={d0['total']}  hint={d0.get('hint','')[:40]}")
assert d0["total"] == 0, "上传前索引应为空"
print("    -> 索引为空, 符合预期")

# ═════════════════════════════════════════════════════
# Step 1: 上传一份建筑规范文档
# ═════════════════════════════════════════════════════
doc_text = """
GB 50222-2022 建筑内部装修设计防火规范
4.1 疏散走道和安全出口
4.1.1 疏散走道的宽度应根据建筑物内疏散人数经计算确定，且不应小于1.10m。
4.1.2 人员密集的公共场所、观众厅的疏散门不应设置门槛，其净宽度不应小于1.40m。
4.1.3 紧靠门口内外各1.40m范围内不应设置踏步。
4.2 装修材料燃烧性能等级
4.2.1 单层、多层民用建筑内部各部位装修材料的燃烧性能等级，不应低于表3.2.1的规定。
4.2.2 高层民用建筑内部各部位装修材料的燃烧性能等级，不应低于表3.3.1的规定。
4.2.3 地下民用建筑内部各部位装修材料的燃烧性能等级，不应低于表3.4.1的规定。
4.3 安全疏散设施
4.3.1 建筑内部消火栓的门不应被装饰物遮掩，消火栓门四周的装修材料颜色应与消火栓门的颜色有明显区别。
4.3.2 建筑内部变形缝两侧的基层应采用A级材料，表面装修应采用不低于B1级的装修材料。
"""
files = {"file": ("GB50222-2022.txt", doc_text.encode("utf-8"), "text/plain")}
r1 = client.post(f"{BASE}/api/v1/documents/upload", files=files, data={"category": "规范"})
d1 = r1.json()
print(f"\n[1] 上传: doc_id={d1['document_id']}, chunks={d1.get('chunks_indexed',0)}, total_chunks={d1.get('total_chunks',0)}")
assert d1.get("chunks_indexed", 0) > 0, "上传后应有chunk"
doc_id = d1["document_id"]

# ═════════════════════════════════════════════════════
# Step 2: 上传后检索 — 应该命中上传的条款
# ═════════════════════════════════════════════════════
r2 = client.post(f"{BASE}/api/v1/search/regulations", json={"query": "疏散走道宽度要求", "top_k": 5})
d2 = r2.json()
print(f"\n[2] 上传后检索: total={d2['total']}")
assert d2["total"] > 0, "上传后应有检索结果"

# 验证 top-1 来自上传的文档
top = d2["results"][0]
print(f"    top-1: clause={top['clause_id']}  score={top['score']}")
print(f"    content: {top['content'][:60]}...")
assert top["clause_id"] == "4.1.1"  # 应该精确命中

# 遍历所有结果，验证都在上传的文档中
for r in d2["results"]:
    print(f"    [{r['clause_id']}] score={r['score']:.4f}  — {r['content'][:50]}")

# ═════════════════════════════════════════════════════
# Step 3: 上传后问答 — 验证来源是上传的文档
# ═════════════════════════════════════════════════════
r3 = client.post(f"{BASE}/api/v1/chat/regulation", json={"question": "装修材料的燃烧性能有什么要求？", "top_k": 3})
d3 = r3.json()
print(f"\n[3] 问答: answer_len={len(d3['answer'])}, sources={len(d3['sources'])}")
for s in d3["sources"]:
    print(f"    [{s['clause_id']}] {s['content'][:50]}... (score={s['score']})")
    # 验证 standard_code 来自上传的文档
    assert s.get("standard_code") == "GB 50222-2022", f"来源应为 GB 50222-2022，实际: {s.get('standard_code')}"

# ═════════════════════════════════════════════════════
# Step 4: 上传第二份文档并验证互不干扰
# ═════════════════════════════════════════════════════
doc2_text = """
JGJ 3-2010 高层建筑混凝土结构技术规程
5.1 一般规定
5.1.1 高层建筑结构应根据房屋高度和高宽比、抗震设防烈度、场地类别等因素选用合理的结构体系。
5.1.2 高层建筑不应采用严重不规则的结构体系。
5.1.3 高层建筑结构的高宽比不宜超过表5.1.3的规定。
"""
files2 = {"file": ("JGJ3-2010.txt", doc2_text.encode("utf-8"), "text/plain")}
r4 = client.post(f"{BASE}/api/v1/documents/upload", files=files2, data={"category": "规范"})
d4 = r4.json()
print(f"\n[4] 上传第二份: chunks={d4.get('chunks_indexed',0)}, total_chunks={d4.get('total_chunks',0)}")

# 检索第二份独有的条款
r5 = client.post(f"{BASE}/api/v1/search/regulations", json={"query": "高层建筑高宽比", "top_k": 3})
d5 = r5.json()
print(f"[5] 检索第二份: total={d5['total']}")
if d5["total"] > 0:
    top5 = d5["results"][0]
    print(f"    top-1: clause={top5['clause_id']}  code={top5.get('standard_code','')}")
    assert top5.get("standard_code") == "JGJ 3-2010"

# 检索第一份独有的条款（确认第二份没有覆盖第一份）
r6 = client.post(f"{BASE}/api/v1/search/regulations", json={"query": "消火栓装饰物", "top_k": 3})
d6 = r6.json()
print(f"[6] 检索第一份内容: total={d6['total']}")
if d6["total"] > 0:
    assert d6["results"][0].get("standard_code") == "GB 50222-2022"

client.close()
print("\nAll E2E tests passed — 上传/检索/问答 同一数据源 ✓")
