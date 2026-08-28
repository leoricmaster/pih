# PIH · 产品情报中心

> 一条"采集 → 核实 → 结构化 → 存储 → 消费"的情报流水线，核心域模型行业无关，行业知识以领域包（Domain Pack，repo 内 YAML 配置）注入。

- 需求：`docs/Product Requirements.md`（V1.0）
- 架构：`docs/Architecture.md`（V0.10）
- Backlog：`docs/Backlog.md`（V1.4）
- ADR：`docs/adr/`

## 仓库布局

| 路径 | 说明 |
|---|---|
| `src/pih/` | 工程包，src-layout；分层对齐架构 §4 |
| `domain_packs/` | 领域包 YAML 事实源（架构 §6.3） |
| `tests/` | unit / contract / integration 三层 |
| `docker-compose.yml` | 本地环境：PG+pgvector / MinIO / app（架构 §3） |
| `spikes/` | Sprint 0 探索性代码，一次性学习品，不演进为工程代码 |
| `docs/` | 需求/架构/Backlog/ADR |

### 包分层（`src/pih/`）

对齐架构 §4 逻辑架构五层：

| 子包 | 层 | 状态 |
|---|---|---|
| `domainpacks/` | 横切·配置治理 | ✅ Sprint 1 已交付（加载器+校验器+schema） |
| `collect/` | 采集层 | ✅ Sprint 2 已交付（适配器+RawItem+快照+robots；CCMA/三一/cehome 三源）＋ probe/collect CLI 与 enabled 门控（S3.2.1 补交付） |
| `process/` | 处理层（LangGraph） | ✅ Sprint 4 已交付（LLM 客户端+粗筛→抽取→校验三节点图+ProcessRunner+process CLI；领域包 v0.2.0 枚举单一事实源） |
| `store/` | 存储层 | ✅ Sprint 3 已交付（PG 落库 + alembic 迁移 + IntelRepository + query CLI；source/intel_item 两表） |
| `consume/` | 消费层 | ✅ Sprint 5a 已交付（FastAPI Web + JSON API 同源 + Jinja2 列表/详情 + Bearer token 鉴权；ADR-006） |
| `core/` | 五元模型命名空间 | 占位，后续 Sprint |

## 工程化启动

```bash
# 依赖（需 uv；安装见 https://docs.astral.sh/uv/）
uv sync --extra dev

# 单元 + 契约测试（无需容器）
uv run pytest tests/unit tests/contract -v

# 集成测试（需 docker compose up）
cp .env.example .env          # 首次
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
uv run alembic upgrade head              # 首次：建表（store 层，Sprint 3）

uv run pih probe-source ccma             # 试抓取单源，产出成败报告（robots/列表/详情/快照）
uv run pih probe-source --all            # 领域包全部信源逐一试抓取
uv run pih probe-source khl --no-snapshot  # 不落快照的快速可达性验证
uv run pih collect ccma                  # 正式采集 + 默认落库（Sprint 3）
uv run pih collect ccma --no-ingest      # 不落库，仅 stdout 摘要（Sprint 2 行为）
uv run pih process --source-id=ccma --limit=5   # 批处理：粗筛→抽取→校验，写回结构化字段（Sprint 4）
uv run pih query --source-id=ccma --limit=10   # 查询库中按信源最近入库
uv run pih query --event-type=新品发布          # 按事件类型筛选（结构化，Sprint 4）
uv run pih query --subject=三一 --tag=电动化    # 按主体/标签筛选（JSONB containment）
uv run pih query --id=42                      # 单条详情（含 Admiralty 与结构化字段）
```

`collect` 输出末尾统计：`产出 N 条 RawItem → 入库 X 新增 / Y 幂等跳过 / Z 失败`
（content_sha1 唯一约束保障重复抓取不产生重复行，ADR-007）。

`process` 需在 `.env` 配置 `PIH_LLM_*` 四变量（OpenAI 兼容端点 + 大小模型名，
见 `.env.example`）；输出逐条明细 + 汇总行（`处理 N 条 → 抽取成功 X / 粗筛丢弃
Y / 待人工 Z / 失败 W`）+ token 用量。抽取成功条目带 Admiralty 码（来源可靠性
×信息可信度，如 B2），判无关条目行级标记 `filtered_out` 保留可审计，校验失败
降级 `needs_manual` 不丢弃（架构 §8）。

退出码：0 成功 / 1 抓取失败或门控拒绝 / 2 用法或环境错误。

## 消费层 Web/API（Sprint 5a，ADR-006）

FastAPI 单 app 双出口——Web 列表/详情（Jinja2 服务端模板）与 JSON API 共用
`QueryService`，同条件返回同集合同序。Web 内网默认开放；API 端点要求 Bearer token。

```bash
# 1. 起依赖 + 迁移 + 造数据
docker compose up -d postgres
uv run alembic upgrade head
uv run pih collect sany_news --max-items 5    # 攒几条真实数据
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

事件核实状态字段（列表列与详情区）当前占位「待事件模型上线后自动激活」——
event 表与核实状态机属下一 Sprint，上线后查询服务自动填实，无需改 consume 层。
排序简版 `admiralty_code ASC NULLS LAST, fetched_at DESC`，完整 score
（W_c × map(admiralty) × decay）待事件+时效 Sprint。

## 领域包机制

领域包是行业知识的唯一载体（ADR-001 / 架构 §6.3）：信源清单、监控关键词、
竞品主体、标签树、报告模板、抽取提示词，以 repo 内 YAML 维护，带 schema 校验。

```bash
# 加载并校验一个领域包
uv run python -c "from pih.domainpacks.loader import load; print(load('domain_packs/construction_machinery/pack.yaml')['meta'])"
```

缺必选字段或 enum 违规会被拒绝并指出位置（见 `tests/unit/test_validator.py`）。
新增领域 = 新增 `domain_packs/<domain>/pack.yaml`，核心代码零变更。
