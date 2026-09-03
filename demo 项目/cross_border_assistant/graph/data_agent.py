# -*- coding: utf-8 -*-
from graph.state import AgentState, get_last_content
from db.duckdb_manager import SessionDB
from utils.llm_client import call_llm
from utils.plot_helper import plot_from_df
import json
import re

# 兼容旧接口：从LLM返回中提取SQL语句（如有markdown代码块）
def extract_sql_from_llm(response: str) -> str:
    """从LLM返回中提取SQL语句（如果有markdown代码块）"""
    match = re.search(r"```sql\n(.*?)\n```", response, re.DOTALL)
    if match:
        return match.group(1).strip()
    # 尝试直接找 SELECT
    if "SELECT" in response.upper():
        # 粗暴提取 SELECT 到分号或结尾
        start = response.upper().find("SELECT")
        end = response.find(";", start)
        if end == -1:
            end = len(response)
        return response[start:end].strip()
    return response.strip()


def extract_json_from_llm(response: str) -> dict:
    """从LLM返回中提取JSON对象（容忍markdown代码块与前后杂讯），失败返回None"""
    # 1. ```json ... ``` 代码块
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # 2. 直接找 {...} 块
    match = re.search(r"\{.*\}", response, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None


def _build_schema_context(db_manager: SessionDB, tables: list) -> str:
    """构造表结构上下文文本（列名+类型+示例行），供 LLM 生成准确 SQL"""
    parts = []
    for t in tables:
        try:
            info = db_manager.get_table_schema(t)
            cols = ", ".join(f"{c['name']}({c['type']})" for c in info["columns"])
            sample = json.dumps(info["sample_rows"], ensure_ascii=False)
            parts.append(f"表 {t} 列结构: {cols}\n示例数据(前5行): {sample}")
        except Exception as e:
            parts.append(f"表 {t} (无法读取结构: {e})")
    return "\n".join(parts)


def _build_system_prompt(schema_text: str, data_type: str = None) -> str:
    prompt = f"""你是一个数据分析专家。以下是当前会话可查询的表结构：
{schema_text}

请根据用户问题生成 DuckDB SQL，并仅输出一个 JSON 对象（不要输出任何其他内容）：
{{"sql": "SQL语句", "need_chart": true或false, "chart_type": "line"或"bar", "answer_type": "list"或"summary"}}

要求：
- SQL 只能使用上述表中真实存在的列名与表名，DuckDB 语法
- 若用户要求趋势/走势/随时间变化 → need_chart=true, chart_type="line"
- 若用户要求对比/占比/分布 → need_chart=true, chart_type="bar"
- 其余情况 need_chart=false, chart_type 置为 "line"
- answer_type: 用户要求"列出/哪些/多少/清单/明细"等 → "list"；要求"统计/平均/趋势/分析/对比/占比"等 → "summary"
"""
    if data_type == "predict":
        prompt += (
            '\n用户要求的是"预测"：请基于历史数据生成聚合SQL'
            '（如按月/周/品类分组统计销量或销售额趋势），'
            '让总结能基于历史表现推断未来趋势。\n'
        )
    elif data_type == "vague":
        prompt += (
            '\n用户只是模糊地想查看数据：请生成最简单的浏览SQL'
            '（如 SELECT * 或按时间排序，可 LIMIT 10），不要过度加工。\n'
        )
    return prompt


def _build_summary_prompt(user_query: str, df, answer_type: str) -> str:
    """构造回答式总结 prompt：区分列表型与汇总型，尽量提供完整数据"""
    total_rows = len(df)
    show = df.head(20) if total_rows > 20 else df
    data_sample = show.to_string()
    if answer_type == "list":
        return (
            f"【总结】用户问题：{user_query}\n"
            f"查询结果共{total_rows}行，数据如下：\n{data_sample}\n"
            f"请直接回答用户的问题：如用户要求列出条目，请列出所有条目及具体数值"
            f"（超过20行时列出前20行并注明共N行）。不要做趋势、对比等额外分析，"
            f"不要编造数据中不存在的信息。"
        )
    return (
        f"【总结】用户问题：{user_query}\n"
        f"数据（共{total_rows}行）：\n{data_sample}\n"
        f"请用中文总结关键发现来回答用户问题（不超过3句话），不要编造数据中不存在的信息。"
    )


def data_agent_node(state: AgentState, db_manager: SessionDB) -> dict:
    """DataAgent 执行数据查询与绘图：schema 注入 + LLM 结构化 JSON 决策"""
    user_query = get_last_content(state)
    session_id = state["session_id"]

    # 1. 获取该会话已有的表
    tables = db_manager.get_session_tables(session_id)
    if not tables:
        return {"error": "当前会话未上传任何数据文件，请先上传CSV或Excel。", "execution_result": None}

    data_type = state.get("data_type")  # trend/stat/list/predict/vague（supervisor 传入）

    # 模糊查看：引导用户明确具体操作（不直接跑 SQL）
    if data_type == "vague":
        return {
            "execution_result": {
                "type": "data",
                "sql": None,
                "dataframe": [],
                "total_rows": 0,
                "chart": None,
                "answer_type": "vague",
                "summary": (
                    f"请明确具体操作，例如：\n"
                    f"- 查询趋势：\"展示7月每日总销售额趋势图\"\n"
                    f"- 统计汇总：\"按品类统计总销量和平均广告费\"\n"
                    f"- 列表查询：\"列出库存低于50的SKU及库存数\"\n"
                    f"当前会话已上传 {len(tables)} 个数据文件。"
                ),
            }
        }

    schema_text = _build_schema_context(db_manager, tables)
    system_prompt = _build_system_prompt(schema_text, data_type)

    def ask_llm(prompt_text, system=None) -> dict:
        """调用 LLM 并解析 JSON，失败返回 None"""
        resp = call_llm(prompt_text, system_prompt=system)
        if resp.startswith("LLM调用失败"):
            raise RuntimeError(resp)
        return extract_json_from_llm(resp)

    # 2. LLM 生成结构化决策（SQL + 图表意图）
    try:
        parsed = ask_llm(f"用户问题：{user_query}\n请输出JSON：", system_prompt)
        if not parsed or not parsed.get("sql"):
            # 修正重试：明确要求 JSON 格式
            parsed = ask_llm(
                f"你上次的输出无法解析，请严格只输出 JSON：{{\"sql\":\"...\",\"need_chart\":true或false,\"chart_type\":\"line或bar\"}}。用户问题：{user_query}",
                system_prompt,
            )
        if not parsed or not parsed.get("sql"):
            return {"error": "无法从模型输出中解析出SQL，请调整问题后重试。", "execution_result": None}
    except RuntimeError as e:
        return {"error": f"生成SQL失败：{e}", "execution_result": None}

    sql = parsed["sql"].strip()
    need_chart = bool(parsed.get("need_chart", False))
    chart_type = parsed.get("chart_type", "line") if need_chart else None
    answer_type = parsed.get("answer_type", "summary")  # list / summary

    # 3. 执行SQL；失败时携带真实表结构重新生成一次
    try:
        df = db_manager.execute_sql(session_id, sql)
    except Exception as e:
        try:
            parsed2 = ask_llm(
                f"SQL执行失败：{e}。原SQL：{sql}。请基于上述真实表结构重新生成正确的DuckDB SQL，仅输出JSON。",
                system_prompt,
            )
            if parsed2 and parsed2.get("sql"):
                sql = parsed2["sql"].strip()
                if parsed2.get("need_chart"):
                    need_chart = True
                    chart_type = parsed2.get("chart_type", chart_type or "line")
                answer_type = parsed2.get("answer_type", answer_type)
            df = db_manager.execute_sql(session_id, sql)
        except Exception as e2:
            if data_type == "vague":
                # 模糊查看兜底：直接浏览全表前10行
                sql = f"SELECT * FROM {tables[0]} LIMIT 10"
                try:
                    df = db_manager.execute_sql(session_id, sql)
                except Exception as e3:
                    return {"error": f"SQL执行失败：{e3}。SQL：{sql}", "execution_result": None}
            else:
                return {
                    "error": f"SQL执行失败：{e2}。SQL：{sql}",
                    "execution_result": None,
                }

    # 4. 按 LLM 决策生成图表
    chart_base64 = None
    if need_chart and len(df) > 1 and len(df.columns) >= 2:
        chart_base64 = plot_from_df(df, title=user_query[:20], chart_type=chart_type or "line")

    # 5. 回答式总结（区分列表型/汇总型）
    summary = call_llm(_build_summary_prompt(user_query, df, answer_type))

    result = {
        "type": "data",
        "sql": sql,
        "dataframe": df.to_dict(orient="records")[:50],  # 只传前50行用于展示
        "total_rows": len(df),
        "chart": chart_base64,
        "chart_type": chart_type,
        "answer_type": answer_type,
        "summary": summary,
    }
    return {"execution_result": result}
