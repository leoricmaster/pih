# Sprint 0 Spike 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 执行 Sprint 0 三个 Spike（SPK-1 信源可抓取性 / SPK-2 LLM 抽取准确率 / SPK-3 LangGraph 端到端），产出报告并回写需求/架构/Backlog 三件套。

**Architecture:** 严格串行 SPK-1 → SPK-2 → SPK-3。所有 Spike 代码与产出放 `spikes/` 独立目录，共享工具在 `spikes/_lib/`（robots 合规抓取、OpenAI 兼容 LLM 客户端）。每个 Spike 完成即回写三件套并翻转 Backlog 状态位。

**Tech Stack:** Python ≥3.10、requests、pytest、jsonschema、langgraph；LLM 走 OpenAI 兼容端点（环境变量配置）。

**设计规格：** `docs/superpowers/specs/2026-08-25-sprint0-spikes-design.md`（已获用户批准）

## Global Constraints

- **robots 合规**：所有抓取先查 robots.txt；不登录、不绕过反爬、不批量抓取（≤5 源、每源 1–3 列表页 + 3–5 条详情；同源请求间隔 ≥2s）
- **禁止编造数据**：报告与记录只写实际观察到的结果。网络不可用、robots 禁止、API 密钥缺失时——记录该事实并停下询问用户，绝不模拟结果
- **密钥永不入库**：`.env` 进 `.gitignore`；LLM 端点用环境变量 `PIH_LLM_BASE_URL` / `PIH_LLM_API_KEY` / `PIH_LLM_LARGE_MODEL` / `PIH_LLM_SMALL_MODEL`
- **Spike 代码非工程代码**：不上重型框架（抓取仅 requests+标准库，无 Playwright/Scrapy）；接口定义以架构文档为准，Spike 脚本用后即弃
- **文档回写纪律**：Sprint 0 内回写只更新 `日期`/`变更`/状态位，版本号统一在收尾任务（Task 8）bump；文档语言为中文
- **提交纪律**：每任务至少一次提交，commit 描述用中文，结尾加 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **运行环境**：Python ≥3.10（先 `python3 --version` 确认）；venv 在 `spikes/.venv`；pytest 一律 `spikes/.venv/bin/python -m pytest <路径> -v`
- **LLM 调用**：温度 0.0；429/5xx 线性退避重试 ≤3；条目间 sleep 0.3s

---

### Task 1: Spike 基座（venv + 目录 + robots 合规抓取工具）

**Files:**
- Create: `spikes/README.md`
- Create: `spikes/requirements.txt`
- Create: `spikes/.env.example`
- Create: `spikes/_lib/__init__.py`（空文件）
- Create: `spikes/_lib/probe.py`
- Test: `spikes/_lib/test_probe.py`
- Modify: `.gitignore`（追加 `spikes/.venv/` 与 `.env`，若缺）

**Interfaces:**
- Consumes: 无（首个任务）
- Produces（后续任务依赖的确切签名）:
  - `UA: str`（User-Agent 常量，形如 `pih-spike/0.1 (+research)`）
  - `robots_allows(robots_txt: str, url: str, base_url: str, user_agent: str = "*") -> bool` —— 纯函数，供 `fetch_robots_ok` 与测试使用
  - `fetch_robots_ok(url: str, timeout: int = 10) -> tuple[bool, str]` —— 返回 `(是否允许抓取, 说明文字)`；说明文字含 robots 摘录或 HTTP 状态
  - `polite_get(url: str, timeout: int = 10) -> requests.Response` —— 带 UA、限单次、不重试的 GET

- [ ] **Step 1: 确认环境并建 venv**

```bash
cd /home/lancer/projects/pih/spikes 2>/dev/null || mkdir -p /home/lancer/projects/pih/spikes
python3 --version   # 必须 ≥ 3.10
python3 -m venv /home/lancer/projects/pih/spikes/.venv
```

Expected: `Python 3.1x.y`

- [ ] **Step 2: 写 requirements.txt 与 .env.example**

`spikes/requirements.txt`:

```
requests>=2.31
pytest>=8.0
jsonschema>=4.21
python-dotenv>=1.0
openai>=1.40
langgraph>=0.2
```

`spikes/.env.example`:

```
# OpenAI 兼容端点（商业 API 或自有模型服务），复制为 .env 并填真实值
PIH_LLM_BASE_URL=https://api.example.com/v1
PIH_LLM_API_KEY=sk-xxxx
PIH_LLM_LARGE_MODEL=模型名（抽取/核实用）
PIH_LLM_SMALL_MODEL=模型名（粗筛/去重用）
```

- [ ] **Step 3: 安装依赖并更新 .gitignore**

```bash
spikes/.venv/bin/pip install -r spikes/requirements.txt
```

`.gitignore` 追加（若缺）:

```
spikes/.venv/
.env
```

- [ ] **Step 4: 写失败测试**

`spikes/_lib/test_probe.py`:

```python
import textwrap

from _lib.probe import UA, robots_allows

ROBOTS_DISALLOW = textwrap.dedent("""\
    User-agent: *
    Disallow: /private/
    Allow: /public/
    """)

ROBOTS_EMPTY = ""

SITE = "https://example.com"


def test_ua_declares_spike_identity():
    assert "pih-spike" in UA


def test_disallowed_path_rejected():
    assert robots_allows(ROBOTS_DISALLOW, f"{SITE}/private/x", SITE) is False


def test_allowed_path_ok():
    assert robots_allows(ROBOTS_DISALLOW, f"{SITE}/public/y", SITE) is True


def test_unlisted_path_defaults_allowed():
    assert robots_allows(ROBOTS_DISALLOW, f"{SITE}/news/z", SITE) is True


def test_empty_robots_allows_all():
    assert robots_allows(ROBOTS_EMPTY, f"{SITE}/anything", SITE) is True


def test_specific_ua_overrides_star():
    robots = "User-agent: pih-spike\nDisallow: /\nUser-agent: *\nAllow: /"
    assert robots_allows(robots, f"{SITE}/a", SITE, user_agent="pih-spike") is False
    assert robots_allows(robots, f"{SITE}/a", SITE, user_agent="other") is True
```

- [ ] **Step 5: 运行确认失败**

```bash
cd /home/lancer/projects/pih/spikes && .venv/bin/python -m pytest _lib/test_probe.py -v
```

Expected: FAIL/ERROR（`ModuleNotFoundError: No module named '_lib.probe'` 或导入错误）

- [ ] **Step 6: 实现 probe.py**

`spikes/_lib/probe.py`:

