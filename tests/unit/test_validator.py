"""领域包校验器单元测试（T4）——位置产出精度。

覆盖 AC1（好包通过）/ AC2（缺必选字段指位置）/ AC3（enum 违规指位置）
+ 嵌套 required、minItems 路径。
"""
from __future__ import annotations

from pathlib import Path

from pih.domainpacks.errors import ValidationIssue
from pih.domainpacks.validator import validate

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _paths(issues: list[ValidationIssue]) -> list[str]:
    return [i.path for i in issues]


class TestValidatorPaths:
    def test_ac1_good_pack_validates_clean(self):
        pack, _ = _load(FIXTURES / "good" / "pack.yaml")
        result = validate(pack)
        assert result.ok
        assert result.issues == []
        assert result.errors == []

    def test_ac2_missing_required_field_points_at_field(self):
        # 缺 sources：required 错误 path 应重写为 'sources'
        pack, _ = _load(FIXTURES / "bad" / "missing_sources.yaml")
        result = validate(pack)
        assert not result.ok
        assert "sources" in _paths(result.issues)

    def test_ac3_enum_violation_points_at_field(self):
        # sources[0].type = 'foo'
        pack, _ = _load(FIXTURES / "bad" / "bad_source_type.yaml")
        result = validate(pack)
        assert not result.ok
        assert "sources[0].type" in _paths(result.issues)

    def test_nested_required_points_at_nested_field(self):
        # sources[0] 缺 reliability → path 应为 sources[0].reliability
        pack, _ = _load(FIXTURES / "bad" / "source_missing_reliability.yaml")
        result = validate(pack)
        assert not result.ok
        assert "sources[0].reliability" in _paths(result.issues)

    def test_minitems_violation_points_at_field(self):
        # keywords = []
        pack, _ = _load(FIXTURES / "bad" / "empty_keywords.yaml")
        result = validate(pack)
        assert not result.ok
        assert "keywords" in _paths(result.issues)

    def test_required_issue_message_is_human_readable(self):
        pack, _ = _load(FIXTURES / "bad" / "missing_sources.yaml")
        result = validate(pack)
        src_issue = next(i for i in result.issues if i.path == "sources")
        assert "必选" in src_issue.message

    def test_raise_if_invalid_raises(self):
        pack, _ = _load(FIXTURES / "bad" / "missing_sources.yaml")
        from pih.domainpacks.errors import LoadError

        try:
            validate(pack).raise_if_invalid()
            raise AssertionError("预期抛 LoadError")
        except LoadError as e:
            assert "sources" in str(e)


# 复用 loader 读夹具（loader 自身已在 test_loader 覆盖，此处只用其读 YAML）
def _load(path: Path) -> tuple[dict, None]:
    from pih.domainpacks.loader import load_yaml

    return load_yaml(path), None
