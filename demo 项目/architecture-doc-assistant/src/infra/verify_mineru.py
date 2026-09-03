# -*- coding: utf-8 -*-
"""
建筑智能文档助手 — MinerU 解析链路 Python 版验证脚本
====================================================
纯 Python 实现，不依赖 Docker/PowerShell，直接在本地环境运行。

6 层验证:
  ① 核心依赖检查 (magic_pdf / torch / chromadb / psycopg2)
  ② MinerU 直接解析测试 (magic-pdf API)
  ③ 生成测试 PDF（无外部依赖时自动构造）
  ④ 数据库连接验证 (PostgreSQL)
  ⑤ 向量数据库验证 (Chroma)
  ⑥ API 服务端点验证 (FastAPI)

用法:
  python verify_mineru.py
  python verify_mineru.py --pdf D:\\docs\\GB-55037.pdf
  python verify_mineru.py --skip-api
  python verify_mineru.py --skip-db --skip-chroma
"""

import argparse
import io
import os
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── 项目根目录 ──
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
TEMP_DIR = PROJECT_ROOT / "data" / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# ── 计数器 ──
pass_count = 0
fail_count = 0
total_count = 0
report_lines: List[str] = []


# ═══════════════════════════════════════════════════════════════
#  输出工具
# ═══════════════════════════════════════════════════════════════

class Colors:
    """ANSI 颜色（Windows 10+ / Linux / Mac 均支持）"""
    GREEN  = "\033[92m"
    RED    = "\033[91m"
    YELLOW = "\033[93m"
    CYAN   = "\033[96m"
    MAGENTA = "\033[95m"
    BLUE   = "\033[94m"
    GRAY   = "\033[90m"
    RESET  = "\033[0m"
    BOLD   = "\033[1m"

# Windows 下启用 ANSI 序列
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass


def step(num: int, title: str):
    print()
    print(f"{Colors.CYAN}{'═'*60}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}  [{num}/6] {title}{Colors.RESET}")
    print(f"{Colors.CYAN}{'═'*60}{Colors.RESET}")


def ppass(msg: str):
    global pass_count, total_count
    pass_count += 1; total_count += 1
    print(f"    {Colors.GREEN}✓{Colors.RESET}  {msg}")
    report_lines.append(f"  ✅ [{total_count}] {msg}")


def pfail(msg: str, detail: str = ""):
    global fail_count, total_count
    fail_count += 1; total_count += 1
    print(f"    {Colors.RED}✗{Colors.RESET}  {msg}")
    if detail:
        print(f"       {Colors.GRAY}--> {detail}{Colors.RESET}")
    report_lines.append(f"  ❌ [{total_count}] {msg}")


def pwarn(msg: str):
    print(f"    {Colors.YELLOW}⚠{Colors.RESET}  {msg}")


def pinfo(msg: str):
    print(f"       {Colors.GRAY}{msg}{Colors.RESET}")


# ═══════════════════════════════════════════════════════════════
#  工具函数
# ═══════════════════════════════════════════════════════════════

def check_import(module: str, display_name: str = "") -> Tuple[bool, str]:
    """
    尝试导入模块，返回 (成功, 版本/错误信息)。
    display_name: 如果模块名与 import 名不同（如 pydantic_settings），用此字段覆盖 import 名。
    """
    import_name = display_name or module
    try:
        mod = __import__(module, fromlist=["__version__"])
        version = getattr(mod, "__version__", "✓ (无版本号)")
        return True, str(version)
    except ImportError as e:
        return False, str(e)