```python
"""SPK-1 共享工具：robots 合规判定与礼貌抓取。

Spike 代码，非工程代码——接口定义以 docs/Architecture.md §4 为准。
"""
from __future__ import annotations

import urllib.robotparser
from urllib.parse import urlsplit

import requests

UA = "pih-spike/0.1 (+research; contact: repo owner)"


def robots_allows(robots_txt: str, url: str, base_url: str, user_agent: str = "*") -> bool:
    """按 robots.txt 规则判定 url 是否允许抓取（纯函数，无网络）。"""
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(robots_txt.splitlines())
    return rp.can_fetch(user_agent, url)


def fetch_robots_ok(url: str, timeout: int = 10) -> tuple[bool, str]:
    """抓取前检查：拉取 url 所在站点的 robots.txt 并判定。

    返回 (允许, 说明)。robots.txt 404/空视为全允许（标准行为）；
    网络错误时返回 (False, 原因)——保守处理，宁可放过不抓。
    """
    parts = urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        resp = requests.get(robots_url, timeout=timeout, headers={"User-Agent": UA})
    except requests.RequestException as exc:
        return False, f"robots.txt 获取失败（网络错误：{type(exc).__name__}），保守判定不允许"
    if resp.status_code == 404:
        return True, "robots.txt 不存在（404），视为允许"
    if resp.status_code != 200:
        return False, f"robots.txt HTTP {resp.status_code}，保守判定不允许"
    ok = robots_allows(resp.text, url, robots_url)
    note = "允许" if ok else "robots.txt 禁止抓取该路径"
    return ok, f"robots.txt 判定：{note}（来源 {robots_url}，正文前 200 字：{resp.text[:200]!r}）"


def polite_get(url: str, timeout: int = 10) -> requests.Response:
    """单次 GET：带声明式 UA，不重试（重试由调用方按指数退避决定）。"""
    return requests.get(url, timeout=timeout, headers={"User-Agent": UA})
```

- [ ] **Step 7: 运行测试通过**

```bash
cd /home/lancer/projects/pih/spikes && .venv/bin/python -m pytest _lib/test_probe.py -v
```

Expected: 6 passed

- [ ] **Step 8: 写 spikes/README.md**

`spikes/README.md`:

```markdown
# Spikes（EPIC-0 开发去风险）

设计规格：`docs/superpowers/specs/2026-08-25-sprint0-spikes-design.md`

## 目录

| 目录 | Spike | 状态 |
|---|---|---|
| `spk1-source-probe/` | SPK-1 信源可抓取性验证 | 待开始 |
| `spk2-extraction-probe/` | SPK-2 LLM 抽取准确率摸底 | 待开始 |
| `spk3-langgraph-e2e/` | SPK-3 LangGraph 端到端验证 | 待开始 |
| `_lib/` | 共享工具（robots 合规、LLM 客户端） | — |

## 纪律

1. 报告与脚本同目录；报告记录：做了什么、看到什么、结论、回写点。
2. Spike 代码是一次性学习品，**不演进为工程代码**——工程实现按架构文档另行落地。
3. 遵守 robots 协议；只取少量样本，不批量抓取，不登录，不绕过反爬。
4. 每个 Spike 完成即回写三件套（需求/架构/Backlog）与状态位。
5. 运行方式：`spikes/.venv/bin/python <脚本>`；测试 `spikes/.venv/bin/python -m pytest _lib/ -v`。
6. 密钥放 `spikes/.env`（已 gitignore），模板见 `.env.example`。
```

- [ ] **Step 9: 提交**

```bash
cd /home/lancer/projects/pih
git add spikes/ .gitignore
git commit -m "spike: Sprint 0 基座——venv、robots 合规抓取工具与 Spike 总览

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: SPK-1 纸面调研（8 类信源摸底卡）

**Files:**
- Create: `spikes/spk1-source-probe/README.md`（SPK-1 说明）
- Create: `spikes/spk1-source-probe/sources/00-template.md`
- Create: `spikes/spk1-source-probe/sources/01-ccma.md` 至 `08-qianlima.md`（8 张摸底卡）

**Interfaces:**
- Consumes: Task 1 的目录结构
- Produces: 8 张摸底卡（Task 3 据此选实抓对象；Task 4 回写附件 A 据此起草锁定清单）

- [ ] **Step 1: 写摸底卡模板**

`spikes/spk1-source-probe/sources/00-template.md`:

```markdown
# [信源名称]

- URL：
- 摸底卡编号：NN
- 调研日期：YYYY-MM-DD
- 调研方式：纸面（浏览器/文档查阅，不抓取）

## 摸底记录

| 字段 | 内容 |
|---|---|
| 类型 | RSS / 列表页 HTML / API / 变更监控候选 |
| 采集方式预判 | RSS 阅读器 / HTTP+解析 / changedetection.io / RSSHub |
| robots 允许度 | robots.txt 摘录 + 对目标路径的判定 |
| 反爬观察 | 登录墙 / 频控 / 验证码 / 字体混淆 / JS 渲染依赖 |
| 更新频率预估 | 日更 / 周更 / 不定期 |
| 历史内容可达性 | 存档/翻页情况，能否回溯 ≥3 个月 |
| 纸面结论 | 直抓 / 需适配 / 需变更监控 / 放弃 |
| 实抓候选 | 是/否 + 理由 |
```

- [ ] **Step 2: SPK-1 README**

`spikes/spk1-source-probe/README.md`:

```markdown
# SPK-1 信源可抓取性验证

目标：摸底附件 A 的 8 类初始信源，锁定 ≤10 信源清单。检验需求 §7"信源反爬/失效"风险。

- `sources/` 摸底卡（纸面，一源一卡）
- `probe/` 实抓脚本与记录（Task 3）
- `samples/` 样本正文存档（Task 3，供 SPK-2）
- `spk1-report.md` 汇总报告（Task 3/4）
```

- [ ] **Step 3: 逐一完成 8 张纸面卡**

8 类信源对应文件（对每张卡：浏览器访问该站点新闻/列表页，查 robots.txt `https://<域名>/robots.txt`，观察登录墙/JS 渲染依赖/翻页结构，填表）：

| 编号 | 文件 | 信源 | 起点线索 |
|---|---|---|---|
| 01 | `01-ccma.md` | CCMA 协会月报 | 中国工程机械工业协会官网 cncma.org |
| 02 | `02-oem-news.md` | 主机厂官网新闻页（三一/徐工任选 2–3 家） | sanygroup.com / xcmg.com 等 |
| 03 | `03-tiejia.md` | 铁甲网 | toujian.com 铁甲网新闻/资讯频道 |
| 04 | `04-d1cm.md` | 第一工程机械网 | d1cm.com |
| 05 | `05-lmjx.md` | 中国路面机械网 | lmjx.net |
| 06 | `06-khl.md` | KHL（国际） | khl.com |
| 07 | `07-cnipa.md` | 国家知识产权局专利公布 | cnipa.gov.cn 专利检索/公布公告 |
| 08 | `08-qianlima.md` | 千里马招标网 | qianlima.com |

**规则**（对应 Global Constraints"禁止编造数据"）：
- 每个字段写**实际观察到的事实**（"robots.txt 第 N 行 Disallow: /news/"这类），不确定就写"未确认+原因"；
- 站点访问失败（网络/DNS/超时）→ 如实记录错误与时间，纸面结论写"访问失败待复核"，**不猜**；
- 机器人可抓性判定不确定时标注"需实抓验证"并列入实抓候选理由。

**验证**：8 个文件都存在，每张卡 8 个字段无空缺（允许填"未确认"）。

- [ ] **Step 4: 提交**

