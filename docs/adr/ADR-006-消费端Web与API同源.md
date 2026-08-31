# ADR-006：消费端——极简只读 Web 与 JSON API 同源交付

- 状态：已接受
- 日期：2026-08-25

## 问题

消费者角色的承担者不限于人——Agent（如产品规划 Agent）需程序化消费情报库。消费端以什么形态交付，才能同时满足人（详情页 AC：引用跳转、核实历史、快照入口）与 Agent（结构化查询）？

## 可选方案

### 方案 A：Dify 聊天界面 + 飞书多维表格

- 优点：零前端开发
- 缺点：交付不了详情页 AC；Agent 只能解析页面，脆弱且不可持续

### 方案 B：完整自研 Web（前后端分离）+ 独立 API 服务

- 优点：体验上限高
- 缺点：单用户下过度设计；两套查询逻辑必然漂移；1 人运维多一个组件

### 方案 C：单一 FastAPI 应用双出口——服务端模板 Web + 只读 JSON API

- 优点：约 3–5 人日；过滤/排序/引用拼装共用一套逻辑，Web 与 API 结果天然一致；Agent 接入零额外开发
- 缺点：Web 交互上限受服务端模板约束（只读场景无此需求）

## 决策

采用方案 C。查询服务为单一事实源，Web 页面与 JSON API 是同一 FastAPI 应用的两类出口，共用结构化过滤、score 排序与引用拼装。API 只读（筛选列表 + 详情，REST），鉴权从简（内网 + 静态 token），权限体系为后续方向；Agent 贡献者线索回写复用人工录入网关，仅预留接口不交付。

## 理由

1. 北极星指标（检索次数）按 Web/API 分别计数，同源使口径天然一致；
2. S1.1.x / S1.2.x 全部 AC 可交付；
3. 1 人运维约束下不新增任何组件。

## 后果

- 检索体验（北极星指标载体）有保障；
- 后续 Web 化演进（核实操作页、RAG 问答）在同一应用内叠加。

## 实施注脚

**落地现状**：`src/pih/consume/` 落地 FastAPI 单 app 双出口——
`QueryService` 为单一事实源，Web 页面（`web.py` + Jinja2 模板）与 JSON API（`api.py` router）
共用过滤/排序/引用拼装；同条件返回同 id 集合同序（集成测试 `test_api_e2e.py::TestAC4SameSource`
断言）。鉴权：API 端点 `Authorization: Bearer <PIH_API_TOKEN>`（`hmac.compare_digest`
常量时间比较），Web 内网默认开放。部署：docker-compose `web` service（独立容器，仅依赖 PG）
+ 本地 `uv run uvicorn pih.consume.web:app`。事件核实状态字段占位「待事件模型上线后自动激活」，
event 表上线后查询服务自动填实。排序简版 `admiralty ASC + fetched_at DESC`，完整 score
待事件与时效模块。
