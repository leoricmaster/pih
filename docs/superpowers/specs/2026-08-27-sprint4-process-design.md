# Sprint 4：process 层第一期 —— 设计规格

> 状态：草案（待评审）
> 范围：LangGraph 抽取流水线工程化（粗筛 → 抽取 → 校验）+ 领域包提示词正式化 + intel_item 结构化字段迁移 + `pih process` 命令 + `pih query` 结构化筛选。让库中情报带上主体/事件类型/标签/Admiralty 评级，可按结构化维度筛选。
> 依据：架构 §4（PROCESS 层）、§5.1（主流程处理段）、§6.2（Admiralty 词表）、§6.3（领域包机制）、§8（可靠性）、ADR-001（领域包）、ADR-004（LangGraph）、ADR-007（重试降级）；Backlog S4.1.2（粗筛）、S4.2.1（结构化抽取）、S4.2.2 AC1（预评级简版）；SPK-2（提示词 v3 + 实测 token/准确率）、SPK-3（三节点图 E2E 成功率 92%）。

---

## 0. 背景与不做什么

**Sprint 3 已交付**：PG + alembic + IntelRepository + `pih collect` 默认落库 + `pih query`。RawItem 已落库，但 `intel_item` 是最小切片——无主体/事件类型/标签/置信度字段，情报只能按信源与时间浏览，不能按结构化维度筛选。process 层仅有占位 `__init__.py`。

**spike 遗产（本 Sprint 工程化的直接输入）**：

| 遗产 | 位置 | 去向 |
|---|---|---|
| 抽取提示词终版 v3 | `spikes/spk2-extraction-probe/prompt_v3.txt` | 工程化进领域包 `extraction_prompt`（占位符注入枚举/标签树/主体清单） |
| 事件类型 11 类枚举 | `spikes/spk2-extraction-probe/golden/make_dataset.py` `EVENTS` | 领域包新增 `event_types` 必填节（单一事实源从 spike 代码移入配置） |
| 三节点 LangGraph 图 | `spikes/spk3-langgraph-e2e/graph.py` | 工程化进 `src/pih/process/graph.py`，修掉 spike 遗留契约（见 §3.4） |
| LLM 客户端 | `spikes/_lib/llm.py`（chat_json/extract_json） | 迁移进 `src/pih/process/llm.py` |
| HTML 剥标签 | `golden/make_dataset.py` `strip_html` | `src/pih/process/textprep.py` |

**本 Sprint 不做**（明确排除）：

- **不做事件聚类 / event 表 / verification_log / 核实状态机**——绑死"双独立信源判定 + 人工终态"语义，工作量大，留 Sprint 5；S4.2.2 仅交付 AC1（预评级简版），AC2/AC3 跨 Sprint 满足（先例：S4.1.1 AC1）。
- **不做调度器**——`pih process` 为手动触发的离线批处理；调度器 Sprint 再串联 collect → process。
- **不做消费层 Web/API**——FastAPI 同源服务（ADR-006）是 M1 末段独立 Sprint；结构化筛选本 Sprint 只扩 `pih query` CLI。
- **不做向量 / 全文索引**——embedding 依赖分段更细的消费场景，留 M1 末段检索 Sprint。
- **不做时效管理器**（expires_at / 过期降权）——S4.3.1 后置。
- **不做抽取质量优化**（few-shot 迭代 / 语义评分）——SPK-2 枚举命中率 52–56% 是提示词问题，靠领域包提示词版本化迭代，不靠本 Sprint 工程化解决。
- **不做 golden 评估器迁移**——25 样本评估器留在 spikes（throwaway 定位不变），集成测试只断言 schema 完整性不断言准确率。

---

## 1. 已锁定决策（用户确认，2026-08-27）