```bash
cd /home/lancer/projects/pih
git add spikes/spk1-source-probe/
git commit -m "spike: SPK-1 纸面调研——8 类信源摸底卡

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: SPK-1 实抓（≤5 源）+ 样本存档

**Files:**
- Create: `spikes/spk1-source-probe/probe/fetch_samples.py`
- Create: `spikes/spk1-source-probe/probe/records/`（每源一份实抓记录 `.md`）
- Create: `spikes/spk1-source-probe/samples/`（正文存档）

**Interfaces:**
- Consumes: Task 1 `polite_get` / `fetch_robots_ok` / `UA`；Task 2 摸底卡实抓候选结论
- Produces: `samples/` 下 ≥15 条正文存档（`.md`，含来源 URL/抓取时间元信息）——Task 5 金答案与 Task 7 端到端的样本来源；实抓记录——Task 4 报告素材

- [ ] **Step 1: 定实抓对象**

从 Task 2 摸底卡选 **≤5 个**信源，覆盖：至少 1 个 RSS（或 RSSHub 候选）、1 个列表页 HTML 解析、1 个变更监控候选。选择与理由写入 `probe/records/00-selection.md`（3–5 句话即可）。

- [ ] **Step 2: 写实抓脚本**

`spikes/spk1-source-probe/probe/fetch_samples.py`:

```python
"""SPK-1 实抓脚本：对选定信源抓 1–3 页列表页 + 3–5 条详情，存档样本。

用法：python fetch_samples.py <信源名> <列表页URL> [<更多列表页URL>...]
纪律：robots 先行；同源请求间隔 ≥2s；每次运行打印逐请求日志。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from _lib.probe import fetch_robots_ok, polite_get

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "samples"
DETAIL_LIMIT = 5
REQUEST_GAP_SECONDS = 2.0


def extract_links(html: str, base_url: str) -> list[str]:
    """从列表页 HTML 提取详情链接（朴素正则，Spike 够用）。"""
    import re
    from urllib.parse import urljoin

    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html)
    seen, links = set(), []
    for h in hrefs:
        full = urljoin(base_url, h)
        if base_url.rstrip("/") in full and full not in seen and full.endswith((".html", ".htm", "")):
            seen.add(full)
            links.append(full)
    return links


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    source_name, list_urls = sys.argv[1], sys.argv[2:]
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    saved = 0
    for list_url in list_urls[:3]:
        ok, note = fetch_robots_ok(list_url)
        print(f"[robots] {list_url} -> {ok} ({note})")
        if not ok:
            print("  跳过（robots 不允许）——如实记录，不绕过")
            continue
        time.sleep(REQUEST_GAP_SECONDS)
        try:
            resp = polite_get(list_url)
        except Exception as exc:  # noqa: BLE001 —— Spike 记录一切网络异常
            print(f"  [失败] {type(exc).__name__}: {exc}")
            continue
        print(f"  [列表页] HTTP {resp.status_code}, {len(resp.text)} chars")
        if resp.status_code != 200:
            continue
        for link in extract_links(resp.text, list_url)[:DETAIL_LIMIT]:
            ok2, note2 = fetch_robots_ok(link)
            if not ok2:
                print(f"  [robots 禁止] {link}")
                continue
            time.sleep(REQUEST_GAP_SECONDS)
            try:
                detail = polite_get(link)
            except Exception as exc:  # noqa: BLE001
                print(f"  [失败] {link} {type(exc).__name__}: {exc}")
                continue
            if detail.status_code != 200:
                print(f"  [详情非200] {link} HTTP {detail.status_code}")
                continue
            fname = SAMPLES_DIR / f"{source_name}-{saved:02d}.md"
            fname.write_text(
                f"---\nsource: {source_name}\nurl: {link}\n"
                f"fetched_at: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n"
                f"http_status: {detail.status_code}\n---\n\n{detail.text}",
                encoding="utf-8",
            )
            saved += 1
            print(f"  [存档] {fname.name}")
    print(f"完成：{source_name} 存档 {saved} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: 逐源实抓并写记录**

对每个选定信源：

```bash
cd /home/lancer/projects/pih/spikes
.venv/bin/python spk1-source-probe/probe/fetch_samples.py <信源名> <列表页URL>
```

运行后写 `probe/records/<信源名>.md`，字段：HTTP 状态、页面结构摘要（列表页是服务端渲染还是 JS 注入——看返回 HTML 里有没有正文链接即可判断）、正文可提取性、反爬行为、抓取耗时、存档条数。

**边界重申**：robots 禁止 → 记录后跳过；某源连续失败 → 记录 3 次尝试即可停，换下一源；**总计实抓源 ≤5**。

- [ ] **Step 4: 核验样本库**

```bash
ls spikes/spk1-source-probe/samples/ | wc -l   # 期望 ≥15（5 源 × 3 条左右）
```

不足 15 条时：优先从已选源的更多列表页补充；仍不足则如实记录差额原因（如某源 robots 限制、JS 渲染拿不到正文），**不凑数、不伪造**。样本正文若为 JS 空壳（HTML 无正文文本），该源实抓记录写明"JS 渲染依赖，直抓不可行，建议 changedetection.io/浏览器渲染"，样本标记为不可用。

- [ ] **Step 5: 提交**

```bash
cd /home/lancer/projects/pih
git add spikes/spk1-source-probe/
git commit -m "spike: SPK-1 实抓——≤5 源试抓与样本存档

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: SPK-1 报告 + 回写三件套

**Files:**
- Create: `spikes/spk1-source-probe/spk1-report.md`
- Modify: `docs/Product Requirements.md`（§7 风险行、附件 A）
- Modify: `docs/Backlog.md`（SPK-1 状态位）

**Interfaces:**
- Consumes: Task 2 全部摸底卡、Task 3 实抓记录与样本库
- Produces: 锁定版 ≤10 信源清单（报告内呈现，附件 A 回写）——Task 5 选样依据

- [ ] **Step 1: 写 spk1-report.md**

结构（每节写实际数据）：

```markdown
# SPK-1 报告：信源可抓取性验证

- 日期：
- 结论一句话：（如"8 类中 N 类可直抓/适配，锁定 M 信源，反爬风险等级下调/维持"）

## 1. 纸面摸底汇总

（8 类信源表格：名称 / 类型 / 纸面结论 / 实抓候选）

## 2. 实抓结果

（每源：HTTP 表现 / 正文可提取性 / 反爬行为 / 耗时）

## 3. 锁定信源清单（≤10）

| # | 信源 | 层级 | 采集方式 | 频率建议 |
|---|---|---|---|---|

## 4. 结论与回写点

- 需求 §7"信源反爬/失效"风险行：更新为（实测后的表述）
- 附件 A 初始信源：替换为锁定版
- Backlog SPK-1：待开发 → 已交付
```

- [ ] **Step 2: 回写需求文档**

`docs/Product Requirements.md`：
- §7 风险表"信源反爬/失效"行：按实测结论改写缓解列（如"实测 5 源中 N 源可直抓"）；
- 附件 A"初始信源"段：替换为锁定清单（保持原有格式：信源 + 采集方式括注）；
- 文档头 `日期` 改今天、`变更` 追加一句"附件 A 信源清单经 SPK-1 实测锁定"。**版本号不动**（Task 8 统一 bump）。

- [ ] **Step 3: 回写 Backlog**

`docs/Backlog.md` EPIC-0 下 `SPK-1（待开发）` → `SPK-1（已交付）`。

- [ ] **Step 4: 提交**

```bash
cd /home/lancer/projects/pih
git add spikes/spk1-source-probe/spk1-report.md docs/Product\ Requirements.md docs/Backlog.md
git commit -m "spike: SPK-1 报告与三件套回写（信源清单锁定）

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: SPK-2 金答案集（人工标注门）

**Files:**
- Create: `spikes/spk2-extraction-probe/README.md`
- Create: `spikes/spk2-extraction-probe/golden/make_dataset.py`
- Create: `spikes/spk2-extraction-probe/golden/samples.json`（脚本产出）
- Create: `spikes/spk2-extraction-probe/golden/golden.jsonl`（脚本产出后人工编辑）
- Test: `spikes/spk2-extraction-probe/golden/test_make_dataset.py`

**Interfaces:**
- Consumes: `spikes/spk1-source-probe/samples/*.md`（Task 3 存档）
- Produces:
  - `golden/samples.json`：`[{"id": "S01", "source": "铁甲网", "url": "...", "level": "L3", "text": "..."}]`——text 为清洗后正文
  - `golden/golden.jsonl`：每行 `{"id": "S01", "主体": "...", "事件类型": "...", "事实描述": "...", "推断与判断": "...", "标签": [...], "量化参数": {...}}`
  - `events` 枚举常量（Task 6/7 复用）：`["新品发布", "功能迭代", "专利公开", "中标落地", "组织人事", "价格变动", "标准动态", "其他"]`
  - 标签词表来源：需求附件 A 初始标签树（无人化作业/远程遥控/3D 引导与机控/电动化/智能辅助施工/场景/核心零部件及其子项）

- [ ] **Step 1: 写 SPK-2 README**

`spikes/spk2-extraction-probe/README.md`:

```markdown
# SPK-2 LLM 抽取准确率摸底

目标：用 SPK-1 真实样本试抽，评估按需求 §4.4 schema 抽取的准确率与提示词工作量。
检验需求 §7"LLM 抽取错误"风险。

- `golden/` 样本集与金答案（人工标注）
- `run_extraction.py` 试抽脚本（Task 6）
- `evaluate.py` 评分脚本（Task 6）
- `spk2-report.md` 报告（Task 6）
```

- [ ] **Step 2: 写失败测试**

`spikes/spk2-extraction-probe/golden/test_make_dataset.py`:

```python
import json
from pathlib import Path

HERE = Path(__file__).parent
SAMPLES_MD = HERE.parent.parent / "spk1-source-probe" / "samples"


def _make(tmp_path, monkeypatch, content: str) -> Path:
    src = tmp_path / "tiejia-00.md"
    src.write_text(content, encoding="utf-8")
    out = tmp_path / "samples.json"
    monkeypatch.setattr("sys.argv", ["make_dataset.py", str(tmp_path), str(out)])
    import golden.make_dataset as m
    import importlib
    importlib.reload(m)
    m.main()
    return out


def test_extracts_frontmatter_and_body(tmp_path, monkeypatch):
    content = (
        "---\nsource: tiejia\nurl: https://example.com/a\n"
        "fetched_at: 2026-08-25T10:00:00+0800\nhttp_status: 200\n---\n\n"
        "<html><body>三一发布无人挖掘机</body></html>"
    )
    out = _make(tmp_path, monkeypatch, content)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["id"] == "S01"
    assert data[0]["source"] == "tiejia"
    assert data[0]["url"] == "https://example.com/a"
    assert "无人挖掘机" in data[0]["text"]


def test_strips_html_tags(tmp_path, monkeypatch):
    content = (
        "---\nsource: x\nurl: https://e.com/b\nfetched_at: t\nhttp_status: 200\n---\n\n"
        "<p>遥控挖掘机</p><script>ignore()</script>"
    )
    out = _make(tmp_path, monkeypatch, content)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "遥控挖掘机" in data[0]["text"]
    assert "ignore" not in data[0]["text"]
```

- [ ] **Step 3: 运行确认失败**

```bash
cd /home/lancer/projects/pih/spikes && .venv/bin/python -m pytest spk2-extraction-probe/golden/test_make_dataset.py -v
```

Expected: ERROR（模块不存在）

- [ ] **Step 4: 实现 make_dataset.py**

`spikes/spk2-extraction-probe/golden/make_dataset.py`:

```python
"""把 SPK-1 样本存档转成 samples.json（清洗 HTML、抽 frontmatter）。

