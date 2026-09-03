# TASK-1.01.02 设计：采集入库与原文可查

> 故事级细粒度设计，上承架构 doc-2（粗粒度稳定层），下接代码与测试（代码即文档）。
> 只记决策与理由、接口与状态语义、事实源偏差——不写数据结构逐字段、函数签名、伪代码。
> 关联：backlog 任务 TASK-1.01.02 ｜ 原型 `docs/prototype.html` 列表/详情节 ｜ ADR-003 / ADR-007 / ADR-009。
> 三处前置裁决（用户已拍板）：AC4 载体引入 `inbox_item`+`dead_letter`（裁决 a）；AC2 模糊去重留演进故事、本故事只做精确指纹；AC3 粗筛本故事内解耦、TASK-1.02.01 不先行。

## 1. 范围与存量映射

存量代码（旧 Sprint 交付）按「需验证资产」复用，不重写；偏差先回来对齐再动手。

| AC | 存量（实测） | 本故事增量 |
|---|---|---|
| AC1 统计+列表+详情+无快照不入库 | CLI `pih collect` 已打印「入库 N 新增 / M 幂等跳过 / K 失败」；web `/` 列表 + `/intel/{id}` 详情（含 snapshot presigned + 原始 url）已在；`collect_source` 经 fetch_detail 存档后落 `intel_item` | 见 §3——落库目标由 `intel_item` 改为 `inbox_item`；补「无快照不入库」显式守卫与端到端证据 |
| AC2 幂等跳过 | `intel_item.content_sha1` ON CONFLICT DO NOTHING 已实现精确去重 | 迁移到 inbox 幂等键；**模糊去重不做**（演进故事）；补「重采同行数不变」端到端证据 |
| AC3 粗筛不进列表+行级标记+漏报审计 | `graph.node_prefilter`（小模型二分类）已存在；`STATUS_FILTERED_OUT` + web `process_status` 筛选已通 | **关键词粗筛分量**（领域包监控关键词命中）新增；**粗筛从整图解耦**为独立可运行子步骤；**列表默认过滤 filtered_out**（行为变更）；漏报审计筛选取证 |
| AC4 先落盘不丢失/可查/可重放 | `intel_item` 采集时即建、`process_status=pending`、`raw_html` 落列；`pih process` 重跑 pending | **引入 `inbox_item`（先落盘）+ `dead_letter`**；采集期 fetch 失败也落一行（含失败原因）；处理期失败态有重放入口；CLI 加 replay/dead-letter 查询 |

范围外（明确不做，防止私扩）：结构化抽取与事件聚类（→TASK-1.02.01）；自动调度（→TASK-4.01.01）；信源健康告警与连续失败统计（→TASK-4.02.01）；模糊/近重复去重（演进故事，本故事记 backlog 单）；`pipeline_run` 运行留痕表（→TASK-4.01.01 调度落地时建，本故事用结构化日志承载留痕，见 D6）。

## 2. 关键决策与理由

| # | 决策 | 备选与否决理由 |
|---|---|---|
| D1 | **引入 `inbox_item` 表作为采集先落盘载体**，采集不再直写 `intel_item` | 现状 intel_item 兼任 inbox 与 intel，违反 doc-2 §6.4「intel_item 在通过质量门、挂入事件后才创建」。裁决 a 要求向事实源靠拢；ADR-009 inbox 汇聚语义对自动采集同样适用 |
| D2 | inbox→intel 的提升由处理链触发（粗筛通过→挂事件→创建 intel_item），**不在本故事做抽取提升** | 本故事只到粗筛；粗筛通过的条目停在 inbox 的 `pending` 态，等 TASK-1.02.01 抽取后提升。中间态是预期的，原文可查在 pending 态已满足（快照+原始链接在 inbox 即有） |
| D3 | **粗筛解耦为独立子步骤**（独立函数 + 可独立调用的编排缝），不耦合大模型配置前置校验 | 现状 `pih process` 跑整图且构造阶段要求 LLM 配置就绪——AC3 验证「判不相关」这条不需要大模型的路径会被前置校验卡住、且取证与抽取绑死。解耦后 AC3 独立取证、范围干净 |
| D4 | **关键词粗筛 + 小模型二分类**双通道，两者皆判不相关才 `filtered_out` | AC3 描述「关键词 + 小模型二分类」；关键词命中属确定性信号，与 LLM 二分类互补。单 LLM 通道不满足 AC 字面要求且依赖外部服务可用 |
| D5 | **引入 `dead_letter` 作为 inbox 失败终态标记**（doc-2 §7：死信为 inbox 条目的失败终态标记而非独立实体） | doc-2 已定死信语义；AC4「失败原因可查、可重放」需要载体。死信复用 inbox 行 + 状态字段，不建独立表（与 doc-2 §7 一致） |
| D6 | 运行留痕用结构化日志（JSON lines，沿用 `pih.collect` logger 模式）承载，**`pipeline_run` 表延后到 TASK-4.01.01** | AC4 要求「失败原因可查、可重放」——可查走日志+dead_letter 查询，可重放走 inbox 行的重处理入口；pipeline_run 的吞吐/时长/token 聚合属调度器诉求，本故事无调度器，建表无写入方 |
| D7 | **列表查询改为合并视图默认排除 `filtered_out`**：检索视图 = inbox(pending/needs_manual) + intel(extracted)，filtered_out 仅按状态显式筛出 | AC1「新条目出现在列表」+ AC3「不相关不进消费列表」是同一视图的两种状态过滤。原型列表「检索」视图示均为已结构化条目，filtered_out 不在其列；显式 process_status 筛选保留漏报审计（AC3 后半） |
| D8 | 幂等键 = 内容指纹 `content_sha1`（精确），**不增 url 独立唯一键、不做模糊去重** | 裁决 2：模糊去重留演进。url 同源重复已被 content 指纹覆盖（同 url 正文一致即 sha1 同）；增 url 唯一键会误伤「同 url 内容更新」（更新正是要入库的新条目） |

