"""
验证 uploads 目录文件命名规则

规则: {SHA256前16位}_{安全文件名}
安全文件名 = 原始文件名中非 \w.\- 字符替换为 _
"""

import hashlib
import re
from pathlib import Path

UPLOAD_DIR = Path(__file__).resolve().parent / "data" / "uploads"

if not UPLOAD_DIR.exists():
    print(f"目录不存在: {UPLOAD_DIR}")
    exit(1)

files = sorted(UPLOAD_DIR.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)

if not files:
    print("目录为空")
    exit(0)

print(f"上传目录: {UPLOAD_DIR}")
print(f"文件总数: {len(files)}\n")
print(f"{'序号':<4} {'磁盘文件名':<60} {'大小':>8} {'哈希前缀':<18} {'推测原名':>30} {'匹配'}")
print("-" * 130)

ok_count = 0
fail_count = 0

for i, f in enumerate(files, 1):
    size = f.stat().st_size
    disk_name = f.name

    # 从磁盘文件名解析哈希前缀和原始文件名
    # 格式: {hash[0:16]}_{safe_name.ext}
    match = re.match(r"^([0-9a-f]{16})_(.+)$", disk_name)
    if not match:
        print(f"{i:<4} {disk_name:<60} {size:>8}  {'N/A':<18} {'N/A':>30}  ❌ 格式不匹配")
        fail_count += 1
        continue

    hash_prefix = match.group(1)
    safe_name = match.group(2)

    # 计算文件实际 SHA256
    actual_hash = hashlib.sha256(f.read_bytes()).hexdigest()
    actual_prefix = actual_hash[:16]

    # 前缀匹配
    match_ok = (hash_prefix == actual_prefix)
    status = "✅" if match_ok else "❌ 实际: " + actual_prefix

    # 推测原始文件名（反转安全替换）
    # 无法完全还原，仅展示
    original_guess = safe_name

    print(f"{i:<4} {disk_name:<60} {size:>8}  {hash_prefix:<18} {original_guess:>30}  {status}")

    if match_ok:
        ok_count += 1
    else:
        fail_count += 1

print(f"\n结果: {ok_count} 正确, {fail_count} 异常 / {len(files)} 总计")
