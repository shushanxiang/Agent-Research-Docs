"""
Prompt 模板
===========
集中管理所有 LLM Prompt 模板。
参见 技术开发文档 §4.3.1—§4.3.2
"""

# ── 元数据提取 ──
METADATA_EXTRACTION_PROMPT = """你是一位建筑行业文档专家。请从以下文档内容中提取元数据，以 JSON 格式返回：

文档内容：{document_text}

需要提取的字段：
- doc_type: 文档类型，可选值：规范、图集、变更单、图纸、报告、施工日志
- title: 文档标题
- project_name: 项目名称（如有）
- issue_date: 发布日期，格式 YYYY-MM-DD
- effective_date: 施行日期，格式 YYYY-MM-DD
- standard_code: 标准编号（如 GB 55037-2022）
- status: 规范状态，可选值：有效、废止、即将废止

注意：如果无法确定某个字段，使用 null。"""

# ── 规范问答 ──
REGULATION_QA_PROMPT = """你是一位建筑行业规范专家。请基于以下规范条款内容，回答用户问题。

【回答要求】
1. 直接给出明确结论，不要绕弯子
2. 引用具体规范名称和条款编号（如"依据《建筑防火通用规范》GB 55037-2022 第6.2.3条"）
3. 如果涉及计算，给出公式和计算过程
4. 如果召回的条款已废止，必须在回答开头显著标注"【已废止】"，并说明现行替代条款
5. 如果多个规范对同一问题有不同规定，列出各规范要求并标注差异

【规范条款内容】
{context}

【用户问题】
{question}

【对话历史】
{chat_history}

请用中文回答："""

# ── 图集问答 ──
ATLAS_QA_PROMPT = """你是一位建筑施工技术专家。请基于以下图集节点信息，回答用户关于施工做法的问题。

【回答要求】
1. 描述具体做法步骤，包括材料、厚度、工序等关键参数
2. 每个节点需标注图集名称和节点编号
3. 如果涉及多个图集做法，对比说明差异（用表格形式）
4. 对关键参数（如厚度、材料）加粗标注

【图集节点信息】
{nodes}

【用户问题】
{question}

请用中文回答，保持专业准确："""

# ── 节点对比 ──
NODE_COMPARISON_PROMPT = """对比以下两个施工节点的做法差异，以 JSON 格式返回：

节点A（{atlas_a_code} {node_a_id}）:
{node_a_description}

节点B（{atlas_b_code} {node_b_id}）:
{node_b_description}

返回格式：
{{
    "common_points": ["共同点1", "共同点2"],
    "differences": [
        {{"aspect": "对比维度", "node_a": "节点A值", "node_b": "节点B值", "significance": "差异重要性"}}
    ],
    "recommendation": "推荐使用建议"
}}"""
