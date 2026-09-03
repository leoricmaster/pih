"""QueryService 单测（ADR-006 同源）。

验：filters → repo.list_by_filter 参数透传 + next_before 游标拼装 + get 委托。
不连 DB——repo 用 MagicMock。
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from pih.consume.query_service import IntelFilters, QueryService
from pih.store.repository import IntelRecord


def _make_record(
    *,
    id: int = 1,
    fetched_at: datetime | None = None,
    subject: str | None = "三一",
    event_type: str | None = "新品发布",
    admiralty_code: str | None = "B2",
) -> IntelRecord:
    """造一条最小可用的 IntelRecord（仅填断言用到的字段）。"""
    return IntelRecord(
        id=id,
        source_id="sany_news",
        url="https://example.com/x",
        title="测试情报",
        list_url="https://example.com/list",
        fetched_at=fetched_at or datetime(2026, 8, 27, 12, 0, 0),
        http_status=200,
        content_type="text/html",
        encoding="utf-8",
        snapshot_id="snap001",
        content_sha1="sha001",
        raw_html="<html/>",
        event_id=None,
        created_at=datetime(2026, 8, 27, 12, 0, 5),
        subject=subject,
        event_type=event_type,
        facts="事实",
        inferences="推断",
        tags=["电动化"],
        quant_params={},
        admiralty_code=admiralty_code,
        process_status="extracted",
        process_error=None,
        process_meta=None,
        processed_at=datetime(2026, 8, 27, 12, 5, 0),
    )


class TestListPassesFilters:
    def test_all_fields_forwarded(self):
        repo = MagicMock()
        repo.list_by_filter.return_value = []
        svc = QueryService(repo)

        since = datetime(2026, 5, 1)
        until = datetime(2026, 8, 27)
        before = datetime(2026, 8, 26)
        filters = IntelFilters(
            subject="三一",
            event_type="新品发布",
            tag="电动化",
            admiralty="B2",
            source_id="sany_news",
            process_status="needs_manual",
            since=since,
            until=until,
            before=before,
            limit=20,
        )
        svc.list(filters)

        repo.list_by_filter.assert_called_once_with(
            subject="三一",
            event_type="新品发布",
            tag="电动化",
            admiralty="B2",
            source_id="sany_news",
            process_status="needs_manual",
            event_status=None,
            since=since,
            until=until,
            before=before,
            limit=20,
            ranking=None,
        )

    def test_defaults_limit_50(self):
        repo = MagicMock()
        repo.list_by_filter.return_value = []
        svc = QueryService(repo)

        svc.list(IntelFilters())

        _, kwargs = repo.list_by_filter.call_args
        assert kwargs["limit"] == 50

    def test_defaults_process_status_to_extracted(self):
        """ADR-011 检索视图：process_status 未给定时默认 extracted（成品）。"""
        repo = MagicMock()
        repo.list_by_filter.return_value = []
        svc = QueryService(repo)

        svc.list(IntelFilters())  # process_status=None

        _, kwargs = repo.list_by_filter.call_args
        assert kwargs["process_status"] == "extracted"

    def test_explicit_status_overrides_default(self):
        """显式 process_status 覆盖默认（needs_manual 复核队列可达，TASK-1.02.01 AC3）。"""
        repo = MagicMock()
        repo.list_by_filter.return_value = []
        svc = QueryService(repo)

        svc.list(IntelFilters(process_status="needs_manual"))

        _, kwargs = repo.list_by_filter.call_args
        assert kwargs["process_status"] == "needs_manual"


class TestNextBeforeCursor:
    def test_full_page_emits_next_before(self):
        repo = MagicMock()
        records = [
            _make_record(id=i, fetched_at=datetime(2026, 8, 27, 12, i, 0))
            for i in range(10)
        ]
        repo.list_by_filter.return_value = records
        svc = QueryService(repo)

        result = svc.list(IntelFilters(limit=10))

        assert result.next_before == records[-1].fetched_at.isoformat()

    def test_partial_page_no_next_before(self):
        repo = MagicMock()
        records = [_make_record(id=1) for _ in range(3)]
        repo.list_by_filter.return_value = records
        svc = QueryService(repo)

        result = svc.list(IntelFilters(limit=10))

        assert result.next_before is None

    def test_empty_page_no_next_before(self):
        repo = MagicMock()
        repo.list_by_filter.return_value = []
        svc = QueryService(repo)

        result = svc.list(IntelFilters(limit=10))

        assert result.next_before is None
        assert result.items == []


class TestGet:
    def test_delegates_to_repo(self):
        repo = MagicMock()
        rec = _make_record(id=42)
        repo.get.return_value = rec
        svc = QueryService(repo)

        assert svc.get(42) is rec
        repo.get.assert_called_once_with(42)

    def test_returns_none_when_missing(self):
        repo = MagicMock()
        repo.get.return_value = None
        svc = QueryService(repo)

        assert svc.get(999) is None


class TestFiltersNonempty:
    def test_only_non_null_fields(self):
        since = datetime(2026, 5, 1)
        filters = IntelFilters(subject="三一", since=since)

        nonempty = filters.nonempty()

        assert nonempty == {
            "subject": "三一",
            "since": since.isoformat(),
        }

    def test_empty_filters_yields_empty_dict(self):
        assert IntelFilters().nonempty() == {}
