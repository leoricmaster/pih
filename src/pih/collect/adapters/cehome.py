"""铁甲网适配器（cehome.com，L2，SPK-1 §4 主选）。

契约（subagent 实测）：
- SSR XHTML，robots allow: / 全站允许
- 详情链接 /news/<YYYYMMDD>/<id>.shtml，列表 /news/hangye/，路径分页 /<N>/
- 编码 utf-8（非 GBK——SPK-1 报告措辞错误；真实缺陷是 HTTP 头缺 charset，
  解码链 header→meta→trial 正确落到 utf-8，本适配器不为 cehome 硬编码编码）
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from ..base import register_for_source
from ..html_adapter import HtmlAdapter

DETAIL_RE = re.compile(r"/news/20\d{6}/\d+\.shtml")


@register_for_source("cehome")
class CehomeAdapter(HtmlAdapter):
    def extract_detail_urls(self, html: str, list_url: str) -> list[str]:
        tree = HTMLParser(html)
        seen, urls = set(), []
        for node in tree.css('a[href]'):
            href = node.attributes.get("href") or ""
            if DETAIL_RE.search(href):
                full = urljoin(list_url, href)
                if full not in seen:
                    seen.add(full)
                    urls.append(full)
        return urls

    def extract_title(self, html: str) -> str:
        tree = HTMLParser(html)
        title = tree.css_first("title")
        return title.text(strip=True) if title else ""
