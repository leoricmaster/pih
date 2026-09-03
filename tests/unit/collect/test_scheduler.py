"""调度器单测（TASK-4.01.01）——run_source_job 编排缝 + 触发器映射。

全部依赖注入（collect/sleep/health/runs 均可替换，doc-5 §4 单测禁真网络真时钟）；
真库往返与真实调度进程在 integration/live。
"""
from __future__ import annotations

from unittest.mock import MagicMock

from pih.collect.base import SourceConfig
from pih.collect.scheduler import JobResult, configure_scheduler, run_source_job


def _src(enabled: bool = True, freq: str = "daily") -> SourceConfig:
    return SourceConfig(
        id="ccma", name="测试源", type="html", url="http://x/",
        list_url="http://x/list", reliability="B", level="L2",
        fetch_frequency=freq, enabled=enabled,
    )


class _FakeRawItem:
    snapshot_id = "sha-abc"
    title = "t"


class _FakeOutcome:
    def __init__(self, status: str) -> None:
        self.status = status


class _FakeHealth:
    def __init__(self) -> None:
        self.successes: list[str] = []
        self.failures: list[tuple[str, str]] = []

    def record_success(self, sid):
        self.successes.append(sid)

    def record_failure(self, sid, reason):
        self.failures.append((sid, reason))


class _FakeRuns:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def record_run(self, **kw):
        self.rows.append(kw)


class TestRunSourceJob:
    def _fakes(self):
        return _FakeHealth(), _FakeRuns(), []

    def test_success_first_try_no_sleep(self):
        health, runs, sleeps = self._fakes()
        collect = MagicMock(
            return_value=([_FakeRawItem()], [_FakeOutcome("saved")])
        )
        res = run_source_job(
            _src(), collect=collect, health=health, runs=runs,
            sleep=sleeps.append, backoff=(2, 4, 8),
        )
        assert isinstance(res, JobResult) and res.ok
        assert res.attempts == 1 and res.items_new == 1
        assert sleeps == []  # 一次成功不退避
        assert health.successes == ["ccma"] and health.failures == []
        assert runs.rows[0]["ok"] is True and runs.rows[0]["items_new"] == 1

    def test_retry_with_backoff_then_success(self):
        health, runs, sleeps = self._fakes()
        calls = {"n": 0}

        def flaky(*a, **kw):
            calls["n"] += 1
            if calls["n"] < 3:
                raise ConnectionError("抖动")
            return ([_FakeRawItem()], [_FakeOutcome("saved")])

        res = run_source_job(
            _src(), collect=flaky, health=health, runs=runs,
            sleep=sleeps.append, backoff=(2, 4, 8),
        )
        assert res.ok and res.attempts == 3
        assert sleeps == [2, 4]  # 第 2、3 次尝试前退避
        assert health.successes == ["ccma"]

    def test_exhausted_retries_count_failure(self):
        health, runs, sleeps = self._fakes()
        collect = MagicMock(side_effect=ConnectionError("一直断"))
        res = run_source_job(
            _src(), collect=collect, health=health, runs=runs,
            sleep=sleeps.append, backoff=(2, 4, 8),
        )
        assert not res.ok and res.attempts == 4  # 首试 + 3 重试
        assert sleeps == [2, 4, 8]
        assert health.failures == [("ccma", "ConnectionError: 一直断")]
        assert health.successes == []
        assert runs.rows[0]["ok"] is False
        assert "一直断" in runs.rows[0]["error"]

    def test_disabled_gate_no_retry(self):
        from pih.collect.run import SourceDisabledError

        health, runs, sleeps = self._fakes()
        collect = MagicMock(side_effect=SourceDisabledError("未启用"))
        res = run_source_job(
            _src(enabled=False), collect=collect, health=health, runs=runs,
            sleep=sleeps.append, backoff=(2, 4, 8),
        )
        assert not res.ok and res.attempts == 1  # 配置错误重试无意义
        assert sleeps == []
        assert health.failures and "未启用" in health.failures[0][1]

    def test_item_level_failures_counted_not_source_failure(self):
        """D9'：条目级死信计入 items_failed，不算信源失败。"""
        health, runs, sleeps = self._fakes()
        collect = MagicMock(
            return_value=([], [])
        )
        # collect_source 返回 (items, outcomes)；items_failed 由 outcomes 统计
        # 这里直接给 saved/skipped/failed 混合 outcomes 验统计
        collect.return_value = (
            [_FakeRawItem()],
            [_FakeOutcome("saved"), _FakeOutcome("skipped"), _FakeOutcome("failed")],
        )
        res = run_source_job(
            _src(), collect=collect, health=health, runs=runs,
            sleep=sleeps.append, backoff=(2, 4, 8),
        )
        assert res.ok
        assert (res.items_new, res.items_skipped, res.items_failed) == (1, 1, 1)
        assert health.successes == ["ccma"]


