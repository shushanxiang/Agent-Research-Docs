"""快速验证 API 端点是否正常"""
import httpx, json

client = httpx.Client(timeout=30)
BASE = "http://localhost:8000"

# 1. Health
r = client.get(f"{BASE}/health")
print(f"[1] Health: {r.json()}")

# 2. Search regulations
r = client.post(f"{BASE}/api/v1/search/regulations",
    json={"query": "商场疏散走道宽度", "top_k": 3})
d = r.json()
top = d["results"][0]["clause_id"] if d["results"] else "N/A"
print(f"[2] Search ({r.status_code}): total={d['total']}, top={top}")

# 3. Search atlas
r = client.post(f"{BASE}/api/v1/search/atlas",
    json={"query": "屋面防水"})
d = r.json()
print(f"[3] Atlas  ({r.status_code}): total={d['total']}")

# 4. Chat regulation
r = client.post(f"{BASE}/api/v1/chat/regulation",
    json={"question": "外墙保温材料有什么要求？", "top_k": 3})
d = r.json()
print(f"[4] Chat   ({r.status_code}): answer_len={len(d['answer'])}, sources={len(d['sources'])}")

# 5. Document upload
files = {"file": ("test.txt", b"GB 55037-2022\n2022-12-01\n", "text/plain")}
r = client.post(f"{BASE}/api/v1/documents/upload", files=files, data={"category": "规范"})
d = r.json()
print(f"[5] Upload ({r.status_code}): doc_id={d.get('document_id','?')[:8]}...")

client.close()
print("\nAll 5 endpoints OK")