## 3. 接口与状态语义

**采集落库链路（重构后）**
- `collect_source` 门控通过 → fetch_list → 逐条 fetch_detail（快照随 fetch_detail 存档 MinIO）→ 每条产出 RawItem **落 `inbox_item`**（不再落 intel_item）
- 「无快照不入库」：fetch_detail 返回 None（含 robots 拒绝、无快照）的条目不产出 RawItem、不落 inbox；落 inbox 的行 `snapshot_id` NOT NULL 为守卫
- 统计口径不变：入库 N 新增 / M 幂等跳过 / K 失败——「新增/跳过」对 inbox 幂等冲突，「失败」对 fetch 或落盘异常

**inbox_item 状态机（处理状态，挂 inbox 行）**
- `pending`：刚落盘待处理（采集入库即此态；AC1 列表可见）
- `filtered_out`：粗筛判不相关（AC3，行级标记保留可审计；默认不出消费列表，按状态可筛）
- `dead`：失败终态（重试耗尽，AC4；失败原因可查、可重放）
- `needs_manual` / `extracted` / 提升→intel_item：**本故事不触发**，留 TASK-1.02.01。本故事范围内 inbox 只在 pending / filtered_out / dead 三态流转

**粗筛独立入口（D3）**
- 独立函数 `prefilter(text, pack) → kept: bool, reason: str`（关键词命中 + 小模型二分类，D4 双通道）；不依赖大模型构造（关键词通道独立成立，小模型通道 API 失败按保留处理——架构 §8 不丢弃）
- 编排缝可独立调用：输入 inbox pending 条目 → 产出 filtered_out 或保持 pending（不进 extract/validate）
- CLI 侧新增独立调用路径或在 `pih process` 增 `--prefilter-only`（实现时定，倾向后者减入口数）

**列表合并视图（D7）**
- `/` 检索视图：UNION inbox(pending/needs_manual) + intel(extracted)，默认 WHERE process_status != 'filtered_out'（且 dead 默认不出现）
- 详情页 `/intel/{id}` 与 `/inbox/{id}`：pending 条目从 inbox 取（原文快照+原始链接在 inbox 即有，AC1「点开可见原文」闭环）；extracted 条目从 intel 取——实现时定路由收敛策略（单一详情路由按来源判表，或双路由），倾向单一路由内部判表减分支
- 漏报审计：process_status=filtered_out 显式筛选可见（AC3 后半）

**失败可重放（AC4 / D5 / D6）**
- 采集期 fetch 失败：异常被 collect_source 捕获 → 落 inbox 一行（失败原因记 process_error，状态留 pending 待重试）；不丢快照索引
- 处理期失败（粗筛异常）：停留 pending 可重试；重试耗尽 → dead（dead_letter 标记），CLI 可查、可重放（重置为 pending 重入处理链）、可丢弃（丢弃留痕）
- 失败原因可查：dead 行 process_error + 结构化日志 JSON lines（pih.collect / pih.process logger）

## 4. 测试与 CI

