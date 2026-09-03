# -*- coding: utf-8 -*-
"""
建筑智能文档助手 — 端到端集成测试
===================================
模拟完整链路: PDF 生成 → 文档解析 → 元数据提取 → 文本切块 →
             向量检索 → LLM 问答 (RAG)

无需 Docker / PostgreSQL / Chroma，纯 Python 本地运行。
DASHSCOPE_API_KEY 从系统环境变量自动读取。

用法:
    python test_e2e_pipeline.py
    python test_e2e_pipeline.py --verbose
    python test_e2e_pipeline.py --skip-llm    (仅模拟解析，不调大模型)
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── 路径 ──
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "test_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════
#  ANSI 输出工具
# ═══════════════════════════════════════════════════════════════
C = type("C", (), {
    "G": "\033[92m", "R": "\033[91m", "Y": "\033[93m",
    "C": "\033[96m", "M": "\033[95m", "B": "\033[94m",
    "X": "\033[90m", "RE": "\033[0m", "BD": "\033[1m",
})()

if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleMode(ctypes.windll.kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass


def hdr(s):
    print(f"\n{C.C}{'═'*62}{C.RE}")
    print(f"{C.C}{C.BD}  {s}{C.RE}")
    print(f"{C.C}{'═'*62}{C.RE}")


def ok(s):
    print(f"  {C.G}✓{C.RE}  {s}")


def err(s):
    print(f"  {C.R}✗{C.RE}  {s}")


def warn(s):
    print(f"  {C.Y}△{C.RE}  {s}")


def info(s):
    print(f"     {C.X}{s}{C.RE}")


def divider():
    print(f"  {C.X}{'─'*56}{C.RE}")


# ═══════════════════════════════════════════════════════════════
#  Stage 0: 模拟建筑规范文档内容
# ═══════════════════════════════════════════════════════════════

MOCK_DOCUMENT = {
    "filename": "GB_55037-2022_建筑防火通用规范.pdf",
    "doc_type": "规范",
    "standard_code": "GB 55037-2022",
    "title": "建筑防火通用规范",
    "issue_date": "2022-12-01",
    "effective_date": "2023-06-01",
    "status": "有效",
    "publisher": "中华人民共和国住房和城乡建设部",
    "chapters": [
        {
            "title": "总则",
            "level": 1,
            "clauses": [
                ("1.0.1", "为预防建筑火灾、减少火灾危害，保护人身和财产安全，制定本规范。"),
                ("1.0.2", "本规范适用于新建、改建和扩建的建筑防火设计、施工和验收。"),
                ("1.0.3", "建筑防火应遵循国家有关方针政策，做到安全适用、技术先进、经济合理。"),
            ]
        },
        {
            "title": "建筑分类和耐火等级",
            "level": 1,
            "clauses": [
                ("2.1.1", "民用建筑根据其建筑高度和层数可分为单、多层民用建筑和高层民用建筑。高层民用建筑根据其建筑高度、使用功能和楼层的建筑面积可分为一类和二类。"),
                ("2.1.2", "建筑构件的燃烧性能和耐火极限应符合表2.2.1的规定。防火墙的耐火极限不应低于3.00h，承重墙不应低于2.00h。"),
                ("2.1.3", "一级耐火等级建筑的主要构件，其燃烧性能均为不燃性。"),
            ]
        },
        {
            "title": "防火分区和层数",
            "level": 1,
            "clauses": [
                ("3.1.1", "除本规范另有规定外，不同耐火等级建筑的允许建筑高度或层数、防火分区最大允许建筑面积应符合表3.1.1的规定。"),
                ("3.1.2", "建筑内设置自动灭火系统时，防火分区的最大允许建筑面积可按本规范的规定增加1.0倍。"),
                ("3.1.3", "地下或半地下建筑（室）的防火分区最大允许建筑面积不应大于500㎡。"),
            ]
        },
        {
            "title": "安全疏散与避难设施",
            "level": 1,
            "clauses": [
                ("4.1.1", "建筑内的安全出口和疏散门应分散布置，且建筑内每个防火分区或一个防火分区的每个楼层、每个住宅单元每层相邻两个安全出口最近边缘之间的水平距离不应小于5m。"),
                ("4.1.2", "公共建筑内每个防火分区或一个防火分区的每个楼层，其安全出口的数量应经计算确定，且不应少于2个。"),
                ("4.1.3", "疏散走道的净宽度：单面布房不应小于1.30m，双面布房不应小于1.40m。人员密集的公共场所疏散门不应设置门槛，其宽度不应小于1.40m。"),
            ]
        },
        {
            "title": "建筑保温",
            "level": 1,
            "clauses": [
                ("5.1.1", "建筑的外墙保温系统应根据建筑高度、建筑类别及防火等级选用相应的保温材料和构造措施。"),
                ("5.1.2", "建筑高度大于27m的住宅建筑和建筑高度大于24m的非单层公共建筑，其外墙外保温材料的燃烧性能应为A级。"),
                ("5.1.3", "除本规范另有规定外，建筑外墙外保温材料的燃烧性能等级不应低于B1级。"),
                ("5.1.4", "建筑外墙外保温系统应采用不燃材料在其表面设置防护层，防护层应将保温材料完全包覆。"),
            ]
        },
    ]
}


def render_document_text(doc: dict) -> str:
    """将 MOCK_DOCUMENT 渲染为完整文本"""
    lines = [
        f"{doc['title']}",
        f"标准编号: {doc['standard_code']}",
        f"发布日期: {doc['issue_date']}  施行日期: {doc['effective_date']}",
        f"发布单位: {doc['publisher']}",
        "",
    ]
    for ch in doc["chapters"]:
        lines.append(f"第{doc['chapters'].index(ch)+1}章  {ch['title']}")
        for clause_id, content in ch["clauses"]:
            lines.append(f"  {clause_id}  {content}")
        lines.append("")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
#  Stage 1: PDF 生成（模拟文档上传）
# ═══════════════════════════════════════════════════════════════

def stage1_generate_pdf(doc: dict) -> Tuple[str, bytes]:
    """生成测试 PDF 并返回 (路径, 字节内容)"""
    hdr("Stage 1: PDF 生成（模拟文档上传）")
    
    t0 = time.time()
    pdf_path = str(OUTPUT_DIR / f"{doc['standard_code'].replace(' ','_')}.pdf")
    raw_text = render_document_text(doc)
    
    # 尝试 reportlab / fpdf2 / 手工
    pdf_bytes = None
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(pdf_path, pagesize=A4)
        text_obj = c.beginText(45, 800)
        text_obj.setFont("Helvetica", 11)
        for line in raw_text.split("\n"):
            text_obj.textLine(line)
            if text_obj.getY() < 50:
                c.drawText(text_obj)
                c.showPage()
                text_obj = c.beginText(45, 800)
                text_obj.setFont("Helvetica", 11)
        c.drawText(text_obj)
        c.save()
        pdf_bytes = open(pdf_path, "rb").read()
    except ImportError:
        try:
            from fpdf import FPDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Helvetica", size=11)
            for line in raw_text.split("\n"):
                pdf.cell(0, 6, line, ln=True)
            pdf.output(pdf_path)
            pdf_bytes = open(pdf_path, "rb").read()
        except ImportError:
            # 最低回退：存入 .txt 并记录
            txt_path = pdf_path.replace(".pdf", ".txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(raw_text)
            pdf_path = txt_path
            pdf_bytes = raw_text.encode("utf-8")
            warn("reportlab/fpdf2 未安装，PDF 降级为 .txt 文件")
    
    file_hash = hashlib.sha256(pdf_bytes).hexdigest()[:16]
    elapsed = time.time() - t0
    
    ok(f"文件生成: {os.path.basename(pdf_path)}")
    ok(f"文件大小: {len(pdf_bytes)} bytes")
    ok(f"SHA256:   {file_hash}")
    info(f"耗时: {elapsed:.2f}s")
    
    return pdf_path, pdf_bytes


# ═══════════════════════════════════════════════════════════════
#  Stage 2: 文档解析（MinerU 模拟）
# ═══════════════════════════════════════════════════════════════

def stage2_parse_document(doc: dict, pdf_path: str, verbose: bool) -> dict:
    """模拟 MinerU 解析流程，输出结构化 JSON"""
    hdr("Stage 2: 文档解析（MinerU 模拟）")
    
    t0 = time.time()
    
    # 尝试真实 MinerU
    try:
        import magic_pdf
        from magic_pdf.data.data_reader_writer import FileBasedDataWriter
        from magic_pdf.data.dataset import PymuDocDataset
        from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze
        
        ok("magic-pdf 已安装，执行真实解析")
        pdf_bytes = open(pdf_path, "rb").read()
        ds = PymuDocDataset(pdf_bytes)
        is_ocr = (ds.classify() == "ocr")
        info(f"PDF 分类: {'OCR 扫描版' if is_ocr else '文字版'}")
        
        task_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = OUTPUT_DIR / f"mineru_{task_id}"
        out_dir.mkdir(exist_ok=True)
        
        infer = ds.apply(doc_analyze, ocr=is_ocr)
        if is_ocr:
            infer.pipe_ocr_mode(FileBasedDataWriter(str(out_dir / "images")))
        else:
            md_path = out_dir / f"{task_id}.md"
            infer.pipe_txt_mode(
                FileBasedDataWriter(str(out_dir / "images")),
                str(md_path),
            )
        
        parsed_text = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
        ok(f"MinerU 解析完成, 输出 {len(parsed_text)} 字符")
        info(f"产物目录: {out_dir}")
    except ImportError:
        warn("magic-pdf 未安装，使用模拟解析（结构化文本直接提取）")
        parsed_text = render_document_text(doc)
    
    # 构建结构化结果
    result = {
        "metadata": {
            "title": doc["title"],
            "doc_type": doc["doc_type"],
            "standard_code": doc["standard_code"],
            "issue_date": doc["issue_date"],
            "effective_date": doc["effective_date"],
            "status": doc["status"],
            "publisher": doc["publisher"],
        },
        "chapters": [],
        "raw_text": parsed_text,
        "parsed_at": datetime.now().isoformat(),
    }
    
    for ch in doc["chapters"]:
        chapter = {
            "title": ch["title"],
            "level": ch["level"],
            "clauses": [
                {
                    "clause_id": cid,
                    "content": ctext,
                    "page_num": doc["chapters"].index(ch) + 1,  # 模拟页码
                }
                for cid, ctext in ch["clauses"]
            ],
        }
        result["chapters"].append(chapter)
    
    elapsed = time.time() - t0
    total_clauses = sum(len(ch["clauses"]) for ch in result["chapters"])
    ok(f"解析完成: {len(result['chapters'])} 章, {total_clauses} 条款, 耗时 {elapsed:.2f}s")
    
    if verbose:
        for ch in result["chapters"]:
            info(f"  └ {ch['title']} ({len(ch['clauses'])} 条款)")
    
    # 持久化
    json_path = OUTPUT_DIR / "parsed_document.json"
    json.dump(result, open(json_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    info(f"解析结果已保存: {json_path}")
    
    return result


# ═══════════════════════════════════════════════════════════════
#  Stage 3: LLM 元数据提取
# ═══════════════════════════════════════════════════════════════

def stage3_extract_metadata(parsed: dict, skip_llm: bool, verbose: bool) -> dict:
    """使用通义千问从文档内容中提取元数据"""
    hdr("Stage 3: LLM 元数据提取")
    
    if skip_llm:
        warn("--skip-llm 已启用，使用规则引擎提取")
        return _rule_based_metadata(parsed)
    
    try:
        from dashscope import Generation
        from http import HTTPStatus
    except ImportError:
        warn("dashscope 未安装，降级为规则引擎提取")
        return _rule_based_metadata(parsed)
    
    t0 = time.time()
    
    # 取文档前 1500 字符作为 LLM 输入
    preview = parsed["raw_text"][:1500]
    
    prompt = f"""你是一位建筑行业文档专家。请从以下文档内容中提取元数据，以严格 JSON 格式返回：

