"""robots 合规单元测试（T4）。

覆盖 AC2：CCMA 软 200 robots（200 但 text/html）→ 无效 robots 判定 + 告警。
网络部分用假 client 注入，不触真实网络。
"""
from __future__ import annotations

from pih.collect.robots import fetch_robots_ok, robots_allows

SITE = "https://example.com"
ROBOTS_DISALLOW = "User-agent: *\nDisallow: /private/\nAllow: /public/\n"
ROBOTS_EMPTY = ""
ROBOTS_ALLOW_ALL = "User-agent: *\nallow: /\n"


class TestRobotsAllowsPure:
    """继承 spike probe 的纯函数行为。"""

    def test_disallowed_rejected(self):
        assert robots_allows(ROBOTS_DISALLOW, f"{SITE}/private/x", SITE) is False

    def test_allowed_ok(self):
        assert robots_allows(ROBOTS_DISALLOW, f"{SITE}/public/y", SITE) is True

    def test_unlisted_defaults_allowed(self):
        assert robots_allows(ROBOTS_DISALLOW, f"{SITE}/news/z", SITE) is True

    def test_empty_allows_all(self):
        assert robots_allows(ROBOTS_EMPTY, f"{SITE}/anything", SITE) is True

    def test_allow_all_directive(self):
        assert robots_allows(ROBOTS_ALLOW_ALL, f"{SITE}/news/1", SITE) is True

    def test_specific_ua_overrides_star(self):
        robots = "User-agent: pih-collector\nDisallow: /\nUser-agent: *\nAllow: /"
        assert robots_allows(robots, f"{SITE}/a", SITE, user_agent="pih-collector") is False
        assert robots_allows(robots, f"{SITE}/a", SITE, user_agent="other") is True


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "", content_type: str = "text/plain"):
        self.status_code = status_code
        self.text = text
        self.headers = {"Content-Type": content_type}


class _FakeClient:
    """假 httpx.Client：按预置响应返回。"""

    def __init__(self, responses: dict[str, _FakeResponse]):
        self._responses = responses
        self.closed = False

    def get(self, url):
        if url not in self._responses:
            raise KeyError(f"未预置响应：{url}")
        return self._responses[url]

    def close(self):
        self.closed = True


ROBOTS_URL = f"{SITE}/robots.txt"


class TestFetchRobotsOk:
    def test_404_allows(self):
        client = _FakeClient({ROBOTS_URL: _FakeResponse(404)})
        r = fetch_robots_ok(f"{SITE}/news/1", client=client)
        assert r.allowed is True
        assert r.invalid_robots is False

    def test_text_plain_robots_parsed(self):
        client = _FakeClient({ROBOTS_URL: _FakeResponse(200, ROBOTS_DISALLOW)})
        r = fetch_robots_ok(f"{SITE}/news/1", client=client)
        assert r.allowed is True  # /news 未被 Disallow
        assert r.invalid_robots is False

    def test_text_plain_disallow_blocked(self):
        client = _FakeClient({ROBOTS_URL: _FakeResponse(200, ROBOTS_DISALLOW)})
        r = fetch_robots_ok(f"{SITE}/private/x", client=client)
        assert r.allowed is False
        assert r.invalid_robots is False

    def test_ac2_soft200_html_robots_invalid(self):
        """AC2 核心用例：CCMA 软 200——robots 200 但 Content-Type=text/html。

        判定：允许（按未声明处理）+ invalid_robots=True（告警）。
        """
        html_body = "<html><title>站点模板</title></html>"
        client = _FakeClient({
            ROBOTS_URL: _FakeResponse(200, html_body, "text/html; charset=utf-8"),
        })
        r = fetch_robots_ok(f"{SITE}/article/123", client=client)
        assert r.allowed is True
        assert r.invalid_robots is True
        assert "软 200" in r.note
        # 二轮验收反馈：结论与排查材料分层——note 面向用户；dump 只进 detail（CLI/日志）
        assert "正文前" not in r.note
        assert "text/html" in r.detail
        assert "正文前 200 字" in r.detail

    def test_non_200_rejected(self):
        client = _FakeClient({ROBOTS_URL: _FakeResponse(500)})
        r = fetch_robots_ok(f"{SITE}/news/1", client=client)
        assert r.allowed is False

    def test_network_error_rejected(self):
        class _ErrorClient:
            def get(self, url):
                import httpx

                raise httpx.ConnectError("connection refused")

            def close(self):
                pass

        r = fetch_robots_ok(f"{SITE}/news/1", client=_ErrorClient())
        assert r.allowed is False