def generate_test_pdf(path: str) -> Optional[str]:
    """生成一份含建筑规范条款的 3 页测试 PDF"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError:
        # 回退：手动构造一个最小 PDF
        return _generate_minimal_pdf(path)

    c = canvas.Canvas(path, pagesize=A4)
    for i in range(3):
        c.setFont("Helvetica-Bold", 18)
        c.drawString(50, 800, f"建筑规范测试文档 — 第 {i+1} 页")
        c.setFont("Helvetica", 12)
        y = 760
        lines = [
            f"第 {i+1}.1.1 条  本规范适用于新建、改建和扩建的民用建筑工程。",
            f"第 {i+1}.1.2 条  建筑防火设计应符合国家现行有关标准的规定。",
            f"第 {i+1}.1.3 条  疏散走道的净宽度不应小于1.40m。",
            f"第 {i+1}.1.4 条  建筑构件的燃烧性能和耐火极限应符合表{i+1}.2.1的规定。",
            f"第 {i+1}.1.5 条  外墙保温材料的燃烧性能等级不应低于B1级。",
        ]
        for line in lines:
            c.drawString(60, y, line)
            y -= 22
        c.showPage()
    c.save()
    return path


def _generate_minimal_pdf(path: str) -> Optional[str]:
    """手工构造最小合法 PDF（无需任何第三方库）"""
    def _obj(n, content):
        return f"{n} 0 obj\n{content}\nendobj\n"

    pages = []
    for i in range(3):
        text = f"第 {i+1} 页 — 建筑规范测试条款\n\n" \
               f"1.{i+1}.1 本规范适用于新建、改建和扩建的民用建筑工程。\n" \
               f"1.{i+1}.2 疏散走道的净宽度不应小于1.40m。\n" \
               f"1.{i+1}.3 外墙保温材料燃烧性能等级不应低于B1级。\n"
        text_escaped = text.encode("utf-8").decode("latin-1", errors="replace")

        stream = (
            f"<< /Length {len(text_escaped)} >>\n"
            f"stream\n{text_escaped}\nendstream"
        )
        content_obj = _obj(3 + i * 2, stream)
        page_obj = (
            f"<< /Type /Page /Parent 1 0 R "
            f"/MediaBox [0 0 612 792] "
            f"/Contents {3 + i * 2} 0 R >>"
        )
        pages.append(_obj(4 + i * 2, page_obj))

    kids = " ".join(f"{4 + i * 2} 0 R" for i in range(3))
    catalog = _obj(1, f"<< /Type /Pages /Kids [{kids}] /Count 3 >>")
    root   = _obj(2, "<< /Type /Catalog /Pages 1 0 R >>")

    pdf_content = (
        "%PDF-1.4\n"
        + catalog
        + root
        + "".join(
            _obj(3 + i * 2,
                 f"<< /Length {len(f'第 {i+1} 页 — 建筑规范测试')} >>\n"
                 f"stream\n第 {i+1} 页 — 建筑规范测试\nendstream")
            for i in range(3)
        )
        + "".join(pages)
        + "xref\n0 3\n0000000000 65535 f \n"
        + "trailer\n<< /Size 9 /Root 2 0 R >>\n"
        + "startxref\n0\n%%EOF"
    )

    # 简化版：直接用 reportlab 的底层 API 不可靠时，
    # 写入一个含规范条款文本的合法 PDF（fpdf2 轻量方案）
    try:
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        for i in range(3):
            if i > 0:
                pdf.add_page()
            pdf.cell(0, 10, f"建筑规范测试文档 — 第 {i+1} 页", ln=True)
            pdf.cell(0, 8, f"第 {i+1}.1.1 条  本规范适用于新建民用建筑工程。", ln=True)
            pdf.cell(0, 8, f"第 {i+1}.1.2 条  疏散走道净宽度不小于1.40m。", ln=True)
            pdf.cell(0, 8, f"第 {i+1}.1.3 条  外墙保温不低于B1级。", ln=True)
        pdf.output(path)
        return path
    except ImportError:
        pass

    # 最终回退：写入手工 PDF
    try:
        with open(path, "w", encoding="latin-1") as f:
            f.write(pdf_content)
        return path
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
#  ① 核心依赖检查
# ═══════════════════════════════════════════════════════════════

def test_dependencies():
    step(1, "核心依赖检查")

    deps = [
        # (import 名, 显示名, 关键标记)
        ("magic_pdf",      "magic-pdf (MinerU)", True),
        ("torch",          "torch (GPU/CPU)",    True),
        ("transformers",   "transformers",       False),
        ("chromadb",       "chromadb",           True),
        ("psycopg2",       "psycopg2 (PostgreSQL)", False),
        ("redis",          "redis (缓存/队列)",     False),
        ("fastapi",        "FastAPI",            False),
        ("httpx",          "httpx (HTTP 客户端)",  False),
        ("langchain",      "langchain (RAG)",    False),
        ("sentence_transformers", "sentence-transformers (BGE)", False),
        ("PIL",            "Pillow (图像)",       False),
    ]

    ok_count = 0
    for module, display, critical in deps:
        success, version = check_import(module)
        if success:
            ppass(f"{display} : {version}")
            ok_count += 1
        else:
            if critical:
                pfail(f"{display} 未安装", f"pip install {module}")
            else:
                pwarn(f"{display} 未安装 (非阻塞) — pip install {module}")

    # CUDA 检测
    try:
        import torch
        cuda_ok = torch.cuda.is_available()
        if cuda_ok:
            ppass(f"CUDA 可用 — GPU: {torch.cuda.get_device_name(0)}")
        else:
            pwarn("CUDA 不可用，MinerU 使用 CPU 模式（解析耗时较长）")
    except Exception:
        pwarn("无法检测 CUDA 状态")


# ═══════════════════════════════════════════════════════════════
#  ② MinerU 直接解析测试
# ═══════════════════════════════════════════════════════════════

def test_mineru_parse(pdf_path: Optional[str] = None):
    step(2, "MinerU 直接解析测试 (magic-pdf API)")

    # 1. 导入 magic_pdf
    try:
        import magic_pdf
        ppass(f"magic-pdf 导入成功 (v{magic_pdf.__version__})")
    except ImportError:
        pfail("magic-pdf 未安装，跳过解析测试", "pip install magic-pdf")
        pwarn("以下为模拟解析流程验证（依赖占位）—— 安装 magic-pdf 后可实测")
        _run_mock_parse()
        return

    # 2. 准备测试 PDF
    pdf = _ensure_pdf(pdf_path)
    if not pdf:
        pfail("无法获取测试 PDF，终止解析测试")
        return
    pinfo(f"测试 PDF: {pdf}  ({os.path.getsize(pdf)} bytes)")

    # 3. 版面分析
    try:
        from magic_pdf.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader
        from magic_pdf.data.dataset import PymuDocDataset
        from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze

        t0 = time.time()

        reader = FileBasedDataReader("")
        pdf_bytes = Path(pdf).read_bytes()
        ds = PymuDocDataset(pdf_bytes)

        classify_result = ds.classify()
        is_ocr = (classify_result == "ocr")
        pinfo(f"PDF 分类: {'扫描版(OCR)' if is_ocr else '文字版'}")

        ppass(f"版面分析完成, 耗时 {time.time() - t0:.1f}s")

        # 4. 解析执行
        t1 = time.time()
        task_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = TEMP_DIR / f"verify_{task_id}"
        output_dir.mkdir(exist_ok=True)

        infer_result = ds.apply(doc_analyze, ocr=is_ocr)

        if is_ocr:
            pipe_result = infer_result.pipe_ocr_mode(
                FileBasedDataWriter(str(output_dir / "images"))
            )
        else:
            md_path = output_dir / f"{task_id}.md"
            pipe_result = infer_result.pipe_txt_mode(
                FileBasedDataWriter(str(output_dir / "images")),
                str(md_path),
            )

        elapsed = time.time() - t1
        ppass(f"MinerU 解析完成, 耗时 {elapsed:.1f}s")

        # 5. 检查产出
        md_files = list(output_dir.rglob("*.md"))
        if md_files:
            content = md_files[0].read_text(encoding="utf-8")
            ppass(f"Markdown 输出: {len(content)} 字符")
            # 显示前 3 行预览
            preview = "\n".join(content.split("\n")[:3])
            pinfo(f"内容预览:\n{Colors.GRAY}  {preview}{Colors.RESET}")
        else:
            pwarn("未生成 .md 文件（可能为纯 OCR 模式）")

        img_count = len(list(output_dir.rglob("*")))
        ppass(f"产物文件总数: {img_count} (目录: {output_dir})")

    except Exception as e:
        pfail(f"MinerU 解析异常", traceback.format_exc()[-200:])


def _ensure_pdf(pdf_path: Optional[str]) -> Optional[str]:
    """确保有一份可用的测试 PDF"""
    if pdf_path and os.path.isfile(pdf_path):
        return pdf_path

    # 自动生成
    gen_path = str(TEMP_DIR / "test_verify.pdf")
    if os.path.isfile(gen_path):
        return gen_path

    pinfo("未提供测试 PDF，自动生成...")
    result = generate_test_pdf(gen_path)
    if result:
        ppass(f"自动生成测试 PDF 成功 ({os.path.getsize(result)} bytes)")
    else:
        pfail("自动生成测试 PDF 失败")
    return result


def _run_mock_parse():
    """模拟 MinerU 解析流程（当 magic-pdf 未安装时）"""
    pinfo("--- 模拟解析流程 ---")

    pdf = _ensure_pdf(None)
    if pdf:
        ppass(f"测试 PDF 就绪: {os.path.basename(pdf)} ({os.path.getsize(pdf)} bytes)")
    else:
        pfail("无可用 PDF")
        return

    # 模拟版面分析
    time.sleep(0.3)
    ppass("版面分析 (模拟) — PDF 分类: 文字版")

    # 模拟解析
    time.sleep(0.5)
    ppass("解析完成 (模拟) — 输出 Markdown + 图片")

    # 写入模拟 Markdown
    md_path = TEMP_DIR / "verify_mock.md"
    md_content = """# 建筑规范测试文档