class TestAlertHook:
    """TASK-4.02.01 D10/D17：恰达连续失败 3 次触发一次站内信告警。"""

    def _run_failing_jobs(self, times: int, notify) -> None:
        class _CountingHealth(_FakeHealth):
            def record_failure(self, sid, reason):
                self.failures.append((sid, reason))
                return len(self.failures)  # 模拟 RETURNING 跨轮递增计数

        h = _CountingHealth()
        collect = MagicMock(side_effect=ConnectionError("断"))
        for _ in range(times):
            run_source_job(
                _src(), collect=collect, health=h, runs=_FakeRuns(),
                sleep=lambda s: None, backoff=(0, 0, 0), notify=notify,
            )

    def test_alert_fires_exactly_at_threshold(self):
        alerts: list[tuple[str, str]] = []
        self._run_failing_jobs(3, lambda t, b: alerts.append((t, b)))
        assert len(alerts) == 1
        title, body = alerts[0]
        assert "测试源" in title and "连续失败 3 次" in title  # 含信源名（AC1）
        assert "断" in body  # 含失败原因（AC1）

    def test_fourth_failure_no_repeat_alert(self):
        """episode 语义（D10）：持续失败不重复告警。"""
        alerts: list[tuple[str, str]] = []
        self._run_failing_jobs(4, lambda t, b: alerts.append((t, b)))
        assert len(alerts) == 1

    def test_below_threshold_no_alert(self):
        alerts: list[tuple[str, str]] = []
        self._run_failing_jobs(2, lambda t, b: alerts.append((t, b)))
        assert alerts == []

    def test_no_notify_no_crash(self):
        self._run_failing_jobs(3, None)  # 未接通知（如 CLI 手动）不炸

    def test_success_path_never_alerts(self):
        alerts: list[tuple[str, str]] = []
        health, runs, _ = _FakeHealth(), _FakeRuns(), []
        run_source_job(
            _src(),
            collect=MagicMock(return_value=([], [])),
            health=health, runs=runs, sleep=lambda s: None,
            notify=lambda t, b: alerts.append((t, b)),
        )
        assert alerts == []


class TestConfigureScheduler:
    def test_registers_startup_sweep_and_frequency_jobs(self):
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.interval import IntervalTrigger

        sched = MagicMock()
        sources = [
            _src(freq="daily"),
            SourceConfig(
                id="sany", name="s", type="html", url="http://y/",
                list_url="http://y/l", reliability="B", level="L2",
                fetch_frequency="hourly", enabled=True,
            ),
            SourceConfig(
                id="weekly1", name="w", type="html", url="http://z/",
                list_url="http://z/l", reliability="C", level="L3",
                fetch_frequency="weekly", enabled=True,
            ),
            _src(freq="daily").__class__(
                id="off", name="o", type="html", url="http://o/",
                list_url="http://o/l", reliability="C", level="L3",
                fetch_frequency="daily", enabled=False,
            ),
        ]
        configure_scheduler(sched, sources, job_fn=lambda **kw: None)
        jobs = {c.kwargs["id"]: c for c in sched.add_job.call_args_list}
        # 启动扫：每启用源一个 startup job（disabled 不注册），run_type=startup
        startup = [j for jid, j in jobs.items() if jid.startswith("startup-")]
        assert len(startup) == 3
        assert all(
            j.kwargs["kwargs"]["run_type"] == "startup" for j in startup
        )
        # 频率 job：daily→cron / hourly→interval / weekly→cron / disabled 无
        # （trigger 为第二个位置参数）
        assert isinstance(jobs["daily-ccma"].args[1], CronTrigger)
        assert isinstance(jobs["hourly-sany"].args[1], IntervalTrigger)
        assert isinstance(jobs["weekly-weekly1"].args[1], CronTrigger)
        assert not any("off" in jid for jid in jobs)
        # 启动扫 stagger 错峰（同源序号 × 45s 递增）
        starts = [
            j.args[1].run_date
            for jid, j in sorted(jobs.items()) if jid.startswith("startup-")
        ]
        deltas = [
            (b - a).total_seconds() for a, b in zip(starts, starts[1:], strict=False)
        ]
        assert all(d == 45 for d in deltas)
