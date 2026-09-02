---
id: TASK-2.02.01
title: 交叉印证与可信度呈现
status: To Do
assignee: []
created_date: '2026-09-01 09:26'
updated_date: '2026-09-02 09:21'
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
- [ ] #1 AC1: Given 列表中一条情报已挂事件 ｜ Then 该条显示所属事件核实状态，未挂事件的情报显示未挂事件 ｜ And 列表带 Admiralty 码与所属事件核实状态，以便一眼看出可信度
- [ ] #2 AC2: Given 消费者打开已挂事件情报的详情页 ｜ Then 详情页展示所属事件的完整状态跃迁历史（自动跃迁标注 system）｜ And 事实与推断分区展示，便于独立判断结论
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 验收面字段与事实源（领域包 schema / 原型 IA / doc-2）逐项核对一致；偏差先修订事实源或记 ADR，不在代码里私自偏移
- [ ] #2 无新增未论证的自部署组件；核心代码不出现行业知识硬编码（违反即返工）
- [ ] #3 AC 全满足，每条有可复现证据（测试名 / 命令 / 截图），实际运行通过——非臆测的「应能通过」推断
- [ ] #4 CI 有增量测试且变绿；覆盖正常路径与关键失败路径
- [ ] #5 无回归（现有测试不破）
- [ ] #6 触碰的架构 / ADR / NFR / 运营手册同步更新，day0 文档改动进正文不留批注
- [ ] #7 结构化日志与运行留痕按 doc-2 §8 落地；迁移 / 配置变更可回滚（1 人可恢复）
- [ ] #8 无密钥硬编码；新增依赖真实、锁版本、无高危 CVE
- [ ] #9 不违反贯穿性约束与 ADR（偏离须先记 ADR）
<!-- DOD:END -->