用法：.venv/bin/python spk2-extraction-probe/golden/make_dataset.py [samples目录] [输出路径]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DEFAULT_SRC = Path(__file__).resolve().parents[2] / "spk1-source-probe" / "samples"
DEFAULT_OUT = Path(__file__).resolve().parent / "samples.json"

# 来源层级映射（Spike 简版：按信源名人工映射，锁定清单为准）
LEVEL_BY_SOURCE: dict[str, str] = {}  # Task 6 前按锁定清单填写，如 {"tiejia": "L3"}


def strip_html(raw: str) -> str:
    txt = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip()


def parse_frontmatter(raw: str) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", raw, flags=re.S)
    if not m:
        return {}, raw
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, m.group(2)


def main() -> int:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SRC
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT
    records = []
    for i, f in enumerate(sorted(src.glob("*.md")), start=1):
        meta, body = parse_frontmatter(f.read_text(encoding="utf-8"))
        text = strip_html(body)
        records.append(
            {
                "id": f"S{i:02d}",
                "source": meta.get("source", f.stem),
                "url": meta.get("url", ""),
                "level": LEVEL_BY_SOURCE.get(meta.get("source", ""), "未知"),
                "text": text,
            }
        )
    out.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(records)} 条 -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

（在 `spikes/spk2-extraction-probe/` 下建空 `__init__.py` 与 `golden/__init__.py`，使 pytest 可导入。）

- [ ] **Step 5: 运行测试通过**

```bash
cd /home/lancer/projects/pih/spikes && .venv/bin/python -m pytest spk2-extraction-probe/golden/test_make_dataset.py -v
```

Expected: 2 passed

- [ ] **Step 6: 生成数据集并填层级**

```bash
cd /home/lancer/projects/pih/spikes
.venv/bin/python spk2-extraction-probe/golden/make_dataset.py
```

然后编辑 `LEVEL_BY_SOURCE`，按 Task 4 锁定清单填层级映射，重跑一次使 `level` 字段生效。

- [ ] **Step 7: 人工标注金答案（用户门）**

从 `samples.json` 选 20–30 条（覆盖不同层级与内容形态），逐条写 `golden/golden.jsonl`：

```
{"id": "S01", "主体": "三一重工 SY375 遥控版", "事件类型": "新品发布", "事实描述": "……含量化参数", "推断与判断": "……（依据：……）", "标签": ["无人化作业", "远程遥控"], "量化参数": {"遥控距离": "1km"}}
```

