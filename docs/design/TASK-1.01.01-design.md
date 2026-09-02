# TASK-1.01.01 设计：信源注册与信源页试抓取

> 故事级细粒度设计，上承架构 doc-2（粗粒度稳定层），下接代码与测试（代码即文档）。
> 只记决策与理由、接口与状态语义、事实源偏差——不写数据结构逐字段、函数签名、伪代码。
> 关联：backlog 任务 TASK-1.01.01 ｜ 原型 `docs/prototype.html` 信源节 ｜ ADR-001 / ADR-002 / ADR-006。

## 1. 范围与存量映射

存量代码（旧 Sprint 交付）按「需验证资产」复用，不重写：

| AC | 存量 | 本故事增量 |
|---|---|---|
| AC1 校验拒载+行号 | validator 报 jq 路径（`sources[2].reliability`），bad fixtures 齐 | **行号**（AC1 明确要求，现缺） |
| AC2 信源页 | 无（web 现有路由 `/`、`/intel/{id}`、`/feedback*`） | 整页新增 |
| AC3 页面试抓 | `probe_source()` 四维报告，仅 CLI 入口 | Web 触发入口+报告渲染 |
| AC4 人工置 enabled | collect 门控、probe 不受门控、工具不改 YAML | 语义已合，补证据 |
| AC5 零代码变更 | pack 加载机制 | 补证据 |

范围外（明确不做，防止私扩）：健康列深化与连续失败统计（→TASK-4.02.01）、告警站内信（→TASK-4.02.01）、采集入库（→TASK-1.01.02）、试抓异步任务化、页面鉴权（Web 内网默认开放，ADR-006）。

## 2. 关键决策与理由

| # | 决策 | 备选与否决理由 |
|---|---|---|
| D1 | 信源页**直读领域包**（loader.load + validate），不走 DB source 表 | DB 表经 collect 同步可能滞后；AC2 要求列表与 sources 节**一一对应**，pack 即事实源 |
| D2 | 试抓**同步执行**，POST 直渲染（无 PRG、无任务队列） | 单运营者内网工具；单源试抓秒级~几十秒可接受；PRG 无法携带报告面板 |
| D3 | pack 校验失败时页面渲染**错误态**（issues 含行号），不抛 500 | AC1「拒绝加载且不半截」的语义呈现在验收面上；信源页兼任配置诊断面 |
| D4 | 行号经 `yaml.compose()` 的 node marks 回溯 | ruamel 可原生保留位置但引新依赖；pyyaml 已有，零新增 |
| D5 | 无适配器源（RSS 等 6 源未接入）报告显示**「适配器未接入」失败态** | 不让运营者面对 500；与「试抓报告是启用依据」语义一致 |
| D6 | 新增 `pih.probe` logger，JSON lines，沿用 `consume/metrics.py` 模式 | doc-2 §8 结构化日志；不引入日志框架新组件 |
| D7 | CI 骨架进本故事（AC 外范围，已获用户批准） | DoD#4「CI 有增量测试且变绿」无 CI 即为空话；GH Actions 非自部署组件，合 DoD#2 |

## 3. 接口与状态语义

**GET /sources**
- pack 有效：渲染信源表格——名称/类型/层级/可靠性/频率/启用（on/off）+ 操作列（试抓按钮）；与 sources 节一一对应
- pack 校验失败：渲染错误态——逐条 issue（路径+行号+说明），表格不出现（不半截）
- pack 文件缺失/不可读：错误态，同上降级

**POST /sources/{id}/probe**
- 同步执行 probe_source()，响应即 /sources 页面 + 报告面板（不重定向）
- 信源 id 不存在于 pack：错误态/404，不 500
- 报告面板四段，三态语义固定：**成功**（该维通过）/ **失败**（该维执行且未通过）/ **未达**（因前置维度失败而未执行）
  - robots 失败 → 列表页/详情/快照 = 未达（probe 已实现：robots 拒绝不发后续请求，合规 NFR · doc-3）
  - 四段与 ProbeReport 字段的聚合映射在实现与测试中固化，三态语义本设计锁定
- 无适配器 → 报告整体「适配器未接入」失败态（D5）

**日志**：probe 执行写 JSON lines——事件（probe_start / probe_done）、source_id、四维成败、耗时、错误摘要。

## 4. 测试与 CI（本故事定型、后续故事复用）

| 层 | 跑在哪 | 本故事增量 |
|---|---|---|
| unit | CI | 行号映射；probe 路由三态（TestClient + monkeypatch probe_source） |
| contract | CI（PG service container） | sources.html 渲染（字段一一对应/报告四段/错误态/autoescape） |
| integration | 本地 compose（pre-merge 手动） | 列表真实 pack 渲染 + probe 端到端 |
| live | 手动 | 不新增（probe 单源实测已有惯例） |

- TDD：三块增量均测试先行（红→绿→重构）
- CI：`.github/workflows/ci.yml`，push/PR 触发——ruff → unit → contract；集成/live 不进 CI（需全栈 compose 与真网络，注释注明）
- 不变式：**CI 可运行集单调增长**——故事增量测试必须落在 CI 能跑的层

## 5. 事实源偏差与裁决

| 偏差 | 裁决 |
|---|---|
| 原型信源表格缺「可靠性」列（AC2 与 pack schema 均要求） | 修订原型补列（DoD#1：偏差修订事实源，不在代码里私自偏移） |
| schema sources required 漏列 fetch_frequency（AC1 必填清单含之） | 修正 schema 与 AC1 对齐，good 夹具/最小包测试同步补（AC1 为事实源，属实现补齐） |
| 执行中新发现的偏差 | 追加于此；架构级 → 先记 ADR 并与用户确认，再动代码 |

## 6. AC 证据清单（finalization 前逐条补齐）

- AC1：bad fixtures 行号断言测试名 + 运行输出
- AC2：模板契约测试名 + `/sources` 页面（compose 下 curl 输出或截图）
- AC3：probe 路由三态测试名 + 页面报告渲染证据
- AC4：门控既有测试复核 + 「工具不改 YAML」说明
- AC5：新增/删除信源后页面与调度反映的操作记录（无代码变更 diff 佐证）
