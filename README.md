# PIH · 产品情报中心

> 一条"采集 → 核实 → 结构化 → 存储 → 消费"的情报流水线，核心域模型行业无关，行业知识以领域包（Domain Pack，repo 内 YAML 配置）注入。

- 需求/任务管理：**Backlog.md 工具**（`backlog/` 目录，CLI `backlog`）——需求树事实源
  - 立项文档：`backlog/docs/doc-001` · 架构：`doc-002` · 非功能需求：`doc-003`
  - ADR：`backlog/decisions/decision-001`…`007`
  - 可点击原型：`docs/prototype.html`（IA 验收参照，非需求事实源）
- **文档分层规则**：工具管理的文档（立项 / 架构 / NFR / ADR）→ `backlog/docs/`、`backlog/decisions/`；独立产物（HTML 原型等）→ `docs/`

## 仓库布局

| 路径 | 说明 |
|---|---|
| `src/pih/` | 工程包，src-layout；分层对齐架构 §4 |
| `domain_packs/` | 领域包 YAML 事实源（架构 §6.3） |
| `tests/` | unit / contract / integration 三层 |
| `docker-compose.yml` | 本地环境：PG+pgvector / MinIO / app / web（架构 §3） |
| `docs/` | 独立产物（HTML 原型）；文档分层规则见上 |
| `backlog/` | Backlog.md 工具：tasks（EPIC-FT-US 三级）/decisions/docs/drafts（需求事实源）；milestone 待规划阶段后补 |

### 包分层（`src/pih/`）

对齐架构 §4 逻辑架构五层：

| 子包 | 层 | 状态 |
|---|---|---|
| `domainpacks/` | 横切·配置治理 | ✅ 加载器+校验器+schema |
| `collect/` | 采集层 | ✅ 适配器+RawItem+快照+robots（CCMA/三一/cehome 三源）＋ probe/collect CLI 与 enabled 门控 |
| `process/` | 处理层（LangGraph） | ✅ LLM 客户端+粗筛→抽取→校验三节点图+ProcessRunner+process CLI（领域包 v0.2.0 枚举单一事实源）；事件聚类（EventService） |
| `store/` | 存储层 | ✅ PG 落库 + alembic 单基线迁移 + IntelRepository + query CLI（source/event/intel_item/verification_log/feedback 五表）；EventRepository + FeedbackRepository |
| `consume/` | 消费层 | ✅ FastAPI Web + JSON API 同源 + Jinja2 列表/详情 + Bearer token 鉴权（ADR-006）；process_status 筛选 + 反馈闭环（表单/聚合视图/JSONL 导出）；事件核实状态字段与筛选 |

## 工程化启动

环境配置分两层（env 漂移治理）：

- **`.env.defaults`（入库）**：非秘密默认值，clone 即得，开箱可跑；
- **`.env`（gitignore）**：只写秘密与本机覆盖（`PIH_API_TOKEN`、`PIH_LLM_*`），不建也行；
- 加载优先级：真实环境变量 > `.env` > `.env.defaults`（`pih.envs.load_env`）；
- `pytest` 启动时自动对账：代码引用但两层 env 均缺的键直接 fail，
  `.env` 里无人引用的死键（改名遗留）打警告。

```bash
# 依赖（需 uv；安装见 https://docs.astral.sh/uv/）
uv sync --extra dev

# 单元测试（无需容器，无需 .env）
uv run pytest tests/unit -v

# 契约测试（其中 test_migrations_apply 需 postgres；纯 YAML/模板部分同上）
uv run pytest tests/contract -v

# 集成测试（需 docker compose up）
docker compose up -d
uv run pytest tests/integration -v

# Lint
uv run ruff check src/ tests/
```

## 运营者 CLI

信源启用走 enabled 门控：新增信源在领域包 YAML 中 `enabled: false` → 试抓取通过后
人工置 `true`（工具不改 YAML，人是最终环节）；`collect` 仅运行已启用源。

```bash
docker compose up -d                     # 快照存档需 MinIO，落库需 postgres
uv run alembic upgrade head              # 首次：建表（store 层）

uv run pih probe-source ccma             # 试抓取单源，产出成败报告（robots/列表/详情/快照）
uv run pih probe-source --all            # 领域包全部信源逐一试抓取
uv run pih probe-source khl --no-snapshot  # 不落快照的快速可达性验证
uv run pih collect ccma                  # 正式采集 + 默认落库
uv run pih collect ccma --no-ingest      # 不落库，仅 stdout 摘要
uv run pih process --source-id=ccma --limit=5   # 批处理：粗筛→抽取→校验，写回结构化字段
uv run pih query --source-id=ccma --limit=10   # 查询库中按信源最近入库
uv run pih query --event-type=新品发布          # 按事件类型筛选（结构化）
uv run pih query --subject=三一 --tag=电动化    # 按主体/标签筛选（JSONB containment）
uv run pih query --id=42                      # 单条详情（含 Admiralty 与结构化字段）

# 事件聚类与人工核实
uv run pih verify list                        # 待人工核实事件队列（双独立信源命中后进队）
uv run pih verify confirm 42                  # 跃迁 single_source → confirmed（人工终态）
uv run pih verify refute 42 --reason="主体误读"  # 跃迁 → refuted（必填理由）
uv run pih cluster --backfill --limit=200     # 对存量 extracted 未挂事件条目聚类回填
```