**此步必须请用户共同完成**——金答案是自标自评的基准，标注质量决定 SPK-2 结论可信度。执行到此处时：向用户展示样本与字段说明（主体=公司+产品线；事件类型 8 选 1；事实描述只写客观陈述；推断必须带"依据："），由用户逐条确认或修订。标注完成后在 `golden/README.md` 记一句"金答案于 YYYY-MM-DD 由用户确认"。

- [ ] **Step 8: 核验并提交**

```bash
cd /home/lancer/projects/pih/spikes
.venv/bin/python -c "
import json, pathlib
s = json.load(open('spk2-extraction-probe/golden/samples.json'))
g = [json.loads(l) for l in open('spk2-extraction-probe/golden/golden.jsonl') if l.strip()]
ids_s = {r['id'] for r in s}; ids_g = {r['id'] for r in g}
assert ids_g <= ids_s, f'金答案含未知id: {ids_g - ids_s}'
assert 20 <= len(g) <= 30, f'金答案 {len(g)} 条，不在 20–30 区间'
"
```

Expected: 无输出（通过）

```bash
cd /home/lancer/projects/pih
git add spikes/spk2-extraction-probe/
git commit -m "spike: SPK-2 金答案集——样本清洗与人工标注

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: SPK-2 试抽 + 评分 + 报告 + 回写

**Files:**
- Create: `spikes/_lib/llm.py`
- Test: `spikes/_lib/test_llm.py`
- Create: `spikes/spk2-extraction-probe/run_extraction.py`
- Create: `spikes/spk2-extraction-probe/evaluate.py`
- Test: `spikes/spk2-extraction-probe/test_evaluate.py`
- Create: `spikes/spk2-extraction-probe/spk2-report.md`
- Create: `spikes/spk2-extraction-probe/prompt_v1.txt`（及迭代版本）
- Modify: `docs/Product Requirements.md`、`docs/Architecture.md`、`docs/Backlog.md`

**Interfaces:**
- Consumes: Task 5 `samples.json` / `golden.jsonl` / 事件类型枚举 / 标签词表；Task 1 venv
- Produces:
  - `spikes/_lib/llm.py`：
    - `class LLMError(Exception)`
    - `chat_json(messages: list[dict], model_env: str = "PIH_LLM_LARGE_MODEL", max_retries: int = 3) -> tuple[dict, dict]` —— 返回 `(解析后的 JSON 对象, usage 统计 {"prompt_tokens", "completion_tokens", "retries"})`；温度 0.0；429/5xx 线性退避；非 JSON 输出视为可重试错误
    - `load_env() -> None` —— 从 `spikes/.env` 读环境变量（python-dotenv）
  - `evaluate.py`：
    - `score_item(golden: dict, pred: dict) -> dict` —— 返回逐字段判定 `{"主体": "正确"|"错误"|"漏抽", ...}`
    - `summarize(per_item: list[dict], usage_rows: list[dict]) -> dict` —— 汇总 5 项指标
  - 试抽结果 `results.json`：`[{"id", "pred": {...}, "retries", "prompt_tokens", "completion_tokens", "elapsed_ms"}]`

- [ ] **Step 1: 写 LLM 客户端失败测试**

`spikes/_lib/test_llm.py`:

```python
import _lib.llm as llm


def test_load_env_reads_spike_env(monkeypatch, tmp_path):
    env = tmp_path / ".env"
    env.write_text("PIH_LLM_BASE_URL=https://x/v1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PIH_LLM_BASE_URL", raising=False)
    # load_env 只在文件存在时加载，不覆盖已有环境变量
    llm.load_env()
    import os
    assert os.environ.get("PIH_LLM_BASE_URL") == "https://x/v1"
```

（`chat_json` 的网络路径不在单测覆盖范围——Spike 以真实调用验证，见 Step 4。）

- [ ] **Step 2: 实现 llm.py**

`spikes/_lib/llm.py`:

```python
"""OpenAI 兼容 LLM 客户端（Spike 版）：温度 0、结构化 JSON、线性退避。"""
from __future__ import annotations

import json
import os
import time

from openai import OpenAI

from _lib.probe import UA  # noqa: F401  —— 统一 UA 出处（部分端点日志用）


class LLMError(Exception):
    """重试耗尽或输出不可解析。"""


def load_env() -> None:
    """加载 spikes/.env（存在时）；不覆盖已设环境变量。"""
    from pathlib import Path
    from dotenv import load_dotenv

    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


def chat_json(
    messages: list[dict],
    model_env: str = "PIH_LLM_LARGE_MODEL",
    max_retries: int = 3,
) -> tuple[dict, dict]:
    """调用 OpenAI 兼容 chat completions，要求 JSON 输出并解析。

    返回 (解析后的 dict, usage{"prompt_tokens","completion_tokens","retries"})。
    429/5xx/JSON 解析失败 → 线性退避重试；耗尽抛 LLMError。
    """
    load_env()
    base = os.environ.get("PIH_LLM_BASE_URL")
    key = os.environ.get("PIH_LLM_API_KEY")
    model = os.environ.get(model_env)
    if not (base and key and model):
        raise LLMError(
            f"缺少环境变量（需要 PIH_LLM_BASE_URL/PIH_LLM_API_KEY/{model_env}）。"
            "请复制 spikes/.env.example 为 spikes/.env 并填写。"
        )
    client = OpenAI(base_url=base, api_key=key)
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "retries": 0}
    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content or ""
            usage["prompt_tokens"] += resp.usage.prompt_tokens if resp.usage else 0
            usage["completion_tokens"] += resp.usage.completion_tokens if resp.usage else 0
            return json.loads(content), usage
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            usage["retries"] = attempt + 1
            if attempt < max_retries:
                time.sleep(2 * (attempt + 1))
    raise LLMError(f"重试耗尽：{last_err}") from last_err
```

- [ ] **Step 3: 运行 LLM 测试**

```bash
cd /home/lancer/projects/pih/spikes && .venv/bin/python -m pytest _lib/test_llm.py -v
```

Expected: 1 passed

- [ ] **Step 4: 写试抽脚本与提示词 v1**

`spikes/spk2-extraction-probe/prompt_v1.txt`（系统提示词，`{事件类型}` 与 `{标签树}` 为占位由脚本填充）:

```
你是竞品情报抽取器。从给定正文中抽取结构化情报，输出 JSON：
{"主体": "公司+产品线（如无具体产品线只写公司）", "事件类型": "从以下枚举选一：<事件类型>",
 "事实描述": "客观事实陈述，含量化参数原文数字", "推断与判断": "正文可支撑的推断，必须以'依据：'开头；无推断则留空字符串",
 "标签": ["从以下标签树选 0–4 个：<标签树>"], "量化参数": {"参数名": "数值+单位"}}

