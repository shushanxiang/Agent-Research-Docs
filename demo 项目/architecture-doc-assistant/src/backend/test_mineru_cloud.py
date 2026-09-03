"""验证 MinerU 云服务解析链路"""
import httpx, json, sys, os

BASE = "http://localhost:8000"
client = httpx.Client(timeout=120)

# 1. Token 检查
token = os.getenv("MINERU_API_TOKEN", "")
print(f"MINERU_API_TOKEN: {'已设置' if token else '未设置'} (len={len(token)})")
if not token:
    print("请在系统环境变量中设置 MINERU_API_TOKEN")
    sys.exit(1)

# 2. 生成一个真实 PDF
pdf_bytes = None
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    import io
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, 800, "GB 50016-2014 建筑设计防火规范")
    c.setFont("Helvetica", 12)
    y = 760
    for line in [
        "5.5.1 民用建筑应根据其建筑高度、使用功能等确定分类。",
        "5.5.17 公共建筑的安全疏散距离应符合表5.5.17的规定。",
        "5.5.18 疏散走道的净宽度不应小于1.10m。",
        "6.4.1 疏散楼梯间应符合下列规定。",
        "6.4.3 防烟楼梯间前室的使用面积公共建筑不应小于6.0㎡。",
    ]:
        c.drawString(60, y, line)
        y -= 24
    c.showPage()
    c.save()
    pdf_bytes = buf.getvalue()
    print(f"生成测试 PDF: {len(pdf_bytes)} bytes")
except ImportError:
    print("reportlab 未安装，使用最小 PDF")
    pdf_bytes = (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Contents 4 0 R>>endobj\n"
        b"4 0 obj<</Length 51>>stream\nBT /F1 12 Tf 72 720 Td (GB 50016 fire code) Tj ET\nendstream\nendobj\n"
        b"xref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000192 00000 n \n"
        b"trailer<</Size 5/Root 1 0 R>>\nstartxref\n290\n%%EOF"
    )

# 3. 上传
print(f"\n上传 {len(pdf_bytes)} bytes PDF ...")
files = {"file": ("GB50016-2014.pdf", pdf_bytes, "application/pdf")}
r = client.post(f"{BASE}/api/v1/documents/upload", files=files, data={"category": "规范"})
d = r.json()
print(f"响应: {json.dumps({k: v for k, v in d.items() if k != 'raw_text'}, ensure_ascii=False, indent=2)}")

# 4. 检索验证
r = client.post(f"{BASE}/api/v1/search/regulations", json={"query": "疏散走道净宽度", "top_k": 3})
d = r.json()
print(f"\n检索: total={d['total']}")
for item in d.get("results", [])[:3]:
    print(f"  [{item['clause_id']}] score={item['score']:.3f} | {item['content'][:60]}")

client.close()
