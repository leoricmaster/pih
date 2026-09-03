"""probe 模块单元测试——细粒度报告与失败原因可辨，不触网络（假 client + HTML 夹具）。

fake client 按 URL 分派响应；robots 用真实 fetch_robots_ok 逻辑
（CCMA 软 200 → 允许 + 告警，顺带覆盖告警文案）。
"""
from __future__ import annotations

from pathlib import Path

import pih.collect.adapters  # noqa: F401  触发注册
from pih.collect.base import SourceConfig
from pih.collect.httpclient import HttpClient
from pih.collect.probe import NullSnapshotStore, probe_source
from pih.collect.snapshot import SnapshotMeta

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "html"

CCMA_SOFT200_ROBOTS = "<html><head><title>协会</title></head><body>导航模板</body></html>"
EMPTY_LIST = "<html><head><title>列表</title></head><body>无链接</body></html>"
TEMPLATE_DETAIL = "<html><head><title>协会</title></head><body>导航</body></html>"


class _Resp:
    def __init__(self, status: int, body: str, content_type: str = "text/html"):
        self.status_code = status
        self.content = body.encode("utf-8")
        self.text = body
        self.headers = {"Content-Type": content_type}


class _FakeClient:
    """按 URL 精确匹配分派；未匹配 URL 返回软 200 模板（模拟 CCMA 行为）。"""

    def __init__(self, mapping: dict[str, _Resp]):
        self.mapping = mapping
        self.calls: list[str] = []

    def get(self, url: str) -> _Resp:
        self.calls.append(url)
        return self.mapping.get(url) or _Resp(200, CCMA_SOFT200_ROBOTS)

    def close(self):
        pass


class _FakeSnapshots:
    def __init__(self):
        self.archived: list[tuple[str, SnapshotMeta]] = []

    def archive(self, source_id: str, raw_bytes: bytes, meta: SnapshotMeta) -> str:
        self.archived.append((source_id, meta))
        return meta.content_sha1

    def exists(self, source_id: str, content_sha1: str) -> bool:
        return True


LIST_URL = "http://www.cncma.org/col/hangyxw"
DETAIL_URL = "http://www.cncma.org/article/22709"


def _source() -> SourceConfig:
    return SourceConfig(
        id="ccma", name="测试", type="html", url="http://www.cncma.org/",
        list_url=LIST_URL, reliability="B", level="L2", enabled=False,
    )


def _http(mapping: dict[str, _Resp]) -> tuple[HttpClient, _FakeClient]:
    hc = HttpClient(gap_seconds=0, max_retries=0)
    fake = _FakeClient(mapping)
    hc._client = fake  # type: ignore[attr-defined]
    return hc, fake


def _mapping(list_body: str, detail_body: str | None) -> dict[str, _Resp]:
    robots = {"http://www.cncma.org/robots.txt": _Resp(200, CCMA_SOFT200_ROBOTS)}
    m = {**robots, LIST_URL: _Resp(200, list_body)}
    if detail_body is not None:
        m[DETAIL_URL] = _Resp(200, detail_body)
    return m


class TestProbeSuccess:
    def test_full_pass(self):
        list_html = (FIXTURES / "ccma_list.html").read_text(encoding="utf-8")
        detail_html = (FIXTURES / "ccma_detail.html").read_text(encoding="utf-8")
        hc, fake = _http(_mapping(list_html, detail_html))
        snaps = _FakeSnapshots()
        report = probe_source(_source(), hc, snaps, details=1)
        assert report.success is True
        assert report.robots_allowed is True
        assert "告警" in report.robots_note  # 软 200 robots → 允许 + 告警
        assert report.list_ok is True
        assert "3 条详情链接" in report.list_note
        d = report.detail_results[0]
        assert d.ok is True
        assert d.url == DETAIL_URL
        assert "工程机械" in d.title
        assert len(d.snapshot_id) == 40
        assert snaps.archived and snaps.archived[0][0] == "ccma"

    def test_null_snapshot_store(self):
        list_html = (FIXTURES / "ccma_list.html").read_text(encoding="utf-8")
        detail_html = (FIXTURES / "ccma_detail.html").read_text(encoding="utf-8")
        hc, _ = _http(_mapping(list_html, detail_html))
        report = probe_source(_source(), hc, NullSnapshotStore(), details=1)
        assert report.success is True
        assert len(report.detail_results[0].snapshot_id) == 40  # 指纹仍产出

    def test_soft200_robots_sets_structured_warn_flag(self):
        """软 200 robots：允许但置结构化告警位（web 结论行聚合用，验收反馈修复）。"""
        list_html = (FIXTURES / "ccma_list.html").read_text(encoding="utf-8")
        detail_html = (FIXTURES / "ccma_detail.html").read_text(encoding="utf-8")
        hc, _ = _http(_mapping(list_html, detail_html))
        report = probe_source(_source(), hc, _FakeSnapshots(), details=1)
        assert report.robots_invalid is True


class TestProbeFailures:
    def test_robots_disallowed_skips_list(self):
        robots = _Resp(200, "User-agent: *\nDisallow: /", content_type="text/plain")
        hc, fake = _http({"http://www.cncma.org/robots.txt": robots})
        report = probe_source(_source(), hc, _FakeSnapshots())
        assert report.success is False
        assert report.robots_allowed is False
        assert "robots 不允许" in report.list_note
        assert fake.calls == ["http://www.cncma.org/robots.txt"]  # 未发起列表请求

    def test_list_non_200(self):
        hc, _ = _http({LIST_URL: _Resp(404, "not found")})
        report = probe_source(_source(), hc, _FakeSnapshots())
        assert report.success is False
        assert "404" in report.list_note

    def test_list_zero_links(self):
        hc, _ = _http(_mapping(EMPTY_LIST, None))
        report = probe_source(_source(), hc, _FakeSnapshots())
        assert report.success is False
        assert report.list_ok is False
        assert "0 条详情链接" in report.list_note

    def test_detail_soft200_template(self):
        list_html = (FIXTURES / "ccma_list.html").read_text(encoding="utf-8")
        hc, _ = _http(_mapping(list_html, TEMPLATE_DETAIL))
        report = probe_source(_source(), hc, _FakeSnapshots())
        assert report.success is False
        assert report.list_ok is True  # 列表正常，详情被软 200 判定拦截
        d = report.detail_results[0]
        assert d.ok is False
        assert "未产出" in d.note
