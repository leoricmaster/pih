"""信源页数据辅助（TASK-1.01.01 AC2）——load_sources_view 三态。

pack 有效 → 信源清单；校验失败 → issues（含行号，配置诊断面）；
文件级错误 → error 文案。均不抛——呈现是页面的事。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from pih.consume import pack_loader

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


@pytest.fixture
def patch_pack_path(monkeypatch):
    def _patch(rel: str):
        monkeypatch.setattr(pack_loader, "_pack_path", lambda: FIXTURES / rel)

    return _patch


class TestLoadSourcesView:
    def test_valid_pack_returns_sources(self, patch_pack_path):
        patch_pack_path("good/pack.yaml")
        sources, issues, error = pack_loader.load_sources_view()
        assert sources and sources[0]["id"] == "s1"
        assert issues == []
        assert error is None

    def test_invalid_pack_returns_issues_with_lines(self, patch_pack_path):
        patch_pack_path("bad/source_missing_reliability.yaml")
        sources, issues, error = pack_loader.load_sources_view()
        assert sources is None
        assert error is None
        assert any(
            i.path == "sources[0].reliability" and i.line == 7 for i in issues
        )

    def test_missing_file_returns_error(self, patch_pack_path):
        patch_pack_path("nope/missing.yaml")
        sources, issues, error = pack_loader.load_sources_view()
        assert sources is None
        assert issues == []
        assert error and "不存在" in error
