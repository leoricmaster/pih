# TASK-4.01.01 设计：自动采集到点可见

> 关联：backlog TASK-4.01.01 ｜ doc-2 §8 可靠性 / §9 部署（pih-worker）｜ ADR-004/008。
> 决策同步 `docs/mvp-run-decisions-2026-09-03.md` D8/D9/D12。

## 1. 范围与存量映射

| AC | 存量（实测） | 本故事增量 |
|---|---|---|
| AC1 到点自动采集→快照→Web 列表可见 | collect_source 为调度预留入口（run.py docstring）；fetch_frequency 字段落盘；compose 有 app(sleep)/web 服务 | **`pih work` worker 进程**（APScheduler 3.x BlockingScheduler）：每启用源一 job；**迁移 0003**（source 健康列 + pipeline_run 表，D6 遗留落地）；compose `worker` 服务（单镜像双角色 ADR-008）；采集入库既有 AC 靠 collect_source 复用（不重写） |
| AC2 失败退避重试×3→计入健康统计 | 无 | `run_source_job`：异常按 2s/4s/8s 指数退避重试 3 次；成功清零计数/失败 +1（D9 列）；每次调度写 pipeline_run + pih.work 结构化日志 |

范围外：采集后自动处理 pending（→TASK-4.01.2，是否入 m-0 待用户裁定 D1）；健康告警呈现（→4.02.01）；追赶风暴（doc-2 §8 明确不做）。

## 2. 关键决策与理由

| # | 决策 | 备选与否决理由 |
|---|---|---|
| D8a | **触发器映射**：hourly→IntervalTrigger(1h)；daily→CronTrigger(hour=7, minute=30±jitter)；weekly→CronTrigger(day_of_week=mon, hour=7)；**worker 启动即做一轮 stagger 起始扫**（每源错开 ~45s，幂等靠 content_sha1 吸收） | 固定 IntervalTrigger(daily=24h) 从启动时刻计——错过即+24h，晨间评审窗口看不到新采集；7:30 晨峰 + 启动扫覆盖「重启补跑」语义（doc-2 §8 错过周期下一轮补跑，不做风暴）；jitter 错峰防齐射 |
| D8b | **退避在 job 内同步做**（sleep 2/4/8，注入可测），3 次重试=首试+3 重试；重试耗尽才计健康失败 | 退避状态入库（过度设计，单机单用户）；APScheduler 自带 misfire 重试（语义是错过不是失败） |
| D9' | **健康语义**：job 级异常（列表抓取失败/适配器异常）=信源失败；列表成功即成功（条目级 dead 行计入 pipeline_run.items_failed，不算信源失败） | 条目级失败混入会让健康计数取决于单条 URL 抖动；信源健康回答「这个源还能不能抓」 |
| D15 | `pih work --once <source_id>`：单源立即跑一轮退出（集成测试与运维手动触发） | 无 dry-run 入口则 integration 只能起真调度进程（慢且不可断言） |
| D16 | pipeline_run 列含 prompt/completion_tokens（NULL 预留，采集阶段不写）——doc-2 §7 口径一次建全，4.01.2 处理接力时启用 | 先建吞吐列后加 token 列=两次迁移 |

## 3. 接口与状态语义

- 迁移 0003：source 加 `consecutive_failures INT NOT NULL DEFAULT 0` / `last_failure_at` / `last_failure_reason` / `last_success_at`；新建 `pipeline_run`（source_id FK、run_type、started_at、duration_ms、ok、items_new/skipped/failed、error、prompt_tokens/completion_tokens NULL、created_at + 索引）；downgrade 全可逆。
- `store/source_health.py` `SourceHealthRepository`：`record_success(source_id)`（清零+last_success_at=now）/ `record_failure(source_id, reason)`（+1+last_failure_*）/ `get_health(source_id)`。
- `store/pipeline_run.py` `PipelineRunRepository`：`record_run(source_id, run_type, duration_ms, ok, items_new, items_skipped, items_failed, error=None)`。
- `collect/scheduler.py`：
  - `run_source_job(source, *, collect=collect_source, health, runs, sleep, backoff=(2,4,8), max_items) -> JobResult(ok, attempts, items_new, items_skipped, items_failed, error)`——编排缝，全部依赖注入（doc-5 §4 单测禁真网络/真时钟）。
  - `configure_scheduler(sched, sources, job_fn)`——注册启动扫（DateTrigger now+stagger）+频率 job（D8a 映射）；纯注册不 start，可注入 stub 断言。
  - `main_work(pack_path, once=None)`——构造依赖（pool/health/runs/http/snapshots）+ BlockingScheduler.run()（`--once` 同步跑单源退出）。
- CLI：`pih work [--pack] [--once SOURCE_ID]`。
- compose：`worker` 服务（build 同镜像，command `pih work`，depends_on postgres/minio）。

## 4. 测试与 CI

| 层 | 增量 |
|---|---|
| unit | 迁移契约（source 健康列/pipeline_run 表/可逆）进 contract（PG）；`test_source_health`（SQL 捕获 _MockConn）+ `test_pipeline_run`；`test_scheduler`：run_source_job 成功路径（一次成功不 sleep）/ 失败退避重试 3 次后成功 / 耗尽计失败+健康回写 / SourceDisabledError 直接失败不重试；configure_scheduler 注册断言（hourly/daily/weekly 触发器类型+启动扫 stagger） |
| contract | 0003 迁移三例（列在/表在索引在/downgrade 可逆） |
| integration | `test_worker_e2e`：run_source_job 注入 fake collect（成功/耗尽失败两路）真库验 source 健康行 + pipeline_run 行落库；`pih work --once ccma` 真实 CLI 入口（fake? 否——live 边界）。真网络采集留 live |
| live | 收尾 `pih work` 实弹起进程 + 手动 collect 对比；明早到点可见由过夜 worker 承载（D12） |

## 5. 事实源偏差与裁决

| 偏差 | 裁决 |
|---|---|
| doc-2 §8「错过的周期下一轮补跑」 vs CronTrigger 错过即跳过 | 启动扫承担「重启补跑」（worker 拉起即全源扫一轮，幂等吸收）；运行中错过的 cron 点跳到下一周期——与「不做追赶风暴」一致，README 记档 |

## 6. AC 证据清单

- AC1：unit configure_scheduler（频率→触发器映射+启动扫）+ integration worker_e2e（真库落 pending 行→Web 列表可见走 1.01.02 既有链）+ live（收尾实弹+过夜）
- AC2：unit run_source_job 退避/耗尽两路 + integration 健康列回写 + live 连续失败场景（演示数据阶段用 disabled/unreachable 源试一把或以 unit/integration 为准）
