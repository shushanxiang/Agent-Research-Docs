"""
文档解析服务
============
封装 MinerU 解析流程、LLM 元数据提取、规则引擎回退。

数据流:
  PDF 文件 → MinerU 解析（或模拟） → 结构化 JSON
    → 规则引擎提取元数据 → LLM 补充增强
    → 文本切块（chunking） → Chroma 入库（异步）

参见 技术开发文档 §4.1.2—§4.1.3
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.utils.llm import extract_metadata_by_llm, is_llm_available

logger = logging.getLogger(__name__)


class ParseService:
    """文档解析服务：MinerU + OCR Fallback + LLM 元数据"""

    async def parse_async(self, document_id: str) -> dict:
        """
        异步解析文档（Celery 任务入口）。

        流程:
          1. 从对象存储下载文件到本地
          2. 调用 MinerU 结构化解析
          3. LLM 辅助元数据提取
          4. 存储解析结果到 PostgreSQL + Chroma
          5. WebSocket 推送进度
        """
        logger.info(f"[ParseService] start parsing document {document_id}")
        # 生产环境由 Celery 调用: parse_document_task(document_id)
        return {"document_id": document_id, "status": "processing"}

    def parse_text_from_bytes(self, pdf_bytes: bytes, filename: str) -> dict:
        """
        从 PDF 字节数据解析文本和结构（同步版，用于测试/小文件）。

        Args:
            pdf_bytes: PDF 文件的原始字节
            filename: 原始文件名

        Returns:
            结构化解析结果:
            {
                "metadata": {"title", "doc_type", "standard_code", ...},
                "chapters": [{"title", "clauses": [{"clause_id", "content", "page_num"}]}],
                "raw_text": "..."
            }
        """
        logger.info(f"[ParseService] parsing '{filename}' ({len(pdf_bytes)} bytes)")

        # ① 优先：MinerU 云服务
        cloud_result = self._try_mineru_cloud_parse(pdf_bytes, filename)
        if cloud_result:
            return cloud_result

        # ② 次选：本地 MinerU (magic-pdf)
        mineru_result = self._try_mineru_parse(pdf_bytes, filename)
        if mineru_result:
            return mineru_result

        # ③ 回退：PyMuPDF / 纯文本解码
        return self._fallback_parse(pdf_bytes, filename)

    def _try_mineru_cloud_parse(self, pdf_bytes: bytes, filename: str) -> Optional[dict]:
        """
        优先：MinerU 云服务 (https://mineru.net)
        使用环境变量 MINERU_API_TOKEN，免费 1000 页/天。
        返回 {"raw_text": "...", "parser": "mineru-cloud"}
        """
        try:
            from app.utils.mineru import get_client
            client = get_client()
            if not client:
                logger.info("[ParseService] MinerU cloud token not set (MINERU_API_TOKEN)")
                return None

            logger.info(f"[ParseService] using MinerU cloud API for '{filename}'")
            markdown = client.parse_file(pdf_bytes, filename)
            if markdown:
                logger.info(f"[ParseService] MinerU cloud output: {len(markdown)} chars")
                return {"raw_text": markdown, "parser": "mineru-cloud"}
            logger.warning("[ParseService] MinerU cloud returned empty")
            return None
        except Exception as e:
            logger.warning(f"[ParseService] MinerU cloud failed: {e}")
            return None

    def _try_mineru_parse(self, pdf_bytes: bytes, filename: str) -> Optional[dict]:
        """尝试使用 MinerU 解析 PDF"""
        try:
            from magic_pdf.data.data_reader_writer import FileBasedDataWriter
            from magic_pdf.data.dataset import PymuDocDataset
            from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze

            ds = PymuDocDataset(pdf_bytes)
            is_ocr = (ds.classify() == "ocr")
            logger.info(f"[ParseService] MinerU classify: {'OCR' if is_ocr else 'text'}")

            task_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_dir = Path("data") / "temp" / f"parse_{task_id}"
            out_dir.mkdir(parents=True, exist_ok=True)

            infer = ds.apply(doc_analyze, ocr=is_ocr)
            if is_ocr:
                infer.pipe_ocr_mode(FileBasedDataWriter(str(out_dir / "images")))
            else:
                md_path = out_dir / f"{task_id}.md"
                infer.pipe_txt_mode(
                    FileBasedDataWriter(str(out_dir / "images")),
                    str(md_path),
                )
            raw_text = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
            logger.info(f"[ParseService] MinerU output: {len(raw_text)} chars")
            return {"raw_text": raw_text, "parser": "mineru"}
        except ImportError:
            logger.info("[ParseService] magic-pdf not installed, using fallback parser")
            return None
        except Exception as e:
            logger.warning(f"[ParseService] MinerU failed: {e}, falling back")
            return None

    def _fallback_parse(self, pdf_bytes: bytes, filename: str) -> dict:
        """回退解析：从 PDF 字节中提取纯文本。拒绝将二进制乱码当作文本。"""
        raw_text = ""
        parser = "fallback"

        # 根据文件扩展名决定策略
        ext = Path(filename).suffix.lower()

        # 1. 尝试 PyMuPDF（真正的 PDF 解析器）
        if ext == ".pdf":
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                for page in doc:
                    raw_text += page.get_text()
                doc.close()
                if raw_text.strip():
                    parser = "pymupdf"
                    logger.info(f"[ParseService] PyMuPDF extracted {len(raw_text)} chars from PDF")
                    return {"raw_text": raw_text, "parser": parser}
            except ImportError:
                logger.info("[ParseService] PyMuPDF (fitz) not installed")
            except Exception as e:
                logger.warning(f"[ParseService] PyMuPDF failed: {e}")

        # 2. 纯文本文件：直接解码
        if ext in (".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm"):
            try:
                raw_text = pdf_bytes.decode("utf-8", errors="replace")
                parser = "utf8"
                return {"raw_text": raw_text, "parser": parser}
            except Exception:
                pass

        # 3. PDF 但 PyMuPDF 不可用：必须拒绝二进制内容
        if ext == ".pdf":
            # 检查是否为合法 PDF（以 %PDF 开头）
            if pdf_bytes[:4] == b"%PDF" or pdf_bytes[:5] == b"%PDF-":
                logger.error(
                    "[ParseService] PDF 文件 (%d bytes) 无法解析 — "
                    "请安装 PyMuPDF: pip install PyMuPDF",
                    len(pdf_bytes),
                )
            else:
                logger.error(
                    "[ParseService] 文件不是有效 PDF (magic bytes=%s)",
                    pdf_bytes[:4],
                )
            return {
                "raw_text": f"[无法解析 PDF: {filename}，{len(pdf_bytes)} bytes。"
                            f"请设置 MINERU_API_TOKEN 使用云解析，或安装 PyMuPDF。]",
                "parser": "rejected",
            }

        # 4. 其他二进制文件：拒绝
        logger.warning(
            "[ParseService] 无法识别的文件类型 %s (%d bytes)，跳过文本提取",
            ext, len(pdf_bytes),
        )
        return {
            "raw_text": f"[二进制文件无法直接解析: {filename}]",
            "parser": "rejected",
        }

    def extract_metadata(self, raw_text: str, doc_type_hint: Optional[str] = None) -> dict:
        """
        规则引擎 + LLM 辅助元数据提取。

        策略:
          1. 规则引擎快速提取编号、日期等结构化字段
          2. LLM 补充标题、类型、关键词等语义字段
          3. LLM 不可用时纯规则引擎

        Returns:
            {doc_type, title, standard_code, issue_date, effective_date, status, publisher, keywords}
        """
        base = self._rule_extract_metadata(raw_text, doc_type_hint)

        if is_llm_available():
            llm_result = extract_metadata_by_llm(raw_text)
            if llm_result:
                # 合并：LLM 填规则引擎的空缺
                for key in ("doc_type", "title", "standard_code", "status", "publisher", "keywords"):
                    if not base.get(key) and llm_result.get(key):
                        base[key] = llm_result[key]
                for key in ("issue_date", "effective_date"):
                    if not base.get(key) and llm_result.get(key):
                        base[key] = llm_result[key]

        logger.info(f"[ParseService] metadata extracted: {base.get('title', 'N/A')}")
        return base

    @staticmethod
    def _rule_extract_metadata(raw_text: str, doc_type_hint: Optional[str] = None) -> dict:
        """规则引擎：正则匹配 + 关键词提取元数据"""
        text = raw_text[:3000]  # 前 3000 字符足够
        result = {
            "doc_type": doc_type_hint or "规范",
            "title": "",
            "standard_code": "",
            "issue_date": None,
            "effective_date": None,
            "status": "有效",
            "publisher": "",
            "keywords": [],
        }

        # 标准编号: GB 55037-2022, JGJ 3-2010, CJJ 12-2013 等
        code_match = re.search(r"(GB|JGJ|CJJ|CECS|DB)\s*\d+[.\-\d]*\d{4}", text)
        if code_match:
            result["standard_code"] = code_match.group(0).strip()

        # 规范状态
        if "废止" in text:
            result["status"] = "废止"
        elif "即将废止" in text or "替代" in text:
            result["status"] = "即将废止"

        # 日期
        date_pattern = r"(\d{4}[年\-/]\d{1,2}[月\-/]\d{1,2})"
        dates = re.findall(date_pattern, text)
        if len(dates) >= 2:
            result["issue_date"] = dates[0].replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")
            result["effective_date"] = dates[1].replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")
        elif len(dates) == 1:
            result["effective_date"] = dates[0].replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")

        # 发布单位
        publisher_match = re.search(r"(中华人民共和国|住房和城乡建设部|国家质量监督|国家标准化)[^\n]{0,30}", text)
        if publisher_match:
            result["publisher"] = publisher_match.group(0).strip()

        # 关键词：取高频建筑术语
        architecture_keywords = [
            "防火", "疏散", "耐火", "保温", "结构", "抗震", "防水",
            "节能", "绿色建筑", "消防", "安全出口", "建筑高度",
        ]
        found = [kw for kw in architecture_keywords if kw in text]
        result["keywords"] = found[:5] if found else ["建筑"]

        return result
