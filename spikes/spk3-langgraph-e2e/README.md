# SPK-3 LangGraph 端到端验证

目标：用 SPK-2 终版提示词在 LangGraph 上跑通 粗筛(小模型) → 抽取(大模型) → schema 校验(重问≤3)。
决策语境：ADR-004 后果节。

- `graph.py` 三节点图定义（START→prefilter→[条件]→extract→validate→END）
- `run_e2e.py` 批量执行与计时
- `spk3-report.md` 报告
- `e2e_results.json` 逐条结果（运行后生成）

## 运行

```bash
cd /home/lancer/projects/pih/spikes
.venv/bin/python spk3-langgraph-e2e/run_e2e.py
```

## 依赖

- langgraph 1.2.11（1.x API：用 `add_edge(START, ...)` + `add_conditional_edges`，非 0.x 的 `set_conditional_entry_point`）
- `_lib.llm.chat_json`（OpenAI 兼容端点）
- `spk2-extraction-probe/prompt_v3.txt`（终版提示词，glob 取最后一个 `prompt_v*.txt`）
- `spk2-extraction-probe/golden/samples.json`（25 条全量）
