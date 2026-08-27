"""extraction 单元测试：PackVocab 构造 + validate_pred 全分支（S4.2.1 AC1）。"""
from __future__ import annotations

import pytest

from pih.process.extraction import (
    IntelExtraction,
    PackVocab,
    ValidationFailure,
    validate_pred,
)


@pytest.fixture
def vocab() -> PackVocab:
    return PackVocab(
        event_types=frozenset({"新品发布", "财报", "其他"}),
        tags=frozenset({"电动化", "场景-矿山"}),
    )


def _ok_pred() -> dict:
    return {
        "主体": "三一",
        "事件类型": "新品发布",
        "事实描述": "销量 1000 台",
        "推断与判断": "依据：正文销量数据",
        "标签": ["电动化"],
        "量化参数": {"销量": "1000台"},
        "信息可信度": "2",
    }


class TestPackVocab:
    def test_from_pack_flattens_tag_tree(self):
        pack = {
            "event_types": ["新品发布", "其他"],
            "tag_tree": {
                "技术特征": ["电动化", "远程遥控"],
                "应用场景": ["场景-矿山"],
            },
        }
        vocab = PackVocab.from_pack(pack)
        assert vocab.event_types == frozenset({"新品发布", "其他"})
        assert vocab.tags == frozenset({"电动化", "远程遥控", "场景-矿山"})


class TestValidatePredOk:
    def test_valid_pred_returns_extraction(self, vocab):
        result = validate_pred(_ok_pred(), vocab)
        assert isinstance(result, IntelExtraction)
        assert result.subject == "三一"
        assert result.event_type == "新品发布"
        assert result.tags == ["电动化"]
        assert result.quant_params == {"销量": "1000台"}
        assert result.credibility == "2"

    def test_empty_tags_and_quant_allowed(self, vocab):
        """标签可空数组、量化参数可空对象（行业统计类常见）。"""
        pred = _ok_pred() | {"标签": [], "量化参数": {}}
        result = validate_pred(pred, vocab)
        assert isinstance(result, IntelExtraction)
        assert result.tags == []
        assert result.quant_params == {}

    def test_empty_inference_allowed(self, vocab):
        pred = _ok_pred() | {"推断与判断": ""}
        result = validate_pred(pred, vocab)
        assert isinstance(result, IntelExtraction)


class TestValidatePredFailures:
    def test_missing_keys_listed(self, vocab):
        pred = {"主体": "三一"}
        result = validate_pred(pred, vocab)
        assert isinstance(result, ValidationFailure)
        for k in ("事件类型", "事实描述", "推断与判断", "标签", "量化参数", "信息可信度"):
            assert k in result.missing_keys

    def test_event_type_out_of_enum(self, vocab):
        pred = _ok_pred() | {"事件类型": "融资轮次"}
        result = validate_pred(pred, vocab)
        assert isinstance(result, ValidationFailure)
        assert any("融资轮次" in b for b in result.bad_values)

    def test_tag_out_of_tree(self, vocab):
        pred = _ok_pred() | {"标签": ["电动化", "场景（矿山）"]}
        result = validate_pred(pred, vocab)
        assert isinstance(result, ValidationFailure)
        assert any("场景（矿山）" in b for b in result.bad_values)

    def test_credibility_out_of_range(self, vocab):
        pred = _ok_pred() | {"信息可信度": "7"}
        result = validate_pred(pred, vocab)
        assert isinstance(result, ValidationFailure)
        assert any("信息可信度" in b for b in result.bad_values)

    def test_empty_subject_and_facts_rejected(self, vocab):
        """主体/事实描述为空串 = 字段存在但无效（AC1 非空口径）。"""
        pred = _ok_pred() | {"主体": "  ", "事实描述": ""}
        result = validate_pred(pred, vocab)
        assert isinstance(result, ValidationFailure)
        assert any("主体" in b for b in result.bad_values)
        assert any("事实描述" in b for b in result.bad_values)

    def test_tags_not_list_rejected(self, vocab):
        pred = _ok_pred() | {"标签": "电动化"}
        result = validate_pred(pred, vocab)
        assert isinstance(result, ValidationFailure)
        assert any("标签" in b for b in result.bad_values)

    def test_quant_not_dict_rejected(self, vocab):
        pred = _ok_pred() | {"量化参数": ["销量"]}
        result = validate_pred(pred, vocab)
        assert isinstance(result, ValidationFailure)
        assert any("量化参数" in b for b in result.bad_values)

    def test_failure_message_readable(self, vocab):
        pred = _ok_pred() | {"事件类型": "融资"}
        del pred["标签"]
        result = validate_pred(pred, vocab)
        assert isinstance(result, ValidationFailure)
        msg = result.message()
        assert "缺字段：标签" in msg
        assert "非法值" in msg
