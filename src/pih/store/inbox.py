"""InboxRepository：采集先落盘 inbox_item 与处理状态读写（TASK-1.01.02 D1）。

架构 §6.4 / ADR-009：处理链唯一输入是 inbox 条目；信源适配器是 inbox 生产者。
采集不再直写 intel_item——intel_item 在通过质量门、挂入事件后才创建
（TASK-1.02.01）。本故事范围内 inbox 三态流转：pending → filtered_out / dead。

死信（dead_letter）为 inbox 条目的失败终态标记而非独立实体（doc-2 §7）：
process_status='dead' 即死信态，失败原因记 process_error，可查、可重放、可丢弃留痕。

接口：
  save(item)            采集条目落 inbox，content_sha1 冲突 → SKIPPED
  save_batch(items)     批量落盘（逐条 save，单条失败不阻塞）
  record_failure(...)   fetch 失败落一行（状态 dead，原因记 process_error）
  get(id)               单条详情（原文快照+原始链接在 inbox 即有）
  list_pending(...)     待处理条目（处理链消费入口，先老后新）
  mark_status(...)      写回处理状态（filtered_out / dead / 重置 pending 重放）
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from pih.collect.rawitem import RawItem

# inbox 处理状态枚举（应用层约束，迁移 0002 落列默认 pending）
STATUS_PENDING = "pending"
STATUS_FILTERED_OUT = "filtered_out"
STATUS_DEAD = "dead"
# 以下两态本故事不触发，留 TASK-1.02.01 提升时用
STATUS_NEEDS_MANUAL = "needs_manual"
STATUS_EXTRACTED = "extracted"

INSERT_SQL = """
    INSERT INTO inbox_item
        (source_id, source_type, url, title, list_url, fetched_at, http_status,
         content_type, encoding, snapshot_id, content_sha1, raw_html)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (content_sha1) DO NOTHING
    RETURNING id
"""

# fetch 失败落行：无快照（抓取未完成）时 snapshot_id 用占位、状态 dead、原因入 process_error。
# 无快照不入库约束针对的是消费条目（无快照的内容不进列表）；失败行是死信留痕，快照字段以
# 失败标识占位以满足 NOT NULL 守卫，且 process_status=dead 使其不进消费列表。
FAILURE_SNAPSHOT = "__no_snapshot_fetch_failed__"

_INSERT_FAILURE_SQL = """
    INSERT INTO inbox_item
        (source_id, source_type, url, title, list_url, fetched_at, http_status,
         content_type, encoding, snapshot_id, content_sha1, raw_html,
         process_status, process_error)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

_COLUMNS = (
    "id, source_id, source_type, url, title, list_url, fetched_at, "
    "http_status, content_type, encoding, snapshot_id, content_sha1, raw_html, "
    "process_status, process_error, process_meta, processed_at, created_at"
)


@dataclass(frozen=True)
class SaveOutcome:
    """save 单条结果（口径与 IntelRepository.SaveOutcome 一致，便于 CLI 聚合）。"""

    SAVED = "saved"
    SKIPPED = "skipped"
    FAILED = "failed"

    status: str
    inbox_id: int | None = None
    reason: str | None = None
    content_sha1: str | None = None


@dataclass(frozen=True)
class InboxRecord:
    """从 inbox_item 读出的条目。

    基础字段同 RawItem + id/created_at + 处理状态字段。原文快照与原始链接
    在 inbox 即有（AC1「点开可见原文」在 pending 态已闭环，不依赖抽取提升）。
    """

    id: int
    source_id: str
    source_type: str
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
    process_status: str
    process_error: str | None = None
    process_meta: dict | None = None
    processed_at: datetime | None = None
    created_at: datetime = None  # type: ignore[assignment]


