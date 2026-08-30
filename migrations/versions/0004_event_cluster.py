"""event cluster: event + verification_log 两表 + intel_item.event_id FK（Sprint 6 事件聚类）

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-28

架构 §7 数据架构 ER 图切片：
  EVENT ||--o{ INTEL_ITEM : "聚合"
  EVENT ||--o{ VERIFICATION_LOG : "状态跃迁留痕"

状态机（架构 §6.1）——状态挂 event 层（ADR-003）：
  pending（待核实，初始）/ single_source（单源确认，自动）/ confirmed（多源确认，人工终态）
  / refuted（已证伪，人工终态）/ expired（已过期，时效 Sprint 才触发，本 Sprint 仅占位权重）
自动跃迁写 verification_log(operator=system)；终态跃迁 operator=人工。

intel_item.event_id 加 FK ON DELETE SET NULL——删事件不删情报，只解关联。
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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
    op.execute(
        "CREATE INDEX idx_event_ready ON event(ready_for_manual) WHERE ready_for_manual"
    )

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
    op.execute(
        "CREATE INDEX idx_vlog_event ON verification_log(event_id, created_at DESC)"
    )

    # intel_item.event_id 加 FK（占位列升级为约束）+ 索引（按 event 反查情报）
    op.execute(
        """
        ALTER TABLE intel_item
            ADD CONSTRAINT intel_item_event_id_fkey
            FOREIGN KEY (event_id) REFERENCES event(id) ON DELETE SET NULL
        """
    )
    op.execute("CREATE INDEX idx_intel_item_event_id ON intel_item(event_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_intel_item_event_id")
    op.execute("ALTER TABLE intel_item DROP CONSTRAINT IF EXISTS intel_item_event_id_fkey")
    op.execute("DROP INDEX IF EXISTS idx_vlog_event")
    op.execute("DROP TABLE IF EXISTS verification_log")
    op.execute("DROP INDEX IF EXISTS idx_event_ready")
    op.execute("DROP INDEX IF EXISTS idx_event_subject_type")
    op.execute("DROP INDEX IF EXISTS idx_event_status")
    op.execute("DROP TABLE IF EXISTS event")
