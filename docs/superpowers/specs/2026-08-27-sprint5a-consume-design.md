# Sprint 5a：consume 层第一期 —— 设计规格

> 状态：草案（待评审）
> 范围：FastAPI 同源 Web+JSON API 落地（QueryService 共用）+ Jinja2 列表/详情模板 + Bearer token 鉴权 + docker-compose web service + 北极星指标日志。让用户能打开浏览器看情报、Agent 能调 API 拿 JSON，第一次端到端「摸到产品」。
> 依据：架构 §4（CONSUME 层）、§5.1（主流程消费段）、§5.3（快照与原文双入口）、§6.2（Admiralty 排序简版）、ADR-006（Web 与 API 同源）；Backlog S1.1.1/S1.1.2/S1.1.4。

---

## 0. 背景与不做什么

**Sprint 4 已交付**：intel_item 11 结构化列 + 迁移 0002 + `IntelRepository.list_by_filter` + `pih query` 结构化筛选 CLI 子集。情报库可按主体/事件类型/标签/信源筛选，但出口仅 CLI——产品端用户「摸不到」。本 Sprint 是用户连续 4 个 Sprint 后第一次接触产品界面。

**本 Sprint 不做**（明确排除）：

- **不做事件聚类 / event 表 / verification_log / 核实状态机**——绑死「双独立信源判定 + 人工终态」语义；列表「所属事件核实状态」列与详情「事件状态 + 跃迁历史」区显示占位「待事件模型上线后自动激活」，event 表上线后查询服务自动填实（不另起 Sprint 改动查询层）。
- **不做时效管理器**（expires_at / 已过期降权）——S1.1.1 AC3「已过期标识 + 排序靠后」整条不交付，待时效 Sprint。
- **不做完整 score 排序**——架构 §6.2 完整 score = W_c × map(admiralty) × decay(采集时间)；W_c 依赖事件状态、decay 依赖 expires_at，均不可用。本 Sprint 简版：admiralty_code ASC（A 最优）+ fetched_at DESC 兜底，完整 score 留事件+时效 Sprint。
- **不做 Web 鉴权**——内网部署默认开放；仅 JSON API 要求 Bearer token。
- **不做 RAG 问答 / 报告 / 推送 / 核实操作页 / 人工录入网关**——M2 或后续方向。
- **不做调度器集成 / 向量与全文索引**——web service 独立进程；混合检索留 RAG Sprint。
- **不做分页「上一页」**——仅「下一页」游标（`?before=<last_fetched_at>`），单向向前，符合 fetched_at DESC 自然顺序。

---

## 1. 已锁定决策（用户确认，2026-08-27）

| 决策 | 选择 | 含义 |
|---|---|---|
| 部署形态 | docker-compose 加独立 web service（build 同 Dockerfile，command uvicorn）+ 本地 `uv run uvicorn pih.consume.web:app` 可跑 | 与 app 容器共用镜像，仅 command 不同；本地开发零额外配置 |
| 鉴权 | 环境变量 `PIH_API_TOKEN`；API 端点要求 `Authorization: Bearer <token>`；Web 页面内网默认开放 | 1 人运维不引入 OAuth/SSO；token 静态，轮换手动改 env 重启 |
| 分页 | 游标 `?before=<iso8601>`，复用 `IntelRepository.list_by_source` 的 before 与 CLI `--before` 逻辑 | offset 分页在 fetched_at 排序下漂移；游标天然稳定 |
| 模板引擎 | Jinja2（starlette.templates 官方支持） | FastAPI 一等公民，不引入前端构建链 |
| 查询服务同源 | 单一 `QueryService`，Web 与 JSON API 共用过滤/排序/引用拼装 | ADR-006 落实；北极星指标按出口分别计数 |

---

## 2. 待定决策（本规格需拍板，给出推荐）