| 决策 | 选择 | 含义 |
|---|---|---|
| 粗筛（S4.1.2）纳入本 Sprint | ✅ | 三节点图（粗筛→抽取→校验）一体工程化；丢弃条目在库标记 `filtered_out` 留审计 |
| 预评级（S4.2.2 AC1）简版纳入 | ✅ | reliability 继承 source 表 + credibility 由抽取 prompt 输出（1–6 枚举），拼 `admiralty_code` 列；AC2/AC3 留 Sprint 5 |
| 结构化筛选出口 | 只扩 `pih query` CLI | `--subject/--event-type/--tag` 过滤；FastAPI 留消费层 Sprint |

---

## 2. 待定决策（本规格需拍板，给出推荐）

| # | 议题 | 推荐 | 理由 |
|---|---|---|---|
| D1 | 处理触发时序 | **离线批处理命令 `pih process`**，collect 不调 LLM | collect 不依赖 LLM 可用性（架构 §8：LLM 故障不得阻塞采集）；调度器 Sprint 再串联；用户可先 `pih collect` 攒数据再择时 `pih process` |
| D2 | 抽取输入文本 | **剥 HTML 标签 + 截断 6000 字符**（spike 口径） | raw_html 含标签浪费 token 且干扰抽取；golden `strip_html` 三步正则已验证；6000 字符是 SPK-2/3 实测口径 |
| D3 | 结构化字段存储 | tags/quant_params 用 **JSONB**；文本字段用 TEXT；`process_meta` JSONB 存可观测数据（node_timings/retries） | JSONB 支持 GIN 索引与 containment 查询；不为可观测性建多列 |
| D4 | 粗筛丢弃的表示 | **intel_item 行保留 + `process_status='filtered_out'`**，不建独立粗筛日志表 | S4.1.2 AC1「记录到粗筛日志供漏报审计」——行级标记即日志（SQL 可查），1 人运维不添表；灰条目（粗筛 API 失败）按保留处理走抽取（SPK-3 结论） |
| D5 | 提示词占位符机制 | extraction_prompt 须含 `<事件类型>`/`<标签树>`/`<主体清单>` 三个 token，**schema 校验 token 存在**，process 层注入 | 枚举单一事实源在领域包节（event_types/tag_tree/competitors），prompt 不重复维护清单；缺 token 拒绝加载（ADR-001 精神） |
| D6 | credibility 判据 | 提示词内嵌 Admiralty 信息可信度判据表（1=已证实 … 6=无法判断），LLM 输出第 7 字段 | 架构 §6.2「LLM 预评级与人工评级共用同一词表」；v3 提示词扩展一个键，抽取行为变化小 |
| D7 | LLM 环境变量 | 统一 `PIH_LLM_BASE_URL / PIH_LLM_API_KEY / PIH_LLM_LARGE_MODEL / PIH_LLM_SMALL_MODEL`，根 `.env.example` 替换现有 `LLM_*` 占位 | 沿用 spikes 已验证命名，spike 代码与新代码 env 口径一致 |
| D8 | 并发策略 | **串行逐条**，不做并发 | 推理模型每条 ~20s，10 条约 3–4 分钟可接受；M1 规模小，并发增加限流与调试复杂度（YAGNI） |

---

## 3. 核心设计

### 3.1 领域包 v2（schema + pack.yaml）

**schema.py 扩展**：

- `event_types`: `array[string], minItems 1`，**必填**——事件类型枚举进配置（行业知识配置化，贯穿性约束 1）；
- `extraction_prompt`: 校验升级——非空 + **必含三个占位符 token** `<事件类型>`、`<标签树>`、`<主体清单>`（缺失拒绝加载并指出缺哪个）。

**pack.yaml（construction_machinery）更新**：

- `event_types`: 11 类，自 golden `EVENTS` 迁移：新品发布/功能迭代/专利公开/中标落地/组织人事/价格变动/标准动态/行业统计/行业合作/财报/其他；
- `tag_tree`: **删除现有「事件类型」子树**（8 类，与 event_types 重复且口径过时）；技术标签树对齐 SPK-1 锁定口径（无人化作业/远程遥控/3D引导与机控/电动化/智能辅助施工/场景-矿山/场景-港口/场景-市政/核心零部件），按现有三分类结构组织；
- `extraction_prompt`: SPK-2 v3 工程化版——保留 v3 全部严格规则，三处清单改占位符，新增第 7 输出键「信息可信度」（D6 判据表内嵌）；
- `meta.version`: 0.1.0 → 0.2.0。