文档内容：
{preview}

需要提取的字段（不确定的用 null）：
- doc_type: 文档类型（规范/图集/变更单/图纸/报告/施工日志）
- title: 文档标题
- standard_code: 标准编号（如 GB 55037-2022）
- issue_date: 发布日期 YYYY-MM-DD
- effective_date: 施行日期 YYYY-MM-DD
- status: 规范状态（有效/废止/即将废止）
- publisher: 发布单位
- keywords: 3-5 个核心关键词

只返回 JSON，不要其他文字。"""

    try:
        resp = Generation.call(
            model="qwen-turbo",
            messages=[{"role": "user", "content": prompt}],
            result_format="message",
            temperature=0.1,
        )
        
        if resp.status_code == HTTPStatus.OK:
            raw_output = resp.output.choices[0].message.content.strip()
            # 清理 markdown 包裹
            raw_output = re.sub(r"^```(?:json)?\s*", "", raw_output)
            raw_output = re.sub(r"\s*```$", "", raw_output)
            metadata = json.loads(raw_output)
            
            elapsed = time.time() - t0
            ok(f"LLM 元数据提取成功, 耗时 {elapsed:.2f}s")
            ok(f"模型: qwen-turbo")
            
            for k, v in metadata.items():
                color = C.G if v else C.Y
                info(f"  {k}: {color}{v}{C.RE}")
            
            return metadata
        else:
            err(f"LLM 调用失败: HTTP {resp.status_code} - {resp.message}")
            return _rule_based_metadata(parsed)
    except Exception as e:
        err(f"LLM 提取异常: {e}")
        return _rule_based_metadata(parsed)


def _rule_based_metadata(parsed: dict) -> dict:
    """规则引擎回退：从解析结果中提取元数据"""
    meta = parsed.get("metadata", {})
    return {
        "doc_type": meta.get("doc_type", "规范"),
        "title": meta.get("title", ""),
        "standard_code": meta.get("standard_code", ""),
        "issue_date": meta.get("issue_date"),
        "effective_date": meta.get("effective_date"),
        "status": meta.get("status", "有效"),
        "publisher": meta.get("publisher", "中华人民共和国住房和城乡建设部"),
        "keywords": ["防火", "建筑", "疏散", "耐火等级", "保温"],
    }


# ═══════════════════════════════════════════════════════════════
#  Stage 4: 文本切块（Chunking）
# ═══════════════════════════════════════════════════════════════

def stage4_chunk_text(parsed: dict, verbose: bool) -> List[Dict]:
    """将条款拆分为适合 RAG 的 chunk"""
    hdr("Stage 4: 文本切块（Chunking）")
    
    t0 = time.time()
    chunks = []
    
    for ch in parsed["chapters"]:
        chapter_title = ch["title"]
        for clause in ch["clauses"]:
            chunk = {
                "chunk_id": str(uuid.uuid4())[:8],
                "content": clause["content"],
                "metadata": {
                    "chapter": chapter_title,
                    "clause_id": clause["clause_id"],
                    "standard_code": parsed["metadata"].get("standard_code", ""),
                    "standard_title": parsed["metadata"].get("title", ""),
                    "status": parsed["metadata"].get("status", "有效"),
                    "page_num": clause.get("page_num", 1),
                },
            }
            chunks.append(chunk)
    
    elapsed = time.time() - t0
    ok(f"切块完成: {len(chunks)} 个 chunk, 耗时 {elapsed:.2f}s")
    
    # 统计
    lengths = [len(c["content"]) for c in chunks]
    info(f"chunk 长度: min={min(lengths)}, max={max(lengths)}, avg={sum(lengths)//len(lengths)} 字符")
    
    if verbose:
        for c in chunks:
            info(f"  [{c['metadata']['clause_id']}] {c['content'][:50]}...")
    
    return chunks


# ═══════════════════════════════════════════════════════════════
#  Stage 5: 向量检索（模拟 BGE-M3 + Chroma）
# ═══════════════════════════════════════════════════════════════

def stage5_search(chunks: List[Dict], query: str, top_k: int = 5, verbose: bool = False) -> List[Dict]:
    """
    模拟混合检索：关键词匹配 (BM25) + 语义排名（用 LLM 做 Rerank）
    真实环境替换为 BGE-M3 + Chroma dense/sparse 检索
    """
    hdr(f"Stage 5: 向量检索（模拟 BGE-M3 + Chroma）")
    info(f"查询: {C.Y}\"{query}\"{C.RE}")
    info(f"Top-K: {top_k}")
    
    t0 = time.time()
    
    # ── 第一轮：关键词粗筛 ──
    query_terms = set(query.replace("？", "").replace("?", ""))
    scored = []
    for chunk in chunks:
        content = chunk["content"]
        # 简单的 overlap 评分
        hit_chars = sum(1 for ch in query_terms if ch in content)
        clause_match = chunk["metadata"]["clause_id"] in query
        keyword_score = hit_chars / max(len(query_terms), 1) + (1.0 if clause_match else 0)
        scored.append((keyword_score, chunk))
    
    # 按粗分排序，取 top_k * 3 进入精排
    scored.sort(key=lambda x: x[0], reverse=True)
    candidates = scored[: top_k * 3]
    
    info(f"关键词粗筛: {len(candidates)} 条候选（从 {len(chunks)} 中筛选）")
    
    # ── 第二轮：LLM Rerank（模拟 BGE-M3 Cross-Encoder）──
    try:
        from dashscope import Generation
        from http import HTTPStatus
        
        reranked = _llm_rerank(query, candidates, top_k)
    except Exception:
        # 纯关键词排序
        reranked = [(c[0], c[1]) for c in candidates[:top_k]]
    
    elapsed = time.time() - t0
    ok(f"检索完成: {len(reranked[:top_k])} 条结果, 耗时 {elapsed:.2f}s")
    
    # 展示结果
    divider()
    for i, (score, chunk) in enumerate(reranked[:top_k]):
        cid = chunk["metadata"]["clause_id"]
        chap = chunk["metadata"]["chapter"]
        content_preview = chunk["content"][:70].replace("\n", " ")
        print(f"  {C.G}#{i+1}{C.RE} [{cid}] {chap}")
        print(f"      {C.X}{content_preview}...{C.RE}")
        print(f"      {C.Y}相关度: {score:.3f}{C.RE}")
    
    return reranked[:top_k]


def _llm_rerank(query: str, candidates: List, top_k: int) -> List:
    """使用 LLM 对候选 chunk 进行精排"""
    from dashscope import Generation
    from http import HTTPStatus
    
    # 构造 rerank 输入
    items_text = ""
    for idx, (_, chunk) in enumerate(candidates):
        cid = chunk["metadata"]["clause_id"]
        items_text += f"[{idx}] 条款{cid}: {chunk['content'][:100]}\n"
    
    prompt = f"""请根据用户查询的相关度，对以下法律条款进行排序。返回最相关 {top_k} 条的索引编号（从最相关到最不相关），格式如: [3, 0, 5, 1, 2]

