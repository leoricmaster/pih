"""采集调度器（TASK-4.01.01，ADR-004/008 · pih-worker 进程内）。

结构：
- run_source_job：编排缝——门控/采集/退避重试/健康回写/pipeline_run 留痕，
  全依赖注入（collect/sleep/health/runs），单测禁真网络真时钟（doc-5 §4）；
- configure_scheduler：把启用源注册进 APScheduler——启动扫（stagger 错峰，
  重启补跑语义）+ 频率 job（hourly=间隔 / daily=每日 07:30 / weekly=周一 07:30，
  CronTrigger 错过即跳过不追赶，doc-2 §8）；
- main_work：pih work 入口（--once 单源同步跑一轮退出，运维/集成测试用）。

健康语义（设计 D9'）：job 级异常=信源失败（连续 3 次触发告警，TASK-4.02.01）；
条目级 fetch 失败落死信行计入 items_failed，不算信源失败。
退避：指数 2s/4s/8s，重试 3 次（首试+3）；SourceDisabledError 属配置错误不重试。
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import datetime, timedelta

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from pih.collect.base import SourceConfig
from pih.collect.run import DEFAULT_MAX_ITEMS, SourceDisabledError, collect_source
from pih.store.pipeline_run import PipelineRunRepository
from pih.store.source_health import SourceHealthRepository

logger = logging.getLogger("pih.work")

# 退避序列（秒）——指数 2/4/8（架构 §8 重试 ×3）
DEFAULT_BACKOFF: tuple[int, ...] = (2, 4, 8)

# 启动扫错峰：每源间隔（秒），避免多源齐射
STARTUP_STAGGER_SECONDS = 45

# daily/weekly 的 cron 锚点（晨峰后，评审窗口前）
_DAILY_HOUR = 7
_DAILY_MINUTE = 30


class JobResult:
    """单源一轮采集的结果（pipeline_run 行的人读形态）。"""

    def __init__(
        self,
        *,
        ok: bool,
        attempts: int,
        items_new: int = 0,
        items_skipped: int = 0,
        items_failed: int = 0,
        error: str | None = None,
    ) -> None:
        self.ok = ok
        self.attempts = attempts
        self.items_new = items_new
        self.items_skipped = items_skipped
        self.items_failed = items_failed
        self.error = error


def _fmt_exc(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def run_source_job(
    source: SourceConfig,
    *,
    collect: Callable = collect_source,
    health: SourceHealthRepository,
    runs: PipelineRunRepository,
    sleep: Callable[[float], None] = time.sleep,
    backoff: tuple[int, ...] = DEFAULT_BACKOFF,
    max_items: int = DEFAULT_MAX_ITEMS,
    run_type: str = "scheduled",
) -> JobResult:
    """单源一轮采集：失败退避重试（首试 + len(backoff) 次），终态回写健康与留痕。"""
    t0 = time.monotonic()
    attempts = 0
    last_exc: Exception | None = None
    while attempts <= len(backoff):
        attempts += 1
        try:
            items, outcomes = collect(source, max_items=max_items)  # type: ignore[call-arg]
            last_exc = None
            break
        except SourceDisabledError as exc:
            last_exc = exc
            break  # 配置错误：重试无意义
        except Exception as exc:  # noqa: BLE001 抓取失败统一退避（架构 §8）
            last_exc = exc
            if attempts <= len(backoff):
                sleep(backoff[attempts - 1])

    duration_ms = int((time.monotonic() - t0) * 1000)
    if last_exc is not None:
        reason = _fmt_exc(last_exc)
        health.record_failure(source.id, reason)
        runs.record_run(
            source_id=source.id, run_type=run_type, duration_ms=duration_ms,
            ok=False, error=reason,
        )
        logger.warning(
            "source=%s ok=false attempts=%d error=%s", source.id, attempts, reason
        )
        return JobResult(ok=False, attempts=attempts, error=reason)

    items_new = sum(1 for o in outcomes if o.status == "saved")
    items_skipped = sum(1 for o in outcomes if o.status == "skipped")
    items_failed = sum(1 for o in outcomes if o.status == "failed")
    health.record_success(source.id)
    runs.record_run(
        source_id=source.id, run_type=run_type, duration_ms=duration_ms,
        ok=True, items_new=items_new, items_skipped=items_skipped,
        items_failed=items_failed,
    )
    logger.info(
        "source=%s ok=true attempts=%d new=%d skipped=%d failed=%d",
        source.id, attempts, items_new, items_skipped, items_failed,
    )
    return JobResult(
        ok=True, attempts=attempts, items_new=items_new,
        items_skipped=items_skipped, items_failed=items_failed,
    )


def _frequency_trigger(freq: str) -> CronTrigger | IntervalTrigger:
    """频率 → 触发器（设计 D8a）。未知频率按日处理（pack 校验层已限枚举）。"""
    if freq == "hourly":
        return IntervalTrigger(hours=1, jitter=120)
    if freq == "weekly":
        return CronTrigger(
            day_of_week="mon", hour=_DAILY_HOUR, minute=_DAILY_MINUTE, jitter=300
        )
    return CronTrigger(hour=_DAILY_HOUR, minute=_DAILY_MINUTE, jitter=300)


def configure_scheduler(
    sched: BlockingScheduler,
    sources: list[SourceConfig],
    job_fn: Callable[[str], None],
    *,
    now: datetime | None = None,
) -> None:
    """注册启动扫（stagger 补跑）+ 频率 job。disabled 源不注册。

    job_fn(source_id) 由调用方闭包 run_source_job（注入 repo/health 等依赖）。
    """
    enabled = [s for s in sources if s.enabled]
    base = (now or datetime.now()) + timedelta(seconds=10)
    for i, s in enumerate(enabled):
        sched.add_job(
            job_fn,
            DateTrigger(run_date=base + timedelta(seconds=i * STARTUP_STAGGER_SECONDS)),
            kwargs={"source_id": s.id, "run_type": "startup"},
            id=f"startup-{s.id}",
            name=f"启动扫 {s.id}",
            max_instances=1,
        )
        sched.add_job(
            job_fn,
            _frequency_trigger(s.fetch_frequency),
            kwargs={"source_id": s.id},
            id=f"{s.fetch_frequency}-{s.id}",
            name=f"采集 {s.id}（{s.fetch_frequency}）",
            max_instances=1,
            coalesce=True,
        )
