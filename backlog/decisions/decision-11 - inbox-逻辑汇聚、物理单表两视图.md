---
id: decision-11
title: inbox 逻辑汇聚、物理单表两视图
date: '2026-09-03 08:10'
status: accepted
---
## Context

doc-2 §6.4 原把 ADR-009 的「inbox 汇聚」解释为**物理独立的 `inbox_item` 表** + 列表读「合并视图」（inbox 进行中条目 UNION intel 已入库条目）。TASK-1.01.02 实现前评审发现该解释无强技术理由支撑，且带真实成本：

- **字段重复**：intel = inbox 全部 raw 字段 + 8 个结构化字段；两表模型下抽取需新建 intel 行、把 `raw_html` 等大字段再抄一遍；
- **跨表查询复杂**：合并视图跨表 UNION 的排序/翻页游标需跨表统一，单用户 <10 万条场景不划算；
- **与现状代码相悖**：现状本是单表原地 UPDATE（ProcessRunner 读 intel 的 pending 行，UPDATE 填结构化字段），两表模型反而要改成「从 inbox 抄到 intel」。

逐条排查 doc-2 否决单表的可能理由（语义洁癖「intel 通过质量门后才创建」/字段形状不同/event_id 外键/查询性能）均不构成强技术理由。ADR-009 只规定 inbox **逻辑汇聚**（人工+自动进同一条处理链、零特判），未要求物理分表。

## Decision

**inbox 为 ADR-009 的逻辑汇聚点，而非物理独立表。** 采用单表 + 两视图：

- 单表 `intel_item` 承载处理状态机（`pending` → `needs_manual` / `filtered_out` / `dead` / `done` / `extracted`）；`source_type` 区分采集/人工（ADR-009 汇聚语义保留）；
- 采集即落 `intel_item` 的 `pending` 行（先落盘可回放，ADR-007），抽取**原地 UPDATE** 升级结构化字段，**不复制 raw_html、不另建 inbox 表**；
- 死信 = `process_status='dead'` 的失败终态标记（doc-2 §7 已定「死信非独立实体」，本决策落实其物理载体）；
- 列表分两视图读同表不同状态：**收件箱视图**（`pending` / `needs_manual` / `filtered_out` / `dead`——采集验收面与漏报审计）+ **检索视图**（`extracted`——消费成品）。每视图只读一张表的一个状态子集，无跨表 UNION。

**理由**：零字段复制（raw 存一份）、AC3 天然成立（`filtered_out` 永不进检索视图，无需排除逻辑）、查询最简、最贴近现状代码。被否选项：① 两实体两页面（字段复制仍在）；② 单表单列表（filtered_out 须额外排除逻辑、消费与处理混在一页）；③ 维持 doc-2 合并视图（跨表复杂 + 字段复制）。

## Consequences

- doc-2 §6.4 状态归属、§7 表行、§7 死注释、§5.4 检索描述、§1 技术栈行、§10 索引已同步修订（指向本 ADR）；
- ADR-009 不变（逻辑汇聚语义仍成立），仅澄清其物理载体为 `intel_item.source_type` + 处理状态机；
- TASK-1.01.02 实现回退此前的 `inbox_item` 迁移与 `InboxRepository`，改回 `intel_item` 单表（加 `source_type` 列）；粗筛解耦模块保留、改指向 `IntelRepository`；
- 收件箱视图与检索视图为两个 Web 路由（`/inbox` 与 `/`），各读同表不同状态；原型列表「检索/待处理」两分栏与本决策的视图划分方向一致（IA 细节随实现 reconcile）。
