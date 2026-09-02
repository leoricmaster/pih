
<!-- BACKLOG.MD GUIDELINES START -->
<!-- backlog.md-instructions-version: 1.50.1 -->
<CRITICAL_INSTRUCTION>

## Backlog.md Workflow

This project uses Backlog.md for task and project management.

**For every user request in this project, run `backlog instructions overview` before answering or taking action.**

Use the overview to decide whether to search, read, create, or update Backlog tasks.

Before task lifecycle actions, read the matching detailed guide:
- `backlog instructions task-creation` before creating or splitting tasks
- `backlog instructions task-execution` before planning, changing status or assignee, adding a plan or implementation notes, or implementing task work
- `backlog instructions task-finalization` before checking acceptance criteria, writing final summaries, or moving tasks to terminal statuses

Use `backlog <command> --help` before running unfamiliar commands. Help shows options, fields, and examples.

Do not edit Backlog task, draft, document, decision, or milestone markdown files directly. Use the `backlog` CLI so metadata, relationships, and history stay consistent.

</CRITICAL_INSTRUCTION>
<!-- BACKLOG.MD GUIDELINES END -->

## 项目工作约定

- **故事交付**：实现故事前读 backlog doc-5《故事交付包 Checklist》（流程纪律、设计文档模板、证据格式、测试分层与 CI 策略；TASK-1.01.01 标杆蒸馏）。
- **术语歧义先查 backlog doc-4《术语词表》**——只收项目特殊含义/易混淆术语（如 reliability vs level、试抓取 vs 采集、未达），再查事实源正文。
- 任务 Implementation Notes 追加：CLI 无对应子命令时按仓内既有实践在任务文件 `SECTION:NOTES` 区间内追加并同步 frontmatter `updated_date`（唯一例外，其余仍走 CLI）。
