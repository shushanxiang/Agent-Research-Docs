import httpx, os
from pathlib import Path

client = httpx.Client(timeout=30)
BASE = "http://localhost:8000"

# 上传测试文件
files = {"file": ("test_fire_code.txt", b"GB 50016 evacuation width >= 1.10m", "text/plain")}
r = client.post(f"{BASE}/api/v1/documents/upload", files=files, data={"category": "规范"})
d = r.json()
doc_id = d["document_id"]
stored = d.get("storage_path", "未返回 storage_path")
print(f"document_id: {doc_id}")
print(f"storage_path: {stored}")
print(f"文件已落盘: {os.path.exists(stored)}")

# 列出 uploads 目录
upload_dir = Path(Path(stored).parent) if os.path.exists(stored) else Path("data/uploads")
print(f"\nuploads 目录 ({upload_dir}):")
for f in sorted(upload_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
    print(f"  {f.stat().st_mtime:0.0f}  {f.name}  ({f.stat().st_size} bytes)")
    if f.suffix == ".txt":
        print(f"    -> {f.read_text()[:60]}")

client.close()