**提示词模板（v3 工程化版，全文进 pack.yaml）**：在 v3 基础上：

1. 输出 JSON 增键 `"信息可信度": "1-6 枚举"`，附判据：1=官方证实/一手数据，2=权威媒体确认，3=单一可靠来源未证实，4=转述/推测成分明显，5=匿名/传闻来源,6=无法判断；
2. `<事件类型>`/`<标签树>`/`<主体清单>` 占位符由 process 层注入（v3 已用前两个，`<主体清单>` 新增——注入 competitors 的 display_name+aliases 帮助主体对齐，v3 规则 2 的落地）。

### 3.2 process 模块结构

```
src/pih/process/
├── __init__.py       # 改：模块说明（去占位）
├── llm.py            # OpenAI 兼容客户端（spikes/_lib/llm.py 工程化）
├── textprep.py       # raw_html → 抽取输入文本（剥标签+截断）
├── extraction.py     # IntelExtraction 模型 + validate_pred（字段齐全/枚举/标签树校验）
├── graph.py          # LangGraph 三节点图（prefilter→extract→validate）
└── run.py            # ProcessRunner：list_pending → 图 → 写回，token/耗时统计
```

### 3.3 LLM 客户端（llm.py）

从 `spikes/_lib/llm.py` 迁移，三处工程化改动：

1. **代理密闭性（关键）**：`OpenAI(..., http_client=httpx.Client(trust_env=False))`——openai SDK 默认继承环境代理变量，用户 shell 常驻 SOCKS 代理会劫持 LLM 流量（与 collect 层 HttpClient 同一口径，spike 未处理因直接跑）；
2. 环境变量按 D7：`PIH_LLM_BASE_URL/PIH_LLM_API_KEY/PIH_LLM_LARGE_MODEL/PIH_LLM_SMALL_MODEL`，缺变量时抛带指引的 `LLMConfigError`（区分于运行时 `LLMError`）；
3. `chat_json(messages, tier)`：tier ∈ {large, small} 替代 model_env 直传（路由集中管理，架构 §9.2「换模型不改代码」）；保留温度 0、`response_format=json_object`、线性退避重试 ×3、`extract_json` 三级容错（fence → 整段 → raw_decode）原样迁移。

### 3.4 LangGraph 图（graph.py）

SPK-3 `graph.py` 工程化，结构不变（`START → prefilter →(条件) extract → validate → END`），修掉三条 spike 遗留契约（process/__init__.py 已沉淀）：

| spike 遗留 | 工程化修正 |
|---|---|
| 重试计数混计（`retries += usage["retries"] + 1`） | state 分列 `api_retries`（chat_json 内部重试累计）与 `validate_rounds`（补问轮次） |
| 异常分支 state 缺 text | state 由 Runner 构造、节点只增改不删；`text` 必填字段 |
| TAGS/EVENTS 硬编码 | 全部来自领域包（event_types/tag_tree/competitors），图构建函数 `build_graph(pack_extras)` 接收注入 |

节点行为：

- **prefilter**：小模型 `{"relevant": bool}`；**API 失败按保留处理**（灰条目走抽取，架构 §8「不丢弃」）；判定不相关 → `process_status='filtered_out'`；
- **extract**：大模型 + 领域包提示词（占位符注入后）；输入 = textprep 产物截 6000；
- **validate**：`validate_pred` 校验 7 字段——6 抽取键齐全、事件类型 ∈ event_types、标签 ⊆ 标签树、信息可信度 ∈ 1–6；不合格自动重问 ≤3（复用原提示词 + 缺陷说明 user 消息）；重问耗尽 → `process_status='needs_manual'`，条目保留（AC2 不丢弃）。

### 3.5 迁移 0002（intel_item 加列）

