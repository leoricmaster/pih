# Sprint 1：工程脚手架 Sprint —— 设计规格

> 状态：草案（待评审）
> 范围：从 spike 探索转入正式工程化；落地架构 §6.3 钦定的最优先技术任务"领域包加载器 + 校验器"，并立起可测试的代码骨架与本地运行环境。
> 依据：架构 §3 容器视图、§4 逻辑分层、§6.3 领域包机制、ADR-001、ADR-004、ADR-005；Backlog §392–395 迁移约定。

---

## 0. 背景与不做什么

**Sprint 0 结论**：三 Spike 已交付，文档三件套 bump 至需求 V1.0 / 架构 V0.9 / Backlog V0.9。spike 代码是探索性 throwaway，停留在 `spikes/`，**不进工程包**，仅作参考与回归夹具来源。

**本 Sprint 不做**（明确排除，避免镀金）：
- 不实现任何业务模块（采集/抽取/核实/查询）——这些是后续 Sprint；
- 不选型需求管理工具——Backlog §392 已定"工具选定前本文档为唯一事实源"，无真实痛点驱动前不支付选型成本；
- 不动 spike 代码做 Minor 修复——Sprint 0 的 6 可选 Minor（HTML 实体解码、重试计数分离等）作为**设计输入**沉淀进本 Sprint 的契约/需求，而非回补 throwaway 代码；
- 不引入 changedetection.io（变更监控，架构 §3 标注"独立变更监控"，非 M1 优先，后续 Sprint）。

---

## 1. 已锁定决策（用户确认）

| 决策 | 选择 | 含义 |
|---|---|---|
| 运行环境 | Docker Compose 先行 | 第一天立 compose：PG+pgvector / MinIO / app；开发与测试在容器内 |
| 包结构 | 单包 `src/pih` + 严格分层 | src-layout 单包，内部分层对齐架构 §4 五层；spike 不进包 |

---

## 2. 待定决策（本规格需拍板，给出推荐）

| # | 议题 | 推荐 | 理由 |
|---|---|---|---|
| D1 | schema 校验库 | **jsonschema**（spike 已用，`requirements.txt` 已锁） | 校验器是"缺必选字段拒绝加载并指出位置"的纯校验语义，jsonschema 的 `jsonschema.Draft` + path 指纹天然给位置；引入 pydantic 会绑定数据模型层，过早。校验器只产 `ValidationResult`，模型类后续 Sprint 再上 pydantic。 |
| D2 | 包管理 / 依赖 | **pyproject.toml + uv** | spike 用 requirements.txt + venv；工程期需锁文件可复现，uv 速度快且与 compose 容器构建兼容；不引入 poetry 的额外约定。 |
| D3 | 示例领域包 fixture | **挖机/工程机械（第一领域）** | SPK-4 物流机器人是"第二领域套模"用于验通用性，属后续；本 Sprint 用第一领域做真实 fixture，golden.jsonl 的 25 样本字段结构（主体/事件类型/事实描述/标签/推断与判断/量化参数）直接喂校验器测试。 |
| D4 | 测试分层 | 单元（纯函数，无 IO）+ 契约（schema 对 fixture）+ 容器集成（compose 起来后 smoke） | 单元用 pytest，不依赖容器；集成测试用 `pytest` mark 隔离，`@pytest.mark.integration` 需 compose up。Sprint 1 只立框架 + 领域包相关测试，不写业务集成。 |
| D5 | DB 迁移工具 | **暂不引入 alembic**，仅立空 `migrations/` 占位 + 一条 init 占位 | Sprint 1 不建业务表（§7 的 intel_item 等是后续）；本 Sprint 只需 PG 可连 + pgvector 扩展可用做 smoke。引入 alembic 留到建第一张表的 Sprint。 |

---

## 3. 目录结构（落地产物）