| # | 议题 | 推荐 | 理由 |
|---|---|---|---|
| D1 | 模块结构 | `consume/{query_service.py, web.py, api.py, auth.py, metrics.py, templates/, static/}`；api.py 作为 router 被 web.py include | 单 app 双出口；router 拆分便于单测分别注入；templates 与代码同包便于打包 |
| D2 | Admiralty URL 参数 | `?admiralty=B2` 精确匹配（与 `--event-type` 同口径） | 双维 `?reliability=B&credibility=2` 暴露内部维度；范围 `?min_admiralty=` 与排序方向耦合；精确匹配最简且对齐 AC「置信度筛选」 |
| D3 | 时间范围 | `?since=<iso>&until=<iso>` 双边界 + 保留 `?before=<iso>` 游标 | AC1「近90天」需 since 边界；before 仅作分页游标；三者可共存，since/until 走 WHERE、before 走游标 |
| D4 | 默认排序二级键 | `admiralty_code ASC NULLS LAST, fetched_at DESC, id DESC` | admiralty 同码时 fetched_at DESC 兜底；id DESC 保证同 fetched_at 确定序（避免测试 flaky） |
| D5 | 鉴权实现 | FastAPI Dependency `verify_api_token`：Header `Authorization: Bearer <t>` 与 `os.environ["PIH_API_TOKEN"]` 用 `hmac.compare_digest` 比较；env 缺失 → 503；缺失/不匹配 header → 401 | 沿用 FastAPI HTTPException 默认形态；常量时间比较防时序攻击；env 缺失与凭据错区分便于 Agent 排错 |
| D6 | Web 分页 UI | 列表底部「下一页」链接携带 `?before=<last.fetched_at>` + 现有筛选参数透传 | 单向向前；无结果或结果数 < limit 时不渲染 |
| D7 | 北极星指标计数 | 结构化日志 `{"event":"query","channel":"web\|api","filters":{...},"count":N,"ts":...}` 一行 JSON；不建 DB 表 | 1 人运维不添表；日志可被 grep/loki 消费；DB 表留调度器 Sprint 引入可观测性时再补 |
| D8 | 健康检查 | `GET /healthz` 不鉴权，返回 `{"status":"ok","pg":bool,"minio":bool}` | docker-compose healthcheck 与反向代理需要；不暴露敏感信息 |
| D9 | 错误响应形态 | 沿用 FastAPI 默认 `{"detail":"..."}`；不自定义 envelope | 减少契约面；Agent 按 HTTP 状态码判断；后续如需 envelope 再加 middleware |
| D10 | 依赖版本 | `fastapi>=0.115`、`uvicorn[standard]>=0.30`、`jinja2>=3.1`；`httpx` 已在 deps（测试用 AsyncClient） | FastAPI 0.115+ 支持 Pydantic v2 与 lifespan |

---

## 3. 核心设计

### 3.1 模块结构

```
src/pih/consume/
├── __init__.py          # 改：去占位
├── query_service.py     # QueryService：IntelFilters → list[IntelRecord] / get(id)
├── web.py               # FastAPI app：lifespan 起 pool、挂 templates、include api router
├── api.py               # JSON API router（/api/intel/list、/api/intel/{id}、/healthz）
├── auth.py              # verify_api_token 依赖
├── metrics.py           # log_query(channel, filters, count) 结构化日志
├── templates/{base,list,detail}.html
└── static/style.css     # 极简（~50 行）
```

### 3.2 查询服务（query_service.py）

`IntelFilters` dataclass 字段：subject、event_type、tag、admiralty（精确）、source_id、since（fetched_at >=）、until（fetched_at <=）、before（游标：fetched_at <）、limit=50。`QueryService(repo)` 暴露 `list(filters)` 与 `get(intel_id)`，内部调 `IntelRepository.list_by_filter` 扩展签名（见 §3.6），统一排序与字段拼装。Web 与 API 出口共用此服务——同条件调用必返同集合同序（ADR-006 / S1.1.4 AC1）。

### 3.3 FastAPI app 与路由（web.py + api.py）

**web.py**：`lifespan` 启动建 pool + `sync_sources`，关闭释放 pool（复用 `store.db.get_pool/close_pool`）；`Jinja2Templates` 开启 `autoescape`；`GET /` 列表页（query 参数 → IntelFilters → QueryService.list → 渲染 list.html）；`GET /intel/{intel_id}` 详情页（404 → 简单 404 页）。

