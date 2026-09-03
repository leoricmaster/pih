"""信源页呈现词映射（doc-4 术语词表「呈现」基线的代码落点）。

事实源=doc-4 各词条「呈现」行；key 集与 domainpacks.schema 枚举的
一致性由 tests/unit/consume/test_labels.py 锁定（schema 加枚举而词表
未跟 → 红）。适配器接入状态不入词表——运行时查注册表渲染（易过时的
状态信息只活在运行时）。
"""
from __future__ import annotations

# 信源类型（doc-2 §4 / doc-4「信源类型」）
TYPE_LABELS = {"html": "网页", "rss": "RSS", "api": "API", "change_monitor": "变更监控"}

# 抓取频率（调度器未上线前仅配置落盘）
FREQ_LABELS = {"hourly": "每小时", "daily": "每日", "weekly": "每周"}

# 字段图例（doc-4「层级 vs 来源可靠性」呈现基线 + 类型/频率）
FIELD_LEGEND = [
    ("类型", "抓取方式：网页 / RSS / API / 变更监控（对方未提供接口时的主动监控）"),
    ("层级", "看出身——L1 官方/主机厂一手、L2 权威/垂直媒体、L3 聚合站、L4 弱信号"),
    (
        "可靠性",
        "看表现——Admiralty 来源可靠性：A 完全可靠 / B 通常可靠 / C 较为可靠 / "
        "D 通常不可靠 / E 不可靠 / F 无法判断",
    ),
    ("频率", "采集节奏（每小时/每日/每周）；调度器上线后生效，当前仅配置记录"),
]
