"""
端到端测试：模拟前端上传→检索→问答完整链路
==========================================
模拟上传 2 份规范文档（产品需求文档中定义的场景），
验证后端解析、检索、问答三级链路是否全部正确返回。

详细日志覆盖每个关键节点：
  - 上传请求参数 / HTTP 状态 / 响应体全量
  - 文档解析：parser 类型、raw_text 长度、chunk 拆分明细
  - 元数据提取：standard_code、doc_type、keywords
  - 检索匹配：top-k 每条的分值、条款编号、内容截断
  - 问答溯源：每条 source 的规范来源、score
  - 时间线：每步耗时
"""

import httpx
import json
import sys
import time
from datetime import datetime

BASE = "http://localhost:8000"
API_TIMEOUT = 60

pass_count = 0
fail_count = 0

_step_timer = 0.0


# ═══════════════════════════════════════════════════════
#  日志工具
# ═══════════════════════════════════════════════════════

def step(n, title):
    global _step_timer
    _step_timer = time.time()
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"\n{'═'*70}")
    print(f"  [{n}] {title}")
    print(f"      开始时间: {ts}")
    print(f"{'═'*70}")


def step_done():
    elapsed = time.time() - _step_timer
    print(f"  ── 本步耗时: {elapsed:.2f}s")


def check(label, condition, detail=""):
    global pass_count, fail_count
    if condition:
        pass_count += 1
        print(f"  ✅ {label}")
    else:
        fail_count += 1
        print(f"  ❌ {label}" + (f"  → {detail}" if detail else ""))


def log(label, value, truncate=200):
    """通用日志行：标签 + 值（长字符串自动截断）"""
    s = str(value)
    if len(s) > truncate and isinstance(value, str):
        s = s[:truncate] + f"...(截断, 全长 {len(str(value))} 字符)"
    print(f"     📋 {label}: {s}")


def log_json(label, obj):
    """JSON 结构化输出"""
    s = json.dumps(obj, ensure_ascii=False, indent=2)
    print(f"     📋 {label}:")
    for line in s.split("\n"):
        print(f"        {line}")


def log_request(method, path, body=None):
    """记录 API 请求"""
    print(f"     → 请求: {method} {path}")
    if body:
        if isinstance(body, dict):
            log_json("请求体", body)
        else:
            log("请求体", str(body)[:300])


def log_response(resp, label="响应"):
    """记录 API 响应"""
    print(f"     ← 响应: HTTP {resp.status_code}")
    body = resp.json()
    # 列出顶层 key
    print(f"     ← 顶层字段: {list(body.keys())}")
    return body


# ═══════════════════════════════════════════════════════
#  前置握手
# ═══════════════════════════════════════════════════════

print()
print("┌" + "─" * 68 + "┐")
print("│" + f"  建筑智能文档助手 — 上传→检索→问答 端到端测试".ljust(56) + "│")
print("│" + f"  开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".ljust(56) + "│")
print("│" + f"  API 地址: {BASE}".ljust(56) + "│")
print("└" + "─" * 68 + "┘")

log("前置检查", f"探测 {BASE}/health ...")
try:
    r = httpx.get(f"{BASE}/health", timeout=5)
    log("health 响应", r.json())
    check("后端连通", r.status_code == 200, r.text[:100])
except Exception as e:
    print(f"  ❌ 后端未启动: {e}")
    sys.exit(1)

client = httpx.Client(timeout=API_TIMEOUT)


# ═══════════════════════════════════════════════════════
#  场景 1：上传第一份规范文档
# ═══════════════════════════════════════════════════════
step(1, "场景 1 — 上传《建筑内部装修设计防火规范》GB 50222-2022")