**api.py**（prefix `/api`，被 web.py include）：`GET /api/intel/list`（依赖 `verify_api_token`，返回 `{"items":[...],"count":N,"next_before":<iso|null>}`）；`GET /api/intel/{intel_id}`（依赖鉴权，返回 IntelRecord dict + `references: {url, snapshot_id, snapshot_url}`）；`GET /healthz`（不鉴权，PG/MinIO 连通性）。JSON 序列化：datetime ISO 化，tags/quant_params 原样，snapshot_url 本 Sprint 渲染占位 `/snapshot/{snapshot_id}`（MinIO presigned URL 留后续 Sprint）。

### 3.4 Jinja2 模板要点

- **base.html**：导航条 + 内容区块 + 极简 CSS 引用。
- **list.html**：顶部 form（subject/event_type/tag/admiralty/source_id/since/until 输入或下拉，GET 同页提交）→ 表格列：标题、主体、事件类型、置信度（admiralty_code）、采集时间、所属事件核实状态（占位单元格「待事件模型上线后自动激活」）→ 空结果整表替换为「无结果，建议放宽条件」（S1.1.1 AC2）→ 表底「下一页」链接携带当前筛选 + `?before=<last.fetched_at>`（结果数 < limit 时不渲染）。
- **detail.html**：分区——基础元信息（title/url/list_url/fetched_at/http_status/content_type/encoding/snapshot_id/content_sha1/created_at）+ 主体/事件类型/标签/量化参数/Admiralty + 事实描述区（facts）+ 推断与判断区（inferences）+ 双入口（原始 URL + MinIO 快照占位链接）+ 处理状态（process_status/process_error/processed_at）+ 事件核实状态与跃迁历史区（占位「待事件模型上线后自动激活」）。

### 3.5 鉴权依赖（auth.py）

`verify_api_token(authorization: str | None = Header(None))`：读 `os.environ["PIH_API_TOKEN"]`，缺失 → `HTTPException(503, "PIH_API_TOKEN 未配置")`；`authorization` 不等于 `f"Bearer {expected}"`（用 `hmac.compare_digest`）→ `HTTPException(401, "invalid credentials")`。Web 路由不挂此依赖；API 路由 `Depends(verify_api_token)` 强制。

### 3.6 IntelRepository 扩展

`list_by_filter` 增参数：`admiralty: str | None`、`since: datetime | None`、`until: datetime | None`、`before: datetime | None`；排序改为 `admiralty_code ASC NULLS LAST, fetched_at DESC, id DESC`（D4）。SQL 拼装复用现有 clauses 模式——admiralty 精确匹配、since/until 走 fetched_at 范围、before 走 fetched_at < 游标。

### 3.7 北极星指标计数（metrics.py）

`log_query(channel, filters, count)` 用 `logging.getLogger("pih.metrics")` 输出 JSON 一行：`{"event":"query","channel":"web|api","filters":{非空字段},"count":N,"ts":"<iso>"}`。QueryService.list 调用后由 web/api 出口分别传入 channel 记录。本 Sprint 仅落日志，不读不聚合。

### 3.8 环境与依赖

`pyproject.toml` 增 `fastapi>=0.115`、`uvicorn[standard]>=0.30`、`jinja2>=3.1`。`.env.example` 增节：

```
# ---- 消费层 Web/API（架构 §4 / ADR-006）----
PIH_API_TOKEN=                 # API 端点鉴权 token（Web 内网默认开放）
PIH_WEB_HOST=127.0.0.1
PIH_WEB_PORT=8000
```

### 3.9 docker-compose web service

```yaml
  web:
    build: .
    depends_on:
      postgres: {condition: service_healthy}
    env_file: .env
    environment:
      POSTGRES_HOST: postgres
    volumes:
      - ./src:/app/src:ro
      - ./domain_packs:/app/domain_packs:ro
    command: uv run uvicorn pih.consume.web:app --host 0.0.0.0 --port 8000
    ports:
      - "${PIH_WEB_PORT:-8000}:8000"
```

不依赖 minio（消费层只读 PG；MinIO 快照入口本 Sprint 给占位路径）。

---

## 4. 目录结构（落地产物）

