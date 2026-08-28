# Sprint 5b：质量闭环 —— 设计规格

> 状态：已批准（2026-08-28 用户确认）
> 范围：S4.2.3 抽取后验质量门（主体占位值 → needs_manual 止损）+ S3.1.3 消费页人类反馈动作最小切片（feedback 表 + 详情页反馈表单 + 聚合视图 + JSONL 导出）+ 支撑项 process_status 筛选（needs_manual 队列可达）。
> 依据：Backlog S4.2.3（V1.5 新增）/ S3.1.3（V1.5 新增）；架构 §4（CONSUME）/ §7（数据架构）/ §8（容错）；Sprint 5a 验收记录（批次性质量问题）。

---

## 0. 背景与不做什么

**Sprint 5a 验收发现**：粗筛误放与抽取误读是**批次性**问题，非个例——13 条里 5 条时政/科普类误入库或主体错抽（电池包技术文主体="未知"仍 extracted 入库；政府调研文主体误读页面栏目名）。错误样本只能靠人在消费时顺手标记积累；无反馈闭环则粗筛口径收紧全靠盲调。

**两卡同期交付的分工**：后验门拦住增量（纯代码止损，不依赖 LLM 改进），反馈样本驱动 prompt 根治（后续专项迭代，不在本 Sprint）。

**本 Sprint 不做**（明确排除）：

- **不改粗筛/抽取 prompt**——等反馈样本积累后专项迭代（加主体判据规则 + 负样本 few-shot）。
- **不做 S3.1.1 离线人工核实队列页**——本 Sprint 的 `?process_status=needs_manual` 筛选即其最小形态。
- **不做 tokened POST /api/feedback**——Agent 程序化写反馈留后续卡。
- **不做反馈修改/删除/分页**——单人运维，100 条明细够用。
- **不做事件模型 / 时效管理器 / 调度器**——后续 Sprint。

---

## 1. 已锁定决策（用户确认，2026-08-28）

