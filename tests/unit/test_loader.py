"""领域包加载器单元测试（T4）。"""
from __future__ import annotations

from pathlib import Path

import pytest

from pih.domainpacks import loader
from pih.domainpacks.errors import LoadError

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class TestLoadYaml:
    def test_load_valid_good_pack(self):
        pack = loader.load_yaml(FIXTURES / "good" / "pack.yaml")
        assert pack["meta"]["domain_id"] == "fixture_good"
        assert isinstance(pack, dict)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(LoadError, match="不存在"):
            loader.load_yaml(tmp_path / "nope.yaml")

    def test_empty_file_raises(self, tmp_path):
        p = tmp_path / "empty.yaml"
        p.write_text("", encoding="utf-8")
        with pytest.raises(LoadError, match="为空"):
            loader.load_yaml(p)

    def test_non_map_top_raises(self, tmp_path):
        p = tmp_path / "list.yaml"
        p.write_text("- a\n- b\n", encoding="utf-8")
        with pytest.raises(LoadError, match="映射"):
            loader.load_yaml(p)

    def test_bad_yaml_raises(self, tmp_path):
        p = tmp_path / "broken.yaml"
        # 故意写成 tab 缩进等非法 YAML
        p.write_text("meta: {\n", encoding="utf-8")
        with pytest.raises(LoadError, match="YAML 解析失败"):
            loader.load_yaml(p)


class TestLoadAndValidate:
    def test_load_validates_and_returns_pack(self):
        pack, result = loader.load_and_validate(FIXTURES / "good" / "pack.yaml")
        assert result.ok
        assert pack["meta"]["domain_id"] == "fixture_good"

    def test_load_strict_raises_on_bad(self):
        with pytest.raises(LoadError):
            loader.load(FIXTURES / "bad" / "missing_sources.yaml")

    def test_load_strict_ok_on_good(self):
        pack = loader.load(FIXTURES / "good" / "pack.yaml")
        assert pack["meta"]["domain_id"] == "fixture_good"


class TestIssueLineNumbers:
    """TASK-1.01.01 AC1：校验 issue 附带 YAML 行号（1 基）。

    语义（docs/design/TASK-1.01.01-design.md §3）：缺必选字段 → 父映射起始行
    （运营者应看的位置）；值违规（enum 等）→ 值所在行。行号由加载器经
    yaml.compose 回填，validator 保持 dict 纯净。
    """

    def _issue(self, fixture: str, path: str):
        _, result = loader.load_and_validate(FIXTURES / "bad" / fixture)
        return next(i for i in result.issues if i.path == path)

    def test_missing_field_points_to_parent_mapping_line(self):
        # source_missing_reliability.yaml：sources[0] 映射起于第 7 行（- id: s1）
        issue = self._issue("source_missing_reliability.yaml", "sources[0].reliability")
        assert issue.line == 7

    def test_missing_enabled_points_to_parent_mapping_line(self):
        issue = self._issue("source_missing_enabled.yaml", "sources[0].enabled")
        assert issue.line == 7

    def test_enum_violation_points_to_value_line(self):
        # bad_source_type.yaml：type: foo 在第 9 行
        issue = self._issue("bad_source_type.yaml", "sources[0].type")
        assert issue.line == 9

    def test_missing_top_level_points_to_root_line(self):
        # missing_sources.yaml：根映射起于第 2 行（meta:）
        issue = self._issue("missing_sources.yaml", "sources")
        assert issue.line == 2

    def test_issue_str_includes_line(self):
        issue = self._issue("source_missing_reliability.yaml", "sources[0].reliability")
        assert "第 7 行" in str(issue)
