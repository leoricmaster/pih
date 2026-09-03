"""粗筛独立模块：关键词命中 + 小模型二分类双通道（TASK-1.01.02 D3/D4）。

从抽取图（graph.node_prefilter）解耦为可独立运行的函数——AC3 验证「判不相关」
不需耦合大模型配置前置校验，也不必跑完整抽取图。

双通道语义（D4）：
- 关键词命中（领域包 keywords 任一子串出现）→ kept=True（确定性相关信号，短路，
  省一次小模型调用）
- 关键词未命中 + 小模型判定不相关 → kept=False（filtered_out）
- 关键词未命中 + 小模型 API 失败 → 按保留处理（灰条目，架构 §8 不丢弃）
- 关键词未命中 + 无 chat 注入（粗筛脱离 LLM 配置独立运行）→ 灰条目保留

调用方（ProcessRunner / 独立入口）据 kept 决定落 filtered_out 或保持 pending。
"""
from __future__ import annotations

from collections.abc import Callable

from pih.process.llm import LLMError

# chat 函数签名同 graph：(messages, tier) → (解析 dict, usage)。
ChatFn = Callable[[list[dict], str], tuple[dict, dict]]

PREFILTER_TEXT_CHARS = 3000


def keyword_hit(text: str, pack: dict) -> bool:
    """正文是否命中领域包任一监控关键词（子串包含）。"""
    keywords = pack.get("keywords", [])
    return any(kw and kw in text for kw in keywords)


def prefilter(
    text: str,
    pack: dict,
    chat: ChatFn | None = None,
) -> tuple[bool, str]:
    """粗筛双通道，返回 (kept, reason)。

    Args:
        text: 正文（已 prepare_text 产物或原文）。
        pack: 领域包（取 keywords 与 meta.display_name）。
        chat: 小模型调用；None 表示脱离 LLM 配置的独立粗筛路径。

    Returns:
        kept: True 保留走抽取；False 判不相关落 filtered_out。
        reason: 人读原因（落 process_error / 统计详情）。
    """
    snippet = text[:PREFILTER_TEXT_CHARS]

    if keyword_hit(snippet, pack):
        return True, "关键词命中（领域相关）"

    # 关键词未命中：交小模型二分类
    if chat is None:
        # 解耦路径：无 LLM 配置时仅关键词通道，未命中按灰条目保留
        return True, "关键词未命中且无小模型，灰条目保留"

    domain = pack["meta"]["display_name"]
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
        {"role": "user", "content": snippet},
    ]
    try:
        out, _usage = chat(msgs, "small")
    except LLMError as exc:
        return True, f"小模型不可用（{type(exc).__name__}），灰条目保留"

    if bool(out.get("relevant")):
        return True, "小模型判定相关"
    return False, "粗筛判定与领域不相关（关键词未命中 + 小模型判否）"
