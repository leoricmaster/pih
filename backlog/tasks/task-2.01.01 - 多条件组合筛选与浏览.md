---
id: TASK-2.01.01
title: 多条件组合筛选与浏览
status: To Do
assignee: []
created_date: '2026-09-01 09:26'
labels:
  - web
dependencies: []
references:
  - docs/prototype.html
parent_task_id: TASK-2.01
type: story
ordinal: 19000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
作为消费者，我想按 主体 / 事件类型 / 时间范围 / 标签 / 置信度 组合筛选情报列表，以便快速定位某类信息。

验收面：Web 列表筛选。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 AC1: Given 情报库已有数据
When 消费者选定 主体 / 事件类型 / 时间范围 / 标签 / 置信度 组合
Then 列表仅展示同时满足所有条件的情报
And 每条显示 标题、主体、事件类型、置信度、采集时间
- [ ] #2 AC2: Given 筛选结果为空
Then 页面提示无结果，并建议放宽条件
<!-- AC:END -->
