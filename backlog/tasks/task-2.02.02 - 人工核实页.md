---
id: TASK-2.02.02
title: 人工核实页
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
ordinal: 21000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
作为运营者，我想在一个 Web 队列页里查看已具备升级条件与待人工的条目，一键确认或证伪，以便控制入库质量、终态由人把关。

验收面：Web 核实页（队列 + 确认 / 证伪操作）。积压提醒并入 AC4。

不在本故事：聚类与「已具备升级条件」的生产侧判定（→ TASK-1.02.01）；可信度与跃迁历史的只读呈现（→ TASK-2.02.01，本故事承载操作不承载只读呈现）；组合筛选（→ TASK-2.01.01）。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 AC1: Given 存在需人工处理的情报 / 事件 ｜ When 运营者打开核实页 ｜ Then 按 置信度升序 + 采集时间升序 排列（低置信、最老的优先）｜ And 队列含三类：已具备升级条件的事件、低置信度情报、待人工条目
- [ ] #2 AC2: Given 运营者对单源确认事件点击确认 ｜ Then 事件状态跃迁为 多源确认（人工终态），写 verification_log（操作人、时间、原状态、新状态）
- [ ] #3 AC3: Given 运营者点击证伪并填写理由 ｜ Then 事件状态跃迁为 已证伪（人工终态），理由写入日志 ｜ And 该事件下情报在检索结果中默认隐藏（检索权重降级为 0，见 doc-2 §6.3）
- [ ] #4 AC4: Given 待核实事件持续 7 天无人处理 ｜ Then 在核实页积压提醒区列出（按滞留时长排序）
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
