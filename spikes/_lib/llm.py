"""OpenAI 兼容 LLM 客户端（Spike 版）：温度 0、结构化 JSON、线性退避。"""
from __future__ import annotations

import json
import os
import re
import time

from openai import OpenAI

from _lib.probe import UA  # noqa: F401  —— 统一 UA 出处（部分端点日志用）


class LLMError(Exception):
    """重试耗尽或输出不可解析。"""


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.S)


def extract_json(content: str) -> dict:
    """从可能含推理文字/代码块的内容中提取首个 JSON 对象。

    MiniMax-M3 等推理模型会在 content 里先输出思维过程再给 JSON；
    有时 JSON 还被 ```json ... ``` 代码块包裹，且思维过程本身可能含
    花括号或"Extra data"。这里按以下顺序尝试：
    1. ```json ... ``` 代码块内整体解析；
    2. 整段解析（content 本身就是纯 JSON）；
    3. 从首个 '{' 开始用 raw_decode 增量解析，容忍尾随多余文本。
    全部失败则抛 JSONDecodeError（由调用方视作可重试）。
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
    # 从每个 '{' 尝试 raw_decode，取首个能成功解析出对象的起点
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


def load_env() -> None:
    """加载 spikes/.env（存在时）；不覆盖已设环境变量。"""
    from pathlib import Path
    from dotenv import load_dotenv

    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


def chat_json(
    messages: list[dict],
    model_env: str = "PIH_LLM_LARGE_MODEL",
    max_retries: int = 3,
) -> tuple[dict, dict]:
    """调用 OpenAI 兼容 chat completions，要求 JSON 输出并解析。

    返回 (解析后的 dict, usage{"prompt_tokens","completion_tokens","retries"})。
    429/5xx/JSON 解析失败 → 线性退避重试；耗尽抛 LLMError。
    """
    load_env()
    base = os.environ.get("PIH_LLM_BASE_URL")
    key = os.environ.get("PIH_LLM_API_KEY")
    model = os.environ.get(model_env)
    if not (base and key and model):
        raise LLMError(
            f"缺少环境变量（需要 PIH_LLM_BASE_URL/PIH_LLM_API_KEY/{model_env}）。"
            "请复制 spikes/.env.example 为 spikes/.env 并填写。"
        )
    client = OpenAI(base_url=base, api_key=key)
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
            # MiniMax-M3 等推理模型 content 可能含思维过程 + JSON，
            # 用 extract_json 容错提取；提取失败视为可重试错误。
            return extract_json(content), usage
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            usage["retries"] = attempt + 1
            if attempt < max_retries:
                time.sleep(2 * (attempt + 1))
    raise LLMError(f"重试耗尽：{last_err}") from last_err
