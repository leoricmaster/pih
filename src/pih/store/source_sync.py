"""领域包 sources → source 表 upsert（Sprint 3 T3）。

事实源是 repo 内 YAML；source 表是镜像，用于查询联结与 FK 约束。
collect / query 启动时自动 sync，用户无感知；不删除表里多余行
（避免误删手填数据），仅 upsert。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from psycopg_pool import ConnectionPool

from pih.collect.base import SourceConfig


@dataclass(frozen=True)
class SyncStats:
    upserted: int
    skipped: int = 0


def sync_sources(
    sources: list[SourceConfig],
    domain_id: str,
    pool: ConnectionPool,
) -> SyncStats:
    """将领域包 sources[] upsert 进 source 表（ON CONFLICT DO UPDATE）。

    Args:
        sources: 已从领域包加载的 SourceConfig 列表
        domain_id: 领域包 meta.domain_id
        pool: PG 连接池
    """
    if not sources:
        return SyncStats(upserted=0)
    sql = """
        INSERT INTO source
            (id, name, domain_id, url, list_url, level, reliability,
             fetch_frequency, enabled, synced_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            name            = EXCLUDED.name,
            domain_id       = EXCLUDED.domain_id,
            url             = EXCLUDED.url,
            list_url        = EXCLUDED.list_url,
            level           = EXCLUDED.level,
            reliability     = EXCLUDED.reliability,
            fetch_frequency = EXCLUDED.fetch_frequency,
            enabled         = EXCLUDED.enabled,
            synced_at       = EXCLUDED.synced_at
    """
    now = datetime.now(UTC)
    with pool.connection() as conn, conn.cursor() as cur:
        for s in sources:
            cur.execute(
                sql,
                (
                    s.id, s.name, domain_id, s.url, s.list_url,
                    s.level, s.reliability, s.fetch_frequency,
                    s.enabled, now,
                ),
            )
    return SyncStats(upserted=len(sources))
