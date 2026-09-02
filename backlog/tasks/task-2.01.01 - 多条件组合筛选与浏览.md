---
id: TASK-2.01.01
title: 多条件组合筛选与浏览
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
parent_task_id: TASK-2.01
priority: high
type: story
ordinal: 19000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
作为消费者，我想按 主体 / 事件类型 / 时间范围 / 标签 / 置信度 组合筛选情报列表，以便快速定位某类信息。

验收面：Web 列表筛选。

不在本故事：情报生产与结构化字段产出（→ TASK-1.02.01）；可信度呈现与事件状态列（→ TASK-2.02.01）；人工核实操作（→ TASK-2.02.02）。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 AC1: Given 情报库已有数据 ｜ When 消费者选定 主体 / 事件类型 / 时间范围 / 标签 / 置信度 组合 ｜ Then 列表仅展示同时满足所有条件的情报 ｜ And 每条显示 标题、主体、事件类型、置信度、采集时间
- [ ] #2 AC2: Given 筛选结果为空 ｜ Then 页面提示无结果，并建议放宽条件
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