规则：只依据正文，不引入外部知识；正文与领域无关时事件类型选"其他"、标签为空数组。
```

`spikes/spk2-extraction-probe/run_extraction.py`:

```python
"""SPK-2 试抽：对金答案集逐条抽取，落 results.json。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from _lib.llm import LLMError, chat_json  # noqa: E402

EVENTS = ["新品发布", "功能迭代", "专利公开", "中标落地", "组织人事", "价格变动", "标准动态", "其他"]
TAGS = "无人化作业/远程遥控/3D引导与机控/电动化/智能辅助施工/场景（矿山·港口·市政）/核心零部件（电液控制·传感器）"

SCHEMA_KEYS = ["主体", "事件类型", "事实描述", "推断与判断", "标签", "量化参数"]


def build_prompt(text: str) -> list[dict]:
    system = (HERE / "prompt_v1.txt").read_text(encoding="utf-8")
    system = system.replace("<事件类型>", "/".join(EVENTS)).replace("<标签树>", TAGS)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": text[:6000]},
    ]


def validate(pred: dict) -> bool:
    return isinstance(pred, dict) and all(k in pred for k in SCHEMA_KEYS)


def main() -> int:
    golden = [json.loads(l) for l in (HERE / "golden" / "golden.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    samples = {r["id"]: r for r in json.loads((HERE / "golden" / "samples.json").read_text(encoding="utf-8"))}
    results = []
    for g in golden:
        text = samples[g["id"]]["text"]
        t0 = time.monotonic()
        try:
            pred, usage = chat_json(build_prompt(text))
            if not validate(pred):
                pred, usage2 = chat_json(build_prompt(text) + [{"role": "user", "content": "输出缺字段，严格按 schema 重出 JSON"}])
                usage = {k: usage[k] + usage2[k] for k in usage}
            elapsed = int((time.monotonic() - t0) * 1000)
            results.append({"id": g["id"], "pred": pred, **usage, "elapsed_ms": elapsed})
            print(f"[ok] {g['id']} retries={usage['retries']} {elapsed}ms")
        except LLMError as exc:
            results.append({"id": g["id"], "pred": None, "error": str(exc), "elapsed_ms": int((time.monotonic() - t0) * 1000)})
            print(f"[fail] {g['id']}: {exc}")
        time.sleep(0.3)
    out = HERE / "results.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for r in results if r.get("pred"))
    print(f"完成 {ok}/{len(results)} -> {out}")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: 首轮试抽**

前置：`spikes/.env` 已配好（用户在 Task 5 前后提供均可；缺失时脚本会给出明确提示并停止——此时向用户要配置，不模拟）。

```bash
cd /home/lancer/projects/pih/spikes
.venv/bin/python spk2-extraction-probe/run_extraction.py
```

Expected: 每条打印 `[ok]`/`[fail]` 与耗时；`results.json` 生成。

- [ ] **Step 6: 写评分脚本（TDD）**

先写失败测试 `spikes/spk2-extraction-probe/test_evaluate.py`:

```python
from spk2 import evaluate  # 若作包导入报错，用 sys.path 注入目录后 import evaluate


def test_score_item_correct_partial_missing():
    golden = {"id": "S01", "主体": "三一 SY375", "事件类型": "新品发布", "事实描述": "x", "标签": ["远程遥控"], "推断与判断": "依据：y", "量化参数": {}}
    pred = {"主体": "三一 SY375", "事件类型": "功能迭代", "事实描述": "x", "标签": ["远程遥控"], "推断与判断": "", "量化参数": {}}
    s = evaluate.score_item(golden, pred)
    assert s["主体"] == "正确"
    assert s["事件类型"] == "错误"
    assert s["推断与判断"] == "漏抽"   # 金答案有推断而预测留空


def test_summarize_metrics():
    per = [
        {"主体": "正确", "事件类型": "正确", "事实描述": "正确", "标签": "正确", "推断与判断": "正确"},
        {"主体": "错误", "事件类型": "错误", "事实描述": "正确", "标签": "漏抽", "推断与判断": "正确"},
    ]
    usage = [
        {"retries": 0, "prompt_tokens": 100, "completion_tokens": 50, "elapsed_ms": 1000},
        {"retries": 2, "prompt_tokens": 150, "completion_tokens": 60, "elapsed_ms": 1500},
    ]
    m = evaluate.summarize(per, usage)
    # 字段准确率口径：KEY_FIELDS(主体/事件类型/事实描述/标签) 中非"跳过"的判定，
    # 本例 8 格中 5 格"正确"（行1×4 + 行2 事实描述）→ 5/8 = 0.625
    assert m["字段准确率"] == 0.625
    assert m["枚举命中率"] == 0.5       # 2 条中 1 条事件类型正确
    assert m["重问率"] == 0.5           # 1/2 条 retries>=1（含 schema 补问）
    assert m["平均耗时ms"] == 1250
```

（注：`字段准确率` 口见实现注释——KEY_FIELDS 四字段中非"跳过"判定的"正确"占比；`重问率` = retries ≥1 的条目占比，含 schema 补问。）

再实现 `spikes/spk2-extraction-probe/evaluate.py`:

```python
"""SPK-2 评分：字段级判定与指标汇总。"""
from __future__ import annotations

KEY_FIELDS = ["主体", "事件类型", "事实描述", "标签"]


def _norm(s: str) -> str:
    return "".join(s.split()).lower()


def score_item(golden: dict, pred: dict) -> dict:
    out = {}
    for f in ["主体", "事件类型", "事实描述", "推断与判断"]:
        g, p = golden.get(f, ""), (pred or {}).get(f, "")
        if not g:
            out[f] = "跳过"          # 金答案本身无该内容
        elif not p:
            out[f] = "漏抽"
        else:
            out[f] = "正确" if _norm(g) == _norm(p) else "错误"
    gt, pt = set(golden.get("标签", [])), set((pred or {}).get("标签", []) or [])
    if not gt:
        out["标签"] = "跳过" if not pt else "错误"
    else:
        overlap = len(gt & pt) / len(gt | pt) if gt | pt else 0
        out["标签"] = "正确" if overlap >= 0.5 else "错误"
    gp = golden.get("量化参数", {})
    if gp:
        hit = sum(1 for k in gp if k in (pred or {}).get("量化参数", {}))
        out["量化参数"] = "正确" if gp and hit / len(gp) >= 0.5 else "错误"
    else:
        out["量化参数"] = "跳过"
    return out


def summarize(per_item: list[dict], usage_rows: list[dict]) -> dict:
    total = correct = 0
    for row in per_item:
        for f in KEY_FIELDS:
            if row.get(f) != "跳过":
                total += 1
                correct += row.get(f) == "正确"
    n = len(per_item)
    sep_ok = sum(1 for r in per_item if r.get("推断与判断") in ("正确", "跳过"))
    usage_cols = ["retries", "prompt_tokens", "completion_tokens", "elapsed_ms"]
    avg = {c: (sum(u.get(c, 0) for u in usage_rows) / len(usage_rows) if usage_rows else 0) for c in usage_cols}
    return {
        "字段准确率": correct / total if total else 0,
        "枚举命中率": sum(1 for r in per_item if r.get("事件类型") == "正确") / n if n else 0,
        "事实推断分离合格率": sep_ok / n if n else 0,
        "重问率": sum(1 for u in usage_rows if u.get("retries", 0) >= 1) / len(usage_rows) if usage_rows else 0,
        "平均耗时ms": avg["elapsed_ms"],
        "平均prompt_tokens": avg["prompt_tokens"],
        "平均completion_tokens": avg["completion_tokens"],
    }
```

同时按需修 `test_summarize_metrics` 中的期望值，使断言与实现口径一致（字段准确率分子=6：行1 全对4 + 行2 事实描述1 + 标签列另行计——见代码：KEY_FIELDS 含标签，行2 标签=漏抽非跳过，计入分母；故 5/8=0.625）。

运行：

```bash
cd /home/lancer/projects/pih/spikes && .venv/bin/python -m pytest spk2-extraction-probe/test_evaluate.py -v
```

Expected: PASS（字段准确率 5/8=0.625；主体/事件类型/事实描述/标签 = KEY_FIELDS，"跳过"格不计分母）

- [ ] **Step 7: 评分 + 迭代提示词**

```bash
cd /home/lancer/projects/pih/spikes
.venv/bin/python - <<'EOF'
import json, sys
sys.path.insert(0, "spk2-extraction-probe")
import evaluate
golden = {json.loads(l)["id"]: json.loads(l) for l in open("spk2-extraction-probe/golden/golden.jsonl") if l.strip()}
results = json.load(open("spk2-extraction-probe/results.json"))
per = [dict(id=r["id"], **evaluate.score_item(golden[r["id"]], r.get("pred") or {})) for r in results]
usage = [r for r in results if r.get("pred")]
print(json.dumps(evaluate.summarize(per, usage), ensure_ascii=False, indent=2))
json.dump(per, open("spk2-extraction-probe/per_item.json", "w"), ensure_ascii=False, indent=2)
EOF
```

迭代循环：字段准确率 <80% → 分析 per_item 错误模式 → 修 `prompt_v*.txt` → 重跑 `run_extraction.py` + 评分。达到 ≥80% 或连续 2 轮无改善即停，记录轮次（v1/v2/...）与各轮指标。

- [ ] **Step 8: 写 spk2-report.md 并回写**

报告结构：结论一句话 / 指标表（5 项 + token 成本折算）/ 逐字段混淆与典型错误案例 ≥3 个 / 提示词迭代轮次记录 / 回写点。

回写：
- 需求 §7"LLM 抽取错误"风险行（按实测表述）；
- 架构 §9.2：成本公式处补一行实测值（"SPK-2 实测每条平均 X prompt + Y completion tokens"）；
- Backlog SPK-2 → 已交付；
- 需求/架构文档头 `日期`/`变更` 更新（版本号留给 Task 8）。

- [ ] **Step 9: 提交**

```bash
cd /home/lancer/projects/pih
git add spikes/ docs/Product\ Requirements.md docs/Architecture.md docs/Backlog.md
git commit -m "spike: SPK-2 试抽评估报告与三件套回写

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: SPK-3 LangGraph 端到端 + 报告 + 回写

**Files:**
- Create: `spikes/spk3-langgraph-e2e/graph.py`
- Create: `spikes/spk3-langgraph-e2e/README.md`
- Create: `spikes/spk3-langgraph-e2e/run_e2e.py`
- Create: `spikes/spk3-langgraph-e2e/spk3-report.md`
- Modify: `docs/adr/ADR-004-流水线编排代码化.md`、`docs/Architecture.md`（视结论）、`docs/Backlog.md`

**Interfaces:**
- Consumes: Task 6 `_lib.llm.chat_json`（`model_env` 参数支持 `"PIH_LLM_SMALL_MODEL"`）、`spk2-extraction-probe/prompt_v*.txt` 终版、`spk2-extraction-probe/golden/samples.json`（≥20 条全量）
- Produces: `spk3-langgraph-e2e/e2e_results.json`：`[{"id", "kept": bool, "pred"|"error", "node_timings_ms": {"prefilter", "extract", "validate"}, "elapsed_ms"}]`

- [ ] **Step 1: 写 SPK-3 README**

`spikes/spk3-langgraph-e2e/README.md`:

```markdown
# SPK-3 LangGraph 端到端验证

目标：用 SPK-2 提示词在 LangGraph 上跑通 粗筛(小模型) → 抽取(大模型) → schema 校验(重问≤3)。
决策语境：ADR-004 后果节。

- `graph.py` 三节点图定义
- `run_e2e.py` 批量执行与计时
- `spk3-report.md` 报告
```

- [ ] **Step 2: 写 graph.py（三节点）**

`spikes/spk3-langgraph-e2e/graph.py`:

```python
"""SPK-3：粗筛 → 抽取 → 校验 三节点 LangGraph 图。

