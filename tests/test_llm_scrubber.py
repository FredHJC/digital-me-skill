"""
_llm_scrub() 函数测试 — 使用 mock 验证 Anthropic API 调用行为。

测试说明：
- 所有 Anthropic API 调用均使用 mock，不进行真实网络请求
- ANTHROPIC_API_KEY 在测试环境中默认不设置
"""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from tools.pii_scrubber import _llm_scrub, scrub


class TestLLMScrubWithMock:
    """测试 _llm_scrub() 正常工作路径（mock Anthropic 客户端）。"""

    def test_returns_scrubbed_text_and_abstractions(self, monkeypatch):
        """_llm_scrub() 应返回 (scrubbed_text, abstractions_dict)。"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "scrubbed": "昨天和[RELATIONSHIP_CONFLICT: 家庭财务争吵]",
            "abstractions": {"[RELATIONSHIP_CONFLICT]": 1},
        })

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch("tools.pii_scrubber._anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = mock_client
            scrubbed, abstractions = _llm_scrub("昨天和老婆吵了一架，因为花钱的事情")

        assert "[RELATIONSHIP_CONFLICT" in scrubbed
        assert abstractions.get("[RELATIONSHIP_CONFLICT]") == 1

    def test_returns_tuple_structure(self, monkeypatch):
        """_llm_scrub() 必须返回 (str, dict) 元组。"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "scrubbed": "some text",
            "abstractions": {},
        })

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch("tools.pii_scrubber._anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = mock_client
            result = _llm_scrub("some personal story")

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], dict)

    def test_uses_model_env_var(self, monkeypatch):
        """_llm_scrub() 应读取 DIGITAL_ME_SCRUB_MODEL 环境变量指定模型。"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("DIGITAL_ME_SCRUB_MODEL", "claude-opus-4-5")

        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "scrubbed": "text",
            "abstractions": {},
        })

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch("tools.pii_scrubber._anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = mock_client
            _llm_scrub("text")
            call_kwargs = mock_client.messages.create.call_args
            assert call_kwargs.kwargs.get("model") == "claude-opus-4-5" or \
                   (call_kwargs.args and call_kwargs.args[0] == "claude-opus-4-5") or \
                   call_kwargs.kwargs.get("model") == "claude-opus-4-5"

    def test_multiple_abstractions_returned(self, monkeypatch):
        """_llm_scrub() 应正确解析多个抽象标签。"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "scrubbed": "[HEALTH_SITUATION: 家人生病] and [FINANCIAL_SITUATION: 财务问题]",
            "abstractions": {"[HEALTH_SITUATION]": 1, "[FINANCIAL_SITUATION]": 1},
        })

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch("tools.pii_scrubber._anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = mock_client
            scrubbed, abstractions = _llm_scrub("我妈最近血压高，家里财务也紧张")

        assert abstractions.get("[HEALTH_SITUATION]") == 1
        assert abstractions.get("[FINANCIAL_SITUATION]") == 1


class TestLLMScrubGracefulDegradation:
    """测试 _llm_scrub() 在缺失条件下的优雅降级行为。"""

    def test_no_api_key_returns_unchanged(self, monkeypatch, capsys):
        """未设置 ANTHROPIC_API_KEY 时，应返回原文并打印警告。"""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with patch("tools.pii_scrubber._anthropic") as mock_anthropic:
            mock_anthropic.__class__ = type  # ensure it's "truthy" as a module
            mock_anthropic.return_value = MagicMock()  # has the attribute
            # But we still pass the module check; the key check should catch it
            result, stats = _llm_scrub("张三在北京海淀区中关村")

        assert result == "张三在北京海淀区中关村"
        assert stats == {}
        captured = capsys.readouterr()
        assert "ANTHROPIC_API_KEY" in captured.err

    def test_no_anthropic_package_returns_unchanged(self, monkeypatch, capsys):
        """anthropic 包未安装时，应返回原文并打印警告。"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("tools.pii_scrubber._anthropic", None):
            result, stats = _llm_scrub("some text")

        assert result == "some text"
        assert stats == {}
        captured = capsys.readouterr()
        assert "anthropic" in captured.err.lower()

    def test_api_error_returns_unchanged(self, monkeypatch, capsys):
        """API 调用失败时，应返回原文并打印警告（非致命错误）。"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API connection failed")

        with patch("tools.pii_scrubber._anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = mock_client
            result, stats = _llm_scrub("some text with personal info")

        assert result == "some text with personal info"
        assert stats == {}

    def test_json_decode_error_returns_unchanged(self, monkeypatch, capsys):
        """LLM 返回非 JSON 响应时，应返回原文并打印警告。"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = "Sorry, I cannot process this request."

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch("tools.pii_scrubber._anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = mock_client
            result, stats = _llm_scrub("some text")

        assert result == "some text"
        assert stats == {}


class TestLLMScrubPlaceholderPreservation:
    """测试 _llm_scrub() 保留正则脱敏阶段产生的占位符。"""

    def test_preserves_phone_placeholder(self, monkeypatch):
        """[PHONE] 占位符不应被 LLM 修改。"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        input_text = "联系方式是 [PHONE]，有问题可以打电话"
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "scrubbed": input_text,  # LLM preserves placeholder
            "abstractions": {},
        })

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch("tools.pii_scrubber._anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = mock_client
            result, _ = _llm_scrub(input_text)

        assert "[PHONE]" in result

    def test_preserves_email_placeholder(self, monkeypatch):
        """[EMAIL] 占位符不应被 LLM 修改。"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        input_text = "发邮件到 [EMAIL] 联系我"
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "scrubbed": input_text,
            "abstractions": {},
        })

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch("tools.pii_scrubber._anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = mock_client
            result, _ = _llm_scrub(input_text)

        assert "[EMAIL]" in result


class TestLLMScrubMarkdownStrip:
    """测试 _llm_scrub() 正确处理 LLM 返回的 markdown 代码围栏。"""

    def test_strips_json_code_fence(self, monkeypatch):
        """```json\\n{...}\\n``` 格式的响应应被正确解析。"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        payload = json.dumps({
            "scrubbed": "scrubbed text",
            "abstractions": {"[PERSONAL_NARRATIVE]": 1},
        })
        # LLM wraps in markdown fence
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = f"```json\n{payload}\n```"

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch("tools.pii_scrubber._anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = mock_client
            result, abstractions = _llm_scrub("some personal text")

        assert result == "scrubbed text"
        assert abstractions.get("[PERSONAL_NARRATIVE]") == 1

    def test_strips_plain_code_fence(self, monkeypatch):
        """``` 格式（无语言标注）的响应应被正确解析。"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        payload = json.dumps({
            "scrubbed": "clean text",
            "abstractions": {},
        })
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = f"```\n{payload}\n```"

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch("tools.pii_scrubber._anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = mock_client
            result, _ = _llm_scrub("some text")

        assert result == "clean text"
