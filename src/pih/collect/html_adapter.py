"""HTML 信源适配器基类（架构 §4 COLLECT 层）。

通用 HTML 抓取流程：robots 检查 → 节流 GET → 解码链 → selectolax 解析。
三源（CCMA/三一/cehome）共用此基类，差异在解析钩子（子类覆盖）：
- extract_detail_urls：列表页详情链接提取
- extract_title：详情页标题
- is_valid_page：存在性判定（CCMA 软 200 需内容判定）
"""
from __future__ import annotations

from datetime import UTC, datetime

from selectolax.parser import HTMLParser

from .base import SourceAdapter, SourceConfig, register
from .encoding import decode_full
from .httpclient import HttpClient
from .rawitem import RawItem, content_fingerprint
from .robots import fetch_robots_ok
from .snapshot import SnapshotMeta, SnapshotStore


@register
class HtmlAdapter(SourceAdapter):
    """HTML 信源通用适配器。子类覆盖解析钩子。"""

    type = "html"

    def __init__(self, http: HttpClient, snapshots: SnapshotStore) -> None:
        self.http = http
        self.snapshots = snapshots

    # ---- 子类覆盖的解析钩子 ----

    def extract_detail_urls(self, html: str, list_url: str) -> list[str]:
        """从列表页 HTML 提取详情 URL（绝对 URL）。子类须实现。"""
        raise NotImplementedError

    def extract_title(self, html: str) -> str:
        """从详情页 HTML 提取标题。子类须实现。"""
        raise NotImplementedError

    def is_valid_page(self, html: str) -> bool:
        """详情页存在性判定。默认：有 <title> 非空即真。

        CCMA 软 200 站点须子类覆盖为内容判定（看详情链接模式）。
        """
        tree = HTMLParser(html)
        title = tree.css_first("title")
        return title is not None and bool(title.text(strip=True))

    # ---- 通用流程 ----

    def fetch_list(self, source: SourceConfig) -> list[str]:
        robots = fetch_robots_ok(source.list_url, client=self.http._client)
        if not robots.allowed:
            return []
        resp = self.http.get(source.list_url)
        if resp.status_code != 200:
            return []
        text, _ = decode_full(resp.content, resp.headers.get("Content-Type", ""))
        return self.extract_detail_urls(text, source.list_url)

    def fetch_detail(self, url: str, source: SourceConfig) -> RawItem | None:
        robots = fetch_robots_ok(url, client=self.http._client)
        if not robots.allowed:
            return None
        resp = self.http.get(url)
        if resp.status_code != 200:
            return None
        raw_bytes = resp.content
        text, encoding = decode_full(raw_bytes, resp.headers.get("Content-Type", ""))
        if not self.is_valid_page(text):
            return None  # 软 200 / 非详情页
        title = self.extract_title(text)
        fetched_at = datetime.now(UTC).isoformat()
        sha = content_fingerprint(raw_bytes)
        meta = SnapshotMeta(
            source_id=source.id,
            url=url,
            fetched_at=fetched_at,
            http_status=resp.status_code,
            content_type=resp.headers.get("Content-Type", ""),
            encoding=encoding,
            content_sha1=sha,
        )
        self.snapshots.archive(source.id, raw_bytes, meta)
        return RawItem(
            source_id=source.id,
            url=url,
            title=title,
            list_url=source.list_url,
            fetched_at=fetched_at,
            http_status=resp.status_code,
            content_type=resp.headers.get("Content-Type", ""),
            encoding=encoding,
            raw_html=text,
            snapshot_id=sha,
            content_sha1=sha,
        )
