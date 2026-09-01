"""事件聚类单元测试（S1.3.1）。

纯函数测试——不连 DB：
- normalize_subject 别名映射（领域包 competitors.aliases → display_name）
- STATUS_LABELS 中文映射完整性

排序权重（W_c × map(admiralty)）的实现在 store/repository.py
_build_ranked_order_sql，由 tests/integration/test_consume_event_fields.py
TestRankingSortOrder 守护——不在本文件重复。
"""
from __future__ import annotations

from pih.process.event import (
    STATUS_CONFIRMED,
    STATUS_EXPIRED,
    STATUS_LABELS,
    STATUS_ORDER,
    STATUS_PENDING,
    STATUS_REFUTED,
    STATUS_SINGLE_SOURCE,
    normalize_subject,
)


def _pack() -> dict:
    """最小领域包（含 competitors 节，单元测试用）。"""
    return {
        "competitors": [
            {
                "id": "sany",
                "display_name": "三一",
                "aliases": ["三一重工", "SANY", "三一集团"],
            },
            {
                "id": "xcmg",
                "display_name": "徐工",
                "aliases": ["徐工集团", "XCMG"],
            },
        ],
    }


class TestNormalizeSubject:
    def test_alias_maps_to_display_name(self):
        """别名映射到规范 display_name。"""
        pack = _pack()
        assert normalize_subject("三一重工", pack) == "三一"
        assert normalize_subject("三一集团", pack) == "三一"
        assert normalize_subject("SANY", pack) == "三一"

    def test_case_insensitive_for_english_alias(self):
        """英文别名大小写不敏感（SANY/sany/Sany 都归一）。"""
        pack = _pack()
        assert normalize_subject("sany", pack) == "三一"
        assert normalize_subject("Sany", pack) == "三一"

    def test_display_name_self_maps(self):
        """display_name 自身也归一到自身。"""
        pack = _pack()
        assert normalize_subject("三一", pack) == "三一"
        assert normalize_subject("徐工", pack) == "徐工"

    def test_unknown_subject_returns_stripped_original(self):
        """未收录的主体返回 strip 后原值（不强行映射）。"""
        pack = _pack()
        assert normalize_subject("某小厂", pack) == "某小厂"
        assert normalize_subject("  中联重科  ", pack) == "中联重科"

    def test_empty_string_returns_empty(self):
        """空串原样返回（占位主体的边界）。"""
        assert normalize_subject("", _pack()) == ""
        assert normalize_subject("   ", _pack()) == ""

    def test_strip_whitespace(self):
        """首尾空白被 strip。"""
        pack = _pack()
        assert normalize_subject("  三一  ", pack) == "三一"
        assert normalize_subject("  三一重工 ", pack) == "三一"

    def test_empty_pack_returns_stripped_original(self):
        """领域包 competitors 为空时，subject strip 后原样返回（降级路径）。"""
        assert normalize_subject("三一", {}) == "三一"
        assert normalize_subject("某厂", {"competitors": []}) == "某厂"


class TestStatusLabels:
    def test_all_status_have_chinese_labels(self):
        """5 个状态枚举都有中文展示。"""
        for s in STATUS_ORDER:
            assert s in STATUS_LABELS
            assert STATUS_LABELS[s]

    def test_labels_match_design(self):
        """中文展示与架构 §6.1 状态机一致。"""
        assert STATUS_LABELS[STATUS_PENDING] == "待核实"
        assert STATUS_LABELS[STATUS_SINGLE_SOURCE] == "单源确认"
        assert STATUS_LABELS[STATUS_CONFIRMED] == "多源确认"
        assert STATUS_LABELS[STATUS_REFUTED] == "已证伪"
        assert STATUS_LABELS[STATUS_EXPIRED] == "已过期"
