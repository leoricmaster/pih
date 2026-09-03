---
id: TASK-4.01.2
title: 采集后自动处理消化 pending
status: To Do
assignee: []
created_date: '2026-09-03 10:28'
labels: []
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
- [ ] #1 Given 调度器完成一次自动采集 | When 该批采集结束 | Then 同批 pending 条目自动进入处理链（粗筛→抽取→校验），全程无需任何人运行命令
- [ ] #2 Given 处理链自动运行 | When 单条粗筛判否或抽取校验失败 | Then 条目落 filtered_out / needs_manual（原因可查、不丢弃、可重放），批处理继续其余条目
- [ ] #3 Given LLM 配置缺失或调用持续失败 | When 处理链被触发 | Then 按 doc-3 可靠性降级不丢弃，失败原因落运行留痕（结构化日志 / pipeline_run）
- [ ] #4 Given 无人值守运行一个完整采集周期 | When 运营者打开收件箱与检索 | Then 新条目不再滞留 pending（自动流转为 extracted 或终态标记），页面仅剩需人工处置的异常态
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 AC 全满足，每条有可复现证据（测试名 / 命令 / 截图），实际运行通过——非臆测的「应能通过」推断
- [ ] #2 CI 有增量测试且变绿；覆盖正常路径与关键失败路径
- [ ] #3 无回归（现有测试不破）
- [ ] #4 触碰的架构 / ADR / NFR / 运营手册同步更新，day0 文档改动进正文不留批注
- [ ] #5 结构化日志与运行留痕按 doc-2 §8 落地；迁移 / 配置变更可回滚（1 人可恢复）
- [ ] #6 无密钥硬编码；新增依赖真实、锁版本、无高危 CVE
- [ ] #7 不违反贯穿性约束与 ADR（偏离须先记 ADR）
<!-- DOD:END -->
