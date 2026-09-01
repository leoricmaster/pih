"""集成测试数据工厂（2026-08-31 收敛各文件内联 seed 辅助）。

- seed_intel_items：批量造 intel_item，混合 subject/event_type/admiralty/source_id/fetched_at，
  供消费层列表筛选（TASK-2.01.01，≥60 条）使用。
- seed_intel：单条 extracted intel_item（聚类测试用，跳过 collect/process 流程）。
- seed_event：单条 event + 对应 verification_log（verify/消费层事件字段测试用）。
- ScriptChat / usage / ok_pred：脚本化 chat 注入确定性 LLM 输出（不依赖凭据）。
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

import psycopg
from psycopg.types.json import Json

# 与 conftest 同口径的裸 DSN（直连断言/造数用）
PG_DSN = os.environ.get(
    "PG_DSN", "postgresql://pih:pih@localhost:5432/pih"
).replace("+psycopg", "")


def usage() -> dict:
    """ChatFn 契约三键（graph 按下标取 retries）。"""
    return {"prompt_tokens": 1, "completion_tokens": 1, "retries": 0}


def ok_pred(subject: str = "三一", event_type: str = "新品发布") -> dict:
    """能过真实领域包（construction_machinery v0.2.0）validate_pred 的输出。"""
    return {
        "主体": subject,
        "事件类型": event_type,
        "事实描述": f"{subject}发布新品",
        "推断与判断": "依据：正文",
        "标签": ["电动化"],
        "量化参数": {},
        "信息可信度": "2",
    }


class ScriptChat:
    """脚本化 chat：按 tier 分派（LLM 不可注入确定性失败时用）。"""

    def __init__(self, small, large) -> None:
        self._small = small
        self._large = large

    def __call__(self, messages: list[dict], tier: str):
        if tier == "small":
            return self._small(messages)
        return self._large(messages)


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


def seed_intel(
    source_id: str,
    subject: str,
    event_type: str,
    fetched_at: datetime,
    *,
    title: str = "测试情报",
    sha_suffix: str = "",
) -> int:
    """造单条 extracted 状态 intel_item（聚类测试用），返回 id。

    跳过 collect+process 流程，直连库 INSERT——单测聚类逻辑本身。
    """
    with psycopg.connect(PG_DSN) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO source (id, name, domain_id, url, list_url, level, reliability, enabled) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, true) ON CONFLICT (id) DO NOTHING",
            (source_id, f"{source_id} 测", "construction",
             f"http://{source_id}.example/", f"http://{source_id}.example/list",
             "L2", "B"),
        )
        sha = f"sha-{source_id}-{subject}-{fetched_at.isoformat()}-{sha_suffix}"
        cur.execute(
            """INSERT INTO intel_item
            (source_id, url, title, list_url, fetched_at, http_status, content_type,
             encoding, snapshot_id, content_sha1, raw_html, subject, event_type,
             facts, inferences, tags, quant_params, admiralty_code, process_status,
             processed_at)
            VALUES (%s, %s, %s, %s, %s, 200, 'text/html', 'utf-8', %s, %s, '<html/>',
                    %s, %s, '事实', '推断', '[]'::jsonb, '{}'::jsonb, 'B2', 'extracted', %s)
            RETURNING id""",
            (source_id, f"http://{source_id}.example/item-{sha}", title,
             f"http://{source_id}.example/list", fetched_at, sha, sha,
             subject, event_type, fetched_at),
        )
        intel_id = cur.fetchone()[0]
        conn.commit()
    return intel_id


def seed_event(
    *,
    subject: str = "三一",
    event_type: str = "新品发布",
    status: str = "single_source",
    source_count: int = 2,
    ready_for_manual: bool = True,
    days_ago: int = 0,
) -> int:
    """造单条 event + 对应 verification_log（verify CLI / 事件字段测试用），返回 event_id。"""
    t = datetime.now() - timedelta(days=days_ago)
    with psycopg.connect(PG_DSN) as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO event
            (subject, event_type, status, source_count, ready_for_manual,
             first_seen_at, last_seen_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (subject, event_type, status, source_count, ready_for_manual, t, t),
        )
        event_id = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO verification_log
            (event_id, from_status, to_status, operator, reason)
            VALUES (%s, NULL, %s, 'system', '事件创建')""",
            (event_id, "pending"),
        )
        if status != "pending":
            cur.execute(
                """INSERT INTO verification_log
                (event_id, from_status, to_status, operator, reason)
                VALUES (%s, %s, %s, 'system', '第二独立信源命中')""",
                (event_id, "pending", status),
            )
        conn.commit()
    return event_id
