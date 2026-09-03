"""inbox_item：采集先落盘载体（TASK-1.01.02 AC4 裁决 a）。

架构 §6.4 / §7 / ADR-009：处理链唯一输入是 inbox 条目（raw 文本 + 附件引用 +
来源标记）；信源适配器与录入网关都只是 inbox 生产者。intel_item 在通过质量门、
挂入事件后才创建——采集不再直写 intel_item。

死信（dead_letter）为 inbox 条目的失败终态标记而非独立实体（doc-2 §7）：
inbox_item.process_status = 'dead' 即死信态，失败原因记 process_error，可查、
可重放（重置 pending 重入处理链）、可丢弃留痕。

inbox 三态流转（本故事范围内）：pending（采集入库即此态）→ filtered_out（粗筛
判不相关，行级标记保留可审计）/ dead（失败终态）。needs_manual / done 及提升→
intel_item 留 TASK-1.02.01。

幂等键 = 内容指纹 content_sha1 UNIQUE（精确去重；模糊/近重复留演进故事）。
无快照不入库（贯穿性约束 2）：snapshot_id NOT NULL 为守卫。
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- inbox_item（采集先落盘，处理状态机挂此行，§6.4）---
    op.execute(
        """
        CREATE TABLE inbox_item (
            id            BIGSERIAL PRIMARY KEY,
            source_id     TEXT NOT NULL REFERENCES source(id),
            source_type   TEXT NOT NULL DEFAULT 'auto',
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
            process_status TEXT NOT NULL DEFAULT 'pending',
            process_error TEXT,
            process_meta  JSONB,
            processed_at  TIMESTAMPTZ,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_inbox_source_fetched ON inbox_item(source_id, fetched_at DESC)"
    )
    op.execute("CREATE INDEX idx_inbox_created ON inbox_item(created_at DESC)")
    op.execute(
        "CREATE INDEX idx_inbox_process_status ON inbox_item(process_status)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_inbox_process_status")
    op.execute("DROP INDEX IF EXISTS idx_inbox_created")
    op.execute("DROP INDEX IF EXISTS idx_inbox_source_fetched")
    op.execute("DROP TABLE IF EXISTS inbox_item")