节点为独立函数、显式状态传递（TypedDict），验证架构 §4 模块切分。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, StateGraph

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from _lib.llm import chat_json  # noqa: E402

EVENTS = ["新品发布", "功能迭代", "专利公开", "中标落地", "组织人事", "价格变动", "标准动态", "其他"]
SCHEMA_KEYS = ["主体", "事件类型", "事实描述", "推断与判断", "标签", "量化参数"]


class ItemState(TypedDict, total=False):
    id: str
    text: str
    kept: bool
    pred: dict | None
    retries: int
    node_timings_ms: dict


def _tick(t0: list[float]) -> int:
    import time
    return int((time.monotonic() - t0[0]) * 1000)


def node_prefilter(state: ItemState) -> ItemState:
    """粗筛：小模型二分类（领域相关 keep / 无关 drop）。"""
    import time

    t0 = [time.monotonic()]
    msgs = [
        {"role": "system", "content": "判断正文是否与工程机械行业情报相关（产品/技术/市场/组织动态）。输出 JSON：{\"relevant\": true|false}"},
        {"role": "user", "content": state["text"][:3000]},
    ]
    try:
        out, _ = chat_json(msgs, model_env="PIH_LLM_SMALL_MODEL")
        kept = bool(out.get("relevant"))
    except Exception:  # noqa: BLE001 —— 粗筛失败按保留处理，走人工兜底
        kept = True
    return {"kept": kept, "node_timings_ms": {"prefilter": _tick(t0)}}


def node_extract(state: ItemState) -> ItemState:
    """结构化抽取：大模型 + SPK-2 终版提示词。"""
    import time

    t0 = [time.monotonic()]
    prompt_file = sorted(HERE.parent.glob("spk2-extraction-probe/prompt_v*.txt"))[-1]
    system = prompt_file.read_text(encoding="utf-8")
    system = system.replace("<事件类型>", "/".join(EVENTS)).replace("<标签树>", "见 SPK-2 词表")
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": state["text"][:6000]}]
    pred, usage = chat_json(msgs, model_env="PIH_LLM_LARGE_MODEL")
    timings = dict(state.get("node_timings_ms", {}))
    timings["extract"] = _tick(t0)
    return {"pred": pred, "retries": usage["retries"], "node_timings_ms": timings}


