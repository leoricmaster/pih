# Sprint 3：store 层第一期 —— 设计规格

> 状态：草案（待评审）
> 范围：情报库 schema 落地（PG + alembic）+ `IntelRepository` 最简落库与查询 + CLI 串联 + 端到端集成测试。让 collect 产出的 RawItem 真正落库可查，端到端验收闭环（"一条命令 → 库里有数据 → 能查出来"）。
> 依据：架构 §4（STORE 层模块职责）、§5.1（主流程入库段）、§5.3（快照与可回溯）、§6.1（核实状态机）、§7（数据架构）、ADR-003（事件与情报分离）、ADR-007（入库幂等键 = 内容指纹）；Backlog S4.1.1 AC1（无快照不入库）、S4.4 流水线可靠性。

---

## 0. 背景与不做什么

**Sprint 2 已交付**：collect 层完整（适配器/RawItem/解码链/robots/httpclient/snapshot）+ probe/collect CLI + enabled 门控。三源（CCMA/三一/cehome）实抓 6/6 通过，RawItem 已能产出并落 MinIO 快照。但 RawItem 停在 stdout 与内存，**未落库，下游无法消费**——这是端到端验收的最大瓶颈。

**本 Sprint 不做**（明确排除）：

- **不做 process 层**（结构化抽取 / 预评级 / 事件聚类）——SPK-3 已验证 LangGraph E2E，工程化进 `src/pih/process/` 工作量不小，且需要 intel_item schema 先就位才有落点；本 Sprint 让 schema 落地，process 层下一 Sprint。
- **不做调度器**——S4.1.1 的 AC2/AC3（去重、重试告警）依赖持续调度，留调度器 Sprint。
- **不做事件表 / verification_log / 核实状态机流转**——这些绑死 process 层（事件聚类、双源升级判定），本 Sprint 仅在 intel_item 表预留 `event_id` 可空外键，状态机模块留下一 Sprint。
- **不做消费层**（Web/JSON API）——ADR-006 同源服务是 M1 末段交付，本 Sprint 只交付 CLI 查询。
- **不做向量与全文索引**——pgvector 扩展已验可用（Sprint 1 smoke），但 embedding 写入与 BM25 索引依赖 process 层产出的结构化文本，留 process Sprint。
- **不做竞品资产库**（competitor_profile / feature_matrix / param_matrix）——表结构设计为后续方向。
- **不做 inbox / dead_letter 表**——Sprint 2 已把快照落 MinIO 满足"原始内容先落盘"最低要求；inbox 表持久化随调度器 Sprint 落地（届时才有持续投递场景）。

> **Backlog 对齐**：本 Sprint 是"技术型 Story"——Backlog V1.1 无专门 store 落库卡，新增 **S4.5「情报库落库与基础检索」**（见 §9 回写）。原 S4.1.1 AC1「无快照不入库」由 Sprint 2 快照机制 + 本 Sprint 入库门控共同满足。

---

## 1. 已锁定决策（用户确认）

| 决策 | 选择 | 含义 |
|---|---|---|
| 主存储 | PostgreSQL + pgvector（Sprint 1 已起容器） | 沿用现有 docker compose，不引入新组件 |
| schema 切片 | **最小切片**：只建 `intel_item` + `source` 两表，event/verification_log 留 process Sprint | schema 跟着已实现的能力走，不预先承载没填的字段（避免抽象债务） |
| 入库幂等键 | `content_sha1` 唯一约束 + `ON CONFLICT DO NOTHING` | ADR-007 落实；重复抓取同条不产生重复行 |

---

## 2. 待定决策（本规格需拍板，给出推荐）

