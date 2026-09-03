"""直接在进程中测试 MinerU 云解析日志"""
import io, os, sys, time, logging

# 启用详细日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)

sys.path.insert(0, ".")
from app.utils.mineru import MinerUClient, get_client

token = os.getenv("MINERU_API_TOKEN", "")
if not token:
    print("MINERU_API_TOKEN not set")
    sys.exit(1)

client = MinerUClient(token)

# 生成测试 PDF
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
buf = io.BytesIO()
c = canvas.Canvas(buf, pagesize=A4)
c.setFont("Helvetica-Bold", 18)
c.drawString(50, 800, "MinerU Log Test")
c.setFont("Helvetica", 11)
for i, line in enumerate([
    "5.5.18 Evacuation width >= 1.10m",
    "6.4.1 Exit stair requirements",
    "6.4.3 Smoke proof area >= 6.0 sqm",
]):
    c.drawString(60, 760 - i * 22, line)
c.showPage()
c.save()
pdf_bytes = buf.getvalue()

print()
markdown = client.parse_file(pdf_bytes, "log_test.pdf")
print()

if markdown:
    print(f"OK: {len(markdown)} chars")
    print(markdown[:200])
else:
    print("FAILED")