def node_validate(state: ItemState) -> ItemState:
    """schema 校验：缺字段重问 ≤3。"""
    import time

    t0 = [time.monotonic()]
    pred, retries = state.get("pred"), state.get("retries", 0)
    while (pred is None or any(k not in pred for k in SCHEMA_KEYS)) and retries < 3:
        msgs = [
            {"role": "system", "content": "严格输出含以下键的 JSON：" + ", ".join(SCHEMA_KEYS)},
            {"role": "user", "content": state["text"][:6000]},
        ]
        pred, usage = chat_json(msgs, model_env="PIH_LLM_LARGE_MODEL")
        retries += usage["retries"] + 1
    timings = dict(state.get("node_timings_ms", {}))
    timings["validate"] = _tick(t0)
    ok = pred is not None and all(k in pred for k in SCHEMA_KEYS)
    return {"pred": pred if ok else None, "retries": retries, "node_timings_ms": timings}


def _route_after_prefilter(state: ItemState) -> str:
    return "extract" if state.get("kept") else END


def build_graph():
    g = StateGraph(ItemState)
    g.add_node("prefilter", node_prefilter)
    g.add_node("extract", node_extract)
    g.add_node("validate", node_validate)
    g.set_conditional_entry_point("prefilter", _route_after_prefilter)
    g.add_edge("extract", "validate")
    g.add_edge("validate", END)
    return g.compile()
```

- [ ] **Step 3: 写 run_e2e.py**

`spikes/spk3-langgraph-e2e/run_e2e.py`:

```python
"""SPK-3 端到端执行：对 samples.json 全量跑图，落 e2e_results.json。"""
from __future__ import annotations

import json
import time
from pathlib import Path

from graph import build_graph

HERE = Path(__file__).resolve().parent
SAMPLES = HERE.parent / "spk2-extraction-probe" / "golden" / "samples.json"


def main() -> int:
    app = build_graph()
    samples = json.loads(SAMPLES.read_text(encoding="utf-8"))
    rows = []
    for s in samples:
        t0 = time.monotonic()
        try:
            final = app.invoke({"id": s["id"], "text": s["text"]})
            rows.append({
                "id": s["id"],
                "kept": final.get("kept"),
                "pred": final.get("pred"),
                "node_timings_ms": final.get("node_timings_ms", {}),
                "elapsed_ms": int((time.monotonic() - t0) * 1000),
            })
            print(f"[ok] {s['id']} kept={final.get('kept')} {rows[-1]['elapsed_ms']}ms")
        except Exception as exc:  # noqa: BLE001
            rows.append({"id": s["id"], "error": f"{type(exc).__name__}: {exc}", "elapsed_ms": int((time.monotonic() - t0) * 1000)})
            print(f"[fail] {s['id']}: {exc}")
        time.sleep(0.3)
    out = HERE / "e2e_results.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{sum(1 for r in rows if 'error' not in r)}/{len(rows)} -> {out}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
```

- [ ] **Step 4: 冒烟（1 条）后全量跑**

```bash
cd /home/lancer/projects/pih/spikes
.venv/bin/python - <<'EOF'
import json, sys
sys.path.insert(0, "spk3-langgraph-e2e")
from graph import build_graph
s = json.load(open("spk2-extraction-probe/golden/samples.json"))[0]
print(build_graph().invoke({"id": s["id"], "text": s["text"][:2000]}))
EOF
```

Expected: 打印含 `kept`/`pred` 的 dict。冒烟通过后：

```bash
.venv/bin/python spk3-langgraph-e2e/run_e2e.py
```

Expected: 全量 ≥20 条执行，`e2e_results.json` 生成。

- [ ] **Step 5: 写 spk3-report.md 并回写**

报告结构：结论一句话（ADR-004 维持/修订/换方案——必答）/ 端到端成功率与各节点延迟分布（从 e2e_results.json 统计 min/median/max）/ 粗筛表现（kept 比例 vs 样本真实相关性）/ 重问行为 / 开发摩擦点记录 / 回写点。

回写：
- `docs/adr/ADR-004-流水线编排代码化.md` 后果节：补一段"SPK-3 实测（日期）：成功率/延迟/摩擦点"；
- 架构 §5.1 与实际流程不符时修订（如校验重问位置）；
- Backlog SPK-3 → 已交付。

- [ ] **Step 6: 提交**

```bash
cd /home/lancer/projects/pih
git add spikes/spk3-langgraph-e2e/ docs/adr/ADR-004-流水线编排代码化.md docs/Architecture.md docs/Backlog.md
git commit -m "spike: SPK-3 LangGraph 端到端报告与回写

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: Sprint 0 收尾（版本 bump + 完成定义核查）

**Files:**
- Modify: `docs/Product Requirements.md`、`docs/Architecture.md`、`docs/Backlog.md`（版本号与 changelog）
- Modify: `spikes/README.md`（状态表）

**Interfaces:**
- Consumes: Task 4/6/7 的全部回写
- Produces: 三件套版本 bump（需求 V1.0、架构 V0.9、Backlog V0.9）

- [ ] **Step 1: 核查完成定义**

逐项检查（规格 §7）：

```bash
cd /home/lancer/projects/pih
ls spikes/spk1-source-probe/spk1-report.md spikes/spk2-extraction-probe/spk2-report.md spikes/spk3-langgraph-e2e/spk3-report.md
grep -c "已交付" docs/Backlog.md          # SPK-1/2/3 三处
grep -n "SPK-" docs/Backlog.md | head
```

Expected: 三份报告存在；SPK-1/2/3 均为"已交付"。**注意**：法务行动项若未完成（用户现实中推进），如实保留原状并在 Step 3 备注——不冒充完成。

- [ ] **Step 2: 版本 bump 与 changelog**

- 需求：V0.9 → **V1.0**，`变更` 写"Sprint 0 回写：附件 A 信源锁定（SPK-1）、§7 风险行实测更新（SPK-1/2）、§9.2 成本实测（SPK-2）"
- 架构：V0.8 → **V0.9**，`变更` 写"Sprint 0 回写：§9.2 成本实测值、ADR-004 实测补充（SPK-3）"
- Backlog：V0.8 → **V0.9**，`变更` 写"Sprint 0 状态位更新（SPK-1/2/3 已交付）"
- `spikes/README.md` 状态表：三个 Spike 改"已完成"

- [ ] **Step 3: 提交**

```bash
cd /home/lancer/projects/pih
git add docs/ spikes/README.md
git commit -m "docs: Sprint 0 收尾——三件套版本 bump 与完成定义核查

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## 附：执行注意事项（对 agentic worker）

1. **网络与密钥门**：Task 3 实抓与 Task 6/7 LLM 调用前，若网络不通或 `.env` 缺失——按脚本提示补齐后重试；两次补救仍失败 → 停下向用户报告环境状况，**绝不编造数据继续**。
2. **用户协作点**：Task 5 Step 7 金答案标注必须与用户共同完成（标注质量 = SPK-2 结论可信度）；法务行动项全程是用户现实事务，计划内只做回写占位。
3. **串行纪律**：任务按编号执行，不并行——SPK-2 依赖 SPK-1 样本，SPK-3 依赖 SPK-2 提示词。
4. **探索性偏差**：实抓脚本对真实网站的行为有不确定性——遇到摸底卡未预见的情况（跳转、cookie 墙），如实记录进实抓记录，按"保守跳过"处理，不为跑通而破坏纪律。