| # | 议题 | 推荐 | 理由 |
|---|---|---|---|
| D1 | DB 驱动 | **psycopg[binary] + 连接池** | psycopg3 同步、轻量、与 PG 原生类型对齐好；不引入 SQLAlchemy ORM（pydantic + SQLAlchemy 绑定模型层过早，查询足够简单用 SQL）；连接池用 `psycopg_pool.ConnectionPool` |
| D2 | 迁移工具 | **alembic**（自动配置） | 第一张业务表即立迁移工具链（Sprint 1 占位说明已约定）；alembic 是 PG 生态最成熟，配 SQLAlchemy MetaData 但只用 DDL 不用 ORM |
| D3 | schema 字段范围 | 见 §3.1，intel_item 含 RawItem 全字段 + `event_id` 可空 + `created_at`；不预置主体/事件类型/标签/置信度字段（process 层上来再 ALTER） | 与 §0「不做 process」对齐；预留字段会有空值噪声且字段语义在 process 设计时才能定型 |
| D4 | CLI 串联方式 | **`pih collect` 默认落库** + 新增 `pih query` 子命令查库 | `collect` 产出 RawItem 直接 ingest，避免新增中间命令；`query --source-id=X --limit=N` 查最近入库；保留 `--no-ingest` 旗标回退到 Sprint 2 行为（仅 stdout） |
| D5 | 查询接口范围 | `list_by_source(source_id, limit, before?)` + `get(id)` 两个方法 | 端到端验收所需最小集；多条件组合筛选（S1.1.1）属消费层 Sprint，本 Sprint 不做 |
| D6 | source 表来源 | **从领域包 YAML 同步**：collect 启动时 `sync_sources(pack)` upsert 进 source 表 | source 表是领域包 sources 的镜像（含 id/name/level/reliability/enabled）；事实源仍是 YAML，表用于查询联结 |
| D7 | 测试 DB | **复用 docker compose postgres** + alembic upgrade head 建表 | 不引入 testcontainers（compose 已在跑，复用降低工具复杂度）；集成测试前置 `alembic upgrade head` + 测试结束不回滚（保留数据便于排查，下次跑前 `alembic downgrade base`） |
| D8 | 容错策略 | 入库失败：条目降级 stdout 报错，不阻塞 collect 其他条目；不引入死信表 | 死信表是 ADR-007 终态设施但绑死调度器场景（重试耗尽）；本 Sprint 单次 collect 失败由用户重跑解决，简化 |

---

## 3. 核心设计

### 3.1 schema 切片（最小两张表）

```sql
-- migrations/versions/0001_initial.py

CREATE TABLE source (
    id           TEXT PRIMARY KEY,          -- 领域包 sources[].id
    name         TEXT NOT NULL,
    domain_id    TEXT NOT NULL,             -- 领域包 meta.domain_id
    url          TEXT NOT NULL,
    list_url     TEXT NOT NULL,
    level        TEXT NOT NULL,             -- L1–L4
    reliability  TEXT NOT NULL,             -- A–F
    fetch_frequency TEXT,                   -- 可选，调度器 Sprint 消费
    enabled      BOOLEAN NOT NULL DEFAULT FALSE,
    synced_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE intel_item (
    id            BIGSERIAL PRIMARY KEY,
    source_id     TEXT NOT NULL REFERENCES source(id),
    url           TEXT NOT NULL,
    title         TEXT NOT NULL,
    list_url      TEXT NOT NULL,
    fetched_at    TIMESTAMPTZ NOT NULL,
    http_status   INTEGER NOT NULL,
    content_type  TEXT,
    encoding      TEXT,
    snapshot_id   TEXT NOT NULL,            -- MinIO 快照 ID = content_sha1
    content_sha1  TEXT NOT NULL UNIQUE,     -- 幂等键（ADR-007）
    raw_html      TEXT NOT NULL,            -- 解码后正文（检索与回显用）
    event_id      BIGINT,                   -- 可空，process Sprint 联 event 表
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_intel_item_source_fetched ON intel_item(source_id, fetched_at DESC);
CREATE INDEX idx_intel_item_created ON intel_item(created_at DESC);
```

**不预置的字段**（process 层上来再 ALTER ADD COLUMN）：
- `subject`（主体）、`event_type`（事件类型）、`facts`（事实描述）、`inferences`（推断）、`tags`（标签）—— 结构化抽取器产出；
- `admiralty_code`（B2 等）—— 预评级产出；
- `expires_at`（有效期）—— 时效管理器产出；
- `event_id` 先建字段但不建 event 表（FK 待 process Sprint 补）。

### 3.2 store 模块结构

```
src/pih/store/
├── __init__.py
├── db.py              # ConnectionPool 单例 + .env 读取
├── repository.py      # IntelRepository: save / list_by_source / get
├── source_sync.py     # sync_sources(pack): 领域包 sources upsert 进 source 表
└── errors.py          # IntegrityError 包装（幂等冲突不算失败）
```

### 3.3 IntelRepository 接口（`repository.py`）

