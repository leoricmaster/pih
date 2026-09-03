# TASK-2.01.01 设计：多条件组合筛选与浏览

> 关联：backlog TASK-2.01.01 ｜ 原型 `docs/prototype.html` 情报·列表节（组合筛选行）｜ ADR-006。
> 本轮按授权（PD1）设计后直接实现，决策同步 `docs/mvp-run-decisions-2026-09-03.md` D4。

## 1. 范围与存量映射

| AC | 存量（实测） | 本故事增量 |
|---|---|---|
| AC1 组合筛选 AND + 列字段 | IntelFilters/list_by_filter 已支持 subject/event_type/tag/admiralty/source_id/process_status/event_status/since/until（AND 语义）；列表列 标题/主体/事件类型/置信度/采集时间 已齐（+状态/事件状态/反馈） | **admiralty 语义改「≥ 档」**（D4，原为精确匹配）；筛选表单按原型 IA 重排：主体/事件类型/时间范围/标签/置信度 五要素为主行（词表下拉注入），信源/处理状态/事件状态/每页 收进「更多筛选」折叠；时间范围预设（近7/30/90天） |
| AC2 空结果提示 | list.html 空态「无结果，建议放宽条件」+ 三条建议已存在；integration test_empty_shows_hint_and_no_next_page 已锁 | 无代码增量；证据索引 |

范围外：可信度与事件状态列深化（→2.02.01）；核实操作（→2.02.02）；筛选词表的「今日新增 N · 共 N 条」统计行（原型示意、AC 无此要求，YAGNI）。

## 2. 关键决策与理由

| # | 决策 | 备选与否决理由 |
|---|---|---|
| D1 | **admiralty 筛选语义 = 来源可靠性 ≥ 所选档**：SQL `left(admiralty_code,1) <= %s`（A 最优，A–F 字典序天然升序），Web/API/CLI 同源生效 | 原精确匹配（"B2"）用户难用：需知道确切双字符；原型即「≥ B ▾」；信源页图例已教育 A–F 档序。可信度维度（1–6）不进筛选（短板语义已由排序承载）。行为变更在 README 与本文记档 |
| D2 | 时间范围用**预设下拉**（近7天/近30天/近90天/时间不限）映射 since；URL 直参 since/until 仍受理（API 兼容），显式 since 优先于预设 | ISO8601 手输（现状）对消费者不友好；原型为单一下拉。服务端映射简单可测（无 JS） |
| D3 | 主体用 **datalist**（输入框+候选），事件类型/标签/置信度用 **select**；候选来自领域包（competitors 全名+别名 / event_types / tag_tree 叶子 / A–E 档） | 主体存在清单外主体（提示词规则 2 允许全名），不能锁死 select；标签/事件类型是封闭枚举适合 select。原型五个字段均▾，主体降级为 datalist 是「可输入的▾」折中 |
| D4 | 高级筛选（信源/处理状态/事件状态/每页）收 `<details>` 折叠不删除 | 原型主行只有五要素；但 process_status 是 1.02.01 AC3 复核队列入口、event_status 是 2.02.01 验收面——保留可达性，渐进披露（信源页字段说明先例） |

## 3. 接口与状态语义

- `IntelRepository.list_by_filter(admiralty=...)`：语义变更（D1），参数仍为单字符档位；传 "B2" 类双字符因字典序比较亦兼容（'A'<'B2'、'C'>'B2'），不特判。
- `pack_loader.load_filter_vocab() -> (subjects, event_types, tags)`：新增，列表筛选表单候选（与 load_pack_vocab 分立，避免动详情页反馈表单契约）。
- `GET /`：新增 `time_range` 参数（7d/30d/90d），映射 since=now-N 天；显式 since 优先。

## 4. 测试与 CI

| 层 | 增量 |
|---|---|
| unit | test_repository admiralty 子句断言改 ≥（先红）；新增 list 页 time_range 映射用例（TestClient+fake repo，模式同 test_inbox_page） |
| contract | test_templates_render list 渲染断言：datalist 主体候选 + 事件类型/标签/置信度 select 选项 + 折叠区（先红） |
| integration | test_api_e2e TestAC1ListFilters 增组合用例：subject+event_type+tag+admiralty≥B+time_range 同时生效，断言排除 C3 档 |

## 5. 事实源偏差与裁决

| 偏差 | 裁决 |
|---|---|
| 原型筛选行「置信度 ≥ B」单轴 vs Admiralty 双维 | 单轴（D1）：可靠性档作筛选门槛，可信度留给排序——与 doc-2 §6.3 词表设计一致，原型为此口径 |
| 原型主行五要素 vs 既有表单八字段 | 不删字段（D4 折叠保留）；IA 主行对齐原型 |

## 6. AC 证据清单

- AC1：integration test_filter_subject_event_since_and_columns（存量）+ 新增组合用例（五条件同时生效）+ unit/contract 增量用例 + live `/`?subject=…&admiralty=B 实弹
- AC2：integration test_empty_shows_hint_and_no_next_page（存量）
