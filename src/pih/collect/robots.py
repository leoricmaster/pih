"""robots.txt 合规判定（架构 §4 采集层 / 实测 robots 契约）。

robots.txt 判定逻辑，两点修正：
1. 软 200 站点（如 CCMA）robots.txt 返回 200 但 Content-Type 为 HTML——
   `urllib.robotparser` 会把 HTML 模板当空规则集（全允许），无法区分「无 robots」
   与「软 200 HTML」。本模块加 content-type 嗅探：非 text/plain 的 200 robots
   视为「无效 robots」按未声明处理（允许）并置 invalid_robots=True 告警。
2. 节流由 httpclient 层统一管（调用 robots 前后 sleep），本模块不 sleep，保持纯可测。
"""
from __future__ import annotations

import urllib.robotparser
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

UA = "pih-collector/0.1 (+https://repo; contact: repo owner)"


@dataclass(frozen=True)
class RobotsResult:
    """robots 检查结果。

    Attributes:
        allowed: 是否允许抓取
        note: 人类可读说明（含 robots 正文前 200 字，便于追溯）
        invalid_robots: robots 是否无效（软 200：200 但非 text/plain）。True 时
            allowed 仍为 True（按未声明处理），但调用方应记录告警。
    """

    allowed: bool
    note: str
    invalid_robots: bool = False


def robots_allows(robots_txt: str, url: str, base_url: str, user_agent: str = "*") -> bool:
    """按 robots.txt 规则判定 url 是否允许抓取（纯函数，无网络）。"""
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(robots_txt.splitlines())
    return rp.can_fetch(user_agent, url)


def _is_text_plain_robots(content_type: str) -> bool:
    """robots.txt 的 Content-Type 是否为 text/plain（有效 robots 的必要条件）。

    软 200 站点（CCMA）返回 text/html，非有效 robots。
    """
    ct = content_type.split(";")[0].strip().lower()
    return ct in ("text/plain", "")


def fetch_robots_ok(
    url: str,
    client: httpx.Client | None = None,
    timeout: float = 10.0,
) -> RobotsResult:
    """抓取前检查：拉取 url 所在站点的 robots.txt 并判定。

    robots.txt 404/空视为全允许（标准行为）；
    200 但非 text/plain（软 200）视为无效 robots，按未声明处理 + 告警；
    网络错误/非 200 保守判定不允许。
    节流由调用方（httpclient）在调用前后保证，本函数不 sleep。
    """
    parts = urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    own_client = client is None
    if own_client:
        client = httpx.Client(headers={"User-Agent": UA}, timeout=timeout)
    try:
        resp = client.get(robots_url)
    except httpx.HTTPError as exc:
        return RobotsResult(
            False,
            f"robots.txt 获取失败（{type(exc).__name__}），保守判定不允许",
        )
    finally:
        if own_client:
            client.close()

    if resp.status_code == 404:
        return RobotsResult(True, "robots.txt 不存在（404），视为允许")
    if resp.status_code != 200:
        return RobotsResult(
            False,
            f"robots.txt HTTP {resp.status_code}，保守判定不允许",
        )

    content_type = resp.headers.get("Content-Type", "")
    if not _is_text_plain_robots(content_type):
        # 软 200：CCMA 这类站点任意路径返 200 HTML，robots 体是模板页
        return RobotsResult(
            True,
            f"无效 robots（软 200：Content-Type={content_type or '空'}，正文非 robots 指令），"
            f"按未声明处理（正文前 200 字：{resp.text[:200]!r}）",
            invalid_robots=True,
        )

    ok = robots_allows(resp.text, url, robots_url)
    note = "允许" if ok else "robots.txt 禁止抓取该路径"
    return RobotsResult(True if ok else False, f"robots.txt 判定：{note}")