```sql
ALTER TABLE intel_item
    ADD COLUMN subject         TEXT,
    ADD COLUMN event_type      TEXT,
    ADD COLUMN facts           TEXT,
    ADD COLUMN inferences      TEXT,
    ADD COLUMN tags            JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN quant_params    JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN admiralty_code  TEXT,
    ADD COLUMN process_status  TEXT NOT NULL DEFAULT 'pending',
    ADD COLUMN process_error   TEXT,
    ADD COLUMN process_meta    JSONB,
    ADD COLUMN processed_at    TIMESTAMPTZ;

CREATE INDEX idx_intel_item_process_status ON intel_item(process_status);
CREATE INDEX idx_intel_item_event_type ON intel_item(event_type);
CREATE INDEX idx_intel_item_tags ON intel_item USING GIN(tags);
```

`process_status` 枚举（应用层约束）：`pending → extracted | filtered_out | needs_manual`。存量行自动获得 `pending` 默认值——Sprint 3 已入库数据可直接被 `pih process` 处理。

### 3.6 store 扩展（repository.py 加三方法）

```python
def list_pending(self, source_id: str | None = None, limit: int = 20) -> list[IntelRecord]:
    """取待处理条目（process_status='pending'，fetched_at ASC 先老后新），JOIN source 带 reliability。"""

def write_process_result(self, intel_id: int, result: ProcessResult) -> None:
    """写回抽取结果 + process_status/processed_at/process_error/process_meta。"""

def list_by_filter(self, *, subject=None, event_type=None, tag=None,
                   source_id=None, limit=50) -> list[IntelRecord]:
    """结构化筛选：subject 精确、event_type 精确、tag 用 tags @> containment；排序 processed_at DESC。"""
```

`IntelRecord` 扩展对应新列；`admiralty_code = reliability + credibility` 由 Runner 拼装写回。

### 3.7 CLI

```bash
pih process [--source-id=ccma] [--limit=5]     # 批处理 pending 条目
pih query --event-type=新品发布 [--subject=三一] [--tag=电动化] [--limit=10]
```

- `pih process`：逐条跑图，实时输出每条结论（✓ extracted [B2] 主体/事件类型 / ✗ needs_manual / ⊘ filtered_out）；末尾统计行 `处理 N 条 → 抽取成功 X / 粗筛丢弃 Y / 待人工 Z / 失败 W` + token 汇总 `prompt 12,345 / completion 6,789 tokens`（成本可观测，架构 §9.2）；LLM env 缺失 → 明确报错退出 2，不产生半写状态（先校验配置再取条目）。
- `pih query`：`--id/--source-id` 之外新增 `--subject/--event-type/--tag`（可与 `--source-id` 组合）；`--id` 与筛选互斥校放宽为：`--id` 单独用（现状），筛选条件可独立使用（不再强制 source-id）；列表输出增列 `process_status / event_type / admiralty_code`，详情打印增结构化字段段。
- 退出码沿用：0 成功 / 1 处理有条目失败 / 2 用法或环境错误。

### 3.8 环境与依赖

`pyproject.toml`：`openai>=1.40`、`langgraph>=0.2` 已预留，无新增（httpx collect 层已有）。

`.env.example`：LLM 节替换为四变量（D7），注明「留空则 LLM 集成测试跳过」。

---

## 4. 目录结构（落地产物）

```
src/pih/process/
├── __init__.py          # 改：去占位说明
├── llm.py               # 新
├── textprep.py          # 新
├── extraction.py        # 新
├── graph.py             # 新
└── run.py               # 新

migrations/versions/
└── 0002_process_fields.py   # 新：§3.5 加列

src/pih/domainpacks/schema.py    # 改：event_types + prompt token 校验
domain_packs/construction_machinery/pack.yaml   # 改：§3.1
src/pih/store/repository.py      # 改：三方法 + IntelRecord 扩展
src/pih/cli.py                   # 改：process 子命令 + query 扩展

tests/unit/process/   # test_llm / test_textprep / test_extraction / test_graph（fake chat_json）/ test_run
tests/unit/store/test_repository.py   # 改：三方法
tests/contract/       # test_migrations_apply 扩 0002；pack 对齐契约；bad fixtures 增样例
tests/integration/test_process_e2e.py # 新：真实 LLM 端到端
```

