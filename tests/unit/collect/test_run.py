"""run 模块单元测试——enabled 门控与采集编排（假适配器，不触网络）。"""
from __future__ import annotations

import pytest

import pih.collect.adapters  # noqa: F401
from pih.collect.base import SourceAdapter, SourceConfig, register_for_source
from pih.collect.rawitem import RawItem
from pih.collect.run import SourceDisabledError, collect_source


@register_for_source("test_run_src")
class _FakeAdapter(SourceAdapter):
    type = "html"
    DETAIL_URLS = ["http://x/1", "http://x/2", "http://x/3"]

    def __init__(self, http=None, snapshots=None) -> None:  # type: ignore[no-untyped-def]
        pass

    def fetch_list(self, source: SourceConfig) -> list[str]:
        return self.DETAIL_URLS

    def fetch_detail(self, url: str, source: SourceConfig) -> RawItem:
        return RawItem(
            source_id=source.id, url=url, title=f"标题-{url}", list_url=source.list_url,
            fetched_at="2026-08-26T00:00:00+00:00", http_status=200,
            content_type="text/html", encoding="utf-8", raw_html="<html></html>",
            snapshot_id=f"sha1-{url}", content_sha1=f"sha1-{url}",
        )


def _source(enabled: bool) -> SourceConfig:
    return SourceConfig(
        id="test_run_src", name="测试", type="html", url="http://x/",
        list_url="http://x/list", reliability="B", level="L2", enabled=enabled,
    )


class TestGate:
    def test_disabled_source_rejected(self):
        with pytest.raises(SourceDisabledError) as exc_info:
            collect_source(_source(enabled=False), http=None, snapshots=None)  # type: ignore[arg-type]
        # 指引信息须含启用流程
        assert "pih probe-source test_run_src" in str(exc_info.value)
        assert "enabled 置 true" in str(exc_info.value)

    def test_enabled_source_collects(self):
        items = collect_source(_source(enabled=True), http=None, snapshots=None)  # type: ignore[arg-type]
        assert len(items) == 3
        assert all(i.source_id == "test_run_src" for i in items)

    def test_max_items_truncates(self):
        items = collect_source(
            _source(enabled=True), http=None, snapshots=None, max_items=2,  # type: ignore[arg-type]
        )
        assert len(items) == 2
