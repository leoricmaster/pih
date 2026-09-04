---
id: TASK-4.01.2
title: 采集后自动处理消化 pending
status: Done
assignee:
  - '@lancer'
created_date: '2026-09-03 10:28'
updated_date: '2026-09-04 02:14'
labels: []
milestone: m-0
dependencies:
  - TASK-4.01.01
references:
  - backlog/docs/doc-2 - 架构设计-Architecture.md
  - backlog/tasks/task-1.01.02 - 采集入库与原文可查.md
parent_task_id: TASK-4.01
type: story
ordinal: 32000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
现状（2026-09-03 TASK-1.01.02 评审暴露）：处理链（粗筛→抽取→校验，ADR-004）仅 CLI 手动入口（pih process / --prefilter-only），采集入库的 pending 条目没有任何自动消化路径；TASK-4.01.01 只加采集调度层（其描述明确排除粗筛与处理）。后果：pending 无限积压、无时限无提醒，收件箱页面成为「只进不出且出口（处理链触发）不可见」的队列。

本故事补位：调度采集完成后自动接力触发处理链，pending 到点自动流转为 extracted / filtered_out / needs_manual，实现「采集→处理」无人值守闭环。

运营模型澄清（随本故事入档）：收件箱页面定位为采集验收面 + 漏报审计（doc-2 §6.4 已载），不承载处理触发；pending 的消化属处理链职责，由本故事的自动接力承接。

不在本故事（2026-09-03 评审裁定暂缓，如需另立）：收件箱页面处理引导文案；Web 处理触发入口；pending 超期提醒。

验收面：无人值守一周期后，新采集条目到点自动从 pending 流转为成品或终态标记，运营者无需运行任何命令。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Given 调度器完成一次自动采集 | When 该批采集结束 | Then 同批 pending 条目自动进入处理链（粗筛→抽取→校验），全程无需任何人运行命令
- [x] #2 Given 处理链自动运行 | When 单条粗筛判否或抽取校验失败 | Then 条目落 filtered_out / needs_manual（原因可查、不丢弃、可重放），批处理继续其余条目
- [x] #3 Given LLM 配置缺失或调用持续失败 | When 处理链被触发 | Then 按 doc-3 可靠性降级不丢弃，失败原因落运行留痕（结构化日志 / pipeline_run）
- [x] #4 Given 无人值守运行一个完整采集周期 | When 运营者打开收件箱与检索 | Then 新条目不再滞留 pending（自动流转为 extracted 或终态标记），页面仅剩需人工处置的异常态
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 AC 全满足，每条有可复现证据（测试名 / 命令 / 截图），实际运行通过——非臆测的「应能通过」推断
- [x] #2 CI 有增量测试且变绿；覆盖正常路径与关键失败路径
- [x] #3 无回归（现有测试不破）
- [x] #4 触碰的架构 / ADR / NFR / 运营手册同步更新，day0 文档改动进正文不留批注
- [x] #5 结构化日志与运行留痕按 doc-2 §8 落地；迁移 / 配置变更可回滚（1 人可恢复）
- [x] #6 无密钥硬编码；新增依赖真实、锁版本、无高危 CVE
- [x] #7 不违反贯穿性约束与 ADR（偏离须先记 ADR）
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
采集成功后接力处理链（设计 docs/design/TASK-4.01.2-design.md）。run_source_job 增 process 编排缝（成功后调用/异常降级不回滚）；CLI _cmd_work 接惰性 ProcessRunner（LLM 缺失降级留 pending）；unit 3 例 + integration 真链 e2e 2 例。AC4 过夜运行明晨验证后置 Done。
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
TDD：unit TestProcessHook 3 例先红（process 参数不存在）→ run_source_job 增 process 编排缝（成功后调用带 source_id/采集失败不调用/处理异常 job 仍 ok 且 pih.work 日志留痕）→ 绿。CLI _cmd_work/_process 接线：惰性 ProcessRunner，LLMConfigError 捕获降级（条目留 pending 可重放，AC3）。
integration test_worker_e2e 增 TestProcessHandoffE2E 2 例：①fake collect 落 pending（raw_html 三一新品文）→ process=真 ProcessRunner+ScriptChat（ok_pred 过真实领域包校验）→ 条目 extracted（subject=三一/admiralty=B2 继承信源）+ event_id 挂载——AC1 采集→处理→聚类跨接线缝闭环；②process 抛 LLMConfigError → job ok + 条目留 pending——AC3 降级不丢弃。
回归：unit+contract 459 / worker_e2e 5 / ruff 干净。修复 test_verify_page 时间脆弱（硬编码 09-03 基准跨日变 11 天→改相对 now）。
AC 证据索引：AC1=unit test_process_called_after_success + integration test_handoff_extracts_and_clusters（真链 extracted+挂事件）+ 过夜 live；AC2=ProcessRunner 既有容错存量（test_process_e2e 单条写库失败继续）；AC3=unit test_process_failure_keeps_job_ok + integration test_llm_missing_degrades_items_stay_pending；AC4=过夜 pih work 运行，明晨打开 /inbox 与 / 验证（本轮结束时启动，见决策日志 D12）。

用户验收（2026-09-04 晨）：认可无人值守闭环，指派 m-0 并验收。AC4 过夜证据：pih work 常驻运行（pid 1074031，logs/worker.log），启动扫 3 源 27 条入库（pipeline_run ccma 10/sany 7/cehome 10 全 ok），处理接力全量消化——0 pending 滞留（23 extracted + 5 filtered_out 终态标记），/inbox 仅剩异常态可审计；web :8000 存活。晨间状态实测（本会话查询）。
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @lancer
created: 2026-09-04 01:18
---
AC4（无人值守一周期 pending 不滞留）留待 2026-09-04 晨过夜运行证据后勾选并置 Done——worker 已于 2026-09-03 夜启动（启动扫+07:30 daily 触发），晨间验收路径见 docs/mvp-run-decisions-2026-09-03.md §5。
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
采集后自动处理消化 pending 交付（用户裁定入 m-0，2026-09-04 验收）。run_source_job 增 process 编排缝：采集成功自动接力处理链（粗筛→抽取→校验→聚类），全程零命令；LLM 配置缺失/处理异常降级不丢弃（条目留 pending 可重放，job 不失败）。AC1-3 unit+integration 真链证据（设计文档 §1 索引）；AC4 过夜实证：启动扫 27 条全量流转 0 滞留（23 extracted+5 终态标记），worker/web 双进程留机运行。回归 unit+contract 459/integration 81/ruff 干净。
<!-- SECTION:FINAL_SUMMARY:END -->
