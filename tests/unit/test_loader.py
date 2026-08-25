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
