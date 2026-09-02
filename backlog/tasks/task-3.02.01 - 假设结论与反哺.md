---
id: TASK-3.02.01
title: 假设结论与反哺
status: To Do
assignee: []
created_date: '2026-09-01 09:26'
labels:
  - web
dependencies: []
references:
  - docs/prototype.html
parent_task_id: TASK-3.02
type: story
ordinal: 23000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
作为消费者，我在证据充分时对假设标记结论（证实 / 证伪，须填依据），超时未决自动失效归档，以便判断留痕可复盘、结论反哺监控方向。

验收面：Web 假设页结论操作 + 结论复盘视图（周报复盘节）。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 要点1: 结论（已证实 / 已证伪）为人工终态，填写依据与结论时间，全程留痕（与事件核实同一纪律）
- [ ] #2 要点2: 时间窗到期未决 → 自动转已失效，不删除、可复盘
- [ ] #3 要点3: 结论是判断层知识资产：结论（含依据与证据链）可检索、可引用，可挂为新假设的证据；不回写情报表（事实 / 判断两层分治，见立项文档 §3 / doc-1）
- [ ] #4 要点4: 结论反哺：已证实 / 已证伪假设的关键词进入周报复盘节，驱动监控关键词与信源调整建议（提示运营者，不自动改配置——人是最终环节）
<!-- AC:END -->
