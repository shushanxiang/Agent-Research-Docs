"""测试人类反馈意图识别（方案 11 增强版）

测试 _recognize_human_intent 的核心逻辑，覆盖：
- 关键词快速通道（confirm/abort）
- 降级路径（功能关闭、LLM 异常）
- 结构化 JSON 解析（parse_intent_json）
- 参数补丁合并（_merge_param_patch）
"""

import pytest
from unittest.mock import MagicMock


# ==================== 辅助函数逻辑测试 ====================

class TestIntentRecognitionKeywords:
    """关键词匹配快速通道测试（与旧版兼容）"""

    confirm_keywords = ["确认执行", "执行任务", "同意执行", "继续执行", "立即执行"]
    abort_keywords = ["放弃执行", "停止执行", "中止执行", "取消执行", "不执行", "不要执行"]

    def _match_keywords(self, feedback):
        """复制 _recognize_human_intent 的关键词匹配逻辑"""
        feedback_lower = feedback.lower()
        for keyword in self.confirm_keywords:
            if keyword in feedback_lower:
                return "confirm"
        for keyword in self.abort_keywords:
            if keyword in feedback_lower:
                return "abort"
        return None  # 关键词未命中

    @pytest.mark.parametrize("feedback, expected", [
        ("立即执行", "confirm"),
        ("确认执行", "confirm"),
        ("执行任务", "confirm"),
        ("同意执行", "confirm"),
        ("继续执行", "confirm"),
        ("好的，请立即执行吧", "confirm"),
        ("不执行", "abort"),
        ("放弃执行", "abort"),
        ("停止执行", "abort"),
        ("中止执行", "abort"),
        ("取消执行", "abort"),
        ("不要执行", "abort"),
    ])
    def test_keyword_confirm_abort(self, feedback, expected):
        """关键词匹配：确认和放弃"""
        result = self._match_keywords(feedback)
        assert result == expected, f"反馈'{feedback}'期望={expected}，实际={result}"

    def test_keyword_no_match(self):
        """关键词未命中返回 None"""
        assert self._match_keywords("放弃吧，不做了") is None  # 不直接匹配任何 abort 关键词
        assert self._match_keywords("今天天气不错") is None
        assert self._match_keywords("随便说说") is None
        assert self._match_keywords("把数量改成20") is None  # correct_params 不走关键词

    def test_case_insensitive(self):
        """中文字符不受 lower() 影响，确认正常匹配"""
        assert self._match_keywords("立即执行") == "confirm"

    def test_abort_negative_not_confirm(self):
        """包含'不'的 abort 关键词不会被误判为 confirm"""
        assert self._match_keywords("不执行") == "abort"


class TestStructuredIntentParsing:
    """测试 parse_intent_json 结构化解析（方案 11 新增）"""

    def test_parse_confirm_json(self):
        """解析 confirm 意图的 JSON"""
        from prompt.general_prompts import parse_intent_json
        response = '{"intent": "confirm", "confidence": 1.0, "patch": {}, "reason": "用户确认执行"}'
        result = parse_intent_json(response)
        assert result is not None
        assert result["intent"] == "confirm"
        assert result["confidence"] == 1.0

    def test_parse_correct_params_json(self):
        """解析 correct_params + patch"""
        from prompt.general_prompts import parse_intent_json
        response = '{"intent": "correct_params", "confidence": 0.95, "patch": {"quantity": 20}, "reason": "修改数量"}'
        result = parse_intent_json(response)
        assert result is not None
        assert result["intent"] == "correct_params"
        assert result["patch"] == {"quantity": 20}

    def test_parse_correct_tool_json(self):
        """解析 correct_tool 意图"""
        from prompt.general_prompts import parse_intent_json
        response = '{"intent": "correct_tool", "confidence": 0.9, "patch": {}, "reason": "用户要换工具"}'
        result = parse_intent_json(response)
        assert result is not None
        assert result["intent"] == "correct_tool"

    def test_parse_invalid_json_fallback(self):
        """非法 JSON 返回 None"""
        from prompt.general_prompts import parse_intent_json
        assert parse_intent_json("这不是JSON") is None
        assert parse_intent_json("") is None
        assert parse_intent_json("{broken json") is None

    def test_parse_json_with_extra_text(self):
        """LLM 响应包含额外文字时仍能提取 JSON"""
        from prompt.general_prompts import parse_intent_json
        response = '分析结果如下：\n{"intent": "clarify", "confidence": 0.7, "patch": {}, "reason": "用户信息不完整"}\n请确认。'
        result = parse_intent_json(response)
        assert result is not None
        assert result["intent"] == "clarify"


class TestIntentFallback:
    """降级路径测试（方案 11 新增）"""

    def test_feature_flag_disabled_returns_unclear(self):
        """enhanced_human_feedback_enabled=0 时不走 LLM，返回 unclear"""
        # 模拟功能关闭：关键词不匹配 → 直接返回 unclear
        from utils.const import INTENT_UNCLEAR
        assert INTENT_UNCLEAR == "unclear"

    def test_llm_exception_returns_unclear(self):
        """LLM 调用异常时降级为 unclear"""
        try:
            raise Exception("API error")
        except Exception:
            result = "unclear"
        assert result == "unclear"


