"""process/llm.py 单元测试：extract_json 容错 / 配置校验 / 重试退避 / trust_env。

chat_json 的 OpenAI 调用全部 mock，不发真实请求。
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import httpx
import pytest

from pih.process.llm import (
    LLMConfigError,
    LLMError,
    chat_json,
    extract_json,
    make_client,
)


class TestExtractJson:
    """三级容错提取（迁移自 spike `_lib/test_llm.py` 口径并扩全分支）。"""

    def test_plain_json(self):
        assert extract_json('{"relevant": true}') == {"relevant": True}

    def test_fenced_json_block(self):
        content = '分析如下：\n```json\n{"主体": "三一"}\n```'
        assert extract_json(content) == {"主体": "三一"}

    def test_fenced_block_with_prose_after(self):
        content = '```json\n{"a": 1}\n```\n以上是结果。'
        assert extract_json(content) == {"a": 1}

    def test_reasoning_prefix_then_bare_json(self):
        """推理模型：思维链前缀 + 裸 JSON，且前缀含花括号干扰。"""
        content = '先想 {一下}：可能是 {候选}。\n最终答案 {"relevant": false}'
        assert extract_json(content) == {"relevant": False}

    def test_json_with_trailing_text(self):
        assert extract_json('{"a": 1} 这是补充说明') == {"a": 1}

    def test_empty_content_raises(self):
        with pytest.raises(json.JSONDecodeError):
            extract_json("")

    def test_no_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            extract_json("完全不是 JSON 的内容")


def _mk_completion(content: str, prompt_tokens: int = 10, completion_tokens: int = 5):
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    resp.usage.prompt_tokens = prompt_tokens
    resp.usage.completion_tokens = completion_tokens
    return resp


class TestMakeClient:
    def test_missing_base_url_raises_config_error(self, monkeypatch):
        monkeypatch.setenv("PIH_LLM_BASE_URL", "")
        monkeypatch.setenv("PIH_LLM_API_KEY", "sk-x")
        with pytest.raises(LLMConfigError, match="PIH_LLM_BASE_URL"):
            make_client()

    def test_missing_api_key_raises_config_error(self, monkeypatch):
        monkeypatch.setenv("PIH_LLM_BASE_URL", "https://api.example/v1")
        monkeypatch.setenv("PIH_LLM_API_KEY", "")
        with pytest.raises(LLMConfigError, match="PIH_LLM_API_KEY"):
            make_client()

    def test_client_uses_trust_env_false_httpx(self, monkeypatch):
        """代理密闭性：http_client 显式 trust_env=False（规格 §3.3-1）。

        断言 OpenAI 实际持有的 httpx.Client._trust_env——openai SDK 默认
        trust_env=True 会读 shell 的 SOCKS/HTTP 代理变量，必须显式关闭。
        """
        monkeypatch.setenv("PIH_LLM_BASE_URL", "https://api.example/v1")
        monkeypatch.setenv("PIH_LLM_API_KEY", "sk-x")
        client = make_client()
        assert isinstance(client._client, httpx.Client)
        assert client._client._trust_env is False
        client.close()


class TestChatJson:
    def _env(self, monkeypatch):
        monkeypatch.setenv("PIH_LLM_BASE_URL", "https://api.example/v1")
        monkeypatch.setenv("PIH_LLM_API_KEY", "sk-x")
        monkeypatch.setenv("PIH_LLM_LARGE_MODEL", "big-model")
        monkeypatch.setenv("PIH_LLM_SMALL_MODEL", "small-model")

    def test_success_returns_parsed_and_usage(self, monkeypatch):
        self._env(monkeypatch)
        client = MagicMock()
        client.chat.completions.create.return_value = _mk_completion('{"a": 1}', 100, 50)
        out, usage = chat_json(client, [{"role": "user", "content": "x"}], tier="large")
        assert out == {"a": 1}
        assert usage == {"prompt_tokens": 100, "completion_tokens": 50, "retries": 0}
        kwargs = client.chat.completions.create.call_args.kwargs
        assert kwargs["model"] == "big-model"
        assert kwargs["temperature"] == 0.0
        assert kwargs["response_format"] == {"type": "json_object"}

    def test_tier_routes_to_small_model(self, monkeypatch):
        self._env(monkeypatch)
        client = MagicMock()
        client.chat.completions.create.return_value = _mk_completion('{"relevant": true}')
        chat_json(client, [{"role": "user", "content": "x"}], tier="small")
        assert client.chat.completions.create.call_args.kwargs["model"] == "small-model"

    def test_missing_model_env_raises_config_error_without_retry(self, monkeypatch):
        """模型名缺失属配置错误：不重试、不吞成 LLMError，快速失败。"""
        self._env(monkeypatch)
        monkeypatch.delenv("PIH_LLM_LARGE_MODEL")
        with pytest.raises(LLMConfigError, match="PIH_LLM_LARGE_MODEL"):
            chat_json(MagicMock(), [{"role": "user", "content": "x"}], tier="large")

    def test_unparsable_output_retries_then_llm_error(self, monkeypatch):
        """JSON 解析失败视为可重试错误；耗尽抛 LLMError。"""
        self._env(monkeypatch)
        client = MagicMock()
        client.chat.completions.create.return_value = _mk_completion("不是 JSON")
        monkeypatch.setattr("pih.process.llm.time.sleep", lambda s: None)
        with pytest.raises(LLMError, match="重试耗尽"):
            chat_json(client, [{"role": "user", "content": "x"}], max_retries=2)
        assert client.chat.completions.create.call_count == 3

    def test_api_error_retries_with_backoff(self, monkeypatch):
        self._env(monkeypatch)
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            RuntimeError("429"),
            _mk_completion('{"ok": true}'),
        ]
        sleeps: list[float] = []
        monkeypatch.setattr("pih.process.llm.time.sleep", sleeps.append)
        out, usage = chat_json(client, [{"role": "user", "content": "x"}], max_retries=3)
        assert out == {"ok": True}
        assert usage["retries"] == 1
        assert sleeps == [2.0]  # 首次重试线性退避 2s

    def test_reasoning_content_extracted(self, monkeypatch):
        """推理模型思维链前缀 + fence JSON 也能解析成功。"""
        self._env(monkeypatch)
        client = MagicMock()
        client.chat.completions.create.return_value = _mk_completion(
            '思考 {过程}……\n```json\n{"主体": "徐工"}\n```'
        )
        out, _ = chat_json(client, [{"role": "user", "content": "x"}])
        assert out == {"主体": "徐工"}