```python
class IntelRepository:
    def __init__(self, pool: ConnectionPool): ...

    def save(self, item: RawItem) -> SaveOutcome:
        """单条入库。content_sha1 冲突 → SKIPPED（幂等成功）；其他异常 → FAILED。

        Returns:
            SAVED: 新入库，id 返回
            SKIPPED: 幂等冲突，已存在
            FAILED: 异常，附 reason
        """

    def save_batch(self, items: list[RawItem]) -> list[SaveOutcome]:
        """批量入库，逐条 save（不批量 ON CONFLICT，便于单条失败定位）。"""

    def list_by_source(self, source_id: str, limit: int = 50, before: datetime | None = None) -> list[IntelRecord]:
        """按信源列出最近入库的情报（fetched_at DESC）。"""

    def get(self, intel_id: int) -> IntelRecord | None: ...
```

`IntelRecord` 是从 DB 读出的轻量 dataclass（与 RawItem 字段同 + `id` + `created_at`），不引入 pydantic。

### 3.4 source 同步（`source_sync.py`，D6）

```python
def sync_sources(pack: dict, pool: ConnectionPool) -> SyncStats:
    """将领域包 sources[] upsert 进 source 表（ON CONFLICT DO UPDATE）。

    事实源仍是 YAML；表用于查询联结与未来信源画像。
    不删除表里多余行（避免误删手填数据），仅 upsert。
    """
```

### 3.5 CLI 串联（`cli.py` 扩展）

```bash
# 修改：collect 默认落库
uv run pih collect ccma                # 抓取 + 落库 + stdout 摘要
uv run pih collect ccma --no-ingest    # Sprint 2 行为（仅 stdout，不落库）

# 新增：query 子命令
uv run pih query --source-id=ccma --limit=10
uv run pih query --source-id=ccma --before=2026-08-25
uv run pih query --id=42               # 单条详情
```

`collect` 输出末尾追加落库统计：`产出 5 条 RawItem → 入库 3 新增 / 2 幂等跳过 / 0 失败`。

退出码沿用：0 成功 / 1 抓取或落库失败 / 2 用法错误。

### 3.6 环境与依赖

`pyproject.toml` 增：
- `psycopg[binary,pool]>=3.2`
- `alembic>=1.13`

`.env.example` 增（已存在 PG 占位，补关键字段）：
```
PG_DSN=postgresql://pih:pih12345@localhost:5432/pih
```

---

## 4. 目录结构（落地产物）

```
src/pih/store/
├── __init__.py
├── db.py
├── repository.py
├── source_sync.py
└── errors.py

migrations/
├── README.md                # 改：去掉"占位"说明
├── env.py                   # alembic 配置（读 PG_DSN）
├── versions/
│   └── 0001_initial.py      # source + intel_item 两表 + 索引
└── script.py.mako           # alembic 模板

src/pih/cli.py               # 改：collect 加落库逻辑 + --no-ingest；新增 query 子命令
src/pih/collect/run.py       # 改：collect_source 接受可选 repository 参数，落库由调用方注入

tests/
├── unit/store/
│   ├── test_repository.py        # 用 mock pool 验 SQL + 幂等冲突分支
│   └── test_source_sync.py       # 验 upsert SQL 生成
├── contract/
│   └── test_migrations_apply.py  # alembic upgrade head / downgrade base 干净跑通
└── integration/
    └── test_end_to_end.py        # collect ccma → 库里有 → query 出来（AC 端到端）
```

---

## 5. 测试策略

| 层 | 内容 | 依赖 |
|---|---|---|
| unit | repository save/list/get 的 SQL 与分支（mock pool，验 SQL 与参数；幂等 SKIPPED 分支）；source_sync 的 upsert SQL | 无 DB |
| contract | alembic upgrade head → 表存在 → downgrade base → 表消失；领域包 sources 字段对齐 source 表列 | docker compose postgres |
| integration | 端到端：`pih collect ccma --max-items=2` → `pih query --source-id=ccma --limit=10` → 断言条目数 ≥1，title/url/snapshot_id 字段非空；幂等：二次 collect 同源，新增=0，跳过≥2 | docker compose 全栈 + 外网 |

集成测试密闭性：每个测试前置 `alembic downgrade base && alembic upgrade head` 保证干净库；不依赖代理（HttpClient 默认 `trust_env=False`，与 Sprint 2 一致）。

---

## 6. 验收标准（Gherkin）