| 层 | 跑在哪 | 本故事增量 |
|---|---|---|
| unit | CI | inbox 落库/幂等/无快照守卫；prefilter 关键词+二分类双通道；合并视图默认排除 filtered_out；dead 落标记 |
| contract | CI（PG service container） | 新迁移 apply（inbox_item + dead 标记列）；合并视图 SQL 行为 |
| integration | 本地 compose | 采集→inbox→列表/详情端到端；重采同行数不变；粗筛 filtered_out 不进默认列表+可筛出；fetch 失败落 inbox 可重放（跨接线缝——单测 monkeypatch 掩盖） |
| live | 手动 | `pih collect` 真源实弹 + 页面 curl（沿用 1.01.01 惯例） |

- TDD：每 AC 切片 红→绿→重构；新迁移先红（contract 断言表存在）
- CI 不变式：**CI 可运行集单调增长**；inbox 合并视图重构不得破坏既有 list/detail/feedback 契约测试（回归底线）
- integration 必做跨接线缝：collect→inbox 写入、web 合并视图读 inbox、粗筛独立入口端到端（doc-5 §4：单测 monkeypatch 会掩盖接线 bug）

## 5. 事实源偏差与裁决

| 偏差 | 裁决 |
|---|---|
| 现状 intel_item 兼任 inbox，违反 doc-2 §6.4「intel_item 通过质量门后才创建」 | **本故事修正**：引入 inbox_item 先落盘，intel_item 回归「通过质量门后创建」。采集落库目标迁移（D1）。重构影响见 §6 |
| 迁移 0001 未建 inbox_item / dead_letter / pipeline_run（doc-2 §7 要求） | 新增迁移建 inbox_item + dead 标记列；pipeline_run 延后 TASK-4.01.01（D6，无调度器无写入方） |
| AC2 写「内容相似度超阈值」模糊去重 | 裁决 2：模糊去重留演进故事（记 backlog 单），本故事只做精确 content_sha1 幂等（D8）；AC2 验收口径据此收窄，**需回填任务 AC 描述或 notes 标注**（DoD#1） |
| AC3「不进入消费列表」与现状列表不过滤 filtered_out 冲突 | 行为变更：列表默认排除 filtered_out（D7）；漏报审计靠显式筛选取证 |
| 执行中新发现的偏差 | 追加于此；架构级 → 先记 ADR 并与用户确认，再动代码 |

## 6. 重构影响与回滚（inbox 迁移，裁决 a 带来的最大改动面）

**迁移路径**：新增迁移建 `inbox_item`（采集落盘列 + process_status + snapshot_id NOT NULL + content_sha1 幂等 + dead 标记）；采集写目标从 intel_item 切到 inbox_item；web 列表/详情读合并视图。

**受影响存量（实测清单）**：
- `store/repository.py`：`save/save_batch` 改写 inbox；`list_pending` 改读 inbox；`list_by_filter`/`get` 改合并视图；`write_process_result` 本故事仅写 filtered_out/dead（extracted 提升留 1.02.01）
- `collect/run.py`：`collect_source` 落库目标切 inbox + fetch 失败捕获落行
- `consume/web.py` + `query_service.py`：列表/详情合并视图路由
- `process/run.py` + `graph.py`：粗筛解耦（D3）；ProcessRunner 构造不再因粗筛路径要求大模型配置
- `cli.py`：collect 统计口径适配 inbox；粗筛独立入口；dead 查询/重放命令
- 既有契约/集成测试：回归底线（合并视图不破 list/detail/feedback）

**回滚（1 人可恢复，DoD#7）**：迁移含 downgrade（drop inbox_item）；代码改动按切片细粒度 commit，可逐切片回退。inbox 引入为加表非改列，intel_item 既有数据不动，回滚不丢数据。

**风险**：合并视图跨表 UNION 的排序/分页（现 list_by_filter 用 fetched_at 游标）需在 inbox+intel 间统一——实现时定（倾向统一 fetched_at 排序键，分页游标跨表一致）。

## 7. AC 证据清单（finalization 前逐条补齐）

- AC1：`pih collect` 实弹输出（入库 N/M/K）+ `/` 列表含新条目 + 详情原文快照与原始链接两个入口 curl + 无快照守卫测试名
- AC2：重采同行数不变的 integration 用例 + inbox 幂等冲突单测名
- AC3：粗筛判不相关→filtered_out 单测名 + 列表默认不含 filtered_out 断言 + process_status=filtered_out 可筛出（漏报审计）用例
- AC4：fetch 失败落 inbox 行（失败原因可查）integration 用例 + dead 标记可重放 CLI 命令 + 结构化日志取证
