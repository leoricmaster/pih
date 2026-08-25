# Spikes（EPIC-0 开发去风险）

设计规格：`docs/superpowers/specs/2026-08-25-sprint0-spikes-design.md`

## 目录

| 目录 | Spike | 状态 |
|---|---|---|
| `spk1-source-probe/` | SPK-1 信源可抓取性验证 | 已完成 |
| `spk2-extraction-probe/` | SPK-2 LLM 抽取准确率摸底 | 已完成 |
| `spk3-langgraph-e2e/` | SPK-3 LangGraph 端到端验证 | 已完成 |
| `_lib/` | 共享工具（robots 合规、LLM 客户端） | — |

## 纪律

1. 报告与脚本同目录；报告记录：做了什么、看到什么、结论、回写点。
2. Spike 代码是一次性学习品，**不演进为工程代码**——工程实现按架构文档另行落地。
3. 遵守 robots 协议；只取少量样本，不批量抓取，不登录，不绕过反爬。
4. 每个 Spike 完成即回写三件套（需求/架构/Backlog）与状态位。
5. 运行方式：`spikes/.venv/bin/python <脚本>`；测试 `spikes/.venv/bin/python -m pytest _lib/ -v`。
6. 密钥放 `spikes/.env`（已 gitignore），模板见 `.env.example`。
