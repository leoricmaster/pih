"""LangGraph 抽取图：粗筛 → 抽取 → 校验（SPK-3 graph.py 工程化，Sprint 4 规格 §3.4）。

图结构不变（SPK-3 已验证），工程化修正三条 spike 遗留契约：
1. 重试计数分列——api_retries（chat_json 内部 API 级重试累计）与
   validate_rounds（schema 补问轮次）分开记录，不再混计；
2. text 在场——初始 state 由 Runner 构造（intel_id + text 必填），
   节点只增改字段不删除；
3. 领域注入——EVENTS/TAGS 等枚举不再硬编码，全部来自领域包
   （event_types / tag_tree / competitors / meta.display_name）。

节点行为：
- prefilter：小模型二分类；API 失败按保留处理（灰条目走抽取，架构 §8 不丢弃）；
  判定不相关 → kept=False（Runner 落 filtered_out）。
- extract：大模型 + 领域包提示词（render_prompt 占位符注入）。
- validate：validate_pred 校验（7 键 + 枚举 + 标签树 + 可信度），
  不合格自动补问 ≤3 轮；仍失败 extraction=None（Runner 落 needs_manual）。
"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypedDict, cast

from langgraph.graph import END, START, StateGraph

from pih.process.extraction import (
    ALL_KEYS,
    IntelExtraction,
    PackVocab,
    ValidationFailure,
    validate_pred,
)
from pih.process.llm import LLMError, Tier, chat_json, make_client

# chat 函数签名：(messages, tier) → (解析 dict, usage)。
# 默认实现包住 OpenAI client；单测注入 fake。
ChatFn = Callable[[list[dict], str], tuple[dict, dict]]

MAX_VALIDATE_ROUNDS = 3

PREFILTER_TEXT_CHARS = 3000


class ItemState(TypedDict, total=False):
    """单条情报的图状态。初始必填 intel_id + text（Runner 构造契约）。"""

    intel_id: int
    text: str
    kept: bool
    pred: dict | None
    extraction: IntelExtraction | None
    api_retries: int
    validate_rounds: int
    prompt_tokens: int
    completion_tokens: int
    node_timings_ms: dict
    error: str | None  # 节点级异常记录（灰条目等，不中断流水线）
    failure: str | None  # 终局校验失败原因（needs_manual 时由 Runner 落库）


def render_prompt(pack: dict) -> str:
    """领域包 extraction_prompt 占位符注入（D5）。

    <事件类型>←event_types；<标签树>←tag_tree 叶子；<主体清单>←competitors
    （规范名 + 别名）。token 缺失在领域包加载时已被校验器拒绝。
    """
    event_types = "/".join(pack["event_types"])
    tags = "/".join(leaf for leaves in pack["tag_tree"].values() for leaf in leaves)
    competitors = "；".join(
        c["display_name"] + ("（别名：" + "、".join(c.get("aliases", [])) + "）"
                             if c.get("aliases") else "")
        for c in pack["competitors"]
    )
    return (
        pack["extraction_prompt"]
        .replace("<事件类型>", event_types)
        .replace("<标签树>", tags)
        .replace("<主体清单>", competitors)
    )


def make_default_chat() -> ChatFn:
    """默认 chat：真实 OpenAI 兼容客户端（配置缺失在此抛 LLMConfigError，快速失败）。"""
    client = make_client()

    def chat(messages: list[dict], tier: str) -> tuple[dict, dict]:
        return chat_json(client, messages, cast(Tier, tier))

    return chat


def build_graph(pack: dict, chat: ChatFn | None = None):
    """构建三节点图。chat 可注入（单测 fake）；默认真实客户端。"""
    if chat is None:
        chat = make_default_chat()
    system_prompt = render_prompt(pack)
    vocab = PackVocab.from_pack(pack)
    domain = pack["meta"]["display_name"]

    def _now() -> float:
        return time.monotonic()

    def node_prefilter(state: ItemState) -> ItemState:
        """粗筛：小模型二分类。API 失败按保留处理（灰条目走抽取）。"""
        t0 = _now()
        msgs = [
            {
                "role": "system",
                "content": (
                    f"判断正文是否与{domain}行业情报相关"
                    "（产品/技术/市场/组织动态，含上游原材料与金融市场"
                    "对该行业的间接影响）。"
                    '仅输出 JSON：{"relevant": true} 或 {"relevant": false}'
                ),
            },
            {"role": "user", "content": state["text"][:PREFILTER_TEXT_CHARS]},
        ]
        timings = dict(state.get("node_timings_ms", {}))
        try:
            out, usage = chat(msgs, "small")
        except LLMError as exc:
            timings["prefilter"] = int((_now() - t0) * 1000)
            return {
                "kept": True,
                "error": f"prefilter:{type(exc).__name__}",
                "node_timings_ms": timings,
            }
        timings["prefilter"] = int((_now() - t0) * 1000)
        return {
            "kept": bool(out.get("relevant")),
            "prompt_tokens": state.get("prompt_tokens", 0) + usage["prompt_tokens"],
            "completion_tokens": state.get("completion_tokens", 0)
            + usage["completion_tokens"],
            "api_retries": state.get("api_retries", 0) + usage["retries"],
            "node_timings_ms": timings,
        }

    def node_extract(state: ItemState) -> ItemState:
        """结构化抽取：大模型 + 领域包提示词。失败留 pred=None 交 validate 补问。"""
        t0 = _now()
        msgs = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": state["text"]},
        ]
        timings = dict(state.get("node_timings_ms", {}))
        try:
            pred, usage = chat(msgs, "large")
        except LLMError as exc:
            timings["extract"] = int((_now() - t0) * 1000)
            return {
                "pred": None,
                "error": f"extract:{type(exc).__name__}",
                "node_timings_ms": timings,
            }
        timings["extract"] = int((_now() - t0) * 1000)
        return {
            "pred": pred,
            "api_retries": state.get("api_retries", 0) + usage["retries"],
            "prompt_tokens": state.get("prompt_tokens", 0) + usage["prompt_tokens"],
            "completion_tokens": state.get("completion_tokens", 0)
            + usage["completion_tokens"],
            "node_timings_ms": timings,
        }

    def node_validate(state: ItemState) -> ItemState:
        """schema 校验 + 补问 ≤3；仍失败 extraction=None（降级待人工不丢弃）。"""
        t0 = _now()
        pred = state.get("pred")
        api_retries = state.get("api_retries", 0)
        prompt_tokens = state.get("prompt_tokens", 0)
        completion_tokens = state.get("completion_tokens", 0)
        timings = dict(state.get("node_timings_ms", {}))

        result = (
            validate_pred(pred, vocab)
            if pred is not None
            else ValidationFailure(missing_keys=list(ALL_KEYS))
        )
        rounds = 0
        failure_msg: str | None = None
        while isinstance(result, ValidationFailure) and rounds < MAX_VALIDATE_ROUNDS:
            rounds += 1
            msgs = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": state["text"]},
                {
                    "role": "user",
                    "content": (
                        f"上一次输出未通过 schema 校验（{result.message()}），"
                        "严格按 schema 重出 JSON，必须包含键：" + "、".join(ALL_KEYS)
                    ),
                },
            ]
            try:
                pred, usage = chat(msgs, "large")
                api_retries += usage["retries"]
                prompt_tokens += usage["prompt_tokens"]
                completion_tokens += usage["completion_tokens"]
            except LLMError as exc:
                failure_msg = f"validate:{type(exc).__name__}"
                pred = None
                break
            result = (
                validate_pred(pred, vocab)
                if pred is not None
                else ValidationFailure(missing_keys=list(ALL_KEYS))
            )

        timings["validate"] = int((_now() - t0) * 1000)
        if isinstance(result, IntelExtraction):
            return {
                "extraction": result,
                "validate_rounds": rounds,
                "api_retries": api_retries,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "node_timings_ms": timings,
                "failure": None,
            }
        return {
            "extraction": None,
            "validate_rounds": rounds,
            "api_retries": api_retries,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "node_timings_ms": timings,
            "failure": failure_msg or result.message(),
        }

    def _route_after_prefilter(state: ItemState) -> str:
        return "extract" if state.get("kept") else END

    g = StateGraph(ItemState)
    g.add_node("prefilter", node_prefilter)
    g.add_node("extract", node_extract)
    g.add_node("validate", node_validate)
    g.add_edge(START, "prefilter")
    g.add_conditional_edges("prefilter", _route_after_prefilter)
    g.add_edge("extract", "validate")
    g.add_edge("validate", END)
    return g.compile()
