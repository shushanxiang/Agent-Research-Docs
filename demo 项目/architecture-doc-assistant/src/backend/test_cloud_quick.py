import httpx, os, io, time, sys

token = os.getenv("MINERU_API_TOKEN", "")
print("Token:", "YES" if token else "NO", "(len=" + str(len(token)) + ")")

BASE = "http://localhost:8000"
client = httpx.Client(timeout=180)

# Test PDF
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
buf = io.BytesIO()
c = canvas.Canvas(buf, pagesize=A4)
c.setFont("Helvetica-Bold", 18)
c.drawString(50, 800, "GB 50016 test")
c.setFont("Helvetica", 12)
for i, line in enumerate([
    "5.5.18 Evacuation width shall not be less than 1.10m",
    "6.4.1 Exit stair requirements per table 6.4.1",
    "6.4.3 Smoke proof stair area >= 6.0 sqm",
]):
    c.drawString(60, 760 - i * 24, line)
c.showPage()
c.save()
pdf = buf.getvalue()

# Upload
print("Uploading", len(pdf), "bytes PDF ...")
files = {"file": ("test_cloud2.pdf", pdf, "application/pdf")}
t0 = time.time()
r = client.post(BASE + "/api/v1/documents/upload",
                files=files, data={"category": "规范"})
d = r.json()
elapsed = time.time() - t0
print(f"Done in {elapsed:.1f}s")
print(f"parser: {d.get('parser', 'NOT RETURNED')}")
print(f"chunks_indexed: {d.get('chunks_indexed', 0)}")

# Doc detail (check raw_text for cloud parse quality)
doc_id = d["document_id"]
r2 = client.get(BASE + "/api/v1/documents/" + doc_id)
detail = r2.json()
raw = detail.get("raw_text", "")
print(f"\nDoc parser: {detail.get('parser', 'N/A')}")
print(f"raw_text ({len(raw)} chars): {raw[:120]}")

# Search test
r3 = client.post(BASE + "/api/v1/search/regulations",
                 json={"query": "evacuation width", "top_k": 2})
d3 = r3.json()
if d3["results"]:
    print(f"\nSearch top-1: {d3['results'][0]['content'][:80]}")

client.close()
