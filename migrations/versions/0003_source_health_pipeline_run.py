"""source 健康统计列 + pipeline_run 运行留痕表（TASK-4.01.01 调度器落地）。

D9：健康是「每源一行」的标量状态——连续失败计数（连续 3 次触发站内信告警，
TASK-4.02.01）+ 最近成败时间与失败原因，挂 source 表不加表（独立表需 1:1 JOIN）。
D6 遗留（TASK-1.01.02）：pipeline_run 记每次调度运行吞吐/失败/时长；token 列
NULL 预留——采集阶段不产 token，处理接力（TASK-4.01.2）启用（doc-2 §7 口径
一次建全，免二次迁移）。
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 健康统计（D9）：成功清零 / 失败 +1（SourceHealthRepository 唯一写手）
    op.execute(
        "ALTER TABLE source ADD COLUMN consecutive_failures INTEGER NOT NULL DEFAULT 0"
    )
    op.execute("ALTER TABLE source ADD COLUMN last_failure_at TIMESTAMPTZ")
    op.execute("ALTER TABLE source ADD COLUMN last_failure_reason TEXT")
    op.execute("ALTER TABLE source ADD COLUMN last_success_at TIMESTAMPTZ")
    # 运行留痕（doc-2 §7/§8 可观测底座；D16 token 列预留）
    op.execute(
        """
        CREATE TABLE pipeline_run (
            id BIGSERIAL PRIMARY KEY,
            source_id TEXT NOT NULL REFERENCES source(id),
            run_type TEXT NOT NULL DEFAULT 'scheduled',
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            duration_ms INTEGER NOT NULL,
            ok BOOLEAN NOT NULL,
            items_new INTEGER NOT NULL DEFAULT 0,
            items_skipped INTEGER NOT NULL DEFAULT 0,
            items_failed INTEGER NOT NULL DEFAULT 0,
            error TEXT,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_pipeline_run_source_time "
        "ON pipeline_run(source_id, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_pipeline_run_source_time")
    op.execute("DROP TABLE IF EXISTS pipeline_run")
    op.execute("ALTER TABLE source DROP COLUMN IF EXISTS last_success_at")
    op.execute("ALTER TABLE source DROP COLUMN IF EXISTS last_failure_reason")
    op.execute("ALTER TABLE source DROP COLUMN IF EXISTS last_failure_at")
    op.execute(
        "ALTER TABLE source DROP COLUMN IF EXISTS consecutive_failures"
    )
