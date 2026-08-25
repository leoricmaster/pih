# Sprint 2：collect 层第一期 —— 设计规格

> 状态：草案（待评审）
> 范围：信源适配器骨架 + RawItem 模型 + 原文快照存档 MinIO + robots 合规抓取；首批接入 CCMA / 三一 / cehome 三源。让领域包 `sources` 配置第一次被代码真实消费，数据流入口打通。
> 依据：架构 §4（COLLECT 层模块职责）、§5.1（主流程）、§5.3（快照与可回溯）、§8（可靠性）、ADR-007；Backlog S3.2.1；SPK-1 实测三源技术约束。

---

## 0. 背景与不做什么

**Sprint 1 已交付**：工程脚手架（src/pih 五层 + Docker Compose 三服务 + uv）、领域包加载器/校验器/schema、第一领域包 `construction_machinery`（9 源落盘但尚无代码消费）。本 Sprint 让 `sources` 配置活起来。

**本 Sprint 不做**（明确排除）：
- **不做调度器**（APScheduler）——架构 §4 调度器是 M1，但 collect 第一期先手动触发（pytest/CLI 单次跑），把抓取本身做扎实；调度器留下一 Sprint。
- **不做去重器 / 粗筛**——架构 §4 COLLECT 层的 DD/FT 节点，依赖 RawItem 与 inbox 落盘先就位，留后续 Sprint。
- **不做 PG 业务表 / inbox 表**——`RawItem` 先以内存对象 + MinIO 快照交付；inbox 表持久化随 store 层 Sprint 落地（本 Sprint 快照已落 MinIO，满足"原始内容先落盘"原则的最低要求）。
- **不做 changedetection.io / RSSHub**——外部依赖，后续。
- **不做 LLM 相关**——粗筛/抽取是 process 层。

> **Backlog 拆解对齐**（用户明确要求：需求要么被实现要么没被实现）：
> 原卡 S3.2.1「信源配置注册与健康监控」含 AC1（试抓取）+ AC2（连续 3 次失败告警）+ AC3（缺字段拒绝）。AC2 隐含持续调度与健康监控，本 Sprint 不做调度器即无法完整交付。
> **拆解方案**：原 S3.2.1 缩范围为「信源注册与试抓取」（保留 AC1 + AC3，AC3 已由 Sprint 1 校验器满足位置产出），状态位本 Sprint 末置「已交付」；新增 **S3.2.3**「信源健康监控与告警」承接原 AC2，状态「待开发」。编号纪律遵循「改卡不改号、不复用」。

---

## 1. 已锁定决策（用户确认）

| 决策 | 选择 | 含义 |
|---|---|---|
| HTTP + 解析库 | **httpx（同步）+ selectolax** | httpx 超时细粒度控制（CCMA HTTPS 25s 超时须严控）；selectolax libxml2 后端 CSS 选择器，三源 SSR HTML 解析快 |
| 调度器 | **不做，手动触发** | 本 Sprint 适配器单次跑（pytest/CLI）；APScheduler 留下一 Sprint |
| 测试抓取策略 | **夹具为主 + 少量真实抓取** | 单元/契约测试用本地 HTML 夹具（从 spike samples 抽）；集成测试真实抓三源各 1–2 条验端到端 |

---

## 2. 待定决策（本规格需拍板，给出推荐）

| # | 议题 | 推荐 | 理由 |
|---|---|---|---|
| D1 | RawItem 模型实现 | **dataclass**（不用 pydantic） | Sprint 1 schema 用 jsonschema 纯校验；RawItem 是内部数据载体，dataclass 轻量无依赖；pydantic 留到 store 层建表时与 ORM 映射一并上 |
| D2 | 适配器插件机制 | **注册表 + 基类**（非动态导入） | ADR-001「配置而非插件」精神延伸：适配器按 `source.type`（rss/html/api/change_monitor）分四类基类，注册表 `type→class`；新增类型加基类+注册，不改核心。三类 HTML 源本期共用 `HtmlAdapter` 基类，差异在解析钩子 |
| D3 | 快照存档格式 | **原始字节 + 元数据 sidecar JSON** | MinIO 存原始 HTML 字节（`snapshots/<source_id>/<sha1>.html`），sidecar JSON 存 url/fetched_at/http_status/content_type/encoding；满足 §5.3「原文快照可回溯」 |
| D4 | 内容指纹 | **sha1(raw_bytes)** | ADR-007 入库幂等键 = 快照内容指纹；sha1 足够且短；不用 md5（已弱）也不用 sha256（40 字符够长，此场景无安全需求） |
| D5 | robots 检查 | **继承 spike probe.py 行为 + 修两点** | 继承：UA 声明式、404=允许、非 200=保守不允许、robotparser 解析。修复：① robots 检查纳入节流（spike 漏掉）；② 软 200 站点（CCMA）robots HTML 模板被当空规则集——加 content-type 嗅探，非 text/plain 的 200 robots 视为「无效 robots」按未声明处理并告警 |
| D6 | 编码解码 | **继承 spike decode_body 链 + 修两点** | 继承：header charset→meta charset（**窗口扩到 4096**，spike 2048 漏深埋 meta）→utf-8/gbk 严格试探→utf-8/replace。修复：① 窗口 2048→4096；② **HTML 实体解码**（`&amp;` `&#xx;` 等，SPK-1 遗留 Minor 沉淀为此契约） |
| D7 | 配置驱动 | **领域包 sources 驱动 + schema 扩字段** | 当前 schema sources 缺 `fetch_frequency` / `level`（Backlog S3.2.1 AC3 要求层级必填）。本 Sprint 扩 schema：sources 加 `level`（L1–L4，必选）、`fetch_frequency`（可选，调度器 Sprint 消费）；pack.yaml 同步补字段 |