```
pih/
├── docker-compose.yml              # 新：PG+pgvector / minio / app（dev）
├── Dockerfile                      # 新：app 镜像
├── pyproject.toml                  # 新：包元数据 + 依赖（uv）
├── uv.lock                         # 新：锁文件
├── README.md                       # 改：补工程化启动说明
├── .env.example                    # 新：DB/MinIO/LLM 连接占位
├── src/pih/
│   ├── __init__.py
│   ├── domainpacks/                # 横切层 PK 节点（§4 CROSS）
│   │   ├── __init__.py
│   │   ├── schema.py               # 领域包 JSON Schema 定义（六元 + ranking）
│   │   ├── loader.py               # 加载器：读 YAML → dict
│   │   ├── validator.py            # 校验器：dict → ValidationResult（含位置）
│   │   └── errors.py               # ValidationIssue / LoadError
│   ├── collect/                    # 采集层占位（仅 __init__，后续 Sprint）
│   ├── process/                    # 处理层占位
│   ├── store/                      # 存储层占位（PG 连接 helper 可后续）
│   ├── consume/                    # 消费层占位
│   └── core/                       # 五元模型等核心域（本 Sprint 仅命名空间占位）
├── domain_packs/                   # 领域包 YAML 事实源（repo 内，§6.3）
│   └── construction_machinery/
│       └── pack.yaml               # 第一领域示例包
├── migrations/                     # 占位（D5）
│   └── README.md
├── tests/
│   ├── conftest.py                 # fixture：fixtures 路径、容器 mark
│   ├── unit/
│   │   ├── test_loader.py
│   │   ├── test_validator.py
│   │   └── test_schema_self_consistency.py
│   ├── contract/
│   │   └── test_pack_yaml_against_schema.py   # domain_packs/*.yaml 对 schema
│   └── integration/
│       └── test_compose_smoke.py   # @pytest.mark.integration
├── spikes/                         # 原样保留，不动
└── docs/                           # 原样保留
```

**分层纪律**（架构 §4 五层落地为包内子模块）：
- `domainpacks/` ← 横切层 PK 节点 —— **本 Sprint 主交付**；
- `collect/` `process/` `store/` `consume/` ← 四层占位，仅 `__init__.py` + 模块 docstring 写明职责（抄架构 §4 模块表），不写实现；
- `core/` ← 五元模型命名空间，占位；
- 严禁跨层反向依赖（`collect` 不 import `consume` 等），用 `tests/unit/test_layering.py` 守护（可选，见 §6）。

---

## 4. 领域包 schema 设计（本 Sprint 核心）

依据架构 §6.3：领域包 = { 信源清单, 监控关键词, 竞品主体清单, 标签树, 报告模板, 抽取提示词 } + `ranking:` 节（§6.2）。

**`pack.yaml` 顶层结构**（第一领域示例）：

```yaml
meta:
  domain_id: construction_machinery      # 必选，与目录名一致
  display_name: 工程机械
  version: 0.1.0                         # 必选，semver
sources:                                 # 信源清单（必选，≥1）
  - id: ccma
    name: 中国工程机械工业协会
    type: rss                            # enum: rss|html|api|change_monitor
    url: http://www.cncma.org/...
    reliability: B                       # Admiralty 来源可靠性 A–F
keywords: [挖机, 装载机, ...]             # 监控关键词（必选，≥1）
competitors:                             # 竞品主体清单（必选，≥1）
  - id: sany
    display_name: 三一
    aliases: [三一, SANY]
tag_tree:                                # 标签树（必选）
  产品类:
    - 挖掘机械
    - 装载机械
  市场类:
    - 进出口
report_template: ...                     # 报告模板（必选，本 Sprint 占位字符串）
extraction_prompt: ...                   # 抽取提示词（必选，本 Sprint 占位）
ranking:                                 # §6.2 排序权重（可选，有默认）
  reliability_weights: {A: 1.0, B: 0.8, ...}
  credibility_weights: {1: 1.0, 2: 0.8, ...}
  event_state_weights: {confirmed: 1.0, single: 0.8, ...}
```

**校验器语义**（ADR-001 / §6.3）：缺必选字段 → 拒绝加载并**指出位置**（如 `sources[0].reliability: 必选字段缺失`）。`ValidationResult` 含 `ok: bool` + `issues: list[ValidationIssue]`，每 issue 带 `path` / `message` / `severity`。

**schema 表达**：用 JSON Schema Draft 2020-12（`schema.py` 内嵌 dict 或加载 `schema.json`）；`type` 用 enum 约束；`sources/keywords/competitors` 用 `minItems: 1`。

---

## 5. 测试策略（用户强调"考虑到测试"）

| 层 | 内容 | 依赖 |
|---|---|---|
| unit | loader 纯函数（读 YAML、路径解析）、validator 纯函数（schema 匹配 + 位置产出）、schema 自洽 | 无 IO，纯 pytest |
| contract | `domain_packs/construction_machinery/pack.yaml` 对 schema 通过校验；故意构造缺字段/坏 enum 的坏包 → 校验器拒绝并指位置 | 用 fixture 文件 |
| integration | compose up 后：PG 可连、`CREATE EXTENSION vector` 成功、MinIO 可连、app 容器 import `pih` 成功 | `@pytest.mark.integration`，需 docker |