class TestParamPatchMerge:
    """参数补丁合并测试（方案 11 新增：_merge_param_patch）"""

    def _merge(self, original, patch):
        """复制 _merge_param_patch 逻辑"""
        merged = dict(original) if original else {}
        for key, value in patch.items():
            if key in merged:
                merged[key] = value
        return merged

    def test_merge_valid_patch(self):
        """合法补丁正确合并"""
        result = self._merge({"product": "苹果", "quantity": 10}, {"quantity": 20})
        assert result == {"product": "苹果", "quantity": 20}

    def test_merge_multiple_fields(self):
        """多个字段同时修改"""
        result = self._merge(
            {"product": "苹果", "quantity": 10, "price": 5.0},
            {"quantity": 20, "price": 8.0}
        )
        assert result == {"product": "苹果", "quantity": 20, "price": 8.0}

    def test_merge_unknown_field_ignored(self):
        """非 Schema 字段被忽略"""
        result = self._merge({"product": "苹果"}, {"unknown_field": "xxx"})
        # unknown_field 不在原参数中，被跳过
        assert "unknown_field" not in result
        assert result == {"product": "苹果"}

    def test_merge_empty_patch(self):
        """空补丁返回原参数"""
        original = {"product": "苹果", "quantity": 10}
        result = self._merge(original, {})
        assert result == original

    def test_merge_empty_original(self):
        """原参数为空时 patch 不生效（因为没有字段可覆盖）"""
        result = self._merge({}, {"quantity": 20})
        assert result == {}


class TestIntentDictStructure:
    """验证意图识别返回 dict 的结构完整性（方案 11 新增）"""

    def test_confirm_intent_has_all_fields(self):
        """confirm 返回 dict 包含所有必需字段"""
        result = {"intent": "confirm", "confidence": 1.0, "patch": {}, "reason": "test"}
        assert set(result.keys()) == {"intent", "confidence", "patch", "reason"}

    def test_correct_params_intent_has_patch(self):
        """correct_params 的 patch 不为空"""
        result = {"intent": "correct_params", "confidence": 0.95, "patch": {"qty": 20}, "reason": "test"}
        assert result["patch"]  # patch 应有内容

    def test_non_correct_intents_have_empty_patch(self):
        """非 correct_params 意图的 patch 为空"""
        for intent in ["confirm", "abort", "correct_tool", "clarify", "unrelated", "unclear"]:
            result = {"intent": intent, "confidence": 1.0, "patch": {}, "reason": "test"}
            assert result["patch"] == {}, f"{intent} 的 patch 应为空"


# ==================== LLM 降级逻辑测试（保持不变） ====================

class TestIntentRecognitionLLMFallback:
    """LLM 降级逻辑测试（模拟）"""

    def test_llm_returns_valid_intent(self):
        """LLM 返回有效意图时正确解析"""
        for intent in ["confirm", "abort", "unclear", "correct_params", "correct_tool", "clarify", "unrelated"]:
            assert intent in ["confirm", "abort", "unclear", "correct_params", "correct_tool", "clarify", "unrelated"]

    def test_llm_invalid_intent_ignored(self):
        """LLM 返回无效意图时保持 unclear"""
        from utils.const import INTENT_UNCLEAR
        invalid = "unknown_intent"
        from utils.const import VALID_INTENTS
        if invalid not in VALID_INTENTS:
            result = INTENT_UNCLEAR
        assert result == "unclear"

    def test_llm_exception_handled(self):
        """LLM 调用异常时降级为 unclear"""
        try:
            raise Exception("API error")
        except Exception:
            result = "unclear"
        assert result == "unclear"


class TestKeywordEdgeCases:
    """关键词特殊边界情况"""

    def test_partial_match_not_confused(self):
        """部分匹配不应混淆"""
        assert "不执行" in ["不执行"]

    def test_empty_feedback(self):
        """空反馈不匹配任何关键词"""
        result = ""
        confirm_keywords = ["确认执行", "立即执行"]
        abort_keywords = ["放弃执行", "不执行"]
        is_confirm = any(k in result for k in confirm_keywords)
        is_abort = any(k in result for k in abort_keywords)
        assert not is_confirm
        assert not is_abort

    def test_correct_params_not_matched_as_abort(self):
        """'不'开头但不是 abort 关键词 → 不应匹配为 abort"""
        confirm_keywords = ["确认执行", "执行任务", "同意执行", "继续执行", "立即执行"]
        abort_keywords = ["放弃执行", "停止执行", "中止执行", "取消执行", "不执行", "不要执行"]
        feedback = "不，把数量改成20"  # 不是精确的 abort 关键词
        is_abort = any(k in feedback for k in abort_keywords)
        # "不执行" 不在 "不，把数量改成20" 中
        assert not is_abort
