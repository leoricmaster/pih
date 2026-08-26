"""CCMA 协会适配器（cncma.org，L2，SPK-1 §4 主选）。

契约（subagent 实测）：
- scheme http only（https 25s 超时）
- robots 软 200（HTML 模板，无指令）→ robots 模块判无效 + 告警，按未声明处理
- 详情链接 /article/<id>，列表 /col/hangyxw，分页 ?pageIndex=N
- 软 200 存在性判定：看正文是否含 /article/\d+ 自链接（非模板页）
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from ..base import register_for_source
from ..html_adapter import HtmlAdapter

DETAIL_RE = re.compile(r"/article/\d+")


@register_for_source("ccma")
class CcmaAdapter(HtmlAdapter):
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

    def is_valid_page(self, html: str) -> bool:
        r"""软 200 判定：真实详情页含 /article/\d+ 自链接 + 非空 title。"""
        if not super().is_valid_page(html):
            return False
        return bool(DETAIL_RE.search(html))
