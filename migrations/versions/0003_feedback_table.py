"""feedback table: 消费页人类反馈动作（Sprint 5b S3.1.3）

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-28

架构 §7 数据架构 / Sprint 5b 规格 §2.2：
- 消费者在详情页对抽取结果一键标记（主体错了/事件类型错/事实不准/不该入库），
  错误样本积累驱动 process 层 prompt/粗筛迭代（人机闭环）
- intel_id FK ON DELETE CASCADE——情报删除时反馈随之清理
- fact_index：fact_wrong 时标注到第几条事实（按"；"拆分序，1 起）
- 无唯一约束：单人内网场景重复提交无害，聚合按 count 计
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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
    op.execute("DROP INDEX IF EXISTS idx_feedback_type")
    op.execute("DROP INDEX IF EXISTS idx_feedback_intel")
    op.execute("DROP TABLE IF EXISTS feedback")