**夹具复用**：spike `golden/golden.jsonl` 的字段结构（主体/事件类型/事实描述/标签/推断与判断/量化参数）作为 schema `extraction_prompt` 约束的**事实依据**——校验器测试断言"该字段集可被领域包描述"，但不把 golden 复制进工程包（spike 留作参考）。

**Sprint 0 Minor 沉淀**：
- "HTML 实体未解码" → 记为采集适配器层的设计契约（后续 collect Sprint 的 AC），本 Sprint 不实现；
- "重试计数口径混计" → 记为处理层可靠性契约（ADR-007 范畴），后续 process Sprint 的 AC。

---

## 6. Docker Compose 设计

`docker-compose.yml` 三服务（架构 §3）：

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16         # 含 pgvector 扩展
    environment: POSTGRES_DB/USER/PASSWORD
    volumes: pgdata
    # 中文分词扩展 zhparser/pg_jieba：pgvector 镜像不含，本 Sprint 暂不装
    # （全文检索是 M1 后续），smoke 仅验 vector 扩展可用
  minio:
    image: minio/minio
    command: server /data
  app:
    build: .
    depends_on: [postgres, minio]
    env_file: .env
    # dev 模式挂载 src/ 热重载；命令默认 sleep（本 Sprint 无长期运行进程）
```

**不在本 Sprint 做**：中文分词扩展安装（M1 全文检索阶段）、备份脚本（§8 部署视图，后续）、changedetection.io。

---

## 7. 验收标准（Gherkin）

```gherkin
AC1: Given 一个合规的 domain_packs/construction_machinery/pack.yaml
     When 执行 loader.load() 然后 validator.validate()
     Then ValidationResult.ok == True 且 issues 为空

AC2: Given 一个缺少 sources 字段的 pack.yaml
     When validate()
     Then ok == False 且某 issue.path == "sources" 且 message 含"必选"

AC3: Given sources[0].type 为非法值 "foo"
     When validate()
     Then 某 issue.path == "sources[0].type" 指出 enum 违规

AC4: Given docker-compose up
     When 跑 @pytest.mark.integration
     Then PG 可连 + CREATE EXTENSION vector 成功 + MinIO bucket 可建 + app 可 import pih

AC5: Given src/pih 任意子模块
     When 静态检查 import 图
     Then 无跨层反向依赖（collect ↛ consume 等）

AC6: Given pyproject.toml + uv.lock
     When 在干净容器内 uv sync
     Then 依赖可复现安装且 pytest 全绿
```

---

## 8. 任务分解（建议 6 个任务，串行/小并行）

1. **T1 仓库骨架**：pyproject.toml + uv.lock + src/pih 分层占位 + tests/ 骨架 + .gitignore 调整。
2. **T2 Docker Compose**：compose + Dockerfile + .env.example，本地 `up` 跑通三服务。
3. **T3 领域包 schema**：`domainpacks/schema.py`（JSON Schema）+ 单元自洽测试。
4. **T4 加载器 + 校验器**：`loader.py` / `validator.py` / `errors.py` + 单元测试（含坏包夹具）。
5. **T5 示例领域包 + 契约测试**：`domain_packs/construction_machinery/pack.yaml` + contract 测试对 schema。
6. **T6 集成 smoke + 收尾**：`test_compose_smoke.py` + README 工程化章节 + 回写 Backlog/架构状态位（如有）。

依赖：T1 → (T2 ‖ T3) → T4 → T5 → T6。T2 与 T3 可并行。

---

## 9. 回写与文档纪律

- Backlog §392"管理工具未定"：本 Sprint 维持未定，**不动**（用户已确认不选型）。
- 架构：若 compose 实现与 §3/§7 有偏差（如 pgvector 镜像选型、分词扩展推迟），在 §3 或 §9 实测节回写一行。
- 不 bump 文档版本号——本 Sprint 是工程实现，文档结构未变；仅必要时补实测行。

---

## 10. 风险

| 风险 | 缓解 |
|---|---|
| pgvector/pgvector:pg16 镜像与 zhparser 不兼容（中文分词后续装不上） | 本 Sprint 不装分词，仅验 vector；分词留 M1 全文检索 Sprint 单独验证镜像选型 |
| schema 过早固化 | 只约束必选字段 + enum，自由文本（prompt/template）只校验非空；第二领域接入（SPK-4）再迭代 |
| 工程化范围蔓延到业务模块 | §0 明确排除 + 任务分解只到脚手架与领域包机制 |
