"""领域包 schema 自洽测试（T3）。

范围：验证 DOMAIN_PACK_SCHEMA 是合法 JSON Schema Draft 2020-12，且关键约束
（必选字段、enum、minItems）按设计生效——即坏包被拒绝、好包通过。
位置产出的精度由 T4 校验器测试覆盖（校验器负责把 jsonschema 原生 error 转成
带清晰 path 的 ValidationIssue）。
"""
from __future__ import annotations

import jsonschema
import pytest

from pih.domainpacks.schema import DOMAIN_PACK_SCHEMA, get_schema


def _minimal_valid_pack() -> dict:
    """构造一个刚好满足所有必选约束的最小领域包。"""
    return {
        "meta": {"domain_id": "test_domain", "display_name": "测试领域", "version": "0.1.0"},
        "sources": [
            {
                "id": "s1", "name": "源1", "type": "rss",
                "url": "http://example.com/feed", "list_url": "http://example.com/list",
                "reliability": "B", "level": "L2", "enabled": True,
            },
        ],
        "keywords": ["关键词1"],
        "competitors": [{"id": "c1", "display_name": "竞品1"}],
        "tag_tree": {"产品类": ["挖掘机械"]},
        "event_types": ["新品发布", "其他"],
        "report_template": "占位模板",
        "extraction_prompt": "占位提示词 <事件类型> <标签树> <主体清单>",
    }


def _assert_valid(pack: dict) -> None:
    jsonschema.validate(pack, DOMAIN_PACK_SCHEMA)


def _assert_rejected(pack: dict) -> None:
    """断言 pack 被 schema 拒绝（至少一条 error）。不检查路径精度。"""
    validator = jsonschema.Draft202012Validator(DOMAIN_PACK_SCHEMA)
    errors = list(validator.iter_errors(pack))
    assert errors, "预期校验失败但 pack 通过了校验"


class TestSchemaIntegrity:
    def test_schema_is_valid_draft(self):
        """schema 本身是合法的 Draft 2020-12。"""
        jsonschema.Draft202012Validator.check_schema(DOMAIN_PACK_SCHEMA)

    def test_get_schema_returns_same_object(self):
        assert get_schema() is DOMAIN_PACK_SCHEMA

    def test_minimal_pack_passes(self):
        _assert_valid(_minimal_valid_pack())

    def test_pack_with_optional_ranking_passes(self):
        pack = _minimal_valid_pack()
        pack["ranking"] = {
            "reliability_weights": {"A": 1.0, "B": 0.8},
            "credibility_weights": {"1": 1.0, "2": 0.8},
            "event_state_weights": {"confirmed": 1.0, "single": 0.8},
        }
        _assert_valid(pack)

    def test_additional_top_level_property_rejected(self):
        """schema 闭包：额外顶层字段被拒（additionalProperties: False）。"""
        pack = _minimal_valid_pack()
        pack["unknown_field"] = "x"
        _assert_rejected(pack)




# ADR-001 后果：缺必选字段拒绝加载。位置精度由 T4 校验器测试覆盖。
@pytest.mark.parametrize(
    "field",
    [
        "meta", "sources", "keywords", "competitors",
        "tag_tree", "event_types", "report_template", "extraction_prompt",
    ],
)
def test_missing_required_field_rejected(field: str):
    pack = _minimal_valid_pack()
    del pack[field]
    _assert_rejected(pack)


def test_missing_meta_subfield_rejected():
    pack = _minimal_valid_pack()
    del pack["meta"]["domain_id"]
    _assert_rejected(pack)


@pytest.mark.parametrize("field", ["reliability", "level", "list_url", "enabled"])
def test_source_missing_required_field_rejected(field: str):
    pack = _minimal_valid_pack()
    del pack["sources"][0][field]
    _assert_rejected(pack)


def test_source_bad_enabled_type_rejected():
    """enabled 非 boolean（如字符串 "true"）被拒。"""
    pack = _minimal_valid_pack()
    pack["sources"][0]["enabled"] = "true"
    _assert_rejected(pack)


def test_source_bad_level_rejected():
    pack = _minimal_valid_pack()
    pack["sources"][0]["level"] = "L9"
    _assert_rejected(pack)
    _assert_rejected(pack)


class TestEnumConstraints:
    def test_bad_source_type_rejected(self):
        pack = _minimal_valid_pack()
        pack["sources"][0]["type"] = "foo"
        _assert_rejected(pack)

    def test_bad_reliability_rejected(self):
        pack = _minimal_valid_pack()
        pack["sources"][0]["reliability"] = "Z"
        _assert_rejected(pack)


class TestMinItemsEnforced:
    def test_empty_sources_rejected(self):
        pack = _minimal_valid_pack()
        pack["sources"] = []
        _assert_rejected(pack)

    def test_empty_keywords_rejected(self):
        pack = _minimal_valid_pack()
        pack["keywords"] = []
        _assert_rejected(pack)

    def test_empty_competitors_rejected(self):
        pack = _minimal_valid_pack()
        pack["competitors"] = []
        _assert_rejected(pack)

    def test_empty_tag_tree_rejected(self):
        pack = _minimal_valid_pack()
        pack["tag_tree"] = {}
        _assert_rejected(pack)

    def test_empty_event_types_rejected(self):
        pack = _minimal_valid_pack()
        pack["event_types"] = []
        _assert_rejected(pack)

    def test_duplicate_event_types_rejected(self):
        pack = _minimal_valid_pack()
        pack["event_types"] = ["新品发布", "新品发布"]
        _assert_rejected(pack)