| 决策 | 选择 | 含义 |
|---|---|---|
| 反馈提交端点 | Web 表单 `POST /feedback`，无鉴权 | 与 Sprint 5a「Web 页面内网默认开放」同口径；提交后 303 重定向回详情页（`?fb=1` 显示已记录）。此前建议文案中的「POST /api/feedback」与现有 /api/* 全量 Bearer token 口径冲突（网页表单无法携带 token），故落为 Web 路由 |
| 后验门触发时字段去向 | **保留已抽取字段 + 置 needs_manual** | 复核时直接看到「主体=未知、事件类型=其他」错在哪，配合反馈按钮一键修正；偏离现有 needs_manual 字段全空口径，属有意扩展（「needs_manual + 结构化字段在场」= 后验门拦下的新子形态） |
| 后验门实现位置 | 谓词 `is_placeholder_subject` 放 `process/extraction.py`，由 Runner 在构 ProcessResult 时判定 | AC 文案「校验节点后验检查」语义等价——发生在 schema 校验通过之后的后验步骤；不改 ItemState 契约，不动 LangGraph 图结构 |
| 反馈类型 | 4 类：subject_wrong / event_type_wrong / fact_wrong / should_filter | 卡片 story 列 4 种、AC 只覆盖 3 种；事件类型错与主体错同机制，顺手补齐 |
| 占位主体判定集 | `{"", "未知", "无", "不详", "unknown"}`（strip + lower 后比对） | Sprint 5a 实证样本是「未知」；集合小而证据驱动，可随反馈样本扩充 |
| 聚合视图口径 | 主体错误率 = 该信源 subject_wrong 数 / 该信源 extracted 条目数，>30% 高亮（AC4） | 分母用 extracted（已通过质量门的正常情报），不是全量条目 |

---

## 2. 核心设计

### 2.1 后验质量门（S4.2.3，process 层）

- `process/extraction.py`：`PLACEHOLDER_SUBJECTS` 常量 + `is_placeholder_subject(subject: str) -> bool`（纯函数）。
- `process/run.py::_process_one`：extraction 非空且谓词命中 →
  `ProcessResult(status=needs_manual, 结构化字段全填, admiralty_code=拼装值, error="后验质量门：主体为占位值「…」", meta)`；CLI 详情行 `[id] ⚠ needs_manual（后验质量门…）`。
- `IntelRepository.write_process_result` 的 UPDATE SQL 本就无条件写全部字段，**零改动**支持该形态。
- 列表不稀释：消费端按 `process_status=extracted` 或默认排序浏览；needs_manual 经状态筛选进入复核视野。

### 2.2 feedback 表（迁移 0003）

```sql
CREATE TABLE feedback (
    id            BIGSERIAL PRIMARY KEY,
    intel_id      BIGINT NOT NULL REFERENCES intel_item(id) ON DELETE CASCADE,
    feedback_type TEXT NOT NULL,   -- subject_wrong | event_type_wrong | fact_wrong | should_filter
    fact_index    INTEGER,         -- fact_wrong 时标注到第几条事实（split_facts 序，1 起）
    wrong_value   TEXT,            -- 当前错值（模板 hidden 带详情页现值）
    correct_value TEXT,            -- 正确值（主体/事件类型反馈填）
    note          TEXT,            -- 自由说明
    user_id       TEXT NOT NULL DEFAULT 'operator',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```
索引：`idx_feedback_intel(intel_id)`、`idx_feedback_type(feedback_type)`。downgrade：DROP TABLE。

### 2.3 store 层 FeedbackRepository（`store/feedback.py` 新文件）

`FeedbackRepository(pool)`：
- `save(...) -> int`：INSERT RETURNING id；
- `list_recent(limit=100) -> list[FeedbackRecord]`：created_at DESC，JOIN intel_item 带 title/source_id（明细表展示用）；
- `aggregate() -> list[FeedbackAggRow]`：① `GROUP BY i.source_id, f.feedback_type` 计数；② extracted 按 source 计数作分母；Python 侧算主体错误率并打 `highlight` 标志（>30%，AC4）。

### 2.4 consume 层（web.py + 模板）

路由（均无鉴权，内网口径）：
- `POST /feedback`（Form：intel_id、feedback_type ∈ 4 类否则 422、correct_value?、fact_index?、note?、user_id? 默认 operator、wrong_value?）→ intel 不存在 404 → 落库 → `303 → /intel/{id}?fb=1`。
- `GET /feedback`：聚合视图页（按信源×类型计数 + 主体错误率高亮行）+ 最近 100 条明细 + 「导出 JSONL」链接。
- `GET /feedback/export`：`list_recent(1000)` 逐行 JSON → `application/x-ndjson`（AC4 few-shot 素材导出）。

模板：
- `detail.html` 新增「反馈」区（`id=feedback`，`?fb=1` 显示「反馈已记录」）：四个内联小表单——主体错了（input + `<datalist>` 领域包主体清单，可自由输入，AC1）、事件类型错了（select 领域包 event_types）、事实不准（select 第 N 条事实 + 说明，按 `；` 拆分序 1 起，AC2）、不该入库（可选说明，AC3）。
- `list.html`：新增「状态」列（process_status 徽章）+ 筛选下拉（全部/extracted/needs_manual/filtered_out/pending）+「反馈」链接列（`/intel/{id}#feedback`）。
- 领域包注入：web.py 以 cli.py `_default_pack` 同款路径解析加载 pack（cwd 优先，回退 `DEFAULT_PACK_DIR`），把 competitors display_name+aliases、event_types 传给 detail 模板；加载失败降级空清单（datalist 空、自由输入仍可用）。

### 2.5 process_status 筛选（支撑项）

`IntelFilters` + `IntelRepository.list_by_filter` 增可选 `process_status` 精确匹配子句；Web 列表页与 `GET /api/intel/list` 同步暴露该参数（ADR-006 同源）。这是 S4.2.3 AC1「条目保留可查，进入人工核实队列」的实际可达路径。

---

## 3. 落地产物

```
src/pih/process/extraction.py        # 改：PLACEHOLDER_SUBJECTS + is_placeholder_subject
src/pih/process/run.py               # 改：_process_one 后验门分支
src/pih/store/feedback.py            # 新：FeedbackRecord/FeedbackAggRow/FeedbackRepository
src/pih/consume/web.py               # 改：三路由 + pack 注入
src/pih/consume/query_service.py     # 改：IntelFilters.process_status
src/pih/consume/api.py               # 改：list 参数透传
src/pih/consume/templates/detail.html # 改：反馈区
src/pih/consume/templates/list.html   # 改：状态列 + 筛选下拉 + 反馈链接
src/pih/store/repository.py          # 改：list_by_filter 增 process_status
migrations/versions/0003_feedback_table.py  # 新
tests/unit/process/test_run.py       # 改：后验门单测
tests/contract/test_migrations_apply.py # 改：0003 检查
tests/integration/test_feedback_e2e.py  # 新
tests/integration/test_process_e2e.py   # 改：门 AC
tests/integration/test_api_e2e.py       # 改：状态筛选同源
```

---

## 4. 测试策略

| 层 | 内容 | 依赖 |
|---|---|---|
| unit | `is_placeholder_subject` 边界（未知/带空白/Unknown/正常）；Runner 门分支：fake chat 返 subject=未知 → ProcessResult.status=needs_manual、字段保留、error 含「后验质量门」；正常主体 → extracted 回归 | 无 DB |
| contract | 0003：feedback 列齐全、FK→intel_item ON DELETE CASCADE、两索引在；downgrade 0002 后表消失 | docker PG |
| integration | `test_feedback_e2e.py`：POST 表单 → 303 → DB 有行（含 wrong_value/hidden 透传）→ `/feedback` 页含明细与聚合计数 → `/feedback/export` JSONL 首行可 json.loads；非法 type 422；intel 不存在 404；`test_process_e2e.py` 加脚本化 chat subject=未知 → 库内 needs_manual + subject 保留 + process_error 含后验质量门；`test_api_e2e.py` 加 `?process_status=` web/API 同源 | docker PG |

---

## 5. 验收标准（Gherkin）

```gherkin
AC1 (S4.2.3): Given 抽取完成的条目主体为"未知"或空值占位
     When 后验质量门执行（schema 校验通过后的后验谓词）
     Then process_status 置 needs_manual（非 extracted），结构化字段保留可查
     And process_error 记录"后验质量门：主体为占位值"
     And 该条目可经 ?process_status=needs_manual 筛选进入复核视野

AC2 (S3.1.3 主体): Given 消费者打开详情页看到主体与原文不符
     When 点击"主体错了"填正确主体（datalist 主体清单可选或自由输入）提交
     Then 反馈写入 feedback 表（intel_id, feedback_type=subject_wrong,
         wrong_value=原值, correct_value, user_id, ts）并重定向回详情页

AC3 (S3.1.3 事实): Given 消费者看到事实描述不准
     When 选择具体第几条事实（按；拆分序）并填说明提交
     Then 反馈记录 fact_index 标注到事实项级别

AC4 (S3.1.3 不该入库): Given 消费者认为这条不该入库（粗筛漏放）
     When 点击"不该入库"提交
     Then 反馈写入 type=should_filter，聚合视图按信源计数

AC5 (S3.1.3 聚合): Given 运营者打开 /feedback
     When 某信源主体错误率（subject_wrong/extracted）>30%
     Then 聚合行高亮提示需迭代该信源抽取 prompt 或粗筛阈值
     And 明细可经 /feedback/export 导出为 JSONL（prompt 迭代 few-shot 素材）
```

---

## 6. 任务分解

T0 规格 → T1 后验门（含单测）→ T2 迁移 0003 → T3 FeedbackRepository → T4 consume 路由+模板 → T5 process_status 筛选 → T6 集成/契约测试 → T7 回写与手动走查。

---

## 7. 回写与文档纪律

- **Backlog**：V1.5→V1.6；S4.2.3、S3.1.3 置已交付（备注端点形态/4 类反馈/导出 JSONL 口径）。
- **架构**：§7 数据架构加 feedback 表；§4 consume 职责补反馈入口。
- **README**：反馈页路径与 needs_manual 筛选用法。

---

## 8. 风险

| 风险 | 缓解 |
|---|---|
| 无鉴权写端点被滥用（内网外露） | 与 Web 页面同信任域；仅内网部署（架构前提）；user_id 留审计字段 |
| 占位主体集合误伤真主体（如真有主体叫「无」） | 集合小而保守；命中只是降 needs_manual 非丢弃，人工复核可纠正 + 反馈样本可扩集合 |
| needs_manual 保留字段与旧口径混淆（字段在场但状态非 extracted） | spec 明确「后验门子形态」语义；列表按 extracted 浏览不受稀释 |
| 反馈表无唯一约束导致重复提交 | 单人场景重复无害；聚合按 count 计，刷数风险内网可忽略 |