---

## 3. SPK-1 三源技术约束（subagent 实测报告，设计依据）

### 3.1 共享约束

- **UA**：`pih-collector/0.1 (+https://repo; contact: repo owner)`（生产期从 spike 的 `pih-spike` 改名，声明身份）。
- **节流**：默认 2s/请求；纳入 robots 检查请求；未来 KHL 类 Crawl-Delay 站点按源配置覆盖。
- **解码链**：见 D6。
- **重试**：指数退避 ×3（架构 §8）；网络错误/5xx 重试，4xx 不重试。

### 3.2 三源适配器契约

| 维度 | CCMA（cncma.org） | 三一（sanygroup.com） | cehome（cehome.com） |
|---|---|---|---|
| scheme | **http only**（https 25s 超时） | https | https |
| robots | 软 200 HTML 模板（无指令）→ 无效 robots，按未声明处理 + 告警 | 58 行真 robots，`/news` 不在 Disallow → 允许 | 2 行 `allow: /` → 全站允许 |
| 列表 URL | `/col/hangyxw` | `/news` | `/news/hangye/` |
| 渲染 | SSR XHTML | Nuxt SSR（`__NUXT__`，`data-server-rendered`） | SSR XHTML |
| 详情链接正则 | `/article/\d+` | `/news/\d+\.html` | `/news/20\d{6}/\d+\.shtml` |
| 分页 | `?pageIndex=N`（44 页 × 30） | `?page=N&size=6` | 路径 `/<N>/`（深页缓存疑点，本期只取首页） |
| HTTP charset 头 | utf-8 声明 | 未记录，字节 utf-8 | **缺失** → requests/httpx 默认 ISO-8859-1 → mojibake |
| meta charset | utf-8 | utf-8 | utf-8（**非 GBK**——SPK-1 报告「GBK」措辞错误，subagent 字节验证为 utf-8） |
| 存在性判定 | **内容判定**（软 200：看 `<title>` + `/article/\d+`） | 状态 200 | 状态 200 |
| 反爬 | 无 | 无 | 无 |
| 间隔 | 2s | 2s | 2s |

### 3.3 两处 SPK-1 报告修正（subagent 发现，须在生产实现纠正）

1. **cehome 编码非 GBK**：报告 §2/§3.1.2/§4 称 cehome 为「GBK 页」，但样本字节与 meta 均为 **UTF-8**。真实缺陷是 HTTP 头缺 charset → 默认 ISO-8859-1 → mojibake。解码链（D6）正确落到 utf-8，**不为 cehome 硬编码 GBK**。本 Sprint 回写架构/需求相关措辞（见 §9）。
2. **CCMA 软 200 robots 陷阱**：`robotparser` 把 HTML 模板当空规则集（全允许）。工具无法区分「无 robots」与「软 200 HTML robots」。生产适配器加 content-type 嗅探（非 text/plain 的 robots 200 视为无效 + 告警，D5）。

---

## 4. 目录结构（落地产物）

