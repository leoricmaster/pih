---
id: TASK-1.01.02
title: 采集入库与原文可查
status: Done
assignee:
  - '@lancer'
created_date: '2026-09-01 09:25'
updated_date: '2026-09-03 10:48'
labels:
  - web
milestone: m-0
dependencies:
  - TASK-1.01.01
references:
  - docs/prototype.html
parent_task_id: TASK-1.01
priority: high
type: story
ordinal: 16000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
作为运营者，执行采集后新条目出现在 Web 列表、点开可见原文快照与原始链接，重复采集不产生重复条目、无关内容不混入，以便不用搬运转录、原文永远找得回。

验收面：Web 列表/详情（+ 采集统计 CLI 报告）。去重、粗筛、先落盘可重放并入本故事 AC 与 NFR（doc-3），不独立成卡。

不在本故事：信源注册与试抓取（→ TASK-1.01.01）；结构化抽取与事件聚类（→ TASK-1.02.01）；自动调度（→ TASK-4.01.01）；信源健康告警与连续失败统计（→ TASK-4.02.01）。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 AC1: Given 某已启用信源 ｜ When 运营者执行采集 ｜ Then 新内容抓取入库，输出统计「入库 N 新增 / M 幂等跳过 / K 失败」｜ And 新条目出现在 Web 列表（标题、信源、采集时间）｜ And 详情页提供原文快照与原始链接两个入口（无快照的内容不入库）
- [x] #2 AC2: Given 重复采集同一信源而内容未更新 ｜ Then URL 指纹相同或内容相似度超阈值的条目被幂等跳过 ｜ And 情报库行数不变
- [x] #3 AC3: Given 一条新内容被粗筛（关键词 + 小模型二分类）判为不相关 ｜ Then 它不进入消费列表，行级标记保留 ｜ And 运营者可在 Web 列表按处理状态筛出复核（漏报审计）
- [x] #4 AC4: Given 抓取或处理失败 ｜ Then 原始内容先落盘不丢失，失败原因可查、可重放（细则见 NFR doc-3 与架构 §8）
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 验收面字段与事实源（领域包 schema / 原型 IA / doc-2）逐项核对一致；偏差先修订事实源或记 ADR，不在代码里私自偏移
- [x] #2 无新增未论证的自部署组件；核心代码不出现行业知识硬编码（违反即返工）
- [x] #3 AC 全满足，每条有可复现证据（测试名 / 命令 / 截图），实际运行通过——非臆测的「应能通过」推断
- [x] #4 CI 有增量测试且变绿；覆盖正常路径与关键失败路径
- [x] #5 无回归（现有测试不破）
- [x] #6 触碰的架构 / ADR / NFR / 运营手册同步更新，day0 文档改动进正文不留批注
- [x] #7 结构化日志与运行留痕按 doc-2 §8 落地；迁移 / 配置变更可回滚（1 人可恢复）
- [x] #8 无密钥硬编码；新增依赖真实、锁版本、无高危 CVE
- [x] #9 不违反贯穿性约束与 ADR（偏离须先记 ADR）
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
设计文档 docs/design/TASK-1.01.02-design.md 已评审通过（三处裁决：inbox_item 先落盘+dead 标记/pipeline_run 延后；精确指纹幂等模糊去重留演进；粗筛解耦不先行 1.02.01）。切片按 AC 推进，每切片 TDD 红→绿→重构→ruff+相关层绿→细粒度 commit→notes 记证据与偏差。

