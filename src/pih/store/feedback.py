"""FeedbackRepository：消费页人类反馈落库与聚合（Sprint 5b S3.1.3 最小切片）。

接口：
  save(...)             单条反馈写入，返回 id
  list_recent(...)      最近反馈明细（JOIN intel_item 带 title/source_id 供展示）
  aggregate(...)        按信源×类型聚合计数 + 主体错误率（>30% 高亮，AC4）

反馈类型 4 类（卡片 story 全集）：
  subject_wrong / event_type_wrong / fact_wrong / should_filter

不引入 ORM；SQL 原生，模型用 dataclass（与 repository.py 同风格）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

FEEDBACK_TYPES = ("subject_wrong", "event_type_wrong", "fact_wrong", "should_filter")

# 主体错误率高亮阈值（AC4：>30% 提示需迭代该信源抽取 prompt 或粗筛阈值）
SUBJECT_ERROR_RATE_HIGHLIGHT = 0.30

_COLUMNS = """
    f.id, f.intel_id, f.feedback_type, f.fact_index,
    f.wrong_value, f.correct_value, f.note, f.user_id, f.created_at,
    i.title AS intel_title, i.source_id
"""


@dataclass(frozen=True)
class FeedbackRecord:
    """单条反馈（list_recent 的行形态，含 JOIN 展示字段）。"""

    id: int
    intel_id: int
    feedback_type: str
    fact_index: int | None
    wrong_value: str | None
    correct_value: str | None
    note: str | None
    user_id: str
    created_at: datetime
    intel_title: str | None = None
    source_id: str | None = None


@dataclass(frozen=True)
class FeedbackAggRow:
    """聚合视图一行：信源 × 反馈类型计数 + 主体错误率（Python 侧算）。"""

    source_id: str
    feedback_type: str
    count: int
    extracted_total: int
    subject_error_rate: float | None  # 仅 subject_wrong 行有值
    highlight: bool = False


class FeedbackRepository:
    """反馈写入与聚合（消费层反馈闭环的 store 侧）。"""

    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def save(
        self,
        *,
        intel_id: int,
        feedback_type: str,
        fact_index: int | None = None,
        wrong_value: str | None = None,
        correct_value: str | None = None,
        note: str | None = None,
        user_id: str = "operator",
    ) -> int:
        """单条写入，返回 feedback.id。feedback_type 合法性由调用方（路由层）校验。"""
        sql = """
            INSERT INTO feedback
                (intel_id, feedback_type, fact_index, wrong_value,
                 correct_value, note, user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                sql,
                (intel_id, feedback_type, fact_index,
                 wrong_value, correct_value, note, user_id),
            )
            return cur.fetchone()[0]

    def list_recent(self, limit: int = 100) -> list[FeedbackRecord]:
        """最近反馈明细（created_at DESC），带情报标题与信源供展示/导出。"""
        sql = f"""
            SELECT {_COLUMNS}
            FROM feedback f
            JOIN intel_item i ON i.id = f.intel_id
            ORDER BY f.created_at DESC, f.id DESC
            LIMIT %s
        """
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall()
        return [FeedbackRecord(**r) for r in rows]

    def aggregate(self) -> list[FeedbackAggRow]:
        """按信源×反馈类型计数；主体错误率 = subject_wrong / 该信源 extracted 数。

        分母用 extracted（已过后验质量门的正常情报）而非全量——
        pending/filtered_out 条目未进入消费视野，不构成"看错的机会"。
        """
        counts_sql = """
            SELECT i.source_id, f.feedback_type, COUNT(*) AS cnt
            FROM feedback f
            JOIN intel_item i ON i.id = f.intel_id
            GROUP BY i.source_id, f.feedback_type
            ORDER BY i.source_id, f.feedback_type
        """
        extracted_sql = """
            SELECT source_id, COUNT(*) AS cnt
            FROM intel_item
            WHERE process_status = 'extracted'
            GROUP BY source_id
        """
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(counts_sql)
            counts = cur.fetchall()
            cur.execute(extracted_sql)
            extracted = dict(cur.fetchall())

        rows: list[FeedbackAggRow] = []
        for source_id, feedback_type, cnt in counts:
            total = extracted.get(source_id, 0)
            rate = cnt / total if feedback_type == "subject_wrong" and total else None
            rows.append(
                FeedbackAggRow(
                    source_id=source_id,
                    feedback_type=feedback_type,
                    count=cnt,
                    extracted_total=total,
                    subject_error_rate=rate,
                    highlight=rate is not None and rate > SUBJECT_ERROR_RATE_HIGHLIGHT,
                )
            )
        return rows
