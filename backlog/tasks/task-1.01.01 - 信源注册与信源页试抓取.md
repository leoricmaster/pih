---
id: TASK-1.01.01
title: 信源注册与信源页试抓取
status: To Do
assignee: []
created_date: '2026-09-01 09:25'
labels:
  - web
dependencies: []
references:
  - docs/prototype.html
parent_task_id: TASK-1.01
type: story
ordinal: 15000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
作为运营者，我在 repo 的领域包 YAML 中注册信源（URL、类型、层级、频率、列表页入口），在 Web 信源页查看全部信源状态、触发试抓取验证可达性，以便信源配置可信、抓得通才启用——状态与验收都在页面上。

验收面：Web 信源页（信源状态列表 + 页内试抓报告）。注册与配置编辑保留在 YAML + Git（版本化留痕，ADR decision-01）；信源页承载可视、试抓与健康（随 Feature 推进逐层加深）。IA：详情页为聚合面、状态词表跨页一致（见原型 docs/prototype.html）。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 AC1: Given 运营者在领域包 YAML 中新增信源并提交
When 流水线加载配置
Then 缺必填字段时加载被拒绝，指出缺失字段与行号
And 信源页列出全部信源：名称、类型、层级、可靠性、频率、启用状态
- [ ] #2 AC2: Given 信源页上某个信源
When 运营者点击试抓取
Then 页面展示试抓报告（robots / 列表页 / 详情 / 快照 逐项成败）
And 试抓取通过才将该源 enabled 置 true（enabled 由 YAML 变更、Git 留痕）
And enabled=false 的源不参与采集
- [ ] #3 AC3: Given 运营者修改领域包 YAML（信源 / 关键词 / 竞品 / 标签树 / 模板 / 提示词）
When 重新加载
Then 采集关键词、抽取标签树、提示词立即按新包生效，核心系统无任何代码变更
<!-- AC:END -->
