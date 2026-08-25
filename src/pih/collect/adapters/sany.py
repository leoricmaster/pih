"""三一集团适配器（sanygroup.com，L1，SPK-1 §4 主选）。

契约（subagent 实测）：
- Nuxt SSR（data-server-rendered，__NUXT__ JSON blob）
- 详情链接 /news/<id>.html，列表 /news，分页 ?page=N&size=6
- 标题 <title> 可能含 stray U+FEFF（须 strip）
- 排除 /product/ 等非新闻链接（spike 误抓产品页的教训）
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from ..base import register_for_source
from ..html_adapter import HtmlAdapter

DETAIL_RE = re.compile(r"/news/\d+\.html")
# 排除非新闻路径（spike 误抓 /product/ 的教训）
EXCLUDE_RE = re.compile(r"/(product|about|list|special|search|col)/")


@register_for_source("sany")
class SanyAdapter(HtmlAdapter):
    def extract_detail_urls(self, html: str, list_url: str) -> list[str]:
        tree = HTMLParser(html)
        seen, urls = set(), []
        for node in tree.css('a[href]'):
            href = node.attributes.get("href") or ""
            if not DETAIL_RE.search(href):
                continue
            if EXCLUDE_RE.search(href):
                continue
            full = urljoin(list_url, href)
            if full not in seen:
                seen.add(full)
                urls.append(full)
        return urls

    def extract_title(self, html: str) -> str:
        tree = HTMLParser(html)
        title = tree.css_first("title")
        if not title:
            return ""
        # strip stray U+FEFF（subagent 发现 Nuxt <title> 前导 BOM-like 字符）
        return title.text(strip=True).lstrip("﻿")
