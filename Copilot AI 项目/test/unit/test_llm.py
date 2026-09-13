"""测试 LLM 模型包装器"""

import pytest
from unittest.mock import MagicMock, patch


class TestLargeLanguageModel:
    """LLM 包装器"""

    def test_init_creates_openai_client(self):
        with patch("models.llm.OpenAI") as mock_openai:
            from models.llm import LargeLanguageModel
            llm = LargeLanguageModel("http://test.api", "test-key")
            mock_openai.assert_called_once()
            assert llm.retries == 3

    def test_chat_completions_returns_content(self):
        with patch("models.llm.OpenAI") as mock_openai:
            mock_client = mock_openai.return_value
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "test response"
            mock_client.chat.completions.create.return_value = mock_response

            from models.llm import LargeLanguageModel
            llm = LargeLanguageModel("http://test.api", "test-key")
            result = llm.chat_completions("test prompt", "test-model", 0.01, 0.01)
            assert result == "test response"

    def test_chat_completions_retry_on_failure(self):
        with patch("models.llm.OpenAI") as mock_openai:
            mock_client = mock_openai.return_value
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "retry response"

            # 第一次调用失败，第二次成功
            mock_client.chat.completions.create.side_effect = [
                Exception("API error"),
                mock_response,
            ]

            with patch("models.llm.random.randint", return_value=1):
                from models.llm import LargeLanguageModel
                llm = LargeLanguageModel("http://test.api", "test-key")
                result = llm.chat_completions("test prompt", "test-model", 0.01, 0.01)
                assert result == "retry response"
                assert mock_client.chat.completions.create.call_count == 2

    def test_chat_completions_max_retries_exhausted(self):
        with patch("models.llm.OpenAI") as mock_openai:
            mock_client = mock_openai.return_value
            mock_client.chat.completions.create.side_effect = Exception("API error")

            with patch("models.llm.random.randint", return_value=1):
                from models.llm import LargeLanguageModel
                llm = LargeLanguageModel("http://test.api", "test-key")
                with pytest.raises(Exception, match="API error"):
                    llm.chat_completions("test prompt", "test-model", 0.01, 0.01)
                assert mock_client.chat.completions.create.call_count == 3

    def test_chat_completions_system_prompt(self):
        with patch("models.llm.OpenAI") as mock_openai:
            mock_client = mock_openai.return_value
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "response"
            mock_client.chat.completions.create.return_value = mock_response

            from models.llm import LargeLanguageModel
            llm = LargeLanguageModel("http://test.api", "test-key")
            llm.chat_completions("test", "model", 0.01, 0.01)

            call_args = mock_client.chat.completions.create.call_args
            messages = call_args[1]["messages"]
            assert len(messages) >= 2
            assert messages[0]["role"] == "system"
            assert messages[1]["role"] == "user"

    def test_backoff_range(self):
        with patch("models.llm.OpenAI"):
            from models.llm import LargeLanguageModel
            llm = LargeLanguageModel("http://test.api", "test-key")
            with patch("models.llm.random.randint", return_value=5) as mock_randint:
                with patch("models.llm.time.sleep") as mock_sleep:
                    llm.backoff()
                    mock_randint.assert_called_once_with(1, 20)
                    mock_sleep.assert_called_once_with(5)

    def test_context_chat_completions(self):
        with patch("models.llm.OpenAI") as mock_openai:
            mock_client = mock_openai.return_value
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "context response"
            mock_client.chat.completions.create.return_value = mock_response

            from models.llm import LargeLanguageModel
            llm = LargeLanguageModel("http://test.api", "test-key")
            contexts = [{"role": "user", "content": "hello"}]
            result = llm.context_chat_completions(contexts, "model", 0.01, 0.01, context_number=5)
            assert result == "context response"

    def test_context_chat_completions_retry(self):
        with patch("models.llm.OpenAI") as mock_openai:
            mock_client = mock_openai.return_value
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "retry context response"

            mock_client.chat.completions.create.side_effect = [
                Exception("error"),
                mock_response,
            ]

            with patch("models.llm.random.randint", return_value=1):
                from models.llm import LargeLanguageModel
                llm = LargeLanguageModel("http://test.api", "test-key")
                contexts = [{"role": "user", "content": "hello"}]
                result = llm.context_chat_completions(contexts, "model", 0.01, 0.01, context_number=5)
                assert result == "retry context response"
                assert mock_client.chat.completions.create.call_count == 2
