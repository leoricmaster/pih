---
id: TASK-6
title: Web 页面原型还原度复查与精美化
status: To Do
assignee: []
created_date: '2026-09-03 02:36'
updated_date: '2026-09-03 10:50'
labels:
  - web
  - ui
dependencies: []
parent_task_id: TASK-2
priority: medium
type: bug
ordinal: 29000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
来源：TASK-1.01.01 验收反馈——「在原型基础上提高还原度与精美度」的闭环单。范围更新（2026-09-03）：信源页（sources）对照已在 TASK-1.01.01 三轮验收循环内闭环——侧边栏 IA 还原、字段图例/呈现词/未接入徽标、试抓报告信息架构（R7 渐进披露）、原型双向同步，本单不再覆盖该页。剩余范围：情报列表/详情/反馈页与 docs/prototype.html 的布局级对照（导航/分区/层级/状态，偏差清单记 notes）、间距/字号层级/状态色/空态的精美化一轮，及后续故事新增页面。验收材料按 doc-5 §5 附原型 IA 布局级对照（不只字段级）。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 逐页对照原型（list/detail/sources/feedback 及后续新增页），产出布局级偏差清单（导航/分区/层级/状态）记入 notes
- [ ] #2 偏差逐条裁决闭环：改代码还原，或提修改原型的理由与方案讨论通过后改原型
- [ ] #3 精美化一轮落地（间距/字号层级/状态色/空态），每页附对照前后说明
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
