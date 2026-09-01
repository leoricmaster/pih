"""原文快照 presigned URL 生成。

MinIO 快照对象路径 snapshots/{source_id}/{content_sha1}.html（collect/snapshot.py）。
消费层详情页用 presigned URL 让用户直接下载原文 HTML，无需通过应用层转发。

本地开发（uv run uvicorn）：MINIO_ENDPOINT=localhost:9000，浏览器与容器同主机，
presigned URL 直接可达。

docker compose 部署：web 容器用 MINIO_ENDPOINT=minio:9000 连通，但 presigned
URL 的 host 也是 minio:9000——容器外浏览器不可达。生产部署需配 MinIO 反向代理
或 host 网络；docker compose 场景降级展示快照 ID 文本（不阻塞验收）。

MinIO 不可达或 presigned 生成失败时返回 None——详情页降级展示快照 ID 文本。
"""
from __future__ import annotations

import os

from minio import Minio

BUCKET = "pih-snapshots"


def make_snapshot_client() -> Minio | None:
    """从 env 构造 MinIO client；不可达返回 None（消费层降级）。"""
    endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
    client = Minio(
        endpoint,
        access_key=os.environ.get("MINIO_ROOT_USER", "pih"),
        secret_key=os.environ.get("MINIO_ROOT_PASSWORD", "pih12345"),
        secure=False,
    )
    try:
        client.bucket_exists(BUCKET)
        return client
    except Exception:  # noqa: BLE001 消费层不因 MinIO 故障崩
        return None


def presigned_snapshot_url(client: Minio, source_id: str, content_sha1: str,
                           expires_hours: int = 1) -> str | None:
    """生成快照临时下载链接；失败返回 None。

    URL host = MINIO_ENDPOINT（client 的 endpoint）。
    本地开发（localhost:9000）浏览器直接可达；
    docker compose（minio:9000）浏览器不可达，需配反向代理——该场景降级展示 ID。
    """
    key = f"snapshots/{source_id}/{content_sha1}.html"
    try:
        from datetime import timedelta

        return client.presigned_get_object(BUCKET, key, expires=timedelta(hours=expires_hours))
    except Exception:  # noqa: BLE001
        return None
