"""集成测试：真实抓取三源（T7 / AC1/AC6）。

需 `docker compose up`（MinIO）+ 外网访问。@pytest.mark.integration。
断言只查结构（不查具体标题文本，防站点变更致 flaky）。
"""
from __future__ import annotations

import os

import pytest
from minio import Minio

# 触发子模块注册
import pih.collect.adapters.ccma  # noqa: F401
import pih.collect.adapters.cehome  # noqa: F401
import pih.collect.adapters.sany  # noqa: F401
from pih.collect.base import SourceConfig, get_adapter
from pih.collect.httpclient import HttpClient
from pih.collect.snapshot import SnapshotStore

pytestmark = pytest.mark.integration

MINIO_USER = os.environ.get("MINIO_ROOT_USER", "pih")
MINIO_PASS = os.environ.get("MINIO_ROOT_PASSWORD", "pih12345")


@pytest.fixture(scope="module")
def snapshot_store() -> SnapshotStore:
    client = Minio(
        "localhost:9000",
        access_key=MINIO_USER,
        secret_key=MINIO_PASS,
        secure=False,
    )
    return SnapshotStore(client)


@pytest.fixture(scope="module")
def http_client() -> HttpClient:
    return HttpClient(gap_seconds=2.0, max_retries=2)


def _source(sid: str, url: str, list_url: str, level: str) -> SourceConfig:
    return SourceConfig(
        id=sid, name=sid, type="html", url=url,
        list_url=list_url, reliability="B", level=level, fetch_frequency="daily",
    )


SOURCES = {
    "ccma": _source("ccma", "http://www.cncma.org/", "http://www.cncma.org/col/hangyxw", "L2"),
    "sany": _source("sany", "https://www.sanygroup.com/", "https://www.sanygroup.com/news", "L1"),
    "cehome": _source(
        "cehome", "https://www.cehome.com/", "https://www.cehome.com/news/hangye/", "L2",
    ),
}


@pytest.mark.parametrize("sid", ["ccma", "sany", "cehome"])
def test_fetch_list_returns_detail_urls(sid, http_client, snapshot_store):
    """AC6：三源列表页真实抓取，返回详情 URL（命中各源正则）。"""
    src = SOURCES[sid]
    adapter = get_adapter(src, http=http_client, snapshots=snapshot_store)
    urls = adapter.fetch_list(src)
    assert len(urls) >= 1, f"{sid} 未抓到详情链接"
    # 结构断言（不查具体 id）
    if sid == "ccma":
        assert all("/article/" in u for u in urls)
    elif sid == "sany":
        assert all(u.endswith(".html") for u in urls)
    elif sid == "cehome":
        assert all(".shtml" in u for u in urls)


@pytest.mark.parametrize("sid", ["ccma", "sany", "cehome"])
def test_fetch_detail_produces_rawitem_with_snapshot(sid, http_client, snapshot_store):
    """AC1/AC6：三源真实抓详情 → RawItem 产出 + 快照落 MinIO。"""
    src = SOURCES[sid]
    adapter = get_adapter(src, http=http_client, snapshots=snapshot_store)
    urls = adapter.fetch_list(src)
    if not urls:
        pytest.skip(f"{sid} 列表抓取未返回链接（网络/站点变更），跳过详情")
    item = adapter.fetch_detail(urls[0], src)
    if item is None:
        pytest.skip(f"{sid} 详情抓取未产出（robots/软200/网络），跳过")
    # RawItem 结构断言
    assert item.source_id == sid
    assert item.http_status == 200
    assert item.url.startswith("http")
    assert len(item.title) > 0, f"{sid} 标题为空"
    assert len(item.snapshot_id) == 40
    assert item.snapshot_id == item.content_sha1
    # 快照已落 MinIO
    assert snapshot_store.exists(sid, item.content_sha1), f"{sid} 快照未落 MinIO"
