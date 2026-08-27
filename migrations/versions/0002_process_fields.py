"""process fields: intel_item 结构化抽取列（Sprint 4 process 层）

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-27

架构 §7 数据架构 / Sprint 4 规格 §3.5：
- 结构化 7 列：subject/event_type/facts/inferences/tags/quant_params/admiralty_code
- 治理 4 列：process_status（pending→extracted|filtered_out|needs_manual，
  应用层枚举约束）/process_error/process_meta/processed_at
- 存量行自动获得 process_status='pending'，可直接被 pih process 处理
- event 表仍留事件聚类 Sprint（event_id 占位 FK 不变）
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE intel_item
            ADD COLUMN subject         TEXT,
            ADD COLUMN event_type      TEXT,
            ADD COLUMN facts           TEXT,
            ADD COLUMN inferences      TEXT,
            ADD COLUMN tags            JSONB NOT NULL DEFAULT '[]'::jsonb,
            ADD COLUMN quant_params    JSONB NOT NULL DEFAULT '{}'::jsonb,
            ADD COLUMN admiralty_code  TEXT,
            ADD COLUMN process_status  TEXT NOT NULL DEFAULT 'pending',
            ADD COLUMN process_error   TEXT,
            ADD COLUMN process_meta    JSONB,
            ADD COLUMN processed_at    TIMESTAMPTZ
        """
    )
    op.execute("CREATE INDEX idx_intel_item_process_status ON intel_item(process_status)")
    op.execute("CREATE INDEX idx_intel_item_event_type ON intel_item(event_type)")
    op.execute("CREATE INDEX idx_intel_item_tags ON intel_item USING GIN(tags)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_intel_item_tags")
    op.execute("DROP INDEX IF EXISTS idx_intel_item_event_type")
    op.execute("DROP INDEX IF EXISTS idx_intel_item_process_status")
    op.execute(
        """
        ALTER TABLE intel_item
            DROP COLUMN IF EXISTS subject,
            DROP COLUMN IF EXISTS event_type,
            DROP COLUMN IF EXISTS facts,
            DROP COLUMN IF EXISTS inferences,
            DROP COLUMN IF EXISTS tags,
            DROP COLUMN IF EXISTS quant_params,
            DROP COLUMN IF EXISTS admiralty_code,
            DROP COLUMN IF EXISTS process_status,
            DROP COLUMN IF EXISTS process_error,
            DROP COLUMN IF EXISTS process_meta,
            DROP COLUMN IF EXISTS processed_at
        """
    )