```
src/pih/consume/
├── __init__.py          # 改：去占位
├── query_service.py     # 新
├── web.py               # 新
├── api.py               # 新
├── auth.py              # 新
├── metrics.py           # 新
├── templates/{base,list,detail}.html   # 新
└── static/style.css     # 新

src/pih/store/repository.py   # 改：list_by_filter 增参数 + 排序调整
pyproject.toml                # 改：加 fastapi/uvicorn/jinja2
docker-compose.yml            # 改：加 web service
.env.example                  # 改：加 PIH_API_TOKEN/PIH_WEB_HOST/PIH_WEB_PORT

tests/
├── _factory.py                              # 新：seed_intel_items(pool, n=60, **overrides)
├── unit/consume/
│   ├── test_query_service.py                # filters → repo 调用参数透传（mock repo）
│   ├── test_auth.py                         # verify_api_token 三分支
│   └── test_metrics.py                      # log_query 输出格式
├── contract/test_templates_render.py        # 新：Jinja2 模板渲染不报错 + 占位文本在
└── integration/test_api_e2e.py              # 新：6 AC + 同源一致性
```

---

## 5. 测试策略

| 层 | 内容 | 依赖 |
|---|---|---|
| unit | query_service：filters dataclass → repo 调用参数透传（mock repo，验 list_by_filter 收到 admiralty/since/until/before）；auth：env 缺失 503 / header 错误 401 / 正确通过 / `compare_digest` 被调用；metrics：log_query JSON 字段齐全 | 无 DB |
| contract | Jinja2 模板渲染：传示例 IntelRecord 列表与单条，list.html/detail.html 不抛未定义变量；模板含「待事件模型上线后自动激活」占位文本；autoescape 生效（`<script>` 被转义） | 无 DB |
| integration | `test_api_e2e.py`：autouse `_clean_db`（alembic downgrade base + upgrade head）；`seed_intel_items(pool, n=60)` 仿 `test_migrations_apply.py:145-156` INSERT 模式，循环造 60 条混合 subject/event_type/admiralty/source_id/fetched_at；`httpx.AsyncClient(ASGITransport(app))` 直连 FastAPI；覆盖 §6 全 6 AC + 同源一致性（Web `/` 与 `/api/intel/list` 同参数返回同 id 序列）；token 用 `monkeypatch.setenv("PIH_API_TOKEN", "test-token")`，缺 token 单独 case 验 503 | docker compose PG |

`tests/conftest.py::pytest_collection_modifyitems` 已自动给 integration/ 加 mark，无需手写装饰器。

---

## 6. 验收标准（Gherkin）

```gherkin
AC1 (S1.1.1): Given 库中已有 ≥60 条情报（seed_intel_items）
     When 消费者选定 主体=X + 事件类型=Y + since=90天前
     Then Web 列表仅展示同时满足三条件的情报
     And 每条显示 标题、主体、事件类型、置信度、采集时间
     And 「所属事件核实状态」列显示「待事件模型上线后自动激活」占位

AC2 (S1.1.1): Given 筛选条件使结果为空
     When 提交筛选
     Then Web 列表显示「无结果，建议放宽条件」
     And 不渲染「下一页」链接

AC3 (S1.1.2): Given 任意一条情报存在
     When 打开 /intel/{id} 详情页
     Then 展示 schema 全字段（基础元信息 + 结构化字段）
     And 事实与推断分区展示
     And 提供原文 URL 与快照入口（快照路径占位）
     And 事件核实状态与跃迁历史区显示「待事件模型上线后自动激活」占位

AC4 (S1.1.4 同源): Given 库中有任意数据
     When 以相同筛选参数分别请求 GET / 与 GET /api/intel/list
     Then 两者返回的情报 id 集合与排序完全一致

AC5 (S1.1.4 响应字段): Given 携带有效 Bearer token 调用 API
     When 提交 主体/事件类型/时间/标签/置信度 组合查询
     Then 响应 JSON 含 情报ID、事实、推断、来源引用(URL+snapshot_id)、置信度(admiralty_code)
     And 含「事件核实状态」字段（占位值，待事件模型上线后自动激活）

AC6 (S1.1.4 鉴权): Given 缺失 Authorization 头或 token 错误
     When 调用 /api/intel/list
     Then 返回 401，body 含 detail，不返回任何情报数据
     And PIH_API_TOKEN 未配置时返回 503
```

