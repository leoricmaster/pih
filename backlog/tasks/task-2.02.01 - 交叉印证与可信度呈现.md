---
id: TASK-2.02.01
title: 交叉印证与可信度呈现
status: To Do
assignee: []
created_date: '2026-09-01 09:26'
labels:
  - web
dependencies: []
references:
  - docs/prototype.html
parent_task_id: TASK-2.02
type: story
ordinal: 20000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
作为消费者，每条情报在列表带 Admiralty 码与所属事件核实状态，详情页呈现事件完整跃迁历史，以便我一眼看出可信度、独立判断结论。

验收面：Web 列表（Admiralty + 事件状态列）与详情页事件区（在结构化分区之上加深）。聚类与自动跃迁逻辑已在生产侧建模（见 TASK-1.02.01 AC4-AC6），本故事承载呈现。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 AC1: Given 列表中一条情报已挂事件
Then 该条显示所属事件核实状态，未挂事件的情报显示未挂事件
And 列表带 Admiralty 码与所属事件核实状态，以便一眼看出可信度
- [ ] #2 AC2: Given 消费者打开已挂事件情报的详情页
Then 详情页展示所属事件的完整状态跃迁历史（自动跃迁标注 system）
And 事实与推断分区展示，便于独立判断结论
<!-- AC:END -->