查询: {query}

候选条款:
{items_text}

只返回 JSON 数组，如 [3, 0, 5, 1, 2]，不要其他文字。"""
    
    try:
        resp = Generation.call(
            model="qwen-turbo",
            messages=[{"role": "user", "content": prompt}],
            result_format="message",
            temperature=0,
        )
        if resp.status_code == HTTPStatus.OK:
            text = resp.output.choices[0].message.content.strip()
            ids = json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", text))
            ranked = [(candidates[i][0] + 0.5, candidates[i][1]) for i in ids if 0 <= i < len(candidates)]
            # 合并未排入的
            for idx, (s, c) in enumerate(candidates):
                if idx not in ids:
                    ranked.append((s, c))
            return ranked[:top_k]
    except Exception:
        pass
    
    return [(c[0], c[1]) for c in candidates[:top_k]]


# ═══════════════════════════════════════════════════════════════
#  Stage 6: RAG 问答（LLM 生成）
# ═══════════════════════════════════════════════════════════════

def stage6_rag_answer(
    query: str,
    retrieved: List[Tuple[float, Dict]],
    metadata: dict,
    skip_llm: bool,
    verbose: bool,
) -> dict:
    """构建 Prompt → 调用通义千问 → 返回结构化答案"""
    hdr("Stage 6: RAG 问答（LLM 生成）")
    
    if skip_llm:
        warn("--skip-llm 已启用，返回拼接上下文模式")
        return _mock_answer(query, retrieved)
    
    try:
        from dashscope import Generation
        from http import HTTPStatus
    except ImportError:
        warn("dashscope 未安装，返回拼接上下文")
        return _mock_answer(query, retrieved)
    
    # 构建上下文
    context_parts = []
    for score, chunk in retrieved:
        cid = chunk["metadata"]["clause_id"]
        chap = chunk["metadata"]["chapter"]
        code = chunk["metadata"]["standard_code"] or metadata.get("standard_code", "GB 55037")
        title = chunk["metadata"]["standard_title"] or metadata.get("title", "建筑防火通用规范")
        status = chunk["metadata"].get("status", "有效")
        status_tag = "" if status == "有效" else "【已废止】"
        context_parts.append(
            f"条款编号: {cid}  {status_tag}\n"
            f"所属章节: {chap}\n"
            f"来源: 《{title}》{code}\n"
            f"原文: {chunk['content']}\n"
        )
    context = "\n---\n".join(context_parts)
    
    prompt = f"""你是一位建筑行业规范专家。请基于以下规范条款内容，回答用户问题。

