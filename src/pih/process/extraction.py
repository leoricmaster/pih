"""结构化抽取模型与校验（Backlog TASK-1.02.01 AC1）。

抽取输出 7 键（领域包提示词定义）：主体/事件类型/事实描述/推断与判断/
标签/量化参数/信息可信度。validate_pred 校验：
- 7 键齐全且类型正确（主体/事件类型/事实描述非空串）；
- 事件类型 ∈ 领域包 event_types；
- 标签 ⊆ 领域包标签树叶子；
- 信息可信度 ∈ 1–6 单字符（Admiralty，架构 §6.2）；
- 推断与判断非空时须含「依据」标记（AC1 推断必须含依据，提示词规则 5 同构）。

校验失败 → validate 节点重问（≤3），仍失败降级 needs_manual 不丢弃（TASK-1.02.01 AC2）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

# 提示词输出键（与领域包 extraction_prompt 的 JSON 模板一一对应）
KEY_SUBJECT = "主体"
KEY_EVENT_TYPE = "事件类型"
KEY_FACTS = "事实描述"
KEY_INFERENCES = "推断与判断"
KEY_TAGS = "标签"
KEY_QUANT = "量化参数"
KEY_CREDIBILITY = "信息可信度"

ALL_KEYS = (
    KEY_SUBJECT, KEY_EVENT_TYPE, KEY_FACTS, KEY_INFERENCES,
    KEY_TAGS, KEY_QUANT, KEY_CREDIBILITY,
)

CREDIBILITY_VALUES = ("1", "2", "3", "4", "5", "6")

# 后验质量门（TASK-1.02.01 AC3）：schema 校验拦不住的语义占位主体——命中即降 needs_manual。
# 实证样本是"未知"；集合保守，随反馈样本可扩充。
PLACEHOLDER_SUBJECTS = frozenset({"", "未知", "无", "不详", "unknown"})


def is_placeholder_subject(subject: str) -> bool:
    """主体是否为占位值（strip + lower 后比对，中文不受 lower 影响）。"""
    return subject.strip().lower() in PLACEHOLDER_SUBJECTS


@dataclass(frozen=True)
class PackVocab:
    """领域包注入的抽取词表（event_types / tag_tree 叶子扁平化）。"""

    event_types: frozenset[str]
    tags: frozenset[str]

    @classmethod
    def from_pack(cls, pack: dict) -> PackVocab:
        """从领域包 dict 构造（event_types 节 + tag_tree 全部叶子）。"""
        event_types = frozenset(pack["event_types"])
        tags = frozenset(
            leaf for leaves in pack["tag_tree"].values() for leaf in leaves
        )
        return cls(event_types=event_types, tags=tags)


@dataclass(frozen=True)
class IntelExtraction:
    """校验通过的结构化抽取结果（写回 store 的中间形态）。"""

    subject: str
    event_type: str
    facts: str
    inferences: str
    tags: list[str] = field(default_factory=list)
    quant_params: dict = field(default_factory=dict)
    credibility: str = ""


@dataclass(frozen=True)
class ValidationFailure:
    """校验失败详情：缺哪些键 + 哪些值越界（重问 user 消息的素材）。"""

    missing_keys: list[str] = field(default_factory=list)
    bad_values: list[str] = field(default_factory=list)

    def message(self) -> str:
        parts: list[str] = []
        if self.missing_keys:
            parts.append("缺字段：" + "、".join(self.missing_keys))
        if self.bad_values:
            parts.append("非法值：" + "；".join(self.bad_values))
        return "；".join(parts) or "未知原因"


def validate_pred(pred: dict, vocab: PackVocab) -> IntelExtraction | ValidationFailure:
    """校验 LLM 抽取输出。

    Returns:
        IntelExtraction: 校验通过的可写回结果；
        ValidationFailure: 不合格详情（调用方决定重问或降级）。
    """
    missing = [k for k in ALL_KEYS if k not in pred]
    bad: list[str] = []

    subject = pred.get(KEY_SUBJECT)
    if isinstance(subject, str) and not subject.strip():
        bad.append(f"{KEY_SUBJECT}为空")
        subject = None
    event_type = pred.get(KEY_EVENT_TYPE)
    if isinstance(event_type, str) and event_type and event_type not in vocab.event_types:
        bad.append(f"{KEY_EVENT_TYPE}「{event_type}」不在枚举内")
    facts = pred.get(KEY_FACTS)
    if isinstance(facts, str) and not facts.strip():
        bad.append(f"{KEY_FACTS}为空")
        facts = None

    # AC1「推断字段必须含依据」：非空推断须含「依据」标记（提示词规则 5 要求
    # 「依据：」开头，此处硬校验兜底；子串匹配容全/半角冒号，空串放行）。
    inferences = pred.get(KEY_INFERENCES)
    if (
        isinstance(inferences, str)
        and inferences.strip()
        and "依据" not in inferences
    ):
        bad.append(f"{KEY_INFERENCES}缺依据（须含「依据：…」）")

    tags = pred.get(KEY_TAGS)
    if tags is not None and not isinstance(tags, list):
        bad.append(f"{KEY_TAGS}非数组")
        tags = None
    elif isinstance(tags, list):
        off = [t for t in tags if t not in vocab.tags]
        if off:
            bad.append(f"{KEY_TAGS}越界：{'、'.join(map(str, off))}")

    quant = pred.get(KEY_QUANT)
    if quant is not None and not isinstance(quant, dict):
        bad.append(f"{KEY_QUANT}非对象")
        quant = None

    credibility = pred.get(KEY_CREDIBILITY)
    if credibility is not None and str(credibility) not in CREDIBILITY_VALUES:
        bad.append(f"{KEY_CREDIBILITY}「{credibility}」不在 1–6 枚举内")

    if missing or bad:
        return ValidationFailure(missing_keys=missing, bad_values=bad)
    return IntelExtraction(
        subject=str(pred[KEY_SUBJECT]).strip(),
        event_type=str(pred[KEY_EVENT_TYPE]),
        facts=str(pred[KEY_FACTS]).strip(),
        inferences=str(pred[KEY_INFERENCES]).strip(),
        tags=[str(t) for t in pred[KEY_TAGS]],
        quant_params=dict(pred[KEY_QUANT]),
        credibility=str(pred[KEY_CREDIBILITY]),
    )
