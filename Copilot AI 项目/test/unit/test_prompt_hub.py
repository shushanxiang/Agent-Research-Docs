"""测试 prompt_hub.py — create_prompt_hub 工厂函数"""

import pytest
from unittest.mock import patch, MagicMock


class TestCreatePromptHub:
    """Prompt Hub 工厂函数"""

    def test_qwen_model_returns_qwen_hub(self):
        from prompt.prompt_hub import create_prompt_hub
        hub = create_prompt_hub("qwen-max-0919")
        from prompt.qwen_model_prompts import QwenModelPromptHub
        assert isinstance(hub, QwenModelPromptHub)

    def test_qwen_model_case_insensitive(self):
        from prompt.prompt_hub import create_prompt_hub
        hub = create_prompt_hub("QWEN-TURBO")
        from prompt.qwen_model_prompts import QwenModelPromptHub
        assert isinstance(hub, QwenModelPromptHub)

    def test_non_qwen_returns_general_hub(self):
        from prompt.prompt_hub import create_prompt_hub
        hub = create_prompt_hub("deepseek-v3")
        from prompt.general_prompts import PromptModelHub
        assert isinstance(hub, PromptModelHub)
        assert type(hub) is PromptModelHub  # 不是 Qwen 子类

    def test_deepseek_model_returns_general_hub(self):
        from prompt.prompt_hub import create_prompt_hub
        hub = create_prompt_hub("gpt-4")
        from prompt.general_prompts import PromptModelHub
        assert isinstance(hub, PromptModelHub)
