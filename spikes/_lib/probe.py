"""SPK-1 共享工具：robots 合规判定与礼貌抓取。

Spike 代码，非工程代码——接口定义以 docs/Architecture.md §4 为准。
"""
from __future__ import annotations

import urllib.robotparser
from urllib.parse import urlsplit

import requests

UA = "pih-spike/0.1 (+research; contact: repo owner)"


def robots_allows(robots_txt: str, url: str, base_url: str, user_agent: str = "*") -> bool:
    """按 robots.txt 规则判定 url 是否允许抓取（纯函数，无网络）。"""
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(robots_txt.splitlines())
    return rp.can_fetch(user_agent, url)


def fetch_robots_ok(url: str, timeout: int = 10) -> tuple[bool, str]:
    """抓取前检查：拉取 url 所在站点的 robots.txt 并判定。

    返回 (允许, 说明)。robots.txt 404/空视为全允许（标准行为）；
    网络错误时返回 (False, 原因)——保守处理，宁可放过不抓。
    """
    parts = urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        resp = requests.get(robots_url, timeout=timeout, headers={"User-Agent": UA})
    except requests.RequestException as exc:
        return False, f"robots.txt 获取失败（网络错误：{type(exc).__name__}），保守判定不允许"
    if resp.status_code == 404:
        return True, "robots.txt 不存在（404），视为允许"
    if resp.status_code != 200:
        return False, f"robots.txt HTTP {resp.status_code}，保守判定不允许"
    ok = robots_allows(resp.text, url, robots_url)
    note = "允许" if ok else "robots.txt 禁止抓取该路径"
    return ok, f"robots.txt 判定：{note}（来源 {robots_url}，正文前 200 字：{resp.text[:200]!r}）"


def polite_get(url: str, timeout: int = 10) -> requests.Response:
    """单次 GET：带声明式 UA，不重试（重试由调用方按指数退避决定）。"""
    return requests.get(url, timeout=timeout, headers={"User-Agent": UA})