doc1 = (
    "GB 50222-2022 建筑内部装修设计防火规范\n"
    "4.1 疏散走道和安全出口\n"
    "4.1.1 疏散走道的宽度应根据建筑物内疏散人数经计算确定，且不应小于1.10m。\n"
    "4.1.2 人员密集的公共场所疏散门不应设置门槛，其净宽度不应小于1.40m。\n"
    "4.1.3 紧靠门口内外各1.40m范围内不应设置踏步。\n"
    "4.2 装修材料燃烧性能等级\n"
    "4.2.1 单层、多层民用建筑内部各部位装修材料的燃烧性能等级，不应低于表3.2.1的规定。\n"
    "4.2.2 高层民用建筑内部各部位装修材料的燃烧性能等级，不应低于表3.3.1的规定。\n"
    "4.2.3 地下民用建筑内部各部位装修材料的燃烧性能等级，不应低于表3.4.1的规定。\n"
    "4.3 安全疏散设施\n"
    "4.3.1 建筑内部消火栓的门不应被装饰物遮掩。\n"
    "4.3.2 变形缝两侧的基层应采用A级材料，表面装修应采用不低于B1级的装修材料。\n"
)

log("文档 1 原始大小", f"{len(doc1.encode('utf-8'))} bytes")
log("文档 1 行数", len(doc1.split("\n")))
# 条款统计
clause_lines = [l for l in doc1.split("\n") if "." in l[:8] and any(c.isdigit() for c in l[:3])]
log("文档 1 含条款行", f"{len(clause_lines)} 行")

log_request("POST", "/api/v1/documents/upload", {"category": "规范"})

r = client.post(
    f"{BASE}/api/v1/documents/upload",
    files={"file": ("GB50222-2022.txt", doc1.encode("utf-8"), "text/plain")},
    data={"category": "规范"},
)
d = log_response(r)

# ── 解析细节 ──
check("HTTP 200", r.status_code == 200)
check("返回 document_id", bool(d.get("document_id")))
log("document_id", d.get("document_id"))
log("filename", d.get("filename"))
log("category", d.get("category"))
log("status", d.get("status"))
log("chunks_indexed (本次)", d.get("chunks_indexed", 0))
log("total_chunks (累计)", d.get("total_chunks", 0))

check("返回 chunks_indexed ≥ 9", d.get("chunks_indexed", 0) >= 9,
      f"实际: {d.get('chunks_indexed')}")
check("返回 total_chunks ≥ 9", d.get("total_chunks", 0) >= 9)

# ── 元数据提取 ──
meta = d.get("metadata", {})
log_json("元数据提取结果", meta)
check("standard_code 正确", meta.get("standard_code") == "GB 50222-2022",
      f"实际: {meta.get('standard_code')}")
check("doc_type 正确", meta.get("doc_type") in ("规范", None))
check("keywords 非空", len(meta.get("keywords", [])) > 0,
      f"实际: {meta.get('keywords')}")

doc1_id = d["document_id"]
step_done()

# ═══════════════════════════════════════════════════════
#  场景 1b：检索验证
# ═══════════════════════════════════════════════════════
step(2, "场景 1 — 检索上传文档中的条款")

query1 = "疏散走道宽度要求"
log_request("POST", "/api/v1/search/regulations", {"query": query1, "top_k": 5})

t0 = time.time()
r = client.post(
    f"{BASE}/api/v1/search/regulations",
    json={"query": query1, "top_k": 5},
)
elapsed = time.time() - t0
d = r.json()

log("检索耗时", f"{elapsed:.3f}s")
log("检索命中总数", d["total"])

check("检索有结果", d["total"] >= 3, f"实际: {d['total']}")

# ── 逐条打印 ──
for i, item in enumerate(d.get("results", [])):
    status_badge = ""
    if item.get("status") == "废止":
        status_badge = " ⚠️废止"
    print(f"     ┌─ 第 {i+1} 名 ───────────────────────────")
    log(f"  clause_id", item.get("clause_id"))
    log(f"  standard_code", item.get("standard_code"))
    log(f"  standard_title", item.get("standard_title"))
    log(f"  score", item.get("score"))
    log(f"  status", f"{item.get('status')}{status_badge}")
    log(f"  content", item.get("content"), truncate=100)
    log(f"  chapter_path", item.get("chapter_path", "(空)"))
    print(f"     └─────────────────────────────────────")
    if i == 0:
        check("Top-1 来自上传文档",
              item.get("standard_code") == "GB 50222-2022",
              f"实际: {item.get('standard_code')}")
        check("Top-1 命中 4.1.1",
              item.get("clause_id") == "4.1.1",
              f"实际: {item.get('clause_id')}")
        check("相关度 > 0", item.get("score", 0) > 0)

