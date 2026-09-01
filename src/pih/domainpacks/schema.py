"""领域包 JSON Schema 定义（架构 §6.3 / ADR-001）。

领域包六元：{ 信源清单, 监控关键词, 竞品主体清单, 标签树, 报告模板, 抽取提示词 }，
外加 ranking 节（§6.2 排序权重，可选有默认）。

设计原则：
- 只约束必选字段 + enum；自由文本（prompt/template）只校验非空。
- 缺必选字段拒绝加载并指出位置（ADR-001 后果节）。
- 不过早固化——第二领域接入后再迭代。
"""
from __future__ import annotations

# Admiralty 来源可靠性词表（架构 §6.2）：A–F
RELIABILITY_VALUES = ["A", "B", "C", "D", "E", "F"]
# 信息可信度词表：1–6
CREDIBILITY_VALUES = ["1", "2", "3", "4", "5", "6"]
# 信源类型（架构 §4 信源适配器：RSS/网页/API/变更监控）
SOURCE_TYPES = ["rss", "html", "api", "change_monitor"]
# 信源层级（架构 §6.2）：L1 官方/主机厂、L2 权威/垂直媒体、L3 聚合、L4 弱信号
SOURCE_LEVELS = ["L1", "L2", "L3", "L4"]
# 抓取频率（调度器 Backlog S1.5.1 消费，当前仅落盘）
FETCH_FREQUENCIES = ["hourly", "daily", "weekly"]

DOMAIN_PACK_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "DomainPack",
    "description": "领域包：行业知识以 YAML 配置注入（架构 §6.3）",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "meta", "sources", "keywords", "competitors",
        "tag_tree", "event_types", "report_template", "extraction_prompt",
    ],
    "properties": {
        "meta": {
            "type": "object",
            "additionalProperties": False,
            "required": ["domain_id", "display_name", "version"],
            "properties": {
                "domain_id": {
                    "type": "string",
                    "pattern": "^[a-z][a-z0-9_]*$",
                    "description": "领域标识，小写蛇形，与目录名一致",
                },
                "display_name": {"type": "string", "minLength": 1},
                "version": {
                    "type": "string",
                    "pattern": r"^\d+\.\d+\.\d+$",
                    "description": "semver",
                },
            },
        },
        "sources": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "id", "name", "type", "url", "reliability", "level", "list_url", "enabled",
                ],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "name": {"type": "string", "minLength": 1},
                    "type": {"type": "string", "enum": SOURCE_TYPES},
                    "url": {"type": "string", "format": "uri", "description": "站点根 URL"},
                    "list_url": {
                        "type": "string", "format": "uri",
                        "description": "列表页入口（采集适配器从此发现详情链接）",
                    },
                    "reliability": {"type": "string", "enum": RELIABILITY_VALUES},
                    "level": {"type": "string", "enum": SOURCE_LEVELS},
                    "fetch_frequency": {"type": "string", "enum": FETCH_FREQUENCIES},
                    "enabled": {
                        "type": "boolean",
                        "description": "试抓取（pih probe-source）通过后由运营者人工置 true；"
                        "采集门控（collect）仅运行 enabled 源（S1.1.1 AC2「成功才允许启用」）",
                    },
                },
            },
        },
        "keywords": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "minLength": 1},
        },
        "competitors": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "display_name"],
                "properties": {
                    "id": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
                    "display_name": {"type": "string", "minLength": 1},
                    "aliases": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                        "default": [],
                    },
                },
            },
        },
        "tag_tree": {
            "type": "object",
            "minProperties": 1,
            "additionalProperties": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
                "minItems": 1,
            },
        },
        "event_types": {
            "type": "array",
            "minItems": 1,
            "uniqueItems": True,
            "items": {"type": "string", "minLength": 1},
            "description": "事件类型枚举（抽取输出的合法值域）；"
            "含兜底类（如「其他」）以便与领域无关内容归类",
        },
        "report_template": {
            "type": "string", "minLength": 1,
            "description": "报告模板，当前为占位字符串",
        },
        "extraction_prompt": {
            "type": "string", "minLength": 1,
            "description": "抽取提示词模板，须含占位符 <事件类型>/<标签树>/<主体清单>"
            "（校验器语义检查，缺失拒绝加载）；process 层注入领域清单",
        },
        "ranking": {
            "type": "object",
            "description": "§6.2 排序权重，可选；缺省由核心代码给默认",
            "additionalProperties": False,
            "properties": {
                "reliability_weights": {
                    "type": "object",
                    "additionalProperties": {"type": "number"},
                },
                "credibility_weights": {
                    "type": "object",
                    "additionalProperties": {"type": "number"},
                },
                "event_state_weights": {
                    "type": "object",
                    "additionalProperties": {"type": "number"},
                },
            },
        },
    },
}