【回答要求】
1. 直接给出明确结论，不要绕弯子
2. 引用具体规范名称和条款编号（如"依据《建筑防火通用规范》GB 55037-2022 第X.X.X条"）
3. 如果涉及具体数值，明确给出
4. 如果多个条款均相关，综合回答并标注各条款对应内容

【规范条款内容】
{context}

【用户问题】
{query}

【对话历史】
（无历史）

请用中文回答："""
    
    t0 = time.time()
    
    try:
        resp = Generation.call(
            model="qwen-max",
            messages=[{"role": "user", "content": prompt}],
            result_format="message",
            temperature=0.2,
            max_tokens=2048,
        )
        
        elapsed = time.time() - t0
        
        if resp.status_code == HTTPStatus.OK:
            answer = resp.output.choices[0].message.content
            usage = resp.usage
            
            ok(f"LLM 生成成功, 耗时 {elapsed:.2f}s")
            ok(f"模型: qwen-max")
            info(f"Token 用量: input={usage.input_tokens}, output={usage.output_tokens}")
            
            divider()
            print(f"\n{C.BD}━━━━━━  AI 回答 ━━━━━━{C.RE}\n")
            print(answer)
            print(f"\n{C.BD}━━━━━━━━━━━━━━━━━━━━{C.RE}\n")
            divider()
            
            # 溯源列举
            info("引用条款:")
            for score, chunk in retrieved:
                cid = chunk["metadata"]["clause_id"]
                info(f"  → 《{chunk['metadata']['standard_title']}》{chunk['metadata']['standard_code']} 第{cid}条  (相关度:{score:.2f})")
            
            return {
                "answer": answer,
                "sources": [
                    {
                        "clause_id": c[1]["metadata"]["clause_id"],
                        "standard_code": c[1]["metadata"]["standard_code"],
                        "standard_title": c[1]["metadata"]["standard_title"],
                        "chapter": c[1]["metadata"]["chapter"],
                        "content": c[1]["content"],
                        "score": round(c[0], 4),
                    }
                    for c in retrieved
                ],
                "model": "qwen-max",
                "tokens": {"input": usage.input_tokens, "output": usage.output_tokens},
                "elapsed": round(elapsed, 2),
                "disclaimer": "AI 回答仅供参考，请以规范原文和纸质图集为准",
            }
        else:
            err(f"LLM 调用失败: HTTP {resp.status_code} - {resp.message}")
            return _mock_answer(query, retrieved)
    except Exception as e:
        err(f"LLM 调用异常: {e}")
        return _mock_answer(query, retrieved)


def _mock_answer(query: str, retrieved: List) -> dict:
    """不调用 LLM 时，直接拼接检索结果作为"答案" """
    parts = []
    for score, chunk in retrieved:
        cid = chunk["metadata"]["clause_id"]
        parts.append(f"【{cid}】(相关度:{score:.2f}) {chunk['content']}")
    
    mock = "\n\n".join(parts)
    print(f"\n{C.Y}▲ 模拟回答（未调 LLM）:{C.RE}\n{mock}\n")
    
    return {
        "answer": f"[模拟] {mock}",
        "sources": [
            {
                "clause_id": c[1]["metadata"]["clause_id"],
                "standard_code": c[1]["metadata"]["standard_code"],
                "content": c[1]["content"][:100],
                "score": round(c[0], 4),
            }
            for c in retrieved
        ],
        "model": "mock (no LLM)",
        "tokens": None,
        "elapsed": 0,
        "disclaimer": "AI 回答仅供参考，请以规范原文和纸质图集为准",
    }


# ═══════════════════════════════════════════════════════════════
#  Stage 7: 图集问答测试（附加场景）
# ═══════════════════════════════════════════════════════════════

def stage7_atlas_qa(skip_llm: bool):
    """测试图集节点图文问答场景"""
    hdr("Stage 7: 图集节点问答（附加场景）")
    
    mock_atlas = {
        "atlas_code": "12J201",
        "atlas_title": "平屋面建筑构造",
        "nodes": [
            {
                "node_id": "A-1",
                "node_name": "上人屋面防水做法（正置式）",
                "description": "1. 40厚C20细石混凝土保护层，配Φ6@200双向钢筋网\n"
                               "2. 10厚低强度等级砂浆隔离层\n"
                               "3. 4厚SBS改性沥青防水卷材（II型）\n"
                               "4. 20厚1:3水泥砂浆找平层\n"
                               "5. 最薄30厚LC5.0轻集料混凝土2%找坡层\n"
                               "6. 100厚挤塑聚苯板（XPS）保温层\n"
                               "7. 钢筋混凝土屋面板",
                "materials": ["C20细石混凝土", "SBS改性沥青防水卷材", "挤塑聚苯板", "水泥砂浆"],
            },
            {
                "node_id": "A-2",
                "node_name": "上人屋面防水做法（倒置式）",
                "description": "1. 40厚C20细石混凝土保护层\n"
                               "2. 100厚挤塑聚苯板（XPS）保温层\n"
                               "3. 4厚SBS改性沥青防水卷材（II型）\n"
                               "4. 20厚1:3水泥砂浆找平层\n"
                               "5. 最薄30厚LC5.0轻集料混凝土2%找坡层\n"
                               "6. 钢筋混凝土屋面板",
                "materials": ["C20细石混凝土", "SBS改性沥青防水卷材", "挤塑聚苯板"],
            },
        ]
    }
    
    query = "屋面防水上人屋面的正置式和倒置式做法有什么区别？哪个更好？"
    info(f"图集: {mock_atlas['atlas_code']} 《{mock_atlas['atlas_title']}》")
    info(f"查询: \"{query}\"")
    
    if skip_llm:
        warn("--skip-llm 已启用")
        return
    
    nodes_text = ""
    for n in mock_atlas["nodes"]:
        nodes_text += (
            f"节点编号: {n['node_id']}  {n['node_name']}\n"
            f"所属图集: 《{mock_atlas['atlas_title']}》{mock_atlas['atlas_code']}\n"
            f"做法描述:\n{n['description']}\n"
            f"主要材料: {', '.join(n['materials'])}\n---\n"
        )
    
    prompt = f"""你是一位建筑施工技术专家。请基于以下图集节点信息，回答用户问题。