---

## 7. 任务分解（建议 6 任务）

1. **T1 依赖 + query_service + repository 扩展**：pyproject 加 fastapi/uvicorn/jinja2；`consume/query_service.py`；`store/repository.py` list_by_filter 加 admiralty/since/until/before + 排序调整；单测。
2. **T2 FastAPI app + 鉴权 + 健康检查 + 指标**：`consume/{web,api,auth,metrics}.py`；单测 auth/metrics；.env.example 加节。
3. **T3 Jinja2 模板**：base/list/detail 三模板 + 极简 CSS；契约测试渲染与 autoescape。
4. **T4 docker-compose web service + 启动验证**：compose 加 service；本地 `uv run uvicorn pih.consume.web:app` 跑通；手动浏览列表/详情。
5. **T5 集成测试 + factory**：`tests/_factory.py::seed_intel_items`；`tests/integration/test_api_e2e.py` 6 AC + 同源一致性。
6. **T6 回写与文档纪律**：Backlog S1.1.1/S1.1.2/S1.1.4 状态位 + 架构 §4 模块表查询服务里程碑 + README 启动说明 + ADR-006 实施注脚。

依赖：T1 → (T2‖T3) → T4 → T5 → T6。T2/T3 可并行（T3 模板基于 T1 filters dataclass 草拟）。

---

## 8. 回写与文档纪律

- **Backlog**（必须）：S1.1.1 置已交付（AC1/AC2 满足；AC3 已过期标识不交付，备注「待时效管理器 Sprint，expires_at 上线后自动激活」）；S1.1.2 置已交付（AC1 满足，事件状态+跃迁历史占位备注「待事件模型上线后自动激活」）；S1.1.4 置已交付（AC1/AC2/AC3 满足，AC2 事件核实状态字段为占位值，待事件模型上线后自动激活）；版本 V1.3 → V1.4。
- **架构**：§4 模块表「查询服务（Web + API）」里程碑 M1 → 「Sprint 5a 已交付（FastAPI 同源 + Jinja2 + Bearer 鉴权；事件状态字段占位待事件模型上线后自动激活）」；§6.2 排序补注「Sprint 5a 简版 admiralty ASC + fetched_at DESC，完整 score 待事件+时效 Sprint」；§7 数据架构无表新增（消费层不落表）。
- **README**：包分层表 consume 行「占位」→「✅ Sprint 5a 已交付（FastAPI Web + JSON API 同源）」；新增「消费层 Web/API 启动」段：`docker compose up -d web` 或 `uv run uvicorn pih.consume.web:app`；API 调用示例（curl 带 Bearer）。
- **ADR-006**：状态不变（已接受），补「Sprint 5a 已落实」实施注脚。
- **不回写**：spike 报告（throwaway）。

---

## 9. 风险

| 风险 | 缓解 |
|---|---|
| Jinja2 autoescape 配置不当导致 XSS（title/facts 含信源原文） | `Jinja2Templates` 显式开启 autoescape；契约测试断言 `<script>` 被转义 |
| 查询服务同源被破坏（Web 与 API 走不同代码路径） | 单一 QueryService，Web/API 出口仅做渲染/序列化差异；集成测试 AC4 同源一致性断言 id 序列完全一致 |
| Bearer token 比较非常量时间（时序攻击） | `hmac.compare_digest` 比较；单测覆盖 |
| PG 连接池在 uvicorn 多 worker 下错配 | docker-compose 单 worker（默认 uvicorn 不加 --workers）；本地同；多 worker 留调度器 Sprint |
| 集成测试 60 条数据造数 SQL 错误 | `seed_intel_items` 仿现有 INSERT 模式；autouse `_clean_db` 保证幂等 |
| 快照入口占位路径未来 MinIO presigned URL 落地成本 | detail.html 集中一处 `snapshot_url` 变量，后续 Sprint 改一处即生效 |
| admiralty_code NULL（pending 条目）排序不稳定 | `NULLS LAST` 显式；本 Sprint 不强制过滤 process_status，留用户反馈后调优 |