```
src/pih/collect/
├── __init__.py
├── rawitem.py            # RawItem dataclass + 内容指纹
├── httpclient.py         # httpx 封装：UA、超时、节流、重试×3、robots 检查
├── encoding.py           # decode_body 解码链（D6，含实体解码）
├── snapshot.py           # MinIO 快照存档（D3）
├── base.py               # Adapter 基类 + 注册表（D2）
├── html_adapter.py       # HtmlAdapter 基类：列表解析 + 详情抓取通用流程
├── adapters/
│   ├── __init__.py
│   ├── ccma.py           # CCMA 适配器（http、软 200 存在性判定、?pageIndex）
│   ├── sany.py           # 三一适配器（Nuxt SSR、/news/\d+\.html、strip U+FEFF）
│   └── cehome.py         # cehome 适配器（路径分页、解码链验 utf-8）
└── robots.py             # robots 合规判定（D5，继承 spike + 修两点）

domain_packs/construction_machinery/pack.yaml   # 改：sources 加 level/fetch_frequency

tests/
├── fixtures/html/        # 从 spike samples 抽的 HTML 夹具
│   ├── ccma_list.html
│   ├── ccma_detail.html
│   ├── sany_list.html
│   ├── sany_detail.html
│   ├── cehome_list.html
│   └── cehome_detail.html
├── unit/collect/
│   ├── test_encoding.py
│   ├── test_robots.py
│   ├── test_rawitem.py
│   ├── test_html_adapter.py
│   └── test_adapters_{ccma,sany,cehome}.py   # 用夹具验解析
├── contract/
│   └── test_pack_sources_fields.py            # sources 必有 level（AC3 对齐）
└── integration/
    └── test_fetch_live.py                     # @integration 真实抓三源各 1–2 条
```

---

## 5. 核心设计

### 5.1 RawItem 模型（`rawitem.py`）

```python
@dataclass(frozen=True)
class RawItem:
    source_id: str          # 领域包 sources[].id
    url: str
    title: str              # 从详情页解析
    list_url: str           # 来源列表页
    fetched_at: str         # ISO8601
    http_status: int
    content_type: str
    encoding: str           # 解码链判定结果
    raw_html: str           # 解码后正文（快照另存原始字节）
    snapshot_id: str        # MinIO 快照 ID = sha1(raw_bytes)
    content_sha1: str       # 内容指纹（= snapshot_id，幂等键）
```

### 5.2 Adapter 基类与注册表（`base.py`，D2）

```python
class SourceAdapter(ABC):
    type: str  # rss/html/api/change_monitor
    @abstractmethod
    def fetch_list(self, source: dict) -> list[str]: ...      # 返回详情 URL 列表
    @abstractmethod
    def fetch_detail(self, url: str, source: dict) -> RawItem: ...

REGISTRY: dict[str, type[SourceAdapter]] = {}
def register(cls): REGISTRY[cls.type] = cls; return cls
def get_adapter(source_type: str) -> SourceAdapter: ...
```

`HtmlAdapter(SourceAdapter)` 实现通用 HTML 流程：robots 检查 → 节流 → httpx GET → 解码 → selectolax 解析列表/详情。三源子类只覆盖解析钩子（`extract_detail_urls`、`extract_title`、`extract_body`、`is_valid_page`）。

### 5.3 robots 合规（`robots.py`，D5）

继承 spike `robots_allows` / `fetch_robots_ok`，加：
- `fetch_robots_ok` 纳入节流（调用方传 gap）；
- 200 但 `Content-Type` 非 `text/plain` → 视为无效 robots（软 200），返回 `(True, "无效 robots（软 200 HTML），按未声明处理")` + 告警标志。

### 5.4 快照存档（`snapshot.py`，D3）

```python
def archive(client: minio_client, source_id: str, raw_bytes: bytes, meta: dict) -> str:
    sha = hashlib.sha1(raw_bytes).hexdigest()
    key = f"snapshots/{source_id}/{sha}.html"
    client.put_object("pih-snapshots", key, BytesIO(raw_bytes), len(raw_bytes), "text/html")
    client.put_object("pih-snapshots", key + ".meta.json", ...meta...)  # sidecar
    return sha
```

### 5.5 schema 扩展（D7）

`domainpacks/schema.py` 的 `sources[].properties` 加：
- `level`: enum `["L1","L2","L3","L4"]`，**必选**（Backlog S3.2.1 AC3）；
- `fetch_frequency`: string，可选（如 `daily`/`weekly`，调度器 Sprint 消费）；
- `list_url`: string format uri，**必选**（列表页入口，当前 pack 只有站点 url，不够）。

`pack.yaml` 同步补三源的 `level` / `list_url` / `fetch_frequency`。

---

## 6. 测试策略

| 层 | 内容 | 依赖 |
|---|---|---|
| unit | encoding（解码链 + 实体解码）、robots（软 200 嗅探、规则判定）、rawitem（指纹）、html_adapter（用夹具验三源解析：链接提取、标题、存在性判定） | 本地夹具，无网络 |
| contract | pack.yaml sources 必有 level/list_url（AC3 对齐） | 领域包文件 |
| integration | 真实抓三源各 1–2 条：robots 通过、HTTP 200、RawItem 产出、快照落 MinIO | `@integration`，需 compose up + 网络 |