---

## 5. 测试策略

| 层 | 内容 | 依赖 |
|---|---|---|
| unit | llm：extract_json 三级容错（迁移 spike 测试）/ chat_json 重试退避 / trust_env=False / tier 路由（mock OpenAI client）；textprep：剥标签（script/style/嵌套/空白）；extraction：validate_pred 各失败分支（缺键/枚举外/标签外/可信度外）；graph：prefilter 三分支（keep/drop/API 失败按保留）、extract 失败、validate 重问与耗尽 → needs_manual、api_retries 与 validate_rounds 分列（注入 fake chat_json）；run：统计汇总、admiralty 拼装、config 缺失快速失败；repository 三方法（mock pool 验 SQL 与参数） | 无 DB 无 LLM |
| contract | alembic upgrade head 加列出索引 → downgrade base 干净；领域包 schema：缺 event_types 拒绝、prompt 缺占位符拒绝（新 bad fixtures）、现网 pack.yaml 通过校验且 event_types=11 类 | docker compose PG |
| integration | 真实端到端：`pih collect ccma --max-items=2` → `pih process ccma --limit=2` → 断言 extracted 条目 subject/event_type/facts 非空 + admiralty_code 首字符=B（ccma reliability）→ `pih query --event-type=<实际值>` 召回该条；幂等重跑：二次 process 处理 0 条 | docker compose 全栈 + 外网 + LLM env（任一缺失整文件 skip，与 collect 集成测试同口径） |

集成测试密闭性：LLM 客户端 trust_env=False 不走 shell 代理；断言结构不断言具体文本（LLM 输出不稳定）。

---

## 6. 验收标准（Gherkin）

```gherkin
AC1: Given docker compose up + LLM env 已配置 + 库中有 ccma pending 条目
     When 运行 pih process --source-id=ccma --limit=2
     Then stdout 显示每条结论与统计行
     And 条目 process_status=extracted
     And subject / event_type / facts 非空，event_type ∈ 领域包 event_types
     And tags ⊆ 领域包标签树，admiralty_code 非空且首字符 = B（继承 ccma.reliability）

AC2: Given 一条条目 LLM 输出反复未通过 schema 校验
     When validate 节点补问 3 次仍失败
     Then process_status=needs_manual，process_error 记录原因
     And 条目保留在库中不丢弃（S4.2.1 AC2）

AC3: Given 一条与领域无关的 pending 条目
     When 粗筛判定不相关
     Then process_status=filtered_out
     And 该条目仍可 pih query 查到（审计口径，S4.1.2 AC1）

AC4: Given LLM 粗筛调用失败（网络/限流）
     When prefilter 节点处理该条目
     Then 按保留处理继续抽取，不因粗筛故障丢条目

AC5: Given 库中有 ≥2 条不同 event_type 的 extracted 条目
     When 运行 pih query --event-type=新品发布
     Then 仅返回该类型条目且按 processed_at DESC
     And 输出含 subject / event_type / admiralty_code 列

AC6: Given 库中已存在 extracted 条目
     When 再次运行 pih process
     Then 仅处理 pending 条目，已处理条目不被重复抽取（无状态幂等）

AC7: Given alembic upgrade head
     Then intel_item 新增 §3.5 全部列
     And process_status 默认 pending，存量行可被处理
     And downgrade base 后新列全部消失

AC8: Given 未配置 PIH_LLM_* 环境变量
     When 运行 pih process
     Then 报错退出码 2，附配置指引，不修改任何条目状态

AC9: Given 领域包 YAML 缺 event_types 节或 extraction_prompt 缺任一占位符
     When 加载领域包
     Then 拒绝加载并指出缺失项
```

---

## 7. 任务分解（建议 7 任务）