1. 前置实测复核存量与设计假设一致（已做：repository/run/web/graph/cli 全读；迁移 0001 仅 5 表缺 inbox/dead/pipeline_run 确认）
2. 迁移：新建迁移建 inbox_item（采集落盘列 + process_status + snapshot_id NOT NULL + content_sha1 幂等 + dead 标记），含 downgrade。contract 先红断言表存在→绿
3. AC4 采集落 inbox：collect_source 落库目标从 intel_item 切 inbox_item；fetch 失败捕获落一行（process_error 记因，pending 待重试）；无快照不入库守卫（snapshot_id NOT NULL）。unit + integration（跨接线缝）
4. AC2 幂等：inbox content_sha1 ON CONFLICT DO NOTHING；重采同行数不变 integration 用例。AC2 描述收窄为精确指纹（模糊去重记 backlog 单）→ notes/AC 标注
5. AC3 粗筛解耦：prefilter 独立函数（关键词命中 + 小模型二分类双通道，不耦合大模型配置前置）；pih process --prefilter-only 入口（倾向减入口）；filtered_out 行级标记；列表默认排除 filtered_out（行为变更）；漏报审计 process_status 显式筛出。unit + integration
6. AC1 列表/详情合并视图：web / 与详情读 inbox(pending)+intel(extracted) UNION，默认 WHERE process_status!=filtered_out；详情路由内部判表（倾向单一）；原文快照+原始链接两入口在 inbox 即有。回归底线：不破既有 list/detail/feedback 契约
7. AC4 dead 可查可重放：dead 标记 + CLI 查询/重放（重置 pending 重入链）/丢弃留痕；结构化日志 pih.collect/pih.process JSON lines
8. 文档同步：README 采集入库章节 + 测试分层更新；原型列表/详情节对照（合并视图）；事实源偏差闭环（AC2 收窄、intel_item 兼任 inbox 修正入 doc-2 §6.4/§7 或 ADR）
9. finalization：逐 AC 客观证据才勾选（测试名/命令+输出）；DoD 逐条核对；final-summary；五问材料包（doc-5 §5）；置 Done
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
迁移 0002 + InboxRepository + collect_source 落 inbox 完成（TDD，slice 2/3）：

迁移 0002 建 inbox_item（source_id FK / source_type / snapshot_id NOT NULL 守卫 / content_sha1 UNIQUE 精确幂等 / process_status 默认 pending / process_error / 三索引），含 downgrade（drop inbox，intel 既有数据不动）。契约测试 6 例先红（模块/表缺）后绿锁表结构；21 passed。

InboxRepository（store/inbox.py）：save（冲突→SKIPPED，异常→FAILED 不抛单条不阻塞 D8）/ save_batch / record_failure（fetch 失败落死信行，状态 dead、process_error 记因、snapshot_id 占位满足 NOT NULL、sha1=url+reason 幂等）/ get / list_pending（先老后新）/ mark_status（filtered_out/dead/重置 pending 重放）。unit 7 例先红后绿。

collect_source 重构落库目标 intel_item→inbox_item：fetch 异常捕获调 record_failure 落死信（AC4 失败原因可查可重放），不阻断其余条目；fetch_detail 返回 None（robots 拒绝/无快照）不落行（无快照不入库）。CLI _cmd_collect 切 InboxRepository。unit collect 10 例（含 3 失败场景：失败落死信不阻断/无 repo 不记录/None 跳过不落死信）。

回归：unit 315 passed、ruff 干净。与计划偏差：save 吞异常返回 FAILED 而非抛出（与 IntelRepository.save 抛出由 batch 捕获不同）——inbox 调用方是采集循环，直接拿 FAILED 计入统计更直白，已注释说明。

AC3 粗筛解耦完成（TDD，slice 5）：prefilter 独立模块（process/prefilter.py）——关键词命中（领域包 keywords 子串）+ 小模型二分类双通道。语义：关键词命中→kept 短路省小模型调用；未命中+小模型判否→filtered_out；未命中+小模型不可用/无 chat→灰条目保留（架构 §8 不丢弃）。不耦合大模型配置（chat=None 独立成立）。

run_prefilter_batch 编排缝（process/run.py）：inbox pending → prefilter → kept=False 落 mark_status(filtered_out)，kept=True 保持 pending 等抽取；mark 异常计入 failed 不阻断。CLI pih process --prefilter-only 入口（InboxRepository，不走大模型配置前置校验）。