step_done()

# ═══════════════════════════════════════════════════════
#  场景 1c：问答验证
# ═══════════════════════════════════════════════════════
step(3, "场景 1 — 基于上传文档的智能问答")

qa_query = "装修材料的燃烧性能有什么要求？"
log_request("POST", "/api/v1/chat/regulation", {"question": qa_query, "top_k": 3})

t0 = time.time()
r = client.post(
    f"{BASE}/api/v1/chat/regulation",
    json={"question": qa_query, "top_k": 3},
)
elapsed = time.time() - t0
d = r.json()

log("问答耗时", f"{elapsed:.3f}s")
log("answer 长度", f"{len(d.get('answer',''))} 字符")
log("回答内容", d.get("answer", ""), truncate=150)
log("sources 数量", len(d.get("sources", [])))
log("disclaimer", d.get("disclaimer", ""), truncate=80)

check("问答有回答", len(d.get("answer", "")) > 5)
check("溯源 ≥ 1 条", len(d.get("sources", [])) >= 1)

# ── 溯源逐条 ──
for i, s in enumerate(d.get("sources", [])):
    abolished = " ⚠️已废止" if s.get("is_abolished") else ""
    print(f"     ┌─ Source {i+1} ────────────────────────────")
    log(f"  clause_id", s.get("clause_id"))
    log(f"  standard_code", s.get("standard_code"))
    log(f"  standard_title", s.get("standard_title"))
    log(f"  score", s.get("score"))
    log(f"  chapter", s.get("chapter"))
    log(f"  abolished", s.get("is_abolished"))
    log(f"  content", s.get("content", ""), truncate=100)
    print(f"     └─────────────────────────────────────")
    check(f"来源是 GB 50222-2022 (clause {s.get('clause_id')})",
          s.get("standard_code") == "GB 50222-2022")

step_done()

# ═══════════════════════════════════════════════════════
#  场景 2：上传第二份文档
# ═══════════════════════════════════════════════════════
step(4, "场景 2 — 上传《高层建筑混凝土结构技术规程》JGJ 3-2010")

doc2 = (
    "JGJ 3-2010 高层建筑混凝土结构技术规程\n"
    "5.1 一般规定\n"
    "5.1.1 高层建筑结构应根据房屋高度和高宽比等因素选用合理的结构体系。\n"
    "5.1.2 高层建筑不应采用严重不规则的结构体系。\n"
    "5.1.3 高层建筑结构的高宽比不宜超过表5.1.3的规定。\n"
    "7.1 框架-剪力墙结构\n"
    "7.1.1 框架-剪力墙结构应设计成双向抗侧力体系。\n"
    "7.1.2 抗震设计时，剪力墙的间距不宜超过表7.1.2的规定。\n"
)

log("文档 2 原始大小", f"{len(doc2.encode('utf-8'))} bytes")
log("文档 2 行数", len(doc2.split("\n")))

log_request("POST", "/api/v1/documents/upload", {"category": "规范"})

r = client.post(
    f"{BASE}/api/v1/documents/upload",
    files={"file": ("JGJ3-2010.txt", doc2.encode("utf-8"), "text/plain")},
    data={"category": "规范"},
)
d = log_response(r)

check("HTTP 200", r.status_code == 200)
check("返回 document_id", bool(d.get("document_id")))
log("chunks_indexed (本次)", d.get("chunks_indexed", 0))
log("total_chunks (累计)", d.get("total_chunks", 0))
log_json("元数据", d.get("metadata", {}))

check("本次 chunks ≥ 5", d.get("chunks_indexed", 0) >= 5)
check("累计 chunks ≥ 14", d.get("total_chunks", 0) >= 14,
      f"实际: {d.get('total_chunks')}")
