---
id: TASK-4.03.02
title: 反馈聚合与迭代驱动
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
ordinal: 27000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
作为运营者，我想查看反馈聚合视图，某类反馈高频时高亮提示迭代，反馈可导出为 prompt few-shot 样本，以便反馈真正驱动抽取 / 粗筛改进。

验收面：Web 反馈聚合页 + JSONL 导出。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 AC1: Given 运营者查看反馈聚合页
When 某信源某类反馈高频出现（如主体错误率 >30%）
Then 视图高亮提示需迭代该信源的抽取 prompt 或调整粗筛阈值
- [ ] #2 AC2: Given 运营者需用反馈改进提示词
When 导出反馈
Then 反馈条目可导出为处理层 prompt 迭代的 few-shot 样本（JSONL）
<!-- AC:END -->