证据：unit test_prefilter 8 例（keyword_hit 3 + prefilter 双通道 5：关键词命中短路/未命中LLM相关保留/未命中LLM不相关过滤/LLM失败灰保留/无chat灰保留）+ test_prefilter_run 5 例（过滤落标记/关键词保持/无chat灰保持/mark失败不阻断/source_id透传）；回归 unit 328 passed、ruff 干净。

范围缝厘清（设计 §3）：粗筛通过条目停 inbox pending 等 TASK-1.02.01 抽取提升 intel_item；本故事 inbox 仅 pending/filtered_out/dead 三态流转，needs_manual/extracted 留 1.02.01。TASK-1.02.01 不先行裁定落实——AC3 取证不绑大模型、不蹭抽取验收。

进度 checkpoint（slice 6 合并视图进行前）：slice 2 迁移 + slice 3 collect→inbox + slice 5 粗筛解耦 已落地提交（unit 328 / contract 21 / ruff 干净）。剩余：slice 4 AC2 幂等端到端、slice 6 合并视图（AC1 列表/详情读 inbox+intel，默认排除 filtered_out）、slice 7 dead 可查可重放 CLI、slice 8 文档同步、slice 9 finalization。

合并视图设计要点（待实现）：list.html 现用 IntelRecord 字段（subject/event_type/admiralty/event_status）；inbox pending 项无结构化字段。统一显示记录需兼容两源——pending 项结构化列显示「—/待抽取」，原文快照+原始链接在 inbox 即有。详情路由倾向单一 /intel/{id} 内部判表（inbox vs intel）。回归底线：不破既有 list/detail/feedback 契约测试与 integration（seed_intel_items 直写 intel 不经 collect，合并视图须同时显示 intel extracted + inbox pending）。

架构裁决 C（ADR-011：inbox 逻辑汇聚、物理单表两视图）落地——回退此前的 inbox_item 独立表方案，改 intel_item 单表 + source_type 列 + 两视图。事实源先行（DoD#1）：doc-2 §6.4 状态归属/§7 表行/§7 死注释/§5.4 检索描述/§1 技术栈/§10 索引同步修订（指向 ADR-011）；ADR-011 创建并 accepted。

代码重构：迁移 0002 改为 ALTER intel_item ADD source_type（NOT NULL default auto）+ 索引，含 downgrade；删 InboxRepository（store/inbox.py）；IntelRepository 增 source_type(save/save_batch)、record_failure（落 dead 行）、list_inbox（收件箱视图读非 extracted）、mark_status（filtered_out/dead/重放 pending）；collect_source 改回写 intel_item（保留 fetch 失败落死信）；run_prefilter_batch + CLI --prefilter-only 改指 IntelRepository；粗筛解耦模块（prefilter.py）保留不变。

证据：契约迁移测试改锁 source_type 列/索引/downgrade 可逆（18 passed）；unit test_inbox 重写为 IntelRepository 采集入库方法测试（source_type save 2 + record_failure 1 + list_inbox 3 + mark_status 2）；回归 unit 329 / contract 57 / ruff 干净。

slice 6 两视图完成（TDD）：ADR-011 落地——QueryService.list 默认 process_status=extracted（检索视图=成品，显式覆盖留 needs_manual 复核队列可达；Web/API 同源 ADR-006 共默认）；新增 /inbox 收件箱视图路由（IntelRepository.list_inbox 读非 extracted：pending/needs_manual/filtered_out/dead）+ inbox.html 模板 + base.html 导航「收件箱」。

AC1 验收面厘清：采集入库的 pending 条目出现在 /inbox（Web）+ pih query --source-id（CLI，list_by_source 不分状态，含 pending）。/检索视图默认 extracted（消费成品），filtered_out 不进检索（AC3 天然成立，不进消费列表）。漏报审计：/inbox 按 process_status=filtered_out 筛出（AC3 后半）。

