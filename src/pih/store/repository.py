"""IntelRepository：情报条目落库与基础检索（Sprint 3 T4）。

接口（规格 §3.3）：
  save(item)          单条入库，幂等冲突 → SKIPPED
  save_batch(items)   批量入库（逐条 save，单条失败不阻塞）
  list_by_source(...)  按信源列出最近入库
  get(id)             单条详情

不引入 ORM；SQL 原生，模型用 dataclass（IntelRecord 与 RawItem 字段同 + id + created_at）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from pih.collect.rawitem import RawItem
from pih.store.errors import IntegrityConflict

INSERT_SQL = """
    INSERT INTO intel_item
        (source_id, url, title, list_url, fetched_at, http_status,
         content_type, encoding, snapshot_id, content_sha1, raw_html)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (content_sha1) DO NOTHING
    RETURNING id
"""


@dataclass(frozen=True)
class SaveOutcome:
    """save 单条结果。"""

    SAVED = "saved"
    SKIPPED = "skipped"
    FAILED = "failed"

    status: str
    intel_id: int | None = None
    reason: str | None = None
    content_sha1: str | None = None


@dataclass(frozen=True)
class IntelRecord:
    """从 DB 读出的情报条目（RawItem 字段同 + id + created_at）。"""

    id: int
    source_id: str
    url: str
    title: str
    list_url: str
    fetched_at: datetime
    http_status: int
    content_type: str | None
    encoding: str | None
    snapshot_id: str
    content_sha1: str
    raw_html: str
    event_id: int | None
    created_at: datetime


class IntelRepository:
    """情报库基础检索（最小切片，规格 D5）。"""

    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def save(self, item: RawItem) -> SaveOutcome:
        """单条入库。content_sha1 冲突 → SKIPPED；其他异常 → FAILED。

        ON CONFLICT DO NOTHING + RETURNING id：插入成功返回 id，
        冲突时无行返回 → SKIPPED。
        """
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                INSERT_SQL,
                (
                    item.source_id, item.url, item.title, item.list_url,
                    item.fetched_at, item.http_status, item.content_type,
                    item.encoding, item.snapshot_id, item.content_sha1,
                    item.raw_html,
                ),
            )
            row = cur.fetchone()
        if row is not None:
            return SaveOutcome(
                status=SaveOutcome.SAVED, intel_id=row[0], content_sha1=item.content_sha1
            )
        return SaveOutcome(status=SaveOutcome.SKIPPED, content_sha1=item.content_sha1)

    def save_batch(self, items: list[RawItem]) -> list[SaveOutcome]:
        """批量入库，逐条 save；单条异常不阻塞其他条目（D8 容错）。"""
        outcomes: list[SaveOutcome] = []
        for item in items:
            try:
                outcomes.append(self.save(item))
            except IntegrityConflict:
                outcomes.append(
                    SaveOutcome(status=SaveOutcome.SKIPPED, content_sha1=item.content_sha1)
                )
            except Exception as exc:  # noqa: BLE001 容错策略 D8：单条失败不阻塞
                outcomes.append(
                    SaveOutcome(
                        status=SaveOutcome.FAILED,
                        reason=str(exc),
                        content_sha1=item.content_sha1,
                    )
                )
        return outcomes

    def list_by_source(
        self, source_id: str, limit: int = 50, before: datetime | None = None
    ) -> list[IntelRecord]:
        """按信源列出最近入库（fetched_at DESC）。

        Args:
            before: 若给定，只返回 fetched_at < before 的条目（分页游标）
        """
        if before is None:
            sql = """
                SELECT id, source_id, url, title, list_url, fetched_at,
                       http_status, content_type, encoding, snapshot_id,
                       content_sha1, raw_html, event_id, created_at
                FROM intel_item
                WHERE source_id = %s
                ORDER BY fetched_at DESC
                LIMIT %s
            """
            params: tuple = (source_id, limit)
        else:
            sql = """
                SELECT id, source_id, url, title, list_url, fetched_at,
                       http_status, content_type, encoding, snapshot_id,
                       content_sha1, raw_html, event_id, created_at
                FROM intel_item
                WHERE source_id = %s AND fetched_at < %s
                ORDER BY fetched_at DESC
                LIMIT %s
            """
            params = (source_id, before, limit)

        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [IntelRecord(**r) for r in rows]

    def get(self, intel_id: int) -> IntelRecord | None:
        sql = """
            SELECT id, source_id, url, title, list_url, fetched_at,
                   http_status, content_type, encoding, snapshot_id,
                   content_sha1, raw_html, event_id, created_at
            FROM intel_item
            WHERE id = %s
        """
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (intel_id,))
            row = cur.fetchone()
        return IntelRecord(**row) if row else None
