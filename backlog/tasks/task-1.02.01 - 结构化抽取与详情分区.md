---
id: TASK-1.02.01
title: 结构化抽取与详情分区
status: In Progress
assignee:
  - '@lancer'
created_date: '2026-09-01 09:25'
updated_date: '2026-09-03 11:06'
labels:
  - web
  - cross-cutting
milestone: m-0
dependencies:
  - TASK-1.01.02
references:
  - docs/prototype.html
parent_task_id: TASK-1.02
priority: high
type: story
ordinal: 17000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
作为消费者，每条入库情报在详情页按 schema 展开结构化分区（主体 / 事件类型 / 事实 / 推断 / 标签 / 量化参数 / Admiralty），抽取明显失败的条目被拦下待人工，以便我读得懂、不被低质条目干扰。

验收面：Web 详情页结构化分区（在原文入口之上加深）+ 列表按处理状态筛选。LLM 校验重问、后验质量门并入本故事 AC，不独立成卡。聚类与可信度建模（事件状态机、Admiralty 预评级、自动跃迁）为生产侧内建要求，无独立验收面，并入 AC4-AC6（横切）。

不在本故事：采集入库与去重 / 粗筛（→ TASK-1.01.02）；可信度与事件状态的 Web 呈现（→ TASK-2.02.01）；人工核实操作与终态把关（→ TASK-2.02.02）。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 AC1: Given 一条通过粗筛的内容完成结构化抽取 ｜ When 消费者打开详情页 ｜ Then 展示 主体 / 事件类型 / 标签 / 量化参数 与 Admiralty 码 ｜ And 事实与推断分区展示，推断字段必须含依据
- [ ] #2 AC2: Given LLM 返回的结构化输出未通过 schema 校验 ｜ Then 自动重问（≤3 次），仍失败则条目降级待人工，不丢弃
- [ ] #3 AC3: Given 抽取结果主体为占位值（未知 / 无 / 不详 / 空） ｜ Then 条目标记待人工，不混入正常情报 ｜ And 可在 Web 列表按处理状态筛出，进入核实页
- [ ] #4 AC4（聚类建模·横切）: Given 一条新情报完成处理 ｜ Then 其来源层级自动继承自信源配置，Admiralty 预评级非空（如 B2）
- [ ] #5 AC5（聚类建模·横切）: Given 新情报与已有事件的主体相同、时间窗 ±7 天、内容相似度超阈值 ｜ Then 自动归入该事件 ｜ And 若这是第二个独立信源，事件状态自动跃迁 待核实→单源确认（操作者=system，写日志）｜ And 事件标记已具备升级条件进入核实页（终态不自动跃迁）
- [ ] #6 AC6（聚类建模·横切）: Given 新情报未命中任何已有事件 ｜ Then 新建事件，初始状态=待核实
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

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
存量验证型故事（设计 docs/design/TASK-1.02.01-design.md）：旧 Sprint 已交付抽取图/重问/质量门/聚类/详情分区，本故事增量最小化。切片：1) D3 推断依据硬校验（validate_pred 单测先红→绿→graph 级链路测试）2) detail.html Admiralty 双维注解（contract 模板断言）3) AC2-AC6 既有测试证据索引 + /inbox 筛选实弹 4) live 实弹（collect→process，兼演示数据）5) 文档同步 + finalization（AC 逐条客观证据，D2 口径收窄 comment 已记）
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @lancer
created: 2026-09-03 11:06
---
AC5 范围裁定（DoD#1 事实源对齐，同 1.01.02 AC2 先例）：AC 字面「内容相似度超阈值」经对齐 doc-2 §4 权威口径（主体归一×事件类型×±7天时间窗）收窄——内容相似度语义属模糊/近重复去重（TASK-9.1 演进），本故事聚类验收口径=主体归一+事件类型精确+时间窗命中即挂事件。
---
<!-- COMMENTS:END -->