修复集成回归：INSERT_SQL 占位符数错（13 vs 12 列，加 source_type 时手误）致采集 3 条全 FAILED——integration 真库抓到（单测 mock 不触 SQL 故未现），已修正为 12 占位符。

证据：unit test_inbox_page 6 例（pending 渲染/status 透传/filtered_out 可见/dead 带原因/空提示/导航）+ test_query_service 增 2 例（默认 extracted / 显式覆盖）；回归 unit 394 / contract / integration end_to_end+process_e2e 13 passed / ruff 干净。

slice 7 AC4 可重放 CLI + slice 8 文档同步完成：

replay 命令：pih replay <id> 重置 dead/needs_manual → pending 重入处理链（mark_status）；未找到 id 退出 1；打印原失败原因（可查）。丢弃=留 dead 态不删行留痕。证据：unit test_cli TestReplayCommand 2 例（重置 pending 含失败原因/未知 id 失败）。

文档同步：README 运营者 CLI 补 --prefilter-only / replay 命令；新增「采集入库与两视图（ADR-011）」段（收件箱/检索两视图、无快照不入库、精确幂等+模糊演进）；Web 段补 /inbox 与检索默认 extracted。AC2 范围裁定记入任务 comment（模糊去重留演进，本故事只精确指纹）。

回归：unit 396 / contract / ruff 干净；integration end_to_end+process_e2e 13 passed。

一轮评审修订（用户多轮评审第 1 轮，7 项反馈）：

R1 页面说明文字去除——inbox.html 页首 lbl「收件箱（采集先落盘·处理状态视图）」+ note 段（pending/filtered_out/dead 解释）删除，实现者口吻不上客户界面（同 TASK-1.01.01 先例）。

R2 IA 归位（用户裁定：并入情报页做 tab）——原型「待处理」tab 与本实现 /inbox 非同一概念（原型=事件核实队列 §6.1，实现=item 处理状态 §6.4），且原实现私自新增侧栏「收件箱」nav 未先讨论（违反原型变更先讨论约定，已记忆）。落地：侧栏撤收件箱 navlink；list.html/inbox.html 页内 [检索]/[收件箱] tab 栏；prototype.html 反向更新（待处理→收件箱 tab，内容改为 item 处理状态表，事件核实队列标注随核实层未来呈现）。

R3 重放上 Web（AC4 页面动作）——POST /inbox/{id}/replay（mark_status pending，303 回收件箱，同 /feedback 信任域）；收件箱非 pending 行「重放」按钮。证据：unit test_inbox_page replay 3 例（仅非 pending 行有按钮/重置 pending+303/未知 id 404）+ live 实弹 POST id5 dead→pending→恢复。

R4 来源列删除——恒 auto（manual 录入未实现）无信息量，manual 实现时再复列。表头现为 标题/信源/处理状态/失败原因/采集时间/操作。

R5 doc-2 对齐——§6.4 状态机去 done（代码与 §7 均无此态）；§6.4 补 process_error 归属（dead←collect 抓取异常/filtered_out←粗筛固定串/needs_manual←抽取校验失败/pending·extracted←无）；§5 开头补端到端管线统览图（主链+状态分支+两视图分读）。经 backlog doc update 写入（diff +16/-2）。

R6 评审答问归档——管线记录处（§5/§6.4/ADR-004·007·009·011，缺单点统览已由 R5 补）、处理状态与 source_type 语义出处（§6.4/§7/ADR-009·011）、失败原因三写手（R5 已入档）。

R7 验收数据重建——contract/integration 测试 fixture 对共享开发库 downgrade base（test_migrations_apply.py:31,55 / conftest.py:34）清空了已造数据；重新 upgrade+collect+seed（3 pending+1 filtered_out+1 dead）。该共享库设计为本地隐患（CI 无害），已向用户提议立独立测试库任务。

