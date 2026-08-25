"""SPK-3：粗筛 → 抽取 → 校验 三节点 LangGraph 图。

节点为独立函数、显式状态传递（TypedDict），验证架构 §4 模块切分。

API 说明：langgraph 1.2.11 下仍保留 0.x 的 `set_conditional_entry_point`
（deprecated alias），但 1.x 惯用法是 `add_edge(START, entry)` +
`add_conditional_edges(entry, router)`。此处采用 1.x 惯用法。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

HERE = Path(__file__).resolve().parent
# spikes/ 在路径上以导入 _lib.llm；golden/ 在路径上以导入 make_dataset.EVENTS
SPIKES = HERE.parents[0]
sys.path.insert(0, str(SPIKES))
sys.path.insert(0, str(SPIKES / "spk2-extraction-probe" / "golden"))

from _lib.llm import LLMError, chat_json  # noqa: E402
from make_dataset import EVENTS  # noqa: E402  —— 11 类枚举，单一出处（golden/make_dataset.py）

# SCHEMA_KEYS 与 SPK-2 保持一致（run_extraction.py）
SCHEMA_KEYS = ["主体", "事件类型", "事实描述", "推断与判断", "标签", "量化参数"]

# 标签树（SPK-1 锁定清单口径；与 SPK-2 run_extraction.py 同源）
TAGS = "无人化作业/远程遥控/3D引导与机控/电动化/智能辅助施工/场景-矿山/场景-港口/场景-市政/核心零部件（电液控制·传感器）"


class ItemState(TypedDict, total=False):
    id: str
    text: str
    kept: bool
    pred: dict | None
    retries: int
    node_timings_ms: dict
    # 节点失败时记录错误（不抛出整条流水线）
    error: str | None


def _now() -> float:
    return time.monotonic()


def _ms(t0: float) -> int:
    return int((time.monotonic() - t0) * 1000)


def _load_prompt() -> str:
    """加载 SPK-2 终版提示词（glob 取最后一个 prompt_v*.txt = v3）。"""
    prompt_file = sorted((SPIKES / "spk2-extraction-probe").glob("prompt_v*.txt"))[-1]
    system = prompt_file.read_text(encoding="utf-8")
    system = system.replace("<事件类型>", "/".join(EVENTS)).replace("<标签树>", TAGS)
    return system


_SYSTEM_PROMPT = _load_prompt()


def node_prefilter(state: ItemState) -> ItemState:
    """粗筛：小模型二分类（领域相关 keep / 无关 drop）。

    粗筛失败按保留处理（走人工兜底），不丢弃条目。
    """
    t0 = _now()
    msgs = [
        {
            "role": "system",
            "content": (
                "判断正文是否与工程机械行业情报相关（产品/技术/市场/组织动态）。"
                '仅输出 JSON：{"relevant": true} 或 {"relevant": false}'
            ),
        },
        {"role": "user", "content": state["text"][:3000]},
    ]
    try:
        out, _ = chat_json(msgs, model_env="PIH_LLM_SMALL_MODEL")
        kept = bool(out.get("relevant"))
    except Exception as exc:  # noqa: BLE001 —— 粗筛失败按保留处理
        kept = True
        return {
            "kept": kept,
            "error": f"prefilter:{type(exc).__name__}",
            "node_timings_ms": {"prefilter": _ms(t0)},
        }
    return {"kept": kept, "node_timings_ms": {"prefilter": _ms(t0)}}


def node_extract(state: ItemState) -> ItemState:
    """结构化抽取：大模型 + SPK-2 终版提示词。

    抽取失败时记录错误并保留原 pred=None，由 validate 节点决定是否重问。
    """
    t0 = _now()
    msgs = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": state["text"][:6000]},
    ]
    timings = dict(state.get("node_timings_ms", {}))
    try:
        pred, usage = chat_json(msgs, model_env="PIH_LLM_LARGE_MODEL")
        retries = usage["retries"]
        error = None
    except LLMError as exc:
        pred, retries, error = None, 0, f"extract:{exc}"
    timings["extract"] = _ms(t0)
    return {"pred": pred, "retries": retries, "error": error, "node_timings_ms": timings}


def node_validate(state: ItemState) -> ItemState:
    """schema 校验：缺字段重问 ≤3。

    重问复用原 SPK-2 终版提示词（而非简版 system），保持一致性；
    重问计数累加（含原始抽取的 retries）。
    """
    t0 = _now()
    pred = state.get("pred")
    retries = state.get("retries", 0)
    text = state["text"]
    timings = dict(state.get("node_timings_ms", {}))

    # 初始抽取已成功且 schema 完整时，无需重问
    needs_retry = pred is None or any(k not in pred for k in SCHEMA_KEYS)
    while needs_retry and retries < 3:
        msgs = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": text[:6000]},
            {
                "role": "user",
                "content": (
                    "上一次输出缺字段或解析失败，严格按 schema 重出 JSON，"
                    "必须包含键：" + ", ".join(SCHEMA_KEYS)
                ),
            },
        ]
        try:
            pred, usage = chat_json(msgs, model_env="PIH_LLM_LARGE_MODEL")
            retries += usage["retries"] + 1
        except LLMError as exc:
            retries += 1
            pred = None
            break
        needs_retry = pred is None or any(k not in pred for k in SCHEMA_KEYS)

    timings["validate"] = _ms(t0)
    ok = pred is not None and all(k in pred for k in SCHEMA_KEYS)
    return {
        "pred": pred if ok else None,
        "retries": retries,
        "node_timings_ms": timings,
    }


def _route_after_prefilter(state: ItemState) -> str:
    """粗筛通过走抽取，否则直接结束（pred=None）。"""
    return "extract" if state.get("kept") else END


def build_graph():
    """构建并编译三节点图。"""
    g = StateGraph(ItemState)
    g.add_node("prefilter", node_prefilter)
    g.add_node("extract", node_extract)
    g.add_node("validate", node_validate)
    # 1.x 惯用法：START → prefilter → 条件路由 → extract → validate → END
    g.add_edge(START, "prefilter")
    g.add_conditional_edges("prefilter", _route_after_prefilter)
    g.add_edge("extract", "validate")
    g.add_edge("validate", END)
    return g.compile()
