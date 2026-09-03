# TASK-2.02.01 设计：交叉印证与可信度呈现

> 关联：backlog TASK-2.02.01 ｜ 原型 `docs/prototype.html` 列表节（Admiralty/事件状态列）与详情节（事件时间线）｜ ADR-002/003/006。

## 1. 范围与存量映射

| AC | 存量（实测） | 本故事增量 |
|---|---|---|
| AC1 列表 Admiralty+事件状态列；未挂显示「未挂事件」 | 列表列与 Admiralty 码已有；事件状态列已有（中文标签 badge）；未挂事件排序末尾已实现（`_build_ranked_order_sql` NULL→W_c=0）；API note 已返回「未挂事件」 | Web 列表未挂事件单元格文案 `—` → `未挂事件`（与 AC 字面与 API 口径一致） |
| AC2 详情页事件完整跃迁历史（自动跃迁标注 system）+ 事实/推断分区 | detail.html 事件区：状态 badge + 完整 verification_log 时间线（`operator=system` 明示）+ 事实描述/推断与判断分区 + 已具备升级条件提示 | 无代码增量；证据索引 |

范围外：核实操作面（→2.02.02）；时间线 sys/human 视觉样式对齐原型（→TASK-6 还原度复查）；组合筛选（→2.01.01 已交付）。

## 2. 关键决策与理由

| # | 决策 | 备选与否决理由 |
|---|---|---|
| D1 | 未挂事件文案改动**只动 Web 列表单元格**，API/详情页不动（已是「未挂事件」口径） | AC1 字面「未挂事件的情报显示未挂事件」；API `event_verification_note` 已返回该文案，Web 对齐即闭环。保持 — 会被验收质询「哪里显示未挂事件」 |

## 3. 测试与 CI

- contract：TestListRender 增未挂事件渲染断言（先红）；api_e2e 存量断言 `—` 改「未挂事件」。
- integration：test_consume_event_fields 既有 7 例复用（列表标签/时间线/排序）。
- live：详情页时间线 + 列表列实弹（finalization）。

## 4. 事实源偏差与裁决

无新偏差（原型 legend「未挂事件条目排末尾」已由 W_c=0 实现；文案口径 API 先行、本次 Web 对齐）。

## 5. AC 证据清单

- AC1：integration TestWebEventFields::test_list_page_shows_event_status_label（存量）+ 新增未挂事件断言 + TestRankingSortOrder 2 例（存量，含未挂末尾）+ live 列表
- AC2：integration test_detail_page_shows_event_timeline（存量，operator=system）+ 1.02.01 交付的事实/推断分区（contract test_renders_all_sections）
