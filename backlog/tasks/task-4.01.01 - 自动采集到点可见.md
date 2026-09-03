---
id: TASK-4.01.01
title: 自动采集到点可见
status: Done
assignee:
  - '@lancer'
created_date: '2026-09-01 09:26'
updated_date: '2026-09-03 11:51'
labels:
  - web
milestone: m-0
dependencies:
  - TASK-1.01.02
references:
  - docs/prototype.html
parent_task_id: TASK-4.01
priority: high
type: story
ordinal: 24000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
作为消费者，注册信源按其频率自动更新，我什么都不做——到点打开 Web 列表就出现新情报（带采集时间戳），以便真正省去盯源与手动触发的机械工作。

验收面：Web 列表到点自动出现新条目（无需任何人运行命令）。

不在本故事：采集入库与去重 / 粗筛 / 落盘可重放（→ TASK-1.01.02，本故事只加调度层）；信源健康告警与连续失败统计的呈现（→ TASK-4.02.01）。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 AC1: Given 信源配置频率为每日且已启用 ｜ When 调度时间到达 ｜ Then 系统自动抓取新内容并生成原文快照 ｜ And 新条目出现在 Web 列表（采集入库故事的全部 AC 对调度触发同样成立）｜ And 无快照的内容不进入后续流水线
- [x] #2 AC2: Given 抓取失败（网络 / 反爬）｜ Then 按指数退避重试 3 次，仍失败计入信源健康统计（触发信源健康告警，跨 TASK-4.02）
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 验收面字段与事实源（领域包 schema / 原型 IA / doc-2）逐项核对一致；偏差先修订事实源或记 ADR，不在代码里私自偏移
- [x] #2 无新增未论证的自部署组件；核心代码不出现行业知识硬编码（违反即返工）
- [x] #3 AC 全满足，每条有可复现证据（测试名 / 命令 / 截图），实际运行通过——非臆测的「应能通过」推断
- [ ] #4 CI 有增量测试且变绿；覆盖正常路径与关键失败路径
- [x] #5 无回归（现有测试不破）
- [x] #6 触碰的架构 / ADR / NFR / 运营手册同步更新，day0 文档改动进正文不留批注
- [x] #7 结构化日志与运行留痕按 doc-2 §8 落地；迁移 / 配置变更可回滚（1 人可恢复）
- [x] #8 无密钥硬编码；新增依赖真实、锁版本、无高危 CVE
- [x] #9 不违反贯穿性约束与 ADR（偏离须先记 ADR）
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
新组件故事（设计 docs/design/TASK-4.01.01-design.md，D8/D9/D12 已决）。切片：1) 迁移 0003（source 健康列+pipeline_run 表）契约先红 2) SourceHealthRepository+PipelineRunRepository（unit SQL 契约）3) run_source_job 编排缝（unit：成功/退避重试/耗尽计健康/门控不重试）4) configure_scheduler 触发器映射（unit stub 断言）+ pih work CLI（--once）5) integration worker_e2e（fake collect 真库）+ compose worker 服务 6) README+finalization
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
TDD 切片 1（迁移 0003）：契约 3 例先红（健康列/pipeline_run 表+索引/downgrade 0002 可逆）→ source 加 consecutive_failures/last_failure_at/last_failure_reason/last_success_at + pipeline_run 表（token 列 NULL 预留 D16）→ 绿（21 passed）。
TDD 切片 2（仓储）：unit test_source_health 5 例（_MockConn SQL 契约）→ SourceHealthRepository（成功清零+last_success_at/失败+1+原因）+ PipelineRunRepository.record_run → 绿。
TDD 切片 3（调度编排缝）：unit test_scheduler 先红 → run_source_job（首试+3 退避重试 2/4/8s；SourceDisabledError 不重试；成功清 last_exc 修复重试后误判 bug；条目级 failed 计入 items_failed 不算信源失败 D9'）→ 绿 6 例。
TDD 切片 4（注册+CLI）：configure_scheduler（启动扫 stagger 45s/源 run_type=startup + 频率映射 hourly=Interval(1h,jitter)/daily=Cron 07:30/weekly=周一 07:30，disabled 不注册；CronTrigger 错过即跳过不追赶）；pih work [--once SOURCE_ID] CLI（--once 打印统计行）。compose worker 服务挂 profile worker（docker compose up -d 不启动，防本地起服即真实采集；生产 --profile worker up -d）。
integration test_worker_e2e 3 例（fake collect 真库）：成功路径健康清零+留痕行/失败路径 4 轮尝试+consecutive_failures≥1+原因入库/成功重置既有失败计数。**修真 bug**：record_failure 参数顺序与占位符颠倒（单测错序被锁成契约、真库现形——参数改 (reason, source_id)）；get_health 缺 dict_row（mock 掩盖，live 现形修复）。
live 实弹：pih work --once ccma --max-items 3 →「✓ 采集完成（尝试 1 轮）：入库 0 新增 / 3 幂等跳过 / 0 失败」（此前一轮已实收 3 新增，幂等吸收）；source.ccma consecutive_failures=0 + last_success_at 落值；pipeline_run 行 duration_ms=6251/6330（真时长）；/inbox Web 列表 3 条 pending 可见（AC1 到点可见的等价单源证据；常驻到点可见由过夜 pih work 承载 D12）。
README：pih work 命令 + 无人值守采集段（启动扫/频率映射/退避/健康/留痕/compose profile）。
回归：unit+contract 437 / integration worker_e2e 3 / ruff 干净（apscheduler==3.11.3 锁版）。
AC 证据索引：AC1=unit configure_scheduler 触发器映射+启动扫+stagger 断言 / integration worker_e2e 真库落行 / live --once 实弹+Web /inbox 可见 / 采集入库 AC 复用 collect_source 同链（不重写）；AC2=unit 退避三例（一次成功不 sleep/重试成功 2,4/耗尽 4 轮）+ integration 失败路径健康计数+原因入库。
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
自动采集到点可见交付（新组件：APScheduler worker）。pih work 常驻进程——启动扫（stagger 45s/源，重启补跑，幂等吸收）+频率触发（hourly 间隔/daily 07:30/weekly 周一 07:30，Cron 错过不追赶）；run_source_job 编排缝全依赖注入：job 级异常 2/4/8s 指数退避重试 3 次（AC2 unit 三路证据），耗尽计入 source.consecutive_failures（迁移 0003 D9，连续 3 次告警底座→4.02.01）；每次调度写 pipeline_run（D6 遗留落地，token 列预留）；pih work --once 运维入口；compose worker 服务（profile 隔离防本地起服即采集）。AC1 调度触发的采集走 collect_source 同链（1.01.02 全 AC 天然成立），live --once 实弹 0新增/3跳过/0失败+健康行+真时长留痕+Web /inbox 3 条可见。修复两个 mock 掩盖的真 bug（record_failure 参数倒序/get_health 缺 dict_row）。回归 unit+contract 437/worker_e2e 3/ruff 干净；apscheduler==3.11.3。DoD 8/9，#4 待 push（PD2）。
<!-- SECTION:FINAL_SUMMARY:END -->
