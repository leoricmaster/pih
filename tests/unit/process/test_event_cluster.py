"""事件聚类单元测试（Sprint 6 §3.6a）。

纯函数测试——不连 DB：
- normalize_subject 别名映射（领域包 competitors.aliases → display_name）
- admiralty_weight / event_state_weight 权重读取
- STATUS_LABELS 中文映射完整性
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
    admiralty_weight,
    event_state_weight,
    normalize_subject,
)


def _pack() -> dict:
    """最小领域包（含 competitors 与 ranking 节，单元测试用）。"""
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
        "ranking": {
            "reliability_weights": {"A": 1.0, "B": 0.8, "C": 0.6, "D": 0.4, "E": 0.2, "F": 0.0},
            "credibility_weights": {"1": 1.0, "2": 0.8, "3": 0.6, "4": 0.4, "5": 0.2, "6": 0.0},
            "event_state_weights": {
                "confirmed": 1.0, "single_source": 0.8, "pending": 0.5,
                "refuted": 0.0, "expired": 0.3,
            },
        },
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
        """中文展示与设计规格一致。"""
        assert STATUS_LABELS[STATUS_PENDING] == "待核实"
        assert STATUS_LABELS[STATUS_SINGLE_SOURCE] == "单源确认"
        assert STATUS_LABELS[STATUS_CONFIRMED] == "多源确认"
        assert STATUS_LABELS[STATUS_REFUTED] == "已证伪"
        assert STATUS_LABELS[STATUS_EXPIRED] == "已过期"


class TestEventStateWeight:
    def test_known_status_returns_weight(self):
        pack = _pack()
        assert event_state_weight("confirmed", pack) == 1.0
        assert event_state_weight("single_source", pack) == 0.8
        assert event_state_weight("pending", pack) == 0.5
        assert event_state_weight("refuted", pack) == 0.0
        assert event_state_weight("expired", pack) == 0.3

    def test_none_status_returns_zero(self):
        """未挂事件（status=None）权重 0——排序末尾。"""
        assert event_state_weight(None, _pack()) == 0.0

    def test_unknown_status_falls_back_to_default(self):
        """未知 status 回退默认 0.5（不崩溃）。"""
        assert event_state_weight("unknown_state", _pack()) == 0.5

    def test_missing_ranking_section_falls_back(self):
        """领域包无 ranking 节时回退默认 0.5。"""
        assert event_state_weight("pending", {}) == 0.5


class TestAdmiraltyWeight:
    def test_standard_codes(self):
        """标准 Admiralty 码权重 = min(rel, cred)（短板决定）。"""
        pack = _pack()
        # A1: min(1.0, 1.0) = 1.0
        assert admiralty_weight("A1", pack) == 1.0
        # B2: min(0.8, 0.8) = 0.8
        assert admiralty_weight("B2", pack) == 0.8
        # C3: min(0.6, 0.6) = 0.6
        assert admiralty_weight("C3", pack) == 0.6
        # 短板：A6 = min(1.0, 0.0) = 0.0
        assert admiralty_weight("A6", pack) == 0.0
        # F1 = min(0.0, 1.0) = 0.0
        assert admiralty_weight("F1", pack) == 0.0

    def test_none_or_short_code_returns_zero(self):
        """空或不足 2 字符返回 0。"""
        pack = _pack()
        assert admiralty_weight(None, pack) == 0.0
        assert admiralty_weight("", pack) == 0.0
        assert admiralty_weight("B", pack) == 0.0

    def test_missing_ranking_falls_back_to_zero(self):
        """领域包无 ranking 节时返回 0（不崩溃）。"""
        assert admiralty_weight("B2", {}) == 0.0
