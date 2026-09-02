---
id: decision-8
title: ADR-008 单一部署单元双运行角色
date: '2026-09-01 11:32'
status: accepted
---
## Context

系统有两个常驻运行面：Web/API（低延迟、人随时打开）与流水线 worker（调度 + LLM 长任务，单条可跑数十秒）。Day0 架构重写（doc-002 §3）需确定进程/部署形态。约束：同一份代码、1 人开发运维、组件最少化（doc-001 §3 工程纪律）。

**方案 A：单进程合并**（调度器 + 流水线 + Web 同进程）
- 优点：容器数最少（compose 3 容器）
- 缺点：LLM 长任务与内存峰值直接阻塞 Web 响应；任何一侧重启都拖累另一侧；崩溃域耦合

**方案 B：双镜像分离**（web 镜像 / worker 镜像）
- 优点：职责物理隔离
- 缺点：同源代码构建两份镜像，构建、版本同步、漂移防护全部翻倍——为不存在的差异付维护成本

**方案 C：单一镜像双运行角色**——`pih serve`（Web/API）与 `pih work`（调度 + 流水线），compose 以不同 command 起两容器
- 优点：部署单元唯一（构建/升级/回滚一次）；两角色进程级隔离互不阻塞；无内部 API
- 缺点：镜像内包含两面的依赖（Python 单语言下体积增量可忽略）

## Decision

采用方案 C。pih-web 与 pih-worker 为同一镜像的两个运行角色；**两者不直接通信，唯一交互介质是 PostgreSQL**（含通知表——worker 产生告警，web 呈现）。

**理由**：
1. 1 人运维的瓶颈是"要维护的东西数"而非容器数——单镜像双角色让构建面收敛为 1，运行面按职责隔离为 2；
2. 交互介质收敛为 PG：表结构（alembic 迁移）即契约，无内部 API 版本协商问题；
3. CLI 运维命令（probe / collect / verify / query）复用同镜像 `docker compose run` 执行，零额外资产。

## Consequences

- compose 目标拓扑 4 容器：postgres / minio / pih-web / pih-worker（架构 §9.1）；
- worker 与 web 的行为耦合只允许经由数据库模式变更（走 alembic 单线迁移）；
- worker 未来若需水平扩容：inbox 消费以行级锁/SKIP LOCKED 保证多副本安全（实施细节，不改变本决策）；
- 告警与消费同入口：流水线异常一律落通知表由 Web 呈现，不引入外部监控组件（架构 §8）。