```gherkin
AC1: Given docker compose up + 外网可达
     When 运行 pih collect ccma --max-items=2
     Then RawItem 抓取成功且落库
     And stdout 显示「入库 N 新增 / 0 幂等跳过 / 0 失败」
     And source 表含 ccma 行（enabled=true, level=L2）

AC2: Given AC1 已执行（库中已有 2 条 ccma 情报）
     When 再次运行 pih collect ccma --max-items=2
     Then 入库 0 新增 / 2 幂等跳过 / 0 失败（content_sha1 唯一约束生效）
     And intel_item 表行数不变

AC3: Given 库中有 ccma 情报 ≥1 条
     When 运行 pih query --source-id=ccma --limit=10
     Then 输出列表含 title / url / snapshot_id / fetched_at
     And 按 fetched_at DESC 排序

AC4: Given 一条情报的 content_sha1 与已存行冲突
     When IntelRepository.save 该条
     Then 返回 SKIPPED，不抛异常，不阻塞同批其他条目

AC5: Given 领域包 sources 含 ccma/sany/cehome（enabled 各异）
     When sync_sources(pack) 执行
     Then source 表含三行，enabled 与 YAML 一致
     And 重复执行不产生重复行（upsert 生效）

AC6: Given alembic upgrade head
     When 检查 schema
     Then intel_item.content_sha1 有 UNIQUE 约束
     And intel_item.source_id 有 FK 指向 source.id
     And event_id 字段存在但无 FK（占位）

AC7: Given alembic downgrade base
     Then intel_item 与 source 表均消失
```

---

## 7. 任务分解（建议 6 任务）

1. **T1 依赖 + alembic 脚手架**：pyproject 加 psycopg/alembic；`migrations/env.py` + `script.py.mako`；契约测试 `alembic upgrade/downgrade` 干净跑通（空迁移）。
2. **T2 第一张迁移 0001_initial**：source + intel_item 两表 + 索引；契约测试验表结构与约束。
3. **T3 store/db.py 连接池 + source_sync**：ConnectionPool 单例从 .env 读 PG_DSN；sync_sources upsert；单元测试（mock pool 验 SQL）。
4. **T4 IntelRepository save/save_batch/list_by_source/get**：含幂等分支与错误包装；单元测试（mock pool）。
5. **T5 CLI 串联**：collect 加落库逻辑 + `--no-ingest` 旗标；新增 `pih query` 子命令；输出统计行。
6. **T6 端到端集成测试 + Backlog 回写**：`test_end_to_end.py`（AC1–AC5）；Backlog 新增 S4.5 卡 + 状态位；README 补 store 层状态与 query 用法；Architecture §7 数据架构回写「source/intel_item 已落地，event/verification_log 待 process Sprint」。

依赖：T1 → T2 → (T3‖T4) → T5 → T6。T3/T4 可并行。

---

## 8. 回写与文档纪律

- **Backlog**（必须）：新增 **S4.5「情报库落库与基础检索」**——技术型 Story，故事句「作为消费者，自动采集的 RawItem 落入情报库可查，以便后续处理与消费」+ AC 见本规格 §6；状态本 Sprint 末置已交付。原 S4.1.1 AC1「无快照不入库」备注「由 Sprint 2 快照机制 + Sprint 3 入库门控共同满足」。
- **架构**：§7 数据架构 ER 图补「source/intel_item 已落地（Sprint 3）；event/verification_log/competitor_profile 待 process Sprint」；§4 STORE 层模块表状态位更新。
- **README**：包分层表 store 行从「占位」改「✅ Sprint 3 已交付（PG 落库 + 基础查询）」；运营者 CLI 段补 `pih query` 用法与 `--no-ingest` 旗标。
- **不回写**：spike 报告（throwaway）。

---

## 9. 风险

| 风险 | 缓解 |
|---|---|
| psycopg 连接池在 CLI 单次运行场景过度设计 | 用最小 pool（min_size=1, max_size=3）；CLI 退出时显式 close；后续调度器 Sprint 再调优 |
| alembic 迁移与 PG 中文全文/pgvector 扩展未来冲突 | 0001 不涉及扩展；后续加 zhparser/pgvector 扩展迁移单独版本号，不与业务表混 |
| raw_html 入库撑大主表（单条 50–500KB） | M1 规模 < 10 万条预估主表 < 5GB，可接受；如未来膨胀用 TOAST 自动压缩 + 译文表分离 hot/cold，本 Sprint 不做 |
| 端到端集成测试 flaky（站点变更/网络） | 沿用 Sprint 2 策略：只抓 1–2 条、断言结构不断言具体文本；失败标 xfail |
| event_id 占位字段未来 FK 补加迁移成本 | ALTER ADD CONSTRAINT 在 PG 是元数据操作（小表秒级），可接受 |
