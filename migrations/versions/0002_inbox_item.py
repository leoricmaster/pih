"""intel_item 加 source_type 列（ADR-011：inbox 逻辑汇聚、物理单表两视图）。

ADR-011：inbox 为 ADR-009 的逻辑汇聚点而非物理独立表。intel_item 单表承载
处理状态机——采集即落 pending 行，抽取原地 UPDATE 升级结构化字段，不另建
inbox 表。source_type 区分采集/人工（ADR-009 汇聚语义的物理载体）。

死信 = process_status='dead' 的失败终态标记（doc-2 §7：死信非独立实体）。
列表分两视图读同表不同状态：收件箱视图（pending/needs_manual/filtered_out/
dead）+ 检索视图（extracted）。
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # source_type：区分采集（auto）与人工录入（manual），ADR-009 汇聚语义的物理载体。
    # 存量行均为自动采集，默认 'auto'。
    op.execute(
        "ALTER TABLE intel_item ADD COLUMN source_type TEXT NOT NULL DEFAULT 'auto'"
    )
    op.execute(
        "CREATE INDEX idx_intel_item_source_type ON intel_item(source_type)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_intel_item_source_type")
    op.execute("ALTER TABLE intel_item DROP COLUMN IF EXISTS source_type")