【回答要求】
1. 描述具体做法步骤，包括材料、厚度、工序等关键参数
2. 对比说明两种做法的差异（用表格形式）
3. 给出推荐意见和适用场景
4. 对关键参数加粗标注

【图集节点信息】
{nodes_text}

【用户问题】
{query}

请用中文回答，保持专业准确："""
    
    try:
        from dashscope import Generation
        from http import HTTPStatus
        
        t0 = time.time()
        resp = Generation.call(
            model="qwen-max",
            messages=[{"role": "user", "content": prompt}],
            result_format="message",
            temperature=0.2,
            max_tokens=2048,
        )
        elapsed = time.time() - t0
        
        if resp.status_code == HTTPStatus.OK:
            answer = resp.output.choices[0].message.content
            ok(f"图集问答完成, 耗时 {elapsed:.2f}s")
            
            divider()
            print(f"\n{C.BD}━━━━━━  图集做法对比 ━━━━━━{C.RE}\n")
            print(answer)
            print(f"\n{C.BD}━━━━━━━━━━━━━━━━━━━━{C.RE}\n")
            
            ok(f"Token 用量: input={resp.usage.input_tokens}, output={resp.usage.output_tokens}")
        else:
            err(f"图集问答失败: {resp.message}")
    except Exception as e:
        err(f"图集问答异常: {e}")


# ═══════════════════════════════════════════════════════════════
#  主流程
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="建筑智能文档助手 — 端到端集成测试")
    parser.add_argument("--skip-llm", action="store_true", help="跳过 LLM 调用（仅模拟检索）")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--query", default="6层住宅楼需要设电梯吗",
                        help="测试查询（默认：6层住宅楼需要设电梯吗）")
    parser.add_argument("--query-atlas", default=None,
                        help="覆盖图集查询（默认测试正置式vs倒置式）")
    args = parser.parse_args()
    
    t_total = time.time()
    
    print(f"\n{C.B}{'┌' + '─'*58 + '┐'}{C.RE}")
    print(f"{C.B}│  建筑智能文档助手 — 端到端集成测试                      │{C.RE}")
    print(f"{C.B}│  开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                               │{C.RE}")
    print(f"{C.B}{'└' + '─'*58 + '┘'}{C.RE}")
    
    # ── Stage 1: PDF 生成 ──
    pdf_path, pdf_bytes = stage1_generate_pdf(MOCK_DOCUMENT)
    
    # ── Stage 2: 文档解析 ──
    parsed = stage2_parse_document(MOCK_DOCUMENT, pdf_path, args.verbose)
    
    # ── Stage 3: 元数据提取 ──
    metadata = stage3_extract_metadata(parsed, args.skip_llm, args.verbose)
    
    # ── Stage 4: 文本切块 ──
    chunks = stage4_chunk_text(parsed, args.verbose)
    
    # ── Stage 5: 向量检索 ──
    query = args.query
    retrieved = stage5_search(chunks, query, top_k=5, verbose=args.verbose)
    
    # ── Stage 6: RAG 问答 ──
    answer = stage6_rag_answer(query, retrieved, metadata, args.skip_llm, args.verbose)
    
    # ── Stage 7: 图集问答 ──
    atlas_query = args.query_atlas or "屋面防水上人屋面的正置式和倒置式做法有什么区别？"
    stage7_atlas_qa(args.skip_llm)
    
    # ── 汇总 ──
    total_elapsed = time.time() - t_total
    print(f"\n{C.M}{'═'*62}{C.RE}")
    print(f"{C.M}{C.BD}  端到端测试完成{C.RE}")
    print(f"{C.M}{'═'*62}{C.RE}")
    print(f"  {C.G}总耗时: {total_elapsed:.1f}s{C.RE}")
    print(f"  {C.G}处理阶段: 7/7{C.RE}")
    print(f"  {C.G}检索命中: {len(retrieved)} 条{C.RE}")
    if not args.skip_llm:
        print(f"  {C.G}LLM 调用: 3 次（元数据提取 + RAG 问答 + 图集问答）{C.RE}")
    print()
    
    # 导出完整报告
    report_path = OUTPUT_DIR / f"e2e_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    json.dump({
        "timestamp": datetime.now().isoformat(),
        "document": MOCK_DOCUMENT["filename"],
        "query": query,
        "stages": {
            "1_pdf_generation": str(pdf_path),
            "2_document_parsing": f"{len(parsed['chapters'])} chapters",
            "3_metadata_extraction": metadata,
            "4_chunking": f"{len(chunks)} chunks",
            "5_retrieval": f"{len(retrieved)} results",
            "6_rag_answer": answer,
        },
        "total_elapsed": round(total_elapsed, 2),
    }, open(report_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    info(f"完整报告已保存: {report_path}")


if __name__ == "__main__":
    main()