class InboxRepository:
    """采集先落盘 inbox_item 与状态读写（最小切片）。"""

    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def save(self, item: RawItem) -> SaveOutcome:
        """单条采集条目落 inbox。content_sha1 冲突 → SKIPPED；其他异常 → FAILED。

        无快照不入库：RawItem 的 snapshot_id 由适配器在存档后填充，
        未存档的条目不产出 RawItem（fetch_detail 返回 None），故此处不另守卫。

        单条异常不抛出而返回 FAILED（容错 D8：采集循环单条失败不阻塞其余条目），
        与 IntelRepository.save（抛出由 save_batch 捕获）不同——inbox 的调用方
        是 collect_source 循环，直接拿 FAILED 计入统计更直白。
        """
        try:
            with self._pool.connection() as conn, conn.cursor() as cur:
                cur.execute(
                    INSERT_SQL,
                    (
                        item.source_id, "auto", item.url, item.title, item.list_url,
                        item.fetched_at, item.http_status, item.content_type,
                        item.encoding, item.snapshot_id, item.content_sha1,
                        item.raw_html,
                    ),
                )
                row = cur.fetchone()
        except Exception as exc:  # noqa: BLE001 容错 D8：单条失败不阻塞
            return SaveOutcome(
                status=SaveOutcome.FAILED, reason=str(exc),
                content_sha1=item.content_sha1,
            )
        if row is not None:
            return SaveOutcome(
                status=SaveOutcome.SAVED, inbox_id=row[0], content_sha1=item.content_sha1
            )
        return SaveOutcome(status=SaveOutcome.SKIPPED, content_sha1=item.content_sha1)

    def save_batch(self, items: list[RawItem]) -> list[SaveOutcome]:
        """批量落盘，逐条 save（save 已吞异常返回 FAILED，单条不阻塞）。"""
        return [self.save(item) for item in items]

    def record_failure(
        self,
        *,
        source_id: str,
        url: str,
        list_url: str,
        reason: str,
        fetched_at: str,
        http_status: int = 0,
    ) -> None:
        """AC4：fetch 失败落一行——状态 dead，process_error 记失败原因。

        抓取未完成无正文/快照；snapshot_id 以失败标识占位满足 NOT NULL 守卫，
        content_sha1 取 url+reason 指纹（失败行幂等，同 url 同因不重复堆）。
        process_status=dead 使其不进消费列表（漏报审计可按状态筛出）。
        """
        import hashlib

        fail_sha = hashlib.sha1(f"{url}|{reason}".encode()).hexdigest()
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                _INSERT_FAILURE_SQL,
                (
                    source_id, "auto", url, "(抓取失败)", list_url, fetched_at,
                    http_status, None, None, FAILURE_SNAPSHOT, fail_sha, "",
                    STATUS_DEAD, reason,
                ),
            )

    def get(self, inbox_id: int) -> InboxRecord | None:
        sql = f"SELECT {_COLUMNS} FROM inbox_item WHERE id = %s"
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (inbox_id,))
            row = cur.fetchone()
        return InboxRecord(**row) if row else None

    def list_pending(
        self, source_id: str | None = None, limit: int = 20
    ) -> list[InboxRecord]:
        """取待处理条目（process_status='pending'），先老后新（fetched_at ASC）。"""
        if source_id is None:
            sql = (
                f"SELECT {_COLUMNS} FROM inbox_item WHERE process_status = %s "
                "ORDER BY fetched_at ASC LIMIT %s"
            )
            params: tuple = (STATUS_PENDING, limit)
        else:
            sql = (
                f"SELECT {_COLUMNS} FROM inbox_item "
                "WHERE process_status = %s AND source_id = %s "
                "ORDER BY fetched_at ASC LIMIT %s"
            )
            params = (STATUS_PENDING, source_id, limit)
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [InboxRecord(**r) for r in rows]

    def mark_status(self, inbox_id: int, status: str, error: str | None = None) -> None:
        """写回处理状态：filtered_out（粗筛）/ dead（失败终态）/ 重置 pending（重放）。

        重放 = mark_status(id, 'pending') 重入处理链（AC4 可重放）；丢弃 = 留 dead 态留痕。
        """
        sql = (
            "UPDATE inbox_item SET process_status = %s, "
            "process_error = COALESCE(%s, process_error), processed_at = NOW() "
            "WHERE id = %s"
        )
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(sql, (status, error, inbox_id))
