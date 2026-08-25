"""httpclient 单元测试（T5）——重试、节流、4xx 不重试。

用假 httpx.Client 替换，不触真实网络；节流 gap 设极小避免拖慢测试。
"""
from __future__ import annotations

import httpx
import pytest

from pih.collect.httpclient import HttpClient


class _FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code
        self.text = f"body-{status_code}"
        self.content = self.text.encode()
        self.headers = {"Content-Type": "text/html"}


class _FakeHttpxClient:
    """假 httpx.Client：按序列响应或异常。"""

    def __init__(self, behaviors: list):
        """behaviors: 每次调用的返回（_FakeResponse 或 Exception 实例/类）。"""
        self._behaviors = list(behaviors)
        self.calls = 0

    def get(self, url):
        if self.calls >= len(self._behaviors):
            raise AssertionError(f"意外第 {self.calls + 1} 次调用 {url}")
        b = self._behaviors[self.calls]
        self.calls += 1
        if isinstance(b, Exception):
            raise b
        if isinstance(b, type) and issubclass(b, Exception):
            raise b("fake")
        return b

    def close(self):
        pass


def _patch_client(hc: HttpClient, fake: _FakeHttpxClient) -> None:
    hc._client = fake  # type: ignore[attr-defined]


class TestRetry:
    def test_200_first_try(self):
        hc = HttpClient(gap_seconds=0, max_retries=3)
        fake = _FakeHttpxClient([_FakeResponse(200)])
        _patch_client(hc, fake)
        resp = hc.get("https://example.com/a")
        assert resp.status_code == 200
        assert fake.calls == 1

    def test_500_retries_then_succeeds(self):
        hc = HttpClient(gap_seconds=0, max_retries=3)
        fake = _FakeHttpxClient([_FakeResponse(500), _FakeResponse(500), _FakeResponse(200)])
        _patch_client(hc, fake)
        resp = hc.get("https://example.com/a")
        assert resp.status_code == 200
        assert fake.calls == 3

    def test_4xx_no_retry(self):
        hc = HttpClient(gap_seconds=0, max_retries=3)
        fake = _FakeHttpxClient([_FakeResponse(404)])
        _patch_client(hc, fake)
        resp = hc.get("https://example.com/a")
        assert resp.status_code == 404
        assert fake.calls == 1

    def test_network_error_retries_then_raises(self):
        hc = HttpClient(gap_seconds=0, max_retries=2)
        fake = _FakeHttpxClient([httpx.ConnectError, httpx.ConnectError, httpx.ConnectError])
        _patch_client(hc, fake)
        with pytest.raises(httpx.ConnectError):
            hc.get("https://example.com/a")
        assert fake.calls == 3  # 初试 + 2 重试

    def test_network_error_retries_then_succeeds(self):
        hc = HttpClient(gap_seconds=0, max_retries=3)
        fake = _FakeHttpxClient([httpx.ConnectTimeout, _FakeResponse(200)])
        _patch_client(hc, fake)
        resp = hc.get("https://example.com/a")
        assert resp.status_code == 200
        assert fake.calls == 2


class TestThrottle:
    def test_throttle_sleeps_between_same_host(self, monkeypatch):
        """同 host 第二次请求前应触发节流 sleep。"""
        slept = []
        monkeypatch.setattr("pih.collect.httpclient.time.sleep", lambda s: slept.append(s))
        hc = HttpClient(gap_seconds=2.0, max_retries=0)
        fake = _FakeHttpxClient([_FakeResponse(200), _FakeResponse(200)])
        _patch_client(hc, fake)
        hc.get("https://example.com/a")
        hc.get("https://example.com/b")
        # 第二次请求距第一次 < 2s，应 sleep 补齐
        assert any(s > 0 for s in slept)
