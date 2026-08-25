# SPK-3 LangGraph 端到端验证报告

- 日期：2026-08-25
- 模型：粗筛=MiniMax-M2.7（小）、抽取=MiniMax-M3（大，OpenAI 兼容端点）
- 样本：25 条金答案集（spk2-extraction-probe/golden/samples.json，全量）
- 提示词：SPK-2 终版 prompt_v3.txt（glob 取最后一个 `prompt_v*.txt`）
- LangGraph 版本：1.2.11
- 代码：`spikes/spk3-langgraph-e2e/graph.py`、`run_e2e.py`

## 决策结论（必答）

**ADR-004 维持**。LangGraph 1.2.11 + MiniMax 端点端到端跑通 25 条样本，成功率 92%（23/25 条产出完整 schema 结构），粗筛→抽取→校验三节点图结构扁平可控、可测试、可版本化，无平台绑定。代码化编排路线（方案 C）成立。

唯一摩擦点：粗筛小模型对"锂矿公司分析/碳酸锂期货"这类**上游矿业/期货**内容判为领域无关而丢弃（2 条假阴性），属粗筛提示词口径问题而非编排问题，生产期可通过调粗筛 prompt 或在粗筛后保留"灰色条目"人工兜底缓解，不影响 ADR-004 决策。

## 端到端成功率与延迟分布

| 指标 | 值 |
|---|---|
| 总样本 | 25 |
| 端到端成功（有 pred + 6 字段 schema 完整） | 23/25 = 92% |
| API 调用成功率（无 429/5xx/解析失败抛出） | 25/25 = 100% |
| 被粗筛丢弃 | 2（S09、S10，均为假阴性） |
| 重试触发条目（retries≥1） | 5/23（S07=1, S08=3, S11=2, S15=1, S23=1） |

各节点延迟分布（ms）：

| 节点 | n | min | median | max | mean |
|---|---|---|---|---|---|
| prefilter | 25 | 4484 | 7787 | 30941 | 9230 |
| extract | 23 | 3910 | 10376 | 28305 | 12698 |
| validate | 23 | 0 | 0 | 48752 | 4218 |
| 端到端 elapsed | 25 | 11931 | 19738 | 68429 | 24797 |

- prefilter 中位 ~7.8s，小模型推理仍偏慢（MiniMax-M2.7 推理模型思维链开销）；与 SPK-2 大模型 ~20s/条 同量级，说明粗筛"省时间"的预期未实现——推理模型无论大小档都带思维链。
- validate 中位 0ms：23 条中 18 条首次抽取即 schema 完整、直接通过；重问仅发生在 5 条。
- 最慢端到端 68.4s（S08，组织人事条目，validate 重试 3 次达上限）。

## 粗筛表现

25 条金答案样本均为领域相关（金答案集本身即"已判为相关"的样本），故粗筛只有"假阴性"（误丢）无"假阳性"（误留）维度。

| 指标 | 值 |
|---|---|
| kept（粗筛通过） | 23/25 = 92% |
| dropped（粗筛丢弃） | 2 |
| recall（相对"全量相关"基线） | 23/25 = 92% |
| precision | 不适用（无负样本，无假阳性可测） |

误丢条目分析：
- **S09**（cehome，L2）：澳洲锂矿上市公司 Global Lithium 深度分析报告。金答案事件类型=财报、主体=Global Lithium（GL1）。粗筛判为无关——**锂矿/上游矿业**与"工程机械"行业字面差异大，粗筛 prompt 仅问"工程机械行业情报相关"未覆盖"工程机械上游原材料/矿业公司"。
- **S10**（cehome，L2）：碳酸锂期货市场分析。金答案事件类型=财报、主体=碳酸锂期货市场。粗筛判为无关——**期货市场**与"工程机械产品/技术/市场/组织动态"的关联需行业知识（碳酸锂是电动化上游电池材料，间接相关）。

结论：粗筛 prompt 口径偏窄，对"上游原材料/金融市场与工程机械的间接关联"判别力不足。生产期改进方向：(1) 粗筛 prompt 显式纳入"上游原材料/电池材料/期货市场对工程机械的间接影响"；(2) 粗筛设"灰色保留"——小模型不确定时默认 keep，走人工兜底（与架构 §8"LLM 调用失败降级为待人工，不丢弃"原则一致）。

## 重问行为

5/23 条触发 validate 重问，重问分布：

| retries | 条目数 | 条目 |
|---|---|---|
| 0 | 18 | 大多数 |
| 1 | 3 | S07、S15、S23 |
| 2 | 1 | S11 |
| 3（达上限） | 1 | S08 |

- 重问率 5/23 ≈ 22%，高于 SPK-2 试抽的 0%（SPK-2 用简版"输出缺字段重出 JSON"提示词，本任务用 SPK-2 终版 prompt + 额外 user 消息提示"缺字段")。
- S08 重试达 3 次上限仍未首次成功（validate 48.7s），最终 pred 完整——说明第 3 次重问成功；但 retries 计数逻辑：`retries += usage["retries"] + 1`，当 usage["retries"]（chat_json 内部重试）为 0 时每轮 validate +1，3 轮即达上限。
- 重问均最终拿到完整 schema（6 字段齐全），无条目因重问耗尽产出 None。

## 开发摩擦点记录

1. **LangGraph 1.2.11 API 与 brief 写法差异**：brief 用 `g.set_conditional_entry_point("prefilter", _route_after_prefilter)`（0.x API，1.x 仍保留为 deprecated alias）。本任务改用 1.x 惯用法 `g.add_edge(START, "prefilter") + g.add_conditional_edges("prefilter", _route_after_prefilter)`，语义等价、无 deprecation 告警。`add_node`/`add_edge`/`compile()` 在 1.x 签名兼容。**回写**：架构 §5.1 无需改（流程描述与实现一致）。
2. **模块路径索引**：`graph.py` 需同时把 `spikes/`（导入 `_lib.llm`）与 `spikes/spk2-extraction-probe/golden/`（导入 `make_dataset.EVENTS`）加入 `sys.path`。brief 用 `HERE.parents[1]` 实为 `pih/`（错了），应为 `HERE.parents[0]`（=spikes/）。已修正。
3. **粗筛小模型仍带思维链**：MiniMax-M2.7 为推理模型，与 SPK-2 发现的 M3 思维链前缀一致；`chat_json` 的 `extract_json` 三级提取对粗筛输出同样有效，无需额外处理。
4. **推理模型耗时**：粗筛（小模型）中位 7.8s、抽取（大模型）中位 10.4s，二者同量级——"小模型省时间"预期在推理模型档位下不成立。生产期粗筛若需进一步降本，应换**非推理**小模型（如 MiniMax 非 M 系列）或本地小模型，而非依赖同系列小档。
5. **重问计数口径**：`retries += usage["retries"] + 1` 把 chat_json 内部重试与 validate 轮次混计，语义略糙但不影响成功率统计；生产期宜拆分"内部重试"与"validate 轮次"两个指标。

## 回写点

- `docs/adr/ADR-004-流水线编排代码化.md` 后果节：补"SPK-3 实测（2026-08-25）：成功率/延迟/摩擦点"段。
- `docs/Architecture.md` §5.1：流程描述（粗筛→抽取→校验）与实现一致，无需修订；§9.2 补 SPK-3 粗筛小模型实测耗时。
- `docs/Backlog.md`：SPK-3 状态改"已交付"并补交付说明。
- 版本号不动（Task 8 统一 bump）。
