---
id: TASK-2.02.01
title: 交叉印证与可信度呈现
status: Done
assignee:
  - '@lancer'
created_date: '2026-09-01 09:26'
updated_date: '2026-09-03 11:30'
labels:
  - web
milestone: m-0
dependencies:
  - TASK-1.02.01
references:
  - docs/prototype.html
parent_task_id: TASK-2.02
priority: high
type: story
ordinal: 20000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
作为消费者，每条情报在列表带 Admiralty 码与所属事件核实状态，详情页呈现事件完整跃迁历史，以便我一眼看出可信度、独立判断结论。

验收面：Web 列表（Admiralty + 事件状态列）与详情页事件区（在结构化分区之上加深）。聚类与自动跃迁逻辑已在生产侧建模（见 TASK-1.02.01 AC4-AC6），本故事承载呈现。

不在本故事：聚类与自动跃迁的生产侧建模（→ TASK-1.02.01 AC4-AC6，本故事只承载呈现）；人工核实操作与终态把关（→ TASK-2.02.02）；组合筛选（→ TASK-2.01.01）。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 AC1: Given 列表中一条情报已挂事件 ｜ Then 该条显示所属事件核实状态，未挂事件的情报显示未挂事件 ｜ And 列表带 Admiralty 码与所属事件核实状态，以便一眼看出可信度
- [x] #2 AC2: Given 消费者打开已挂事件情报的详情页 ｜ Then 详情页展示所属事件的完整状态跃迁历史（自动跃迁标注 system）｜ And 事实与推断分区展示，便于独立判断结论
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
存量验证型故事（设计 docs/design/TASK-2.02.01-design.md）：列表列/时间线/排序末尾均存量。切片：1) 未挂事件文案（contract 先红→list.html 单元格 — → 未挂事件→绿；api_e2e 存量断言同步）2) AC 证据索引（consume_event_fields 7 例复用）+ live 实弹 3) finalization
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
存量验证型故事：列表 Admiralty 列/事件状态列/未挂事件排末尾（_build_ranked_order_sql NULL→W_c=0）/详情时间线（operator=system 明示）/事实推断分区 均存量已交付。
增量切片（D1 未挂事件文案）：contract test_unattached_event_shows_label 先红（模板显示 —）→ list.html 事件列空值 — → 「未挂事件」（.no-event 弱化样式）→ 绿；同步更新两处存量断言（contract test_event_status_column_renders_label_or_dash、integration api_e2e 列表断言）到新口径——行为变更即本故事 AC1 字面要求。
回归：unit+contract 411 / integration consume_event_fields+api_e2e 22 / ruff 干净。
AC 证据索引：AC1=integration test_list_page_shows_event_status_label（存量）+ test_unattached_event_shows_label（新增）+ TestRankingSortOrder 2 例（存量，含未挂末尾）+ API event_verification_note=未挂事件（存量）；AC2=integration test_detail_page_shows_event_timeline（存量，完整跃迁历史+operator=system）+ contract test_renders_all_sections（事实/推断分区，1.02.01 交付）+ live 详情时间线随收尾演示数据补实弹。
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
交叉印证与可信度呈现交付（存量验证型：呈现面 95% 由旧 Sprint 与 1.02.01 交付）。AC1 列表带 Admiralty 码与所属事件核实状态中文标签、未挂事件显示「未挂事件」（本故事唯一代码增量：模板空值 — → 未挂事件，两处存量断言同步新口径）、未挂排末尾（W_c=0 存量）；AC2 详情页完整状态跃迁历史时间线（自动跃迁 operator=system 明示，integration 存量用例）+ 事实/推断分区（1.02.01 contract 存量）。回归 unit+contract 411/integration 22/ruff 干净。DoD 8/9，#4 待 push（PD2）。
<!-- SECTION:FINAL_SUMMARY:END -->
