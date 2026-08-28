"""集成测试数据工厂（Sprint 5a）。

seed_intel_items：批量造 intel_item，混合 subject/event_type/admiralty/source_id/fetched_at，
供消费层列表筛选 AC（≥60 条）使用。仿 test_migrations_apply.py:145 的 INSERT 模式。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from psycopg.types.json import Json


def seed_intel_items(
    conn,
    n: int = 60,
    *,
    source_id: str = "sany_news",
    subject_cycle: tuple = ("三一", "徐工", "中联重科", "柳工", "山推"),
    event_type_cycle: tuple = ("新品发布", "功能迭代", "专利公开", "中标落地", "财报"),
    admiralty_cycle: tuple = ("A1", "B2", "C3", "B1", "A2"),
    tags_cycle: tuple = ("电动化", "矿山", "远程遥控", "3D引导", "智能辅助施工"),
    base_fetched_at: datetime | None = None,
) -> list[int]:
    """造 n 条 intel_item，返回 id 列表。字段循环取值以保证筛选 AC 有数据命中。

    Args:
        conn: psycopg 已打开的连接（调用方负责 commit/关闭）
    """
    base = base_fetched_at or datetime(2026, 8, 27, 12, 0, 0)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO source (id, name, domain_id, url, list_url, level, reliability, enabled) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, true) ON CONFLICT (id) DO NOTHING",
            (source_id, f"{source_id} 测试源", "construction",
             f"http://{source_id}.example/", f"http://{source_id}.example/list",
             "A", "B"),
        )
        ids: list[int] = []
        for i in range(n):
            cur.execute(
                """INSERT INTO intel_item
                (source_id, url, title, list_url, fetched_at, http_status, content_type,
                 encoding, snapshot_id, content_sha1, raw_html, subject, event_type,
                 facts, inferences, tags, quant_params, admiralty_code,
                 process_status, processed_at)
                VALUES (%s, %s, %s, %s, %s, 200, 'text/html', 'utf-8',
                        %s, %s, '<html/>', %s, %s, %s, %s, %s, %s, %s, 'extracted', %s)
                RETURNING id""",
                (
                    source_id,
                    f"http://{source_id}.example/item-{i}",
                    f"{subject_cycle[i % len(subject_cycle)]} 第{i}条测试情报",
                    f"http://{source_id}.example/list",
                    base - timedelta(hours=i),
                    f"snap-{i:04d}",
                    f"sha-{i:04d}",
                    subject_cycle[i % len(subject_cycle)],
                    event_type_cycle[i % len(event_type_cycle)],
                    f"事实描述 #{i}",
                    f"推断与判断 #{i}",
                    Json([tags_cycle[i % len(tags_cycle)]]),
                    Json({"idx": i}),
                    admiralty_cycle[i % len(admiralty_cycle)],
                    base - timedelta(hours=i, minutes=-5),
                ),
            )
            ids.append(cur.fetchone()[0])
    conn.commit()
    return ids
