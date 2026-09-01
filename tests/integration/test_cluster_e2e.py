"""事件聚类端到端集成测试（S1.3.1 AC1-AC5）。

需 docker compose up（postgres + minio）+ 真实领域包。
脚本化 chat 注入确定性抽取输出，验证：
  AC1  单条 extracted → event 表新建 pending + verification_log 首条
  AC2  同主体+同事件类型+时间窗内、第二独立信源 → 跃迁 single_source + ready_for_manual
  AC3  同主体+同源第二条 → source_count 不增，status 仍 pending
  AC4  时间窗外（>7 天）→ 新建 event 不挂入旧的
  AC5  不同 event_type → 不归并

不依赖 LLM 凭据——脚本化 chat 输出 _ok_pred() 确定性通过 schema 校验。
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from _factory import seed_intel
from conftest import q as _q

from pih.cli import _default_pack, main
from pih.domainpacks.loader import load
from pih.envs import load_env
from pih.store.db import close_pool, get_pool
from pih.store.repository import IntelRepository

load_env()

pytestmark = pytest.mark.integration


def _cluster_one(intel_id: int):
    """对单条情报跑聚类（真实 EventService），返回 AttachOutcome 或 None。"""
    pool = get_pool()
    try:
        from pih.process.event import EventService
        from pih.store.event_repository import EventRepository

        repo = IntelRepository(pool)
        event_repo = EventRepository(pool)
        svc = EventService(event_repo, repo, load(_default_pack()))
        return svc.cluster(intel_id)
    finally:
        close_pool()


class TestAC1NewEventCreated:
    def test_single_extracted_creates_pending_event(self):
        """AC1：单条 extracted → 新建 pending 事件 + 首条 log（to=pending）。"""
        intel_id = seed_intel(
            "sany", "三一", "新品发布", datetime(2026, 8, 27, 10, 0, 0)
        )
        event_id = _cluster_one(intel_id).event_id

        assert event_id is not None
        events = _q(
            "SELECT subject, event_type, status, source_count, ready_for_manual "
            "FROM event WHERE id = %s", (event_id,)
        )
        assert events
        subject, et, status, sc, rfm = events[0]
        assert subject == "三一"
        assert et == "新品发布"
        assert status == "pending"
        assert sc == 1
        assert rfm is False

        # verification_log 首条
        logs = _q(
            "SELECT from_status, to_status, operator, reason FROM verification_log "
            "WHERE event_id = %s ORDER BY created_at ASC", (event_id,)
        )
        assert len(logs) == 1
        assert logs[0] == (None, "pending", "system", "事件创建")

        # intel_item.event_id 已挂
        attached = _q("SELECT event_id FROM intel_item WHERE id = %s", (intel_id,))
        assert attached == [(event_id,)]


class TestAC2SecondIndependentSourceAdvances:
    def test_second_source_triggers_single_source(self):
        """AC2：同主体+同事件类型+时间窗内、第二独立信源 → 跃迁 single_source。"""
        t = datetime(2026, 8, 27, 10, 0, 0)
        id1 = seed_intel("sany", "三一", "新品发布", t)
        _cluster_one(id1)

        # 第二条：异源 ccma，3 天后（时间窗内）
        id2 = seed_intel("ccma", "三一", "新品发布", t + timedelta(days=3))
        event_id2 = _cluster_one(id2).event_id

        # 应挂入同一事件
        events = _q("SELECT id FROM event WHERE subject='三一' AND event_type='新品发布'")
        assert len(events) == 1
        event_id = events[0][0]
        assert event_id2 == event_id

        # 状态跃迁 single_source
        rows = _q(
            "SELECT status, source_count, ready_for_manual FROM event WHERE id = %s",
            (event_id,),
        )
        assert rows[0] == ("single_source", 2, True)

        # verification_log 有 2 条：创建 + 跃迁
        logs = _q(
            "SELECT from_status, to_status, operator, reason FROM verification_log "
            "WHERE event_id = %s ORDER BY created_at ASC",
            (event_id,),
        )
        assert len(logs) == 2
        assert logs[1] == ("pending", "single_source", "system", "第二独立信源命中")


class TestAC3SameSourceDoesNotAdvance:
    def test_same_source_second_item_no_advance(self):
        """AC3：同主体+同源第二条 → source_count 不增，status 仍 pending。"""
        t = datetime(2026, 8, 27, 10, 0, 0)
        id1 = seed_intel("sany", "三一", "新品发布", t)
        _cluster_one(id1)

        # 第二条：同源 sany，2 天后
        id2 = seed_intel("sany", "三一", "新品发布", t + timedelta(days=2))
        _cluster_one(id2)

        events = _q(
            "SELECT status, source_count, ready_for_manual FROM event "
            "WHERE subject='三一' AND event_type='新品发布'"
        )
        assert events
        status, sc, rfm = events[0]
        assert status == "pending"  # 未跃迁
        assert sc == 1  # 同源不增
        assert rfm is False


class TestAC4OutsideTimeWindowNewEvent:
    def test_beyond_7_days_creates_new_event(self):
        """AC4：时间窗外（>7 天）→ 新建 event 不挂入旧的。"""
        t1 = datetime(2026, 8, 20, 10, 0, 0)
        id1 = seed_intel("sany", "三一", "新品发布", t1)
        event_id1 = _cluster_one(id1).event_id

        # 10 天后——超出 ±7 天窗
        id2 = seed_intel("ccma", "三一", "新品发布", t1 + timedelta(days=10))
        event_id2 = _cluster_one(id2).event_id

        assert event_id2 is not None
        assert event_id2 != event_id1  # 不同事件

        events = _q(
            "SELECT COUNT(*) FROM event WHERE subject='三一' AND event_type='新品发布'"
        )
        assert events[0][0] == 2  # 两个独立事件


class TestAC5DifferentEventTypeNoMerge:
    def test_different_event_type_creates_separate_events(self):
        """AC5：同主体+不同 event_type → 不归并（建独立事件）。"""
        t = datetime(2026, 8, 27, 10, 0, 0)
        id1 = seed_intel("sany", "三一", "新品发布", t)
        event_id1 = _cluster_one(id1).event_id

        id2 = seed_intel("ccma", "三一", "专利公开", t + timedelta(days=1))
        event_id2 = _cluster_one(id2).event_id

        assert event_id2 is not None
        assert event_id2 != event_id1

        events = _q(
            "SELECT event_type FROM event WHERE subject='三一' ORDER BY id"
        )
        assert {r[0] for r in events} == {"新品发布", "专利公开"}


class TestAliasNormalization:
    def test_alias_subject_merges_into_same_event(self):
        """主体归一化：三一重工 → 三一，应挂入已有「三一」事件。"""
        t = datetime(2026, 8, 27, 10, 0, 0)
        id1 = seed_intel("sany", "三一", "新品发布", t)
        _cluster_one(id1)

        # 第二条抽取输出 subject=「三一重工」（领域包别名），异源
        id2 = seed_intel("ccma", "三一重工", "新品发布", t + timedelta(days=2))
        event_id2 = _cluster_one(id2).event_id

        events = _q("SELECT id FROM event WHERE subject='三一'")
        assert len(events) == 1
        assert event_id2 == events[0][0]

        # 不应留下 subject='三一重工' 的事件
        bad = _q("SELECT id FROM event WHERE subject='三一重工'")
        assert bad == []


class TestBackfillCommand:
    def test_cluster_backfill_attaches_existing_extracted(self, capsys):
        """pih cluster --backfill：对存量 extracted 但 event_id IS NULL 条目逐条聚类。"""
        # 造 3 条 extracted 但未挂事件（直接 INSERT 跳过聚类）
        t = datetime(2026, 8, 27, 10, 0, 0)
        seed_intel("sany", "三一", "新品发布", t)
        seed_intel("ccma", "三一", "新品发布", t + timedelta(days=1))  # 第二独立信源
        seed_intel("sany", "徐工", "财报", t + timedelta(days=2))

        # 跑 backfill
        code = main(["cluster", "--backfill", "--limit=10"])
        out = capsys.readouterr().out
        assert code == 0, f"backfill 失败：\n{out}"
        assert "挂入 3 条" in out

        # 三一两条应触发跃迁（第二独立信源）
        events = _q(
            "SELECT subject, status, source_count FROM event "
            "WHERE subject='三一' AND event_type='新品发布'"
        )
        assert events
        _, status, sc = events[0]
        assert status == "single_source"
        assert sc == 2

        # 徐工单独一个 pending 事件
        xcmg_events = _q(
            "SELECT status, source_count FROM event WHERE subject='徐工'"
        )
        assert xcmg_events
        assert xcmg_events[0] == ("pending", 1)

        # 所有 extracted 条目都已挂 event_id
        unattached = _q(
            "SELECT COUNT(*) FROM intel_item "
            "WHERE process_status='extracted' AND event_id IS NULL"
        )
        assert unattached[0][0] == 0
