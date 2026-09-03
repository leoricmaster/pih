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
        items, outcomes = collect_source(_source(enabled=True), http=None, snapshots=None)  # type: ignore[arg-type]
        assert len(items) == 3
        assert all(i.source_id == "test_run_src" for i in items)
        assert outcomes == []  # 未传 repository 不落库

    def test_max_items_truncates(self):
        items, _ = collect_source(
            _source(enabled=True), http=None, snapshots=None, max_items=2,  # type: ignore[arg-type]
        )
        assert len(items) == 2


@register_for_source("test_fail_src")
class _FailAdapter(SourceAdapter):
    """第二条详情 fetch 抛异常，验证失败落死信、不阻断其余条目（AC4）。"""

    type = "html"

    def __init__(self, http=None, snapshots=None) -> None:  # type: ignore[no-untyped-def]
        pass

    def fetch_list(self, source: SourceConfig) -> list[str]:
        return ["http://x/ok", "http://x/boom", "http://x/ok2"]

    def fetch_detail(self, url: str, source: SourceConfig) -> RawItem:
        if "boom" in url:
            raise ConnectionError("timeout")
        return RawItem(
            source_id=source.id, url=url, title=f"标题-{url}", list_url=source.list_url,
            fetched_at="2026-08-26T00:00:00+00:00", http_status=200,
            content_type="text/html", encoding="utf-8", raw_html="<html></html>",
            snapshot_id=f"sha1-{url}", content_sha1=f"sha1-{url}",
        )


def _fail_source() -> SourceConfig:
    return SourceConfig(
        id="test_fail_src", name="测试失败", type="html", url="http://x/",
        list_url="http://x/list", reliability="B", level="L2", enabled=True,
    )


class TestFetchFailure:
    def test_failure_recorded_and_does_not_block(self):
        """AC4：fetch 失败 → record_failure 落死信；其余条目正常采集不阻断。"""
        from unittest.mock import MagicMock

        repo = MagicMock()
        repo.save_batch.return_value = []
        items, _ = collect_source(
            _fail_source(), http=None, snapshots=None, repository=repo  # type: ignore[arg-type]
        )
        # 失败的 boom 不在 items，其余两条入
        assert len(items) == 2
        assert all("boom" not in i.url for i in items)
        # record_failure 被调用一次（boom 那条），原因含异常类型
        assert repo.record_failure.call_count == 1
        call = repo.record_failure.call_args
        assert call.kwargs["url"] == "http://x/boom"
        assert "ConnectionError" in call.kwargs["reason"]
        assert call.kwargs["source_id"] == "test_fail_src"

    def test_no_repo_no_failure_recording(self):
        """未传 repository 时 fetch 失败不抛、不记录（仅跳过）。"""
        items, _ = collect_source(
            _fail_source(), http=None, snapshots=None, repository=None  # type: ignore[arg-type]
        )
        assert len(items) == 2

    def test_none_detail_skipped_no_failure_row(self):
        """fetch_detail 返回 None（robots 拒绝/无快照）：无快照不入库，不落死信行。"""
        from unittest.mock import MagicMock

        class _NoneAdapter(_FakeAdapter):
            DETAIL_URLS = ["http://x/1", "http://x/2"]

            def fetch_detail(self, url: str, source: SourceConfig) -> RawItem | None:
                return None

        _NoneAdapter.DETAIL_URLS = ["http://x/1", "http://x/2"]
        # register under test_run_src 已有 _FakeAdapter；此处直接构造走 get_adapter 不便，
        # 改用显式编排：传 repository 验证不调 record_failure
        repo = MagicMock()
        repo.save_batch.return_value = []
        # 用 _FakeAdapter 但 monkeypatch fetch_detail 返回 None
        original = _FakeAdapter.fetch_detail

        def _none(self, url, source):  # noqa: ANN001
            return None

        _FakeAdapter.fetch_detail = _none  # type: ignore[assignment]
        try:
            items, _ = collect_source(
                _source(enabled=True), http=None, snapshots=None, repository=repo  # type: ignore[arg-type]
            )
        finally:
            _FakeAdapter.fetch_detail = original  # type: ignore[assignment]
        assert items == []
        repo.record_failure.assert_not_called()
        repo.save_batch.assert_not_called()
