# TASK-4.01.2 设计：采集后自动处理消化 pending

> 决策依据：`docs/mvp-run-decisions-2026-09-03.md` D1（6 故事全绿后追加，用户离场授权）。
> 关联：backlog TASK-4.01.2 ｜ doc-2 §8（at-least-once，先落盘可重放）｜ ADR-004/007。

## 1. 方案

在 `run_source_job` 增可选 `process: Callable[[str], None]` 编排缝——**采集成功后**接力调用
（传入 source_id；采集失败不触发处理）。`pih work` 接线：闭包惰性构造 ProcessRunner
（构造期 LLM 配置缺失抛 LLMConfigError → 捕获降级：记日志与 pipeline_run error，
条目留 pending 不丢弃——AC3 可靠性降级口径）。处理异常同样不使 job 失败
（采集已成功，健康不应归零语义混乱；处理失败留痕可重放）。

| AC | 落点 | 证据 |
|---|---|---|
| AC1 采集完自动接力、全程无命令 | run_source_job process 钩子 + CLI 接线 | unit（成功后调用/失败不调用）+ integration（真链 e2e）+ 过夜 live |
| AC2 单条失败不阻断批 | ProcessRunner 既有容错（单条写库失败继续，test_process_e2e 存量） | 存量证据引用 |
| AC3 LLM 缺失/持续失败降级不丢弃+留痕 | 闭包 LLMConfigError 捕获→pih.work 日志+pipeline_run error 行 | unit（process 异常 job 不失败）+ integration（LLM 配置缺失模拟：process 抛 LLMConfigError） |
| AC4 一周期后 pending 不滞留 | 过夜 pih work 实证 | live（明日晨验收路径） |

## 2. 不做

收件箱页面引导文案 / Web 处理触发入口 / pending 超期提醒（2026-09-03 评审裁定暂缓，任务描述已载）。

## 3. 测试

- unit test_scheduler 增 TestProcessHook：成功后调用（带 source_id）/ 采集失败不调用 / process 抛异常 job 仍 ok 且留痕细节行。
- integration test_worker_e2e 增：fake collect 落 pending（raw_html 带「三一发布新品…销量 1000 台」）→ process=真 ProcessRunner+ScriptChat → 条目 extracted + 事件挂载（AC1 跨接线缝）；process 抛 LLMConfigError → 条目留 pending、job ok（AC3）。
