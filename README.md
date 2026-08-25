# PIH · 产品情报中心

> 一条"采集 → 核实 → 结构化 → 存储 → 消费"的情报流水线，核心域模型行业无关，行业知识以领域包（Domain Pack，repo 内 YAML 配置）注入。

- 需求：`docs/Product Requirements.md`（V1.0）
- 架构：`docs/Architecture.md`（V0.9）
- Backlog：`docs/Backlog.md`（V0.9）
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
| `collect/` | 采集层 | ✅ Sprint 2 已交付（适配器+RawItem+快照+robots；CCMA/三一/cehome 三源） |
| `process/` | 处理层（LangGraph） | 占位，后续 Sprint |
| `store/` | 存储层 | 占位，后续 Sprint |
| `consume/` | 消费层 | 占位，后续 Sprint |
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

## 领域包机制

领域包是行业知识的唯一载体（ADR-001 / 架构 §6.3）：信源清单、监控关键词、
竞品主体、标签树、报告模板、抽取提示词，以 repo 内 YAML 维护，带 schema 校验。

```bash
# 加载并校验一个领域包
uv run python -c "from pih.domainpacks.loader import load; print(load('domain_packs/construction_machinery/pack.yaml')['meta'])"
```

缺必选字段或 enum 违规会被拒绝并指出位置（见 `tests/unit/test_validator.py`）。
新增领域 = 新增 `domain_packs/<domain>/pack.yaml`，核心代码零变更。
