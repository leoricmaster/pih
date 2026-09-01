---
id: TASK-4.03.01
title: 消费页反馈动作
status: To Do
assignee: []
created_date: '2026-09-01 09:26'
labels:
  - web
dependencies: []
references:
  - docs/prototype.html
parent_task_id: TASK-4.03
type: story
ordinal: 26000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
作为消费者 / 运营者，我想在情报详情页对抽取结果一键标记反馈（主体错了 / 事件类型错 / 事实不准 / 不该入库），以便上游处理层提示词 / 粗筛据此迭代，形成人机闭环。

验收面：Web 详情页反馈区（按钮 + 表单）。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 AC1: Given 消费者打开情报详情页，看到主体字段与原文不符
When 点击主体错了反馈按钮
Then 可填正确主体（从主体清单选或自由输入）
And 反馈记录写入 feedback 表（item_id, field=subject, wrong_value, correct_value, user_id, ts）
- [ ] #2 AC2: Given 消费者看到事实描述不准
When 点击事实不准反馈按钮
Then 可选择具体哪条事实并填说明
And 反馈标注到具体事实项级别
- [ ] #3 AC3: Given 消费者认为事件类型标错
When 点击事件类型错反馈按钮
Then 可选正确事件类型，反馈写入 feedback 表
- [ ] #4 AC4: Given 消费者认为这条不该入库（粗筛漏放）
When 点击不该入库反馈按钮
Then 反馈写入 feedback 表（type=should_filter）
And 该信号聚合到粗筛漏报审计（与采集入库 AC3 互补）
<!-- AC:END -->