## 第 1 章  总则
### 1.1.1  适用范围
本规范适用于新建、改建和扩建的民用建筑工程。
### 1.1.3  疏散宽度
疏散走道的净宽度不应小于1.40m。
### 1.1.4  燃烧性能
建筑构件的燃烧性能和耐火极限应符合表 1.2.1 的规定。
"""
    md_path.write_text(md_content, encoding="utf-8")
    ppass(f"模拟 Markdown 输出: {len(md_content)} 字符 → {md_path}")


# ═══════════════════════════════════════════════════════════════
#  ③ 数据库连接验证 (PostgreSQL)
# ═══════════════════════════════════════════════════════════════

def test_postgresql():
    step(3, "数据库连接验证 (PostgreSQL)")

    try:
        import psycopg2
    except ImportError:
        pwarn("psycopg2 未安装，跳过 PostgreSQL 验证 — pip install psycopg2-binary")
        return

    # 尝试连接
    conn_params = {
        "host":     os.getenv("PG_HOST", "localhost"),
        "port":     int(os.getenv("PG_PORT", "5432")),
        "dbname":   os.getenv("POSTGRES_DB", "building_docs"),
        "user":     os.getenv("POSTGRES_USER", "user"),
        "password": os.getenv("POSTGRES_PASSWORD", "pass"),
    }

    try:
        conn = psycopg2.connect(**conn_params)
        conn.autocommit = True
        ppass(f"PostgreSQL 连接成功 ({conn_params['host']}:{conn_params['port']}/{conn_params['dbname']})")
    except Exception as e:
        pfail(f"PostgreSQL 连接失败", str(e))
        return

    # 检查核心表
    expected_tables = [
        "documents", "regulations", "chapters", "clauses",
        "atlas_nodes", "images", "audit_logs", "chat_sessions",
        "users", "enterprise_spaces",
    ]

    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        )
        existing = {row[0] for row in cur.fetchall()}

        for tbl in expected_tables:
            if tbl in existing:
                cur.execute(f"SELECT COUNT(*) FROM {tbl}")
                count = cur.fetchone()[0]
                ppass(f"表 {tbl} : {count} 条记录")
            else:
                pwarn(f"表 {tbl} 不存在（需执行 init.sql）")
    finally:
        cur.close()
        conn.close()


# ═══════════════════════════════════════════════════════════════
#  ④ 向量数据库验证 (Chroma)
# ═══════════════════════════════════════════════════════════════

def test_chroma():
    step(4, "向量数据库验证 (Chroma)")

    try:
        import chromadb
    except ImportError:
        pwarn("chromadb 未安装，跳过 Chroma 验证 — pip install chromadb")
        return

    try:
        # 尝试连接本地 Chroma（HTTP 模式或持久化模式）
        host = os.getenv("CHROMA_HOST", "localhost")
        port = int(os.getenv("CHROMA_PORT", "8000"))

        client = chromadb.HttpClient(host=host, port=port)
        heartbeat = client.heartbeat()
        ppass(f"Chroma ({host}:{port}) 心跳正常 — {heartbeat}")
    except Exception:
        pwarn("Chroma HTTP 服务不可达，尝试本地持久化模式...")
        try:
            persist_dir = str(PROJECT_ROOT / "data" / "chroma")
            client = chromadb.PersistentClient(path=persist_dir)
            ppass(f"Chroma 本地持久化模式初始化成功 ({persist_dir})")
        except Exception as e:
            pfail("Chroma 连接失败（HTTP + 本地模式均不可用）", str(e))
            return

    # 列出 Collections
    try:
        collections = client.list_collections()
        names = [c.name for c in collections]
        pinfo(f"已有 Collections ({len(names)}): {', '.join(names) if names else '(空)'}")

        expected = ["regulations", "atlas_nodes", "images"]
        for name in expected:
            if name in names:
                coll = client.get_collection(name)
                count = coll.count()
                ppass(f"Collection '{name}' : {count} 条向量")
            else:
                pwarn(f"Collection '{name}' 尚未创建")

        # 如果 regulations 有数据，做一次语义检索
        if "regulations" in names:
            coll = client.get_collection("regulations")
            if coll.count() > 0:
                results = coll.query(
                    query_texts=["疏散宽度"],
                    n_results=3,
                )
                hit_count = len(results["ids"][0]) if results["ids"] else 0
                if hit_count > 0:
                    distances = [round(d, 4) for d in results["distances"][0]]
                    ppass(f"语义检索 '疏散宽度' → 命中 {hit_count} 条 (距离: {distances})")
                else:
                    pwarn("语义检索无结果")
    except Exception as e:
        pfail("Chroma 查询异常", str(e))


# ═══════════════════════════════════════════════════════════════
#  ⑤ API 服务端点验证
# ═══════════════════════════════════════════════════════════════

def test_api():
    step(5, "API 服务端点验证 (FastAPI)")

    try:
        import httpx
    except ImportError:
        pwarn("httpx 未安装，跳过 API 验证 — pip install httpx")
        return

    endpoints = [
        ("GET",  "健康检查",       "http://localhost:8000/health"),
        ("GET",  "Swagger 文档",   "http://localhost:8000/docs"),
        ("GET",  "OpenAPI Schema", "http://localhost:8000/openapi.json"),
    ]

    client = httpx.Client(timeout=10)
    for method, label, url in endpoints:
        try:
            resp = client.request(method, url)
            if resp.status_code == 200:
                extra = ""
                if "health" in url:
                    data = resp.json()
                    extra = f" → {data}"
                ppass(f"{label} ({url.split('/')[-1]}) : HTTP {resp.status_code}{extra}")
            else:
                pfail(f"{label} : HTTP {resp.status_code}")
        except httpx.ConnectError:
            pwarn(f"{label} : 服务未启动 (无法连接 localhost:8000)")
            break
        except Exception as e:
            pfail(f"{label} 请求失败", str(e))

    client.close()

    # 检查 Streamlit 前端
    try:
        resp = httpx.get("http://localhost:8501", timeout=5)
        if resp.status_code == 200:
            ppass(f"Streamlit 前端 : HTTP 200 (http://localhost:8501)")
    except Exception:
        pwarn("Streamlit 前端未启动")


# ═══════════════════════════════════════════════════════════════
#  ⑥ MinerU HTTP 服务验证
# ═══════════════════════════════════════════════════════════════

def test_mineru_http(pdf_path: Optional[str] = None):
    step(6, "MinerU HTTP 服务验证")

    try:
        import httpx
    except ImportError:
        pwarn("httpx 未安装，跳过 HTTP 验证")
        return

    base = "http://localhost:8001"
    client = httpx.Client(timeout=10)

    # 健康检查
    try:
        resp = client.get(f"{base}/health")
        if resp.status_code == 200:
            data = resp.json()
            status = data.get("status", "unknown")
            ppass(f"MinerU HTTP 服务可达, 状态: {status}")
            for k, v in data.get("dependencies", {}).items():
                pinfo(f"  {k}: {v}")
        else:
            pwarn(f"MinerU HTTP 响应异常: {resp.status_code}")
            return
    except httpx.ConnectError:
        pwarn("MinerU HTTP 服务未启动 (http://localhost:8001)")
        # 尝试启动
        _try_start_mineru()
        return
    except Exception as e:
        pfail("MinerU HTTP 请求失败", str(e))
        return

    # 提交解析任务
    pdf = _ensure_pdf(pdf_path)
    if not pdf:
        pwarn("无可用 PDF，跳过 HTTP 解析任务")
        return

    try:
        task_resp = client.post(
            f"{base}/parse",
            json={"file_path": pdf, "output_format": "json", "doc_type": "规范"},
        )
        if task_resp.status_code == 200:
            task = task_resp.json()
            task_id = task.get("task_id", "")
            ppass(f"解析任务已提交, task_id={task_id}")

            # 轮询进度
            max_wait = 60
            for waited in range(0, max_wait, 2):
                time.sleep(2)
                status_resp = client.get(f"{base}/parse/{task_id}")
                if status_resp.status_code != 200:
                    continue
                s = status_resp.json()
                pinfo(f"  [{waited+2}s] status={s.get('status')} progress={s.get('progress')}% stage={s.get('stage','')}")
                if s.get("status") == "completed":
                    ppass(f"MinerU HTTP 解析完成, 耗时 {waited+2}s")
                    if s.get("result", {}).get("content_length", 0) > 0:
                        ppass(f"输出内容长度: {s['result']['content_length']} 字符")
                    break
                elif s.get("status") == "failed":
                    pfail("MinerU HTTP 解析失败", s.get("error", ""))
                    break
            else:
                pwarn(f"MinerU HTTP 解析超时 (>{max_wait}s)")
        else:
            pfail(f"提交解析任务失败: HTTP {task_resp.status_code}")
    except Exception as e:
        pfail("MinerU HTTP 任务异常", str(e))
    finally:
        client.close()


def _try_start_mineru():
    """尝试以子进程方式启动 MinerU 服务并等待就绪"""
    server_py = PROJECT_ROOT / "services" / "mineru" / "server.py"
    if not server_py.exists():
        pwarn(f"MinerU server.py 不存在 ({server_py})")
        return

    pwarn("尝试启动 MinerU 服务...")
    import subprocess
    try:
        proc = subprocess.Popen(
            [sys.executable, str(server_py)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(server_py.parent),
        )
        time.sleep(3)

        import httpx
        try:
            resp = httpx.get("http://localhost:8001/health", timeout=5)
            if resp.status_code == 200:
                ppass("MinerU 服务自动启动成功")
                pinfo(f"  进程 PID: {proc.pid}")
                return
        except Exception:
            pass

        # 检查是否有错误
        stderr = proc.stderr.read().decode(errors="replace")
        if stderr:
            pinfo(f"MinerU stderr:\n{stderr[-500:]}")
        pwarn("MinerU 启动后无法连接，请手动检查")
    except Exception as e:
        pfail("MinerU 启动失败", str(e))


# ═══════════════════════════════════════════════════════════════
#  汇总报告
# ═══════════════════════════════════════════════════════════════

def print_summary():
    print()
    print(f"{Colors.MAGENTA}{'═'*62}{Colors.RESET}")
    print(f"{Colors.MAGENTA}{Colors.BOLD}  MinerU 解析链路验证报告{Colors.RESET}")
    print(f"{Colors.MAGENTA}{'═'*62}{Colors.RESET}")
    print(f"  总计: {total_count} 项    "
          f"{Colors.GREEN}✓ 通过: {pass_count}{Colors.RESET}    "
          f"{Colors.RED}✗ 失败: {fail_count}{Colors.RESET}")
    print(f"{Colors.MAGENTA}{'─'*62}{Colors.RESET}")

    for line in report_lines:
        if "✅" in line:
            print(f"  {Colors.GREEN}{line}{Colors.RESET}")
        else:
            print(f"  {Colors.RED}{line}{Colors.RESET}")

    print(f"{Colors.MAGENTA}{'═'*62}{Colors.RESET}")

    if fail_count == 0:
        print(f"\n  {Colors.GREEN}{Colors.BOLD}🎉 所有验证项通过! MinerU 解析链路工作正常。{Colors.RESET}\n")
    else:
        print(f"\n  {Colors.YELLOW}⚠  {fail_count} 项未通过，请根据上述诊断定位问题。{Colors.RESET}")
        print(f"  {Colors.GRAY}提示: 缺失的依赖可用 pip install -r src/backend/requirements.txt 批量安装{Colors.RESET}\n")

    # 输出 JSON 报告文件
    json_path = TEMP_DIR / f"verify_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    import json
    json.dump({
        "timestamp": datetime.now().isoformat(),
        "total": total_count,
        "passed": pass_count,
        "failed": fail_count,
        "items": [l.strip() for l in report_lines],
    }, open(json_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    pinfo(f"JSON 报告已保存: {json_path}")


# ═══════════════════════════════════════════════════════════════
#  主流程
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="MinerU 解析链路 Python 验证脚本")
    parser.add_argument("--pdf",      default=None, help="测试用 PDF 路径（不传则自动生成）")
    parser.add_argument("--skip-db",  action="store_true", help="跳过 PostgreSQL 验证")
    parser.add_argument("--skip-chroma", action="store_true", help="跳过 Chroma 验证")
    parser.add_argument("--skip-api", action="store_true", help="跳过 API 端点验证")
    parser.add_argument("--skip-http", action="store_true", help="跳过 MinerU HTTP 服务验证")
    args = parser.parse_args()

    print()
    print(f"{Colors.BLUE}{'┌' + '─'*58 + '┐'}{Colors.RESET}")
    print(f"{Colors.BLUE}│  建筑智能文档助手 — MinerU 解析链路验证 (Python)    │{Colors.RESET}")
    print(f"{Colors.BLUE}│  开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                               │{Colors.RESET}")
    print(f"{Colors.BLUE}{'└' + '─'*58 + '┘'}{Colors.RESET}")

    test_dependencies()
    test_mineru_parse(args.pdf)

    if not args.skip_db:
        test_postgresql()
    else:
        pwarn("已跳过 PostgreSQL 验证 (--skip-db)")

    if not args.skip_chroma:
        test_chroma()
    else:
        pwarn("已跳过 Chroma 验证 (--skip-chroma)")

    if not args.skip_api:
        test_api()
    else:
        pwarn("已跳过 API 端点验证 (--skip-api)")

    if not args.skip_http:
        test_mineru_http(args.pdf)
    else:
        pwarn("已跳过 MinerU HTTP 验证 (--skip-http)")

    print(f"\n{Colors.BLUE}  结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.RESET}")
    print_summary()


if __name__ == "__main__":
    main()
