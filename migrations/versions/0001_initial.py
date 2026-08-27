"""initial: source + intel_item 两表（Sprint 3 store 层最小切片）

Revision ID: 0001
Revises:
Create Date: 2026-08-26

架构 §7 数据架构 ER 图切片：
  SOURCE ||--o{ INTEL_ITEM : "产出"

不预置 process 层字段（主体/事件类型/置信度/标签/有效期），类型未定型，
等 process Sprint ADD COLUMN（PG ADD COLUMN NULLABLE 是元数据操作，秒级）。
event_id 占位字段（无 FK），event 表留 process Sprint。
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
            event_id      BIGINT,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_intel_item_source_fetched ON intel_item(source_id, fetched_at DESC)"
    )
    op.execute("CREATE INDEX idx_intel_item_created ON intel_item(created_at DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_intel_item_created")
    op.execute("DROP INDEX IF EXISTS idx_intel_item_source_fetched")
    op.execute("DROP TABLE IF EXISTS intel_item")
    op.execute("DROP TABLE IF EXISTS source")