`collect` 输出末尾统计：`产出 N 条 RawItem → 入库 X 新增 / Y 幂等跳过 / Z 失败`
（content_sha1 唯一约束保障重复抓取不产生重复行，ADR-007）。

`process` 需在 `.env` 配置 `PIH_LLM_*` 四变量（OpenAI 兼容端点 + 大小模型名，
模板见入库的 `.env.defaults` 注释区）；输出逐条明细 + 汇总行（`处理 N 条 → 抽取成功 X / 粗筛丢弃
Y / 待人工 Z / 失败 W`）+ token 用量。抽取成功条目带 Admiralty 码（来源可靠性
×信息可信度，如 B2），判无关条目行级标记 `filtered_out` 保留可审计，校验失败
降级 `needs_manual` 不丢弃（架构 §8）。

退出码：0 成功 / 1 抓取失败或门控拒绝 / 2 用法或环境错误。

## 消费层 Web/API（ADR-006）

FastAPI 单 app 双出口——Web 列表/详情（Jinja2 服务端模板）与 JSON API 共用
`QueryService`，同条件返回同集合同序。Web 内网默认开放；API 端点要求 Bearer token。

```bash
# 1. 起依赖 + 迁移 + 造数据
docker compose up -d postgres
uv run alembic upgrade head
uv run pih collect sany --max-items 5          # 攒几条真实数据
uv run pih process                              # 抽取结构化字段（需 .env 配 PIH_LLM_*）

# 2. 配置 API token
export PIH_API_TOKEN=dev-token                  # 或写进 .env

# 3a. 容器启动（生产形态）
docker compose up -d web
# 3b. 本地开发启动（热重载）
uv run uvicorn pih.consume.web:app --reload --port 8000

# 4. 浏览器访问 http://127.0.0.1:8000 —— 列表页 + 筛选 form + 下一页游标
#    点标题进入 /intel/{id} 详情页（事实/推断分区 + 快照入口占位）

# 5. 调 JSON API（Agent 消费者）
curl -H "Authorization: Bearer dev-token" \
  "http://127.0.0.1:8000/api/intel/list?subject=三一&event_type=新品发布&limit=10"
curl -H "Authorization: Bearer dev-token" \
  http://127.0.0.1:8000/api/intel/1
curl http://127.0.0.1:8000/api/intel/list       # 无 token → 401
curl http://127.0.0.1:8000/api/healthz          # 健康检查（不鉴权）
```

事件核实状态：列表「所属事件核实状态」列与详情页事件区显示
挂载事件的状态中文标签（待核实/单源确认/多源确认/已证伪）+ 跃迁历史时间线；
未挂事件条目显示 —。可按 `?event_status=` 筛选（Web/API 同源）。
排序 `W_c(event.status) × map(admiralty) DESC, fetched_at DESC`（架构 §6.2 简化，
权重来自领域包 ranking 节，CASE WHEN 注入 SQL；decay 待时效管理器）。

## 质量闭环

后验质量门 + 消费页人类反馈，拦住低质条目增量、积累错误样本驱动 prompt 迭代：

- **后验质量门（TASK-1.02.01 AC3）**：`pih process` 时主体抽成占位值（未知/无/不详/unknown）
  → `process_status=needs_manual`（结构化字段保留供复核），不再混入 extracted；
- **复核队列**：列表页/API 按 `?process_status=needs_manual` 筛出待复核条目
  （Web 下拉或 API 参数，同源）；
- **反馈（TASK-4.03.01）**：详情页反馈区四动作——主体错了（datalist 主体清单可选）、
  事件类型错、事实不准（标注到第几条事实）、不该入库；提交即写 `feedback` 表；
- **聚合视图**：`/feedback` 按信源×类型计数，主体错误率 >30% 高亮提示迭代；
  `/feedback/export` 导出 JSONL 作 prompt 迭代 few-shot 素材。

```bash
curl "http://127.0.0.1:8000/api/intel/list?process_status=needs_manual" \
  -H "Authorization: Bearer dev-token"   # API 按状态筛
curl http://127.0.0.1:8000/feedback/export | head -1   # 反馈明细 JSONL
```

## 事件聚类与核实状态机

extracted 条目自动按聚类规则挂事件（架构 §6.1）：主体归一化（领域包别名 →
display_name）+ event_type 精确匹配 + ±7 天时间窗。第二独立信源命中 →
pending → single_source 自动跃迁并进人工队列；多源确认/证伪为人工终态
（`pih verify confirm/refute`，全程写 verification_log 留痕，ADR-002）。

## 领域包机制

领域包是行业知识的唯一载体（ADR-001 / 架构 §6.3）：信源清单、监控关键词、
竞品主体、标签树、报告模板、抽取提示词，以 repo 内 YAML 维护，带 schema 校验。

```bash
# 加载并校验一个领域包
uv run python -c "from pih.domainpacks.loader import load; print(load('domain_packs/construction_machinery/pack.yaml')['meta'])"
```

缺必选字段或 enum 违规会被拒绝并指出位置（见 `tests/unit/test_validator.py`）。
新增领域 = 新增 `domain_packs/<domain>/pack.yaml`，核心代码零变更。
