"""notification 站内信表（TASK-4.02.01，doc-2 §7 运营层）。

告警与消费同一入口（doc-2 §8）：信源健康告警先行（type='source_health'），
假设命中（hypothesis_hit）/流水线异常随对应故事激活——type 枚举开放不设
CHECK，加渠道/类型不改模型（演进 §11 通知表类型化设计）。
未读 = read_at IS NULL；标记已读写 read_at。
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
        CREATE TABLE notification (
            id BIGSERIAL PRIMARY KEY,
            type TEXT NOT NULL,
            source_id TEXT REFERENCES source(id),
            title TEXT NOT NULL,
            body TEXT NOT NULL DEFAULT '',
            read_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_notification_unread ON notification(read_at, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_notification_unread")
    op.execute("DROP TABLE IF EXISTS notification")
