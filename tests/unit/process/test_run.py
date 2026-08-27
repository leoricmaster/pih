"""ProcessRunner 单元测试：mock repository + fake chat（Sprint 4 T6）。

覆盖：三状态映射、Admiralty 拼装、token 聚合、写库失败容错、统计行格式。
"""
from __future__ import annotations

from unittest.mock import MagicMock

from pih.process.run import ProcessRunner, RunnerStats, assemble_admiralty
from pih.store.repository import (
    STATUS_EXTRACTED,
    STATUS_FILTERED_OUT,
    STATUS_NEEDS_MANUAL,
    IntelRecord,
    ProcessResult,
)

PACK = {
    "meta": {"domain_id": "test_domain", "display_name": "测试行业", "version": "0.1.0"},
    "event_types": ["新品发布", "财报", "其他"],
    "tag_tree": {"技术特征": ["电动化", "远程遥控"]},
    "competitors": [{"id": "sany", "display_name": "三一", "aliases": ["三一重工"]}],
    "extraction_prompt": "抽取提示词：<事件类型> <标签树> <主体清单>",
}


def _ok_pred() -> dict:
    return {
        "主体": "三一",
        "事件类型": "新品发布",
        "事实描述": "销量 1000 台",
        "推断与判断": "依据：正文销量",
        "标签": ["电动化"],
        "量化参数": {"销量": "1000台"},
        "信息可信度": "2",
    }


def _usage(p: int = 100, c: int = 50, r: int = 0) -> dict:
    return {"prompt_tokens": p, "completion_tokens": c, "retries": r}


class FakeChat:
    def __init__(self, responses: list) -> None:
        self.responses = list(responses)

    def __call__(self, messages: list[dict], tier: str):
        resp = self.responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


def _rec(rid: int = 1, reliability: str = "B") -> IntelRecord:
    return IntelRecord(
        id=rid, source_id="ccma", url=f"http://x/{rid}", title="标题",
        list_url="http://x/list", fetched_at="2026-08-27T10:00:00+00:00",
        http_status=200, content_type="text/html", encoding="utf-8",
        snapshot_id=f"sha{rid}", content_sha1=f"sha{rid}",
        raw_html="<p>三一发布新品挖掘机，销量 1000 台</p>",
        event_id=None, created_at="2026-08-27T10:00:00+00:00",
        process_status="pending", source_reliability=reliability,
    )


def _repo(records: list[IntelRecord]) -> tuple[MagicMock, list[ProcessResult]]:
    """mock repository：list_pending 返回脚本条目，捕获 write_process_result。"""
    repo = MagicMock()
    repo.list_pending.return_value = records
    written: list[ProcessResult] = []
    repo.write_process_result.side_effect = lambda i, r: written.append((i, r))
    return repo, written


class TestAssembleAdmiralty:
    def test_b2(self):
        assert assemble_admiralty("B", "2") == "B2"

    def test_a1(self):
        assert assemble_admiralty("A", "1") == "A1"


class TestRunnerStatusMapping:
    def test_extracted_with_admiralty(self):
        repo, written = _repo([_rec(reliability="B")])
        chat = FakeChat([
            ({"relevant": True}, _usage(10, 5)),
            (_ok_pred(), _usage(100, 60)),
        ])
        stats = ProcessRunner(repo, PACK, chat=chat).run()
        assert stats.extracted == 1
        intel_id, result = written[0]
        assert intel_id == 1
        assert result.status == STATUS_EXTRACTED
        assert result.admiralty_code == "B2"  # ccma reliability B × 可信度 2
        assert result.subject == "三一"
        assert result.tags == ["电动化"]
        assert stats.prompt_tokens == 110
        assert stats.completion_tokens == 65

    def test_filtered_out(self):
        repo, written = _repo([_rec()])
        chat = FakeChat([({"relevant": False}, _usage())])
        stats = ProcessRunner(repo, PACK, chat=chat).run()
        assert stats.filtered_out == 1
        _, result = written[0]
        assert result.status == STATUS_FILTERED_OUT
        assert result.subject is None
        assert "粗筛" in result.error

    def test_needs_manual_after_exhausted_rounds(self):
        repo, written = _repo([_rec()])
        bad = _ok_pred() | {"事件类型": "瞎写"}
        chat = FakeChat([
            ({"relevant": True}, _usage()),
            (bad, _usage()), (bad, _usage()), (bad, _usage()), (bad, _usage()),
        ])
        stats = ProcessRunner(repo, PACK, chat=chat).run()
        assert stats.needs_manual == 1
        _, result = written[0]
        assert result.status == STATUS_NEEDS_MANUAL
        assert result.subject is None
        assert "瞎写" in result.error

    def test_graph_exception_maps_to_needs_manual(self):
        """图级意外异常（如配置错抛出）→ needs_manual 不崩批处理。"""
        repo, written = _repo([_rec(1), _rec(2)])
        responses = [
            ValueError("意外"),
            ({"relevant": True}, _usage()),
            (_ok_pred(), _usage()),
        ]
        stats = ProcessRunner(repo, PACK, chat=FakeChat(responses)).run()
        assert stats.needs_manual == 1
        assert stats.extracted == 1
        assert "graph:" in written[0][1].error

    def test_write_failure_counted_failed_not_blocking(self):
        """写库失败：计 failed，后续条目继续。"""
        repo, written = _repo([_rec(1), _rec(2)])
        calls = {"n": 0}

        def _write(intel_id: int, result: ProcessResult) -> None:
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("db down")
            written.append((intel_id, result))

        repo.write_process_result.side_effect = _write
        chat = FakeChat([
            ({"relevant": True}, _usage()),
            (_ok_pred(), _usage()),
            ({"relevant": True}, _usage()),
            (_ok_pred(), _usage()),
        ])
        stats = ProcessRunner(repo, PACK, chat=chat).run()
        assert stats.failed == 1
        assert stats.extracted == 1
        assert len(written) == 1 and written[0][0] == 2


class TestRunnerStats:
    def test_summary_line_format(self):
        stats = RunnerStats(total=5, extracted=3, filtered_out=1, needs_manual=1, failed=0)
        line = stats.summary_line()
        assert "处理 5 条" in line
        assert "抽取成功 3" in line
        assert "粗筛丢弃 1" in line
        assert "待人工 1" in line

    def test_token_line_format(self):
        line = RunnerStats(prompt_tokens=12345, completion_tokens=6789).token_line()
        assert "12,345" in line and "6,789" in line

    def test_empty_batch(self):
        repo, _ = _repo([])
        stats = ProcessRunner(repo, PACK, chat=FakeChat([])).run()
        assert stats.total == 0
        assert stats.summary_line().startswith("处理 0 条")
