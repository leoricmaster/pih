"""原文快照存档（架构 §5.3 快照与可回溯 / ADR-007）。

原始 HTML 字节写入 MinIO，sidecar JSON 存元数据；
快照 ID = sha1(原始字节) = 内容指纹（入库幂等键）。
「无快照不入库」贯穿约束的落地：RawItem.snapshot_id 即此产出。

为可测性，SnapshotStore 接收可注入的 minio client（集成测试用真 MinIO，
单元测试可用假 client）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from io import BytesIO

from minio import Minio

from .rawitem import content_fingerprint

BUCKET = "pih-snapshots"


@dataclass(frozen=True)
class SnapshotMeta:
    """快照元数据（sidecar JSON 内容）。"""

    source_id: str
    url: str
    fetched_at: str
    http_status: int
    content_type: str
    encoding: str
    content_sha1: str


class SnapshotStore:
    """MinIO 快照存档。

    Args:
        client: minio.Minio 实例（可注入假对象用于单测）
        bucket: MinIO bucket 名
    """

    def __init__(self, client: Minio, bucket: str = BUCKET) -> None:
        self.client = client
        self.bucket = bucket

    def _ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def archive(self, source_id: str, raw_bytes: bytes, meta: SnapshotMeta) -> str:
        """存档原始字节 + sidecar 元数据，返回快照 ID（= 内容指纹）。

        幂等：相同内容指纹覆盖写（MinIO 同 key 覆盖），不产生重复。
        """
        self._ensure_bucket()
        sha = content_fingerprint(raw_bytes)
        if sha != meta.content_sha1:
            raise ValueError(
                f"meta.content_sha1({meta.content_sha1}) 与实际字节指纹({sha})不一致"
            )
        key = f"snapshots/{source_id}/{sha}.html"
        self.client.put_object(
            self.bucket,
            key,
            BytesIO(raw_bytes),
            len(raw_bytes),
            "text/html; charset=utf-8",
        )
        sidecar = {
            "source_id": meta.source_id,
            "url": meta.url,
            "fetched_at": meta.fetched_at,
            "http_status": meta.http_status,
            "content_type": meta.content_type,
            "encoding": meta.encoding,
            "content_sha1": meta.content_sha1,
        }
        self.client.put_object(
            self.bucket,
            key + ".meta.json",
            BytesIO(json.dumps(sidecar, ensure_ascii=False).encode("utf-8")),
            len(json.dumps(sidecar, ensure_ascii=False).encode("utf-8")),
            "application/json",
        )
        return sha

    def exists(self, source_id: str, content_sha1: str) -> bool:
        """快照是否已存在（幂等检查）。"""
        try:
            self.client.stat_object(self.bucket, f"snapshots/{source_id}/{content_sha1}.html")
            return True
        except Exception:  # minio S3Error 当对象不存在
            return False