本轮回归：unit 343（+4 净增）/ contract 57 / ruff 干净；integration 未重跑（改动缝无 integration 覆盖，grep 零引用；重放缝已 live 实弹验证）。README 同步（两视图段+浏览器访问段改 tab IA）。

二轮评审问答（页面运营模型四问，客观结论）+ 裁定规划补位（不改码）：

入口：收件箱内容现役仅 `pih collect` 手动 CLI（调度 TASK-4.01.01 To Do 只加调度层、明确排除处理；人工录入 TASK-1.03 未实现）；演示数据为验收手造。时限：pending 无 TTL——时效管理器（draft-009 规划）管事件层过期/decay、健康监视（TASK-4.02）管信源连续失败，均不管条目积压。滞留根因：处理链无自动触发（任务树此前无「采集后自动处理」归属），页面亦无引导；收件箱定位为采集验收面+漏报审计（doc-2 §6.4 已载），消化 pending 属处理链职责非页面职责。

处置：新建 TASK-4.01.2「采集后自动处理消化 pending」（挂 TASK-4.01，dep TASK-4.01.01；描述含运营模型澄清与暂缓项入档）；页面引导文案 / Web 处理触发入口 / pending 超期提醒三项裁定暂缓（如需另立）。milestone 未指派（是否入 m-0 待用户定夺）。
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @lancer
created: 2026-09-03 08:34
---
AC2 范围裁定（DoD#1 事实源对齐）：AC2 原文「内容相似度超阈值」模糊去重经用户裁定留演进故事，本故事只做精确指纹（content_sha1 ON CONFLICT + url 同源）幂等。模糊去重另记 backlog 单。本故事 AC2 验收口径据此收窄：重采同源内容未变 → 行数不变（精确 sha1 幂等已满足），不验模糊相似度。
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
采集入库与原文可查交付（ADR-011 枢轴：inbox 逻辑汇聚、物理单表两视图）。AC1 采集落 intel_item pending + 统计「入库 N/M/K」+ /inbox 收件箱视图显示新条目 + /intel/{id} 详情原文快照与原始链接双入口 + 无快照不入库（snapshot_id NOT NULL 守卫）；AC2 精确 content_sha1 幂等（重采 0 新增/2 跳过，行数不变），模糊去重留演进故事（裁定记 comment）；AC3 粗筛解耦独立模块（关键词+小模型二分类双通道，不耦合大模型配置，pih process --prefilter-only）+ filtered_out 行级标记 + 不进检索视图（/ 默认 extracted，天然成立）+ /inbox 按状态筛出漏报审计；AC4 fetch 失败落 dead 行（process_error 记因）+ /inbox 可查 + pih replay <id> 重置 pending 重入链。

架构事实源同步（DoD#1）：doc-2 §6.4/§7/§5.4/§1/§10 修订 + ADR-011 accepted（inbox 逻辑汇聚而非独立表，intel_item 单表承载处理状态机，采集落 pending 抽取原地升级不复制 raw）。裁决 C 由用户在评审中拍板（质疑两表合并视图→一实体两页面）。回退了此前的 inbox_item 独立表迁移与 InboxRepository（slice 2/3 初版），保留粗筛解耦（slice 5）改指 IntelRepository。

证据：unit 339 / contract 57 / integration 77 / ruff 干净；live :8001 实弹——pih collect ccma 入库 2 新增、重采 0 新增/2 跳过、pih query 见 pending 行、--prefilter-only 关键词命中保留；/inbox 200 显示 2 条 pending（标题/信源/采集时间）、/ 检索默认 extracted「无结果」（AC3 天然）、/intel/2 详情原文快照+原始链接。DoD 8/9 勾选，#4（CI 变绿）留待 push 后 GitHub Actions 首跑确认（本地已等价演练全绿，未 push 依项目惯例停在人类验收后）。

DoD#4 达成：push ea327c6 后 GitHub Actions 首跑变绿（run 33745297956，success，2026-09-03）。DoD 9/9。
<!-- SECTION:FINAL_SUMMARY:END -->
