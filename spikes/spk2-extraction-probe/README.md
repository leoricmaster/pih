# SPK-2 LLM 抽取准确率摸底

目标：用 SPK-1 真实样本试抽，评估按需求 §4.4 schema 抽取的准确率与提示词工作量。
检验需求 §7"LLM 抽取错误"风险。

- `golden/` 样本集与金答案（人工标注）
- `run_extraction.py` 试抽脚本（Task 6）
- `evaluate.py` 评分脚本（Task 6）
- `spk2-report.md` 报告（Task 6）
