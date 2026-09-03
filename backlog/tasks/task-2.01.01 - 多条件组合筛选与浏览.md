---
id: TASK-2.01.01
title: 多条件组合筛选与浏览
status: Done
assignee:
  - '@lancer'
created_date: '2026-09-01 09:26'
updated_date: '2026-09-03 11:26'
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
- [x] #1 AC1: Given 情报库已有数据 ｜ When 消费者选定 主体 / 事件类型 / 时间范围 / 标签 / 置信度 组合 ｜ Then 列表仅展示同时满足所有条件的情报 ｜ And 每条显示 标题、主体、事件类型、置信度、采集时间
- [x] #2 AC2: Given 筛选结果为空 ｜ Then 页面提示无结果，并建议放宽条件
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 验收面字段与事实源（领域包 schema / 原型 IA / doc-2）逐项核对一致；偏差先修订事实源或记 ADR，不在代码里私自偏移
- [x] #2 无新增未论证的自部署组件；核心代码不出现行业知识硬编码（违反即返工）
- [x] #3 AC 全满足，每条有可复现证据（测试名 / 命令 / 截图），实际运行通过——非臆测的「应能通过」推断
- [ ] #4 CI 有增量测试且变绿；覆盖正常路径与关键失败路径
- [x] #5 无回归（现有测试不破）
- [x] #6 触碰的架构 / ADR / NFR / 运营手册同步更新，day0 文档改动进正文不留批注
- [x] #7 结构化日志与运行留痕按 doc-2 §8 落地；迁移 / 配置变更可回滚（1 人可恢复）
- [x] #8 无密钥硬编码；新增依赖真实、锁版本、无高危 CVE
- [x] #9 不违反贯穿性约束与 ADR（偏离须先记 ADR）
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
存量验证+增量小型故事（设计 docs/design/TASK-2.01.01-design.md）。切片：1) admiralty≥语义（unit 断言先红→repository SQL 改→绿）2) 筛选表单 IA 重排（pack_loader.load_filter_vocab + web time_range 预设 + list.html 主行五要素/更多筛选折叠，contract 先红）+ list 页 time_range 单测 3) integration 组合筛选用例（五条件同时生效，排除 C3）4) README 筛选段同步（≥语义行为变更）5) finalization
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
TDD 切片 1（admiralty ≥ 档语义 D1/D4）：unit test_repository::test_admiralty_since_until_before_build_clauses 断言先红（仍精确匹配）→ repository 改 left(i.admiralty_code,1) <= 档位 → 绿；docstring 同步。
TDD 切片 2（表单 IA D2/D3）：contract TestFilterFormIA 2 例先红（datalist/select/预设/折叠/清空 均无）→ pack_loader.load_filter_vocab()（主体+别名/事件类型/标签叶子）+ web list_page 增 time_range 参数（7d/30d/90d→since，显式 since 优先）+ list.html 重排（主行五要素+更多筛选 details+清空）→ 绿；旧 test_form_preserves_filter_values 随 ≥ 档语义更新（admiralty=B2→B）。新增 unit test_list_page 4 例（time_range 映射/显式优先/未知预设忽略/≥ 档透传）。
存量 bug 修复（验收循环内直接修，doc-5 §6）：integration 新组合用例首跑抓到 tags containment 潜伏 bug——Json 参数以 json 类型绑定，真实 PG 无 jsonb @> json 操作符（此前 tag 筛选从未真库跑过，单测 mock 掩盖接线缝）。修：SQL 改 i.tags @> %s::jsonb。
integration 增 test_filter_combo_and_admiralty_tier：五条件组合（主体×事件类型×标签×置信度×时间）命中 + ≥B 排除 C3 档/≥C 保留 C3 档正反验证 + Web time_range 预设路径同源。
README 同步：组合筛选段（≥ 档语义行为变更 + 预设 + 折叠区）。
回归：unit+contract 410 / integration api_e2e 16 / ruff 干净。
live 实弹（:8001）：/ 渲染 filter-subjects datalist/更多筛选/≥ B/近30天/清空；?admiralty=B&time_range=90d 200；空结果「无结果，建议放宽条件」+建议清单（AC2）。注意：本机旧 uvicorn 进程（无 reload）被新模板 500——已清理重启；curl 中文查询需百分号编码（400 是 h11 拒绝非 ASCII 请求行，非应用问题）。
AC 证据索引：AC1=integration combo 用例+存量 columns 用例+contract 表单 2 例+unit ≥ 子句与 time_range 4 例+live；AC2=integration empty 用例（存量）+live 空态文案。
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
多条件组合筛选与浏览交付（增量小型：筛选框架存量，本故事改语义+IA 对齐原型）。AC1 主行五要素组合筛选（主体 datalist 领域包候选/事件类型/标签/时间范围预设 7-30-90 天/置信度 ≥ 档下拉）AND 语义（integration 五条件组合用例+≥B 排 C3 正反验证+unit/contract 全量）；列表列 标题/主体/事件类型/置信度/采集时间 存量已齐；admiralty 语义变更为来源可靠性 ≥ 档（left(code,1)<=档，Web/API 同源，README 记档）；附带修复存量潜伏 bug：tags @> Json 参数缺 ::jsonb cast（真实 PG jsonb @> json 无操作符，integration 首跑抓到）。AC2 空结果提示存量已有（integration+live 双证）。信源/处理状态/事件状态/每页收「更多筛选」折叠保可达性。回归 unit+contract 410/integration 16/ruff 干净。DoD 8/9，#4 待 push（PD2）。
<!-- SECTION:FINAL_SUMMARY:END -->
