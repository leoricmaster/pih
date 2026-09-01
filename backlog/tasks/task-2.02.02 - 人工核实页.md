---
id: TASK-2.02.02
title: 人工核实页
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
ordinal: 21000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
作为运营者，我想在一个 Web 队列页里查看已具备升级条件与待人工的条目，一键确认或证伪，以便控制入库质量、终态由人把关。

验收面：Web 核实页（队列 + 确认 / 证伪操作）。积压降级并入 AC4。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 AC1: Given 存在需人工处理的情报 / 事件
When 运营者打开核实页
Then 按 置信度升序 + 采集时间升序 排列（低置信、最老的优先）
And 队列含三类：已具备升级条件的事件、低置信度情报、待人工条目
- [ ] #2 AC2: Given 运营者对单源确认事件点击确认
Then 事件状态跃迁为 多源确认（人工终态），写 verification_log（操作人、时间、原状态、新状态）
- [ ] #3 AC3: Given 运营者点击证伪并填写理由
Then 事件状态跃迁为 已证伪，理由写入日志
And 该事件下情报在检索结果中默认隐藏
- [ ] #4 AC4: Given 待核实情报持续 7 天无人处理
Then 其检索权重降级，并在核实页积压提醒区列出
<!-- AC:END -->
