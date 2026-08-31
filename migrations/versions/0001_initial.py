"""initial: 全量 schema 基线（source / intel_item / event / verification_log / feedback）

Revision ID: 0001
Revises:
Create Date: 2026-08-31

架构 §7 数据架构 ER 图切片：
  SOURCE ||--o{ INTEL_ITEM : "产出"
  EVENT ||--o{ INTEL_ITEM : "聚合"
  EVENT ||--o{ VERIFICATION_LOG : "状态跃迁留痕"
  INTEL_ITEM ||--o{ FEEDBACK : "人类反馈"

建表顺序依 FK 依赖：source → event → intel_item → verification_log → feedback。
intel_item 自始含全部结构化/治理列与 event_id FK（无占位中间态）。
状态挂 event 层（ADR-003）；intel_item.event_id ON DELETE SET NULL（删事件不删情报）。
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- source ---
    op.execute(
        """
        CREATE TABLE source (
            id              TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            domain_id       TEXT NOT NULL,
            url             TEXT NOT NULL,
            list_url        TEXT NOT NULL,
            level           TEXT NOT NULL,
            reliability     TEXT NOT NULL,
            fetch_frequency TEXT,
            enabled         BOOLEAN NOT NULL DEFAULT FALSE,
            synced_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # --- event（状态挂此层，ADR-003；先于 intel_item，因后者 event_id FK 指向它）---
    op.execute(
        """
        CREATE TABLE event (
            id               BIGSERIAL PRIMARY KEY,
            subject          TEXT NOT NULL,
            event_type       TEXT NOT NULL,
            status           TEXT NOT NULL DEFAULT 'pending',
            source_count     INTEGER NOT NULL DEFAULT 0,
            ready_for_manual BOOLEAN NOT NULL DEFAULT FALSE,
            first_seen_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_seen_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX idx_event_status ON event(status)")
    op.execute("CREATE INDEX idx_event_subject_type ON event(subject, event_type)")
    op.execute("CREATE INDEX idx_event_ready ON event(ready_for_manual) WHERE ready_for_manual")

    # --- intel_item（结构化/治理列 + event_id FK 全含）---
    op.execute(
        """
        CREATE TABLE intel_item (
            id            BIGSERIAL PRIMARY KEY,
            source_id     TEXT NOT NULL REFERENCES source(id),
            url           TEXT NOT NULL,
            title         TEXT NOT NULL,
            list_url      TEXT NOT NULL,
            fetched_at    TIMESTAMPTZ NOT NULL,
            http_status   INTEGER NOT NULL,
            content_type  TEXT,
            encoding      TEXT,
            snapshot_id   TEXT NOT NULL,
            content_sha1  TEXT NOT NULL UNIQUE,
            raw_html      TEXT NOT NULL,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            event_id      BIGINT REFERENCES event(id) ON DELETE SET NULL,
            subject       TEXT,
            event_type    TEXT,
            facts         TEXT,
            inferences    TEXT,
            tags          JSONB NOT NULL DEFAULT '[]'::jsonb,
            quant_params  JSONB NOT NULL DEFAULT '{}'::jsonb,
            admiralty_code TEXT,
            process_status TEXT NOT NULL DEFAULT 'pending',
            process_error TEXT,
            process_meta  JSONB,
            processed_at  TIMESTAMPTZ
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_intel_item_source_fetched ON intel_item(source_id, fetched_at DESC)"
    )
    op.execute("CREATE INDEX idx_intel_item_created ON intel_item(created_at DESC)")
    op.execute("CREATE INDEX idx_intel_item_process_status ON intel_item(process_status)")
    op.execute("CREATE INDEX idx_intel_item_event_type ON intel_item(event_type)")
    op.execute("CREATE INDEX idx_intel_item_tags ON intel_item USING GIN(tags)")
    op.execute("CREATE INDEX idx_intel_item_event_id ON intel_item(event_id)")

    # --- verification_log（状态跃迁留痕，FK 级联删除）---
    op.execute(
        """
        CREATE TABLE verification_log (
            id          BIGSERIAL PRIMARY KEY,
            event_id    BIGINT NOT NULL REFERENCES event(id) ON DELETE CASCADE,
            from_status TEXT,
            to_status   TEXT NOT NULL,
            operator    TEXT NOT NULL DEFAULT 'system',
            reason      TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX idx_vlog_event ON verification_log(event_id, created_at DESC)")

    # --- feedback（消费页人类反馈，intel_id FK 级联删除）---
    op.execute(
        """
        CREATE TABLE feedback (
            id            BIGSERIAL PRIMARY KEY,
            intel_id      BIGINT NOT NULL REFERENCES intel_item(id) ON DELETE CASCADE,
            feedback_type TEXT NOT NULL,
            fact_index    INTEGER,
            wrong_value   TEXT,
            correct_value TEXT,
            note          TEXT,
            user_id       TEXT NOT NULL DEFAULT 'operator',
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX idx_feedback_intel ON feedback(intel_id)")
    op.execute("CREATE INDEX idx_feedback_type ON feedback(feedback_type)")


def downgrade() -> None:
    # 反序 drop（依 FK 依赖反向：建表 source→event→intel_item→vlog→feedback）
    op.execute("DROP INDEX IF EXISTS idx_feedback_type")
    op.execute("DROP INDEX IF EXISTS idx_feedback_intel")
    op.execute("DROP TABLE IF EXISTS feedback")

    op.execute("DROP INDEX IF EXISTS idx_vlog_event")
    op.execute("DROP TABLE IF EXISTS verification_log")

    # intel_item 先于 event——其 event_id FK 指向 event，须先释放依赖
    op.execute("DROP INDEX IF EXISTS idx_intel_item_event_id")
    op.execute("DROP INDEX IF EXISTS idx_intel_item_tags")
    op.execute("DROP INDEX IF EXISTS idx_intel_item_event_type")
    op.execute("DROP INDEX IF EXISTS idx_intel_item_process_status")
    op.execute("DROP INDEX IF EXISTS idx_intel_item_created")
    op.execute("DROP INDEX IF EXISTS idx_intel_item_source_fetched")
    op.execute("DROP TABLE IF EXISTS intel_item")

    op.execute("DROP INDEX IF EXISTS idx_event_ready")
    op.execute("DROP INDEX IF EXISTS idx_event_subject_type")
    op.execute("DROP INDEX IF EXISTS idx_event_status")
    op.execute("DROP TABLE IF EXISTS event")

    op.execute("DROP TABLE IF EXISTS source")
