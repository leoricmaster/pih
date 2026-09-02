---
id: TASK-1.01.02
title: 采集入库与原文可查
status: To Do
assignee: []
created_date: '2026-09-01 09:25'
updated_date: '2026-09-02 09:21'
labels:
  - web
milestone: m-0
dependencies:
  - TASK-1.01.01
references:
  - docs/prototype.html
parent_task_id: TASK-1.01
priority: high
type: story
ordinal: 16000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
作为运营者，执行采集后新条目出现在 Web 列表、点开可见原文快照与原始链接，重复采集不产生重复条目、无关内容不混入，以便不用搬运转录、原文永远找得回。

验收面：Web 列表/详情（+ 采集统计 CLI 报告）。去重、粗筛、先落盘可重放并入本故事 AC 与 NFR（doc-3），不独立成卡。

不在本故事：信源注册与试抓取（→ TASK-1.01.01）；结构化抽取与事件聚类（→ TASK-1.02.01）；自动调度（→ TASK-4.01.01）；信源健康告警与连续失败统计（→ TASK-4.02.01）。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 AC1: Given 某已启用信源 ｜ When 运营者执行采集 ｜ Then 新内容抓取入库，输出统计「入库 N 新增 / M 幂等跳过 / K 失败」｜ And 新条目出现在 Web 列表（标题、信源、采集时间）｜ And 详情页提供原文快照与原始链接两个入口（无快照的内容不入库）
- [ ] #2 AC2: Given 重复采集同一信源而内容未更新 ｜ Then URL 指纹相同或内容相似度超阈值的条目被幂等跳过 ｜ And 情报库行数不变
- [ ] #3 AC3: Given 一条新内容被粗筛（关键词 + 小模型二分类）判为不相关 ｜ Then 它不进入消费列表，行级标记保留 ｜ And 运营者可在 Web 列表按处理状态筛出复核（漏报审计）
- [ ] #4 AC4: Given 抓取或处理失败 ｜ Then 原始内容先落盘不丢失，失败原因可查、可重放（细则见 NFR doc-3 与架构 §8）
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
