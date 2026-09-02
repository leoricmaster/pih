---
id: doc-5
title: 故事交付包 Checklist
type: guide
created_date: '2026-09-02 11:24'
updated_date: '2026-09-02 11:24'
---
# 故事交付包 Checklist（标杆蒸馏）

来源：TASK-1.01.01（m-0 首故事）按标杆标准交付后蒸馏。后续故事照此执行；
项目级流程事实源与之一致，冲突时以本表+README「测试分层与 CI」为准并回来修订。

## 1. 交付包定义

一个故事的「完成」= 代码 + 测试 + 流程纪律 + 文档同步 + 证据，五者齐备才 finalization：

1. **前置复核**：实测存量与计划假设对齐（读代码不臆测），偏差先回来对齐再动手
2. **设计文档**：`docs/design/<TASK-ID>-design.md`，经用户评审后进入实现
3. **TDD 切片**：每 AC 一至多个切片；每切片 红→绿→重构→（ruff+相关层测试绿）→细粒度 commit→task notes 记证据与偏差
4. **测试分层落位**：新用例显式选层（unit/contract/integration/live）并在设计文档记理由；能降层就降层（CI 可运行集单调增长）
5. **文档同步**：README 相关章节、事实源偏差闭环（架构级→ADR+用户确认；小偏差→设计文档 §偏差 与 notes）
6. **finalization**：逐 AC 客观验证（测试名/命令+输出）才勾选；DoD 逐条核对；final-summary 命名验证证据；置 Done

## 2. 设计文档模板（`docs/design/<TASK-ID>-design.md`）

- **存量映射**：AC ↔ 既有代码 ↔ 增量表——增量最小化是默认姿态
- **决策记录**：D1..Dn，每条=决策+理由+被否选项；不写代码级细节（防成为代码另一表述）
- **接口与状态语义**：新路由/函数签名、状态机与三态类语义（如有）
- **测试分层**：每类用例的层位与理由
- **事实源偏差与裁决**：实现中发现的 doc/原型/schema 偏差，逐条闭环
- **AC 证据清单**：AC → 计划取证的测试/命令（占位，finalization 前补实测）

粒度红线：人类可评审（每节 ≤ 300 字级），不复述实现。

## 3. 证据格式

- **测试类**：`文件::类::用例` + 层位 + 一句话说明锁什么语义；先红后绿须记录「红的原因」
- **命令类**：命令 + 输出摘录（状态码/关键行）；冒烟（curl/uvicorn）记 URL+状态码+关键文案
- **页面类**：优先 DOM/文案断言的自动化用例；必要时截图（存 notes 引用）
- 反例：以「代码存在」「应能通过」充当证据——一律不算

## 4. 测试与 CI 策略

- 分层表与运行方式：README「测试分层与 CI」（unit 无容器 / contract 需 PG / integration 需 compose / live 需外网）
- CI（ci.yml）固定跑 `ruff → pytest tests/unit tests/contract`；新用例默认目标=进 CI（unit/contract），进不了时在设计文档记理由
- 用例降层单向：live→integration→contract→unit 允许，反向须说明
- 依赖容器的用例在模块 docstring 写启动前置（如「需 docker compose up postgres minio」）
- 单测禁止真网络/真时钟；编排缝（如 `run_probe`）在模块命名空间引用依赖供 monkeypatch
- **integration 层必做**：编排接线的端到端用例（单测 monkeypatch 会掩盖注册表/参数装配类接线 bug——TASK-1.01.01 实证：web 进程适配器注册表为空仅 integration 抓到）

## 5. 遗留改进（不阻塞后续故事）

- ci.yml actions 由版本 tag 收紧为 commit SHA 锁定
- 引入 actionlint 进本地/CI 校验 workflow 语法
