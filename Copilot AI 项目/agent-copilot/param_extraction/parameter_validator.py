from datetime import datetime
from typing import List, Dict, Optional, Any

from entity import Tool
from utils import logger


class ParameterValidator:
    """
    代码层参数校验器 — 不依赖大模型，作为纵深防御的第一道防线。
    检查参数值的业务合法性（数值范围、格式、业务规则）。
    """

    # 通用业务规则
    BUSINESS_RULES: Dict[str, dict] = {
        # 数值范围
        "quantity":       {"min": 0,     "max": 999_999},
        "price":          {"min": 0,     "max": 99_999_999},
        "amount":         {"min": 0,     "max": 99_999_999},
        "weight":         {"min": 0,     "max": 99_999},
        "discount":       {"min": 0,     "max": 100},
        # 分页
        "pageSize":       {"min": 1,     "max": 100},
        "pageNum":        {"min": 1,     "max": 9_999},
        "limit":          {"min": 1,     "max": 1_000},
        "offset":         {"min": 0,     "max": 999_999},
    }

    # 参数名关键词 → 业务规则映射（启发式匹配）
    KEYWORD_RULES: Dict[str, str] = {
        "quantity":  "quantity",
        "count":     "quantity",
        "num":       "quantity",
        "price":     "price",
        "amount":    "amount",
        "weight":    "weight",
        "discount":  "discount",
        "pageSize":  "pageSize",
        "page_size": "pageSize",
        "pageNum":   "pageNum",
        "page_num":  "pageNum",
        "limit":     "limit",
        "offset":    "offset",
    }

    @classmethod
    def validate(cls, tool: Tool, params: Dict[str, Any]) -> List[str]:
        """
        校验参数的业务合法性。

        Args:
            tool: 工具定义
            params: 待校验的参数 dict

        Returns:
            错误信息列表，空列表表示全部通过
        """
        errors = []

        for param_def in tool.request_body:
            value = params.get(param_def.name)

            # 跳过未提供的参数（由 Pydantic 桥接层处理缺失，此处只做值校验）
            if value is None:
                continue

            # --- 1. 空值检查（Pydantic 已做类型校验，但字符串空值仍需业务层判断） ---
            if isinstance(value, str) and len(value.strip()) == 0:
                errors.append(f"参数「{param_def.name}」不能为空字符串")
                continue

            # --- 2. 数值范围检查 ---
            if isinstance(value, (int, float)):
                rule = cls._match_rule(param_def.name)
                if rule:
                    if "min" in rule and value < rule["min"]:
                        errors.append(
                            f"参数「{param_def.name}」的值为 {value}，"
                            f"不能为负数（最小值: {rule['min']}），请检查输入"
                        )
                    if "max" in rule and value > rule["max"]:
                        errors.append(
                            f"参数「{param_def.name}」的值为 {value}，"
                            f"超出上限（最大值: {rule['max']}），请检查输入"
                        )

            # --- 3. 日期格式校验 ---
            if param_def.type in ("date-time", "timestamp"):
                if isinstance(value, str):
                    try:
                        cleaned = value.replace("Z", "+00:00")
                        datetime.fromisoformat(cleaned)
                    except (ValueError, TypeError):
                        errors.append(
                            f"参数「{param_def.name}」的值「{value}」日期格式无效，"
                            f"期望格式: 2025-08-12T13:58:04Z"
                        )

            # --- 4. 枚举值检查 ---
            if hasattr(param_def, 'enum') and param_def.enum and len(param_def.enum) > 0:
                if value not in param_def.enum:
                    errors.append(
                        f"参数「{param_def.name}」的值「{value}」不在允许范围内，"
                        f"可选值: {param_def.enum}"
                    )

            # --- 5. 字符串长度检查 ---
            if isinstance(value, str) and len(value) > 10_000:
                errors.append(
                    f"参数「{param_def.name}」的值过长（{len(value)}字符），"
                    f"可能存在注入攻击"
                )

        if errors:
            logger.warning(
                f"[参数校验] 工具={tool.name_for_human} 不通过，"
                f"错误数={len(errors)}: {'; '.join(errors[:3])}"
            )

        return errors

    @classmethod
    def _match_rule(cls, param_name: str) -> Optional[dict]:
        """
        匹配业务规则：先精确匹配名称，再启发式匹配关键词。
        先做精确名称匹配（param_name in BUSINESS_RULES）；
        如果没命中，再用关键词包含匹配——只要参数名的小写形式中包含 KEYWORD_RULES 中的任意关键词，
        就应用对应的业务规则。比如 order_count、totalNum、item_quantity 都会被映射到 quantity 的 {min: 0, max: 999_999} 规则
        """
        if param_name in cls.BUSINESS_RULES:
            return cls.BUSINESS_RULES[param_name]

        lower_name = param_name.lower()
        for keyword, rule_name in cls.KEYWORD_RULES.items():
            if keyword.lower() in lower_name:
                return cls.BUSINESS_RULES.get(rule_name)

        return None
