---
id: TASK-1.02.01
title: 结构化抽取与详情分区
status: To Do
assignee: []
created_date: '2026-09-01 09:25'
updated_date: '2026-09-02 08:58'
labels:
  - web
  - cross-cutting
dependencies: []
references:
  - docs/prototype.html
parent_task_id: TASK-1.02
type: story
ordinal: 17000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
作为消费者，每条入库情报在详情页按 schema 展开结构化分区（主体 / 事件类型 / 事实 / 推断 / 标签 / 量化参数 / Admiralty），抽取明显失败的条目被拦下待人工，以便我读得懂、不被低质条目干扰。

验收面：Web 详情页结构化分区（在原文入口之上加深）+ 列表按处理状态筛选。LLM 校验重问、后验质量门并入本故事 AC，不独立成卡。聚类与可信度建模（事件状态机、Admiralty 预评级、自动跃迁）为生产侧内建要求，无独立验收面，并入 AC4-AC6（横切）。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 AC1: Given 一条通过粗筛的内容完成结构化抽取
When 消费者打开详情页
Then 展示 主体 / 事件类型 / 标签 / 量化参数 与 Admiralty 码
And 事实与推断分区展示，推断字段必须含依据
- [ ] #2 AC2: Given LLM 返回的结构化输出未通过 schema 校验
Then 自动重问（≤3 次），仍失败则条目降级待人工，不丢弃
- [ ] #3 AC3: Given 抽取结果主体为占位值（未知 / 无 / 不详 / 空）
Then 条目标记待人工，不混入正常情报
And 可在 Web 列表按处理状态筛出，进入核实页
- [ ] #4 AC4（聚类建模·横切）: Given 一条新情报完成处理
Then 其来源层级自动继承自信源配置，Admiralty 预评级非空（如 B2）
- [ ] #5 AC5（聚类建模·横切）: Given 新情报与已有事件的主体相同、时间窗 ±7 天、内容相似度超阈值
Then 自动归入该事件
And 若这是第二个独立信源，事件状态自动跃迁 待核实→单源确认（操作者=system，写日志）
And 事件标记已具备升级条件进入核实页（终态不自动跃迁）
- [ ] #6 AC6（聚类建模·横切）: Given 新情报未命中任何已有事件
Then 新建事件，初始状态=待核实
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
