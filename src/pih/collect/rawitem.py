"""RawItem：采集产出的原始情报条目（架构 §4 COLLECT 层 / §5.1 数据流）。

RawItem 是采集适配器的产出、处理链的输入。原始内容先落盘 MinIO（快照），
RawItem 持有快照 ID 与内容指纹（入库幂等键，ADR-007）。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass


def content_fingerprint(raw_bytes: bytes) -> str:
    """内容指纹 = sha1(raw_bytes)，作为入库幂等键（ADR-007）与快照 ID。

    sha1 此场景无安全需求（非密码学用途），取其短定长（40 字符）。
    """
    return hashlib.sha1(raw_bytes).hexdigest()


@dataclass(frozen=True)
class RawItem:
    """采集产出的原始情报条目。

    Attributes:
        source_id: 领域包 sources[].id
        url: 详情页 URL
        title: 从详情页解析的标题（已解码、已去实体）
        list_url: 来源列表页 URL
        fetched_at: 抓取时间 ISO8601
        http_status: 详情页 HTTP 状态码
        content_type: 详情页 Content-Type 响应头
        encoding: 解码链判定的字符集（如 utf-8）
        raw_html: 解码后正文 HTML
        snapshot_id: MinIO 快照 ID = sha1(原始字节) = content_sha1
        content_sha1: 内容指纹（幂等键，等于 snapshot_id）
    """

    source_id: str
    url: str
    title: str
    list_url: str
    fetched_at: str
    http_status: int
    content_type: str
    encoding: str
    raw_html: str
    snapshot_id: str
    content_sha1: str

    def __post_init__(self) -> None:
        """快照 ID 与内容指纹须一致（ADR-007：入库幂等键 = 快照内容指纹）。"""
        if self.snapshot_id != self.content_sha1:
            raise ValueError(
                f"snapshot_id 与 content_sha1 不一致：{self.snapshot_id} != {self.content_sha1}"
            )