1. **T1 LLM 客户端**：`process/llm.py`（extract_json 迁移 + trust_env=False + tier 路由 + LLMConfigError）+ 单测；`.env.example` 替换 LLM 节。
2. **T2 领域包 v2**：schema event_types + prompt token 校验；pack.yaml（event_types 11 类 / tag_tree 修正 / v3 工程化提示词 + 信息可信度）；bad fixtures 三例；契约测试。
3. **T3 迁移 0002 + store 扩展**：加列迁移 + 契约测试；IntelRepository 三方法 + IntelRecord 扩展 + 单测。
4. **T4 textprep + extraction 模型**：剥标签 + 截断；IntelExtraction + validate_pred + 单测。
5. **T5 LangGraph 图**：`graph.py` 工程化（pack 注入 + 重试分列 + text 在场契约）+ 单测（fake chat_json 全分支）。
6. **T6 ProcessRunner + CLI**：`run.py`（统计/admiralty 拼装/配置前置校验）+ `pih process` 子命令 + `pih query` 扩展 + 单测。
7. **T7 端到端集成测试 + 回写**：`test_process_e2e.py`（AC1–AC6）；Backlog（S4.1.2/S4.2.1 置已交付、S4.2.2 备注拆分、版本 V1.3）；架构 §4/§7 回写；README 状态位 + process/query 用法。

依赖：T1、T2、T3、T4 可并行起步；T5 依赖 T1+T2+T4；T6 依赖 T3+T5；T7 收尾。

---

## 8. 回写与文档纪律

- **Backlog（必须）**：S4.2.1 置已交付（AC1/AC2 满足；备注「标签可为空数组」口径——行业统计类情报常无技术标签，AC1『非空』按字段存在 + 合法性满足）；S4.1.2 置已交付（AC1 粗筛日志 = 行级 filtered_out 标记，SQL 可审计）；S4.2.2 备注「AC1 Sprint 4 满足（简版），AC2/AC3 待事件聚类 Sprint」（先例 S4.1.1 AC1 跨 Sprint 备注）；S1.1.1 备注「CLI 子集已交付（pih query 结构化筛选），Web/API 出口待消费层 Sprint」。版本 V1.2 → V1.3。
- **架构**：§4 PROCESS 层模块表（结构化抽取器/核实引擎[预评级段]/相关性粗筛 状态更新，事件聚类器仍待）；§7 数据架构（intel_item 结构化列已落地；event/verification_log 仍待）；§3 Sprint 实测注脚补一条 Sprint 4 备注（可选）。
- **README**：分层表 process 行「占位」→「✅ Sprint 4 已交付（LangGraph 抽取 + 预评级 + 结构化筛选）」；CLI 段补 `pih process` 与 `pih query` 新参数。
- **不回写**：spike 报告（throwaway）。

---

## 9. 风险

| 风险 | 缓解 |
|---|---|
| openai SDK 继承 shell 代理（用户常驻 SOCKS）导致集成测试/运行流量被劫持 | llm.py 显式 `http_client=httpx.Client(trust_env=False)`（§3.3-1），单测断言构造参数 |
| LLM 输出枚举漂移（事件类型/标签不在清单内） | validate_pred 枚举校验 + 重问 ≤3；仍失败 needs_manual 不丢弃（AC2）；质量优化属提示词迭代，非本 Sprint 范围 |
| 信息可信度新增键改变抽取行为（v3 未验证过 7 键输出） | 集成测试 AC1 先跑 2 条实测；若 completion 质量明显劣化，提示词内可信度判据收紧（D6 判据表已给锚点） |
| 推理模型每条 ~20s，批处理慢 | 串行 + `--limit` 控批量（D8）；CLI 实时逐条输出进度；并发留调度器 Sprint 按需引入 |
| raw_html 超长条目 token 超限 | textprep 剥标签 + 截 6000 字符（spike 口径，D2） |
| 0002 迁移对存量表锁表 | M1 规模 < 1 万行，ALTER ADD COLUMN 秒级；无生产数据风险 |
| 集成测试依赖外部 LLM 服务可用性 | env 缺失整文件 skip；断言结构不断言文本；失败重跑不污染（process 幂等，AC6） |