check("standard_code 为 JGJ 3-2010",
      d.get("metadata", {}).get("standard_code") == "JGJ 3-2010",
      f"实际: {d.get('metadata', {}).get('standard_code')}")

doc2_id = d["document_id"]
step_done()

# ═══════════════════════════════════════════════════════
#  场景 2b：跨文档检索
# ═══════════════════════════════════════════════════════
step(5, "场景 2 — 跨文档检索：两份内容共存不覆盖")

# 查第二份独有的
q2 = "高层建筑高宽比"
log_request("POST", "/api/v1/search/regulations", {"query": q2, "top_k": 3})

r = client.post(f"{BASE}/api/v1/search/regulations", json={"query": q2, "top_k": 3})
d = r.json()
log("检索 '" + q2 + "'", f"命中 {d['total']} 条")
for item in d.get("results", []):
    log(f"  [{item.get('clause_id')}] {item.get('standard_code')}",
        f"score={item.get('score')} | {item.get('content','')[:60]}")
check("检索第二份：有结果", d["total"] > 0)
if d["results"]:
    check("检索第二份：code=JGJ3",
          d["results"][0].get("standard_code") == "JGJ 3-2010")

# 查第一份独有的
q3 = "消火栓装饰物"
log_request("POST", "/api/v1/search/regulations", {"query": q3, "top_k": 3})

r = client.post(f"{BASE}/api/v1/search/regulations", json={"query": q3, "top_k": 3})
d = r.json()
log("检索 '" + q3 + "'", f"命中 {d['total']} 条")
for item in d.get("results", []):
    log(f"  [{item.get('clause_id')}] {item.get('standard_code')}",
        f"score={item.get('score')} | {item.get('content','')[:60]}")
check("检索第一份：第一份仍在", d["total"] > 0)
if d["results"]:
    check("检索第一份：code=GB50222",
          d["results"][0].get("standard_code") == "GB 50222-2022")

step_done()

# ═══════════════════════════════════════════════════════
#  场景 3：文档列表
# ═══════════════════════════════════════════════════════
step(6, "场景 3 — 文档列表（验证前端刷新列表）")

log_request("GET", "/api/v1/documents/")

r = client.get(f"{BASE}/api/v1/documents/")
d = r.json()
log("文档总数", d["total"])

for item in d.get("items", []):
    log("  📄", f"{item['filename']} | {item.get('category','')} | {item.get('file_size',0)} bytes | {item.get('status','')}")

names = [item["filename"] for item in d.get("items", [])]
check("文档总数 ≥ 2", d["total"] >= 2, f"实际: {d['total']}")
check("列表含 GB50222", "GB50222-2022.txt" in names)
check("列表含 JGJ3", "JGJ3-2010.txt" in names)

step_done()

# ═══════════════════════════════════════════════════════
#  场景 4：索引状态检查
# ═══════════════════════════════════════════════════════
step(7, "场景 4 — 索引状态检查")

log_request("GET", "/api/v1/documents/stats")

r = client.get(f"{BASE}/api/v1/documents/stats")
d = r.json()
log_json("索引状态", d)

# ═══════════════════════════════════════════════════════
#  汇总
# ═══════════════════════════════════════════════════════
client.close()
total = pass_count + fail_count

print()
print("╔" + "═" * 68 + "╗")
print("║" + f"  测试汇总".ljust(56) + "║")
print("╠" + "═" * 68 + "╣")
print("║" + f"  总计: {total} 项检查".ljust(56) + "║")
print("║" + f"  ✅ 通过: {pass_count}".ljust(56) + "║")
print("║" + f"  ❌ 失败: {fail_count}".ljust(56) + "║")
print("║" + f"  结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".ljust(56) + "║")
print("╚" + "═" * 68 + "╝")

if fail_count:
    print(f"\n  请根据上述 ❌ 项排查对应的后端日志。")
    sys.exit(1)
else:
    print(f"\n  全部通过 ✓")
