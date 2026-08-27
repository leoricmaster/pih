"""OpenAI 兼容 LLM 客户端（process 层，SPK-2/3 spike `_lib/llm.py` 工程化）。

与 spike 版的三处工程化差异（Sprint 4 规格 §3.3）：
1. http_client 显式 trust_env=False——openai SDK 默认继承环境代理变量，
   shell 常驻 SOCKS 代理会劫持 LLM 流量（与 collect 层 HttpClient 同口径）；
2. 配置缺失抛 LLMConfigError（调用方快速失败），区别于运行时 LLMError；
3. tier 路由（large/small）替代逐调用点传 model_env——模型路由集中管理，
   换模型/换端点不改代码（架构 §9.2）。

环境变量：PIH_LLM_BASE_URL / PIH_LLM_API_KEY /
          PIH_LLM_LARGE_MODEL（抽取/核实用）/ PIH_LLM_SMALL_MODEL（粗筛用）
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Literal

import httpx
from openai import OpenAI

Tier = Literal["large", "small"]

TIER_MODEL_ENV: dict[Tier, str] = {
    "large": "PIH_LLM_LARGE_MODEL",
    "small": "PIH_LLM_SMALL_MODEL",
}


class LLMError(Exception):
    """运行时失败：重试耗尽或输出不可解析。"""


class LLMConfigError(Exception):
    """配置缺失：环境变量未配置。调用方应快速失败并附指引。"""


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.S)


def extract_json(content: str) -> dict:
    """从可能含推理文字/代码块的内容中提取首个 JSON 对象。

    推理模型（如 MiniMax-M3）会在 content 里先输出思维过程再给 JSON，
    有时被 ```json ... ``` 包裹且思维过程本身可能含花括号。按序尝试：
    1. ```json ... ``` 代码块内整体解析；
    2. 整段解析（content 本身就是纯 JSON）；
    3. 从首个 '{' 起用 raw_decode 增量解析，容忍尾随多余文本。
    全部失败抛 JSONDecodeError（调用方视作可重试）。
    """
    if not content:
        raise json.JSONDecodeError("empty content", content or "", 0)
    text = content.strip()
    fenced = _JSON_FENCE_RE.search(text)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    dec = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch == "{":
            try:
                obj, _end = dec.raw_decode(text[i:])
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                continue
    raise json.JSONDecodeError("no JSON object found", content, 0)


def _resolve_model(tier: Tier) -> str:
    """tier → 模型名；缺配置抛 LLMConfigError。"""
    env = TIER_MODEL_ENV[tier]
    model = os.environ.get(env, "").strip()
    if not model:
        raise LLMConfigError(
            f"缺少环境变量 {env}（tier={tier}）。"
            "请在 .env 配置 PIH_LLM_BASE_URL / PIH_LLM_API_KEY / "
            "PIH_LLM_LARGE_MODEL / PIH_LLM_SMALL_MODEL。"
        )
    return model


def _check_base_config() -> tuple[str, str]:
    base = os.environ.get("PIH_LLM_BASE_URL", "").strip()
    key = os.environ.get("PIH_LLM_API_KEY", "").strip()
    missing = [n for n, v in (("PIH_LLM_BASE_URL", base), ("PIH_LLM_API_KEY", key)) if not v]
    if missing:
        raise LLMConfigError(
            f"缺少环境变量：{', '.join(missing)}。"
            "请在 .env 配置 PIH_LLM_BASE_URL / PIH_LLM_API_KEY / "
            "PIH_LLM_LARGE_MODEL / PIH_LLM_SMALL_MODEL。"
        )
    return base, key


def make_client() -> OpenAI:
    """构造 OpenAI 客户端；配置缺失抛 LLMConfigError。

    trust_env=False：不读环境代理变量（HTTP_PROXY/ALL_PROXY 等），
    保证测试与运行密闭性——需要代理的网络环境由用户在 .env 显式配置。
    """
    base, key = _check_base_config()
    return OpenAI(
        base_url=base,
        api_key=key,
        http_client=httpx.Client(trust_env=False, timeout=120.0),
    )


def chat_json(
    client: OpenAI,
    messages: list[dict],
    tier: Tier = "large",
    max_retries: int = 3,
) -> tuple[dict, dict]:
    """调用 chat completions 要求 JSON 输出并解析。

    Args:
        client: make_client() 产物（调用方持有，便于复用连接与 mock 注入）。
        tier: 模型档位——large（抽取/核实）或 small（粗筛）。
        max_retries: 429/5xx/解析失败的重试次数（线性退避 2s/4s/6s）。

    Returns:
        (解析后的 dict, usage)——usage 含
        prompt_tokens / completion_tokens（累计）/ retries（API 级重试次数）。

    Raises:
        LLMConfigError: 模型名未配置（不重试，调用方快速失败）。
        LLMError: 重试耗尽或输出不可解析。
    """
    model = _resolve_model(tier)
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "retries": 0}
    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content or ""
            usage["prompt_tokens"] += resp.usage.prompt_tokens if resp.usage else 0
            usage["completion_tokens"] += resp.usage.completion_tokens if resp.usage else 0
            # 推理模型 content 可能含思维过程 + JSON，extract_json 容错提取；
            # 提取失败视为可重试错误。
            return extract_json(content), usage
        except LLMConfigError:
            raise
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            usage["retries"] = attempt + 1
            if attempt < max_retries:
                time.sleep(2 * (attempt + 1))
    raise LLMError(f"重试耗尽：{last_err}") from last_err