夹具来源：从 `spikes/spk1-source-probe/samples/{ccma,sany,cehome}-00.md` 抽 HTML 存 `tests/fixtures/html/`（spike 样本 YAML 头 + 正文，取正文部分）。

---

## 7. 验收标准（Gherkin，对齐 Backlog S3.2.1 拆解后）

```gherkin
AC1: Given 领域包 construction_machinery 的 sources 含 ccma/sany/cehome（含 level/list_url）
     When 适配器按 sources 配置抓取（手动触发）
     Then 三源各产出 ≥1 RawItem，含 title/url/fetched_at/http_status/snapshot_id/content_sha1
     And 原文快照落 MinIO snapshots/<source_id>/<sha>.html

AC2: Given CCMA 的 robots.txt 返回 200 但 Content-Type 为 text/html
     When robots 检查
     Then 判定为「无效 robots（软 200）」按未声明处理（允许）并产出告警标志

AC3: Given cehome 详情页 HTTP 响应头无 charset
     When 解码
     Then 解码链落到 utf-8（非 ISO-8859-1 mojibake），标题可读
     And HTML 实体（&amp; 等）已解码

AC4: Given 领域包 sources 缺 level 字段
     When schema 校验
     Then 拒绝并指出位置 sources[i].level（Sprint 1 校验器已支持，本 Sprint 加字段后回归）

AC5: Given 三源的列表页 HTML 夹具
     When html_adapter 解析
     Then 提取详情 URL 命中各源正则（/article/\d+、/news/\d+\.html、/news/20\d{6}/\d+\.shtml）

AC6: Given docker compose up + 网络
     When 跑 test_fetch_live（@integration）
     Then 三源各真实抓 1–2 条，端到端产出 RawItem + MinIO 快照
```

> 原 S3.2.1 AC2「连续 3 次失败告警」移至新卡 **S3.2.3**，本 Sprint 不交付。

---

## 8. 任务分解（建议 7 任务）

1. **T1 schema 扩展 + pack.yaml 补字段**：sources 加 level/list_url/fetch_frequency；三源补值；契约测试。
2. **T2 RawItem + 内容指纹**：dataclass、sha1、单元测试。
3. **T3 encoding 解码链**：decode_body（窗口 4096 + 实体解码）+ 单元测试（含 cehome utf-8 验证、实体用例）。
4. **T4 robots 合规**：继承 spike + 软 200 嗅探 + 节流纳入 + 单元测试。
5. **T5 httpclient + snapshot**：httpx 封装（UA/超时/重试/节流）、MinIO 快照存档 + 单元测试。
6. **T6 HtmlAdapter + 三源适配器**：基类 + ccma/sany/cehome 子类 + HTML 夹具抽取 + 单元测试（解析）。
7. **T7 集成测试 + Backlog 拆解回写**：test_fetch_live 真实抓取；Backlog S3.2.1 拆分 + 新增 S3.2.3；架构/需求 cehome GBK 修正回写。

依赖：T1 → (T2‖T3‖T4) → T5 → T6 → T7。T2/T3/T4 可并行。

---

## 9. 回写与文档纪律

- **Backlog**（必须，用户要求）：S3.2.1 缩范围为「信源注册与试抓取」+ 状态位本 Sprint 末置已交付；新增 S3.2.3「信源健康监控与告警」待开发。版本 bump V0.9→V1.0。
- **架构**：§3.1.2（若有 cehome GBK 措辞）或附件 A 信源表，按 subagent 修正改「GBK」→「HTTP 头缺 charset，解码链落到 utf-8」；§4 调度器里程碑说明（手动触发阶段）。
- **需求**：§6/§7 信源风险行若有 GBK 措辞同步修正。
- **不回写**：spike 报告（throwaway，不回补）。

---

## 10. 风险

| 风险 | 缓解 |
|---|---|
| 真实抓取集成测试 flaky（站点变更/网络抖动） | 集成测试只抓 1–2 条、容错断言（不断言具体标题文本，只断言结构）；失败标 xfail 不阻塞 |
| cehome 深分页缓存导致夹具不代表真实 | 本期只取首页列表；深分页留后续 |
| selectolax 对 Nuxt SSR 的 `__NUXT__` 解析 | 详情页按 article 容器选择器切片，不碰 `__NUXT__` JSON blob |
| 三源 schema 扩字段破坏 Sprint 1 契约测试 | T1 同步更新 contract 测试 + pack.yaml，回归 46 passed |
