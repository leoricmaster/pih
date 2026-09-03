---
id: TASK-1.01.01
title: 信源注册与信源页试抓取
status: In Progress
assignee:
  - '@lancer'
created_date: '2026-09-01 09:25'
updated_date: '2026-09-03 12:05'
labels:
  - web
milestone: m-0
dependencies: []
references:
  - docs/prototype.html
parent_task_id: TASK-1.01
priority: high
type: story
ordinal: 15000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
作为运营者，我在 repo 的领域包 YAML 中注册信源（URL、类型、层级、频率、列表页入口），在 Web 信源页查看全部信源状态、触发试抓取验证可达性，以便信源配置可信、抓得通才启用——状态与验收都在页面上。

验收面：Web 信源页（信源状态列表 + 页内试抓报告）。注册与配置编辑保留在 YAML + Git（版本化留痕，ADR-001）；信源页承载可视、试抓与健康（健康随 Feature 推进逐层加深）。IA：详情页为聚合面、状态词表跨页一致（见原型 docs/prototype.html）。

不在本故事：采集入库与去重 / 粗筛（→ TASK-1.01.02）；信源健康告警与连续失败统计（→ TASK-4.02.01）；领域包其它节（关键词 / 竞品 / 标签树 / 模板 / 提示词）的生效由各消费故事自验（→ TASK-1.02.01 等）。
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 AC1: Given 运营者在领域包 YAML 中新增信源并提交且缺必填字段之一（id / name / type / url / list_url / reliability / level / fetch_frequency / enabled）｜When 流水线加载配置｜Then 加载被拒绝，错误指出缺失字段名与所在行号，且已加载配置不受影响（不半截加载）
- [x] #2 AC2: Given 一个已成功加载的领域包｜When 运营者打开 Web 信源页｜Then 页面列出全部信源，每源展示名称、类型、层级、可靠性、频率、启用状态，列表与 sources 节一一对应；新增或删除信源经重载后在页面上反映
- [x] #3 AC3: Given 信源页上某个 enabled=false 的新增信源｜When 运营者点击试抓取｜Then 页面展示试抓报告，按 robots / 列表页 / 详情 / 快照 四维逐项标成败；robots 禁止抓取时标记拒绝且不发起后续抓取（合规 NFR · doc-3）
- [x] #4 AC4: Given 某信源试抓取通过｜Then 报告仅作启用依据——通过后由运营者在 YAML 中将 enabled 置 true（Git 留痕），工具不自动改写 YAML（人最终环节，ADR-001 / ADR-002）；enabled=false 的源不参与采集（调度器不拾取，跨 TASK-4.01）
- [x] #5 AC5: Given 运营者在领域包 YAML 中新增 / 修改 / 删除信源｜When 重新加载配置｜Then 信源页与调度器按新信源清单生效，核心系统无任何代码变更（ADR-001）
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 验收面字段与事实源（领域包 schema / 原型 IA / doc-2）逐项核对一致；偏差先修订事实源或记 ADR，不在代码里私自偏移
- [x] #2 无新增未论证的自部署组件；核心代码不出现行业知识硬编码（违反即返工）
- [x] #3 AC 全满足，每条有可复现证据（测试名 / 命令 / 截图），实际运行通过——非臆测的「应能通过」推断
- [ ] #4 CI 有增量测试且变绿；覆盖正常路径与关键失败路径
- [x] #5 无回归（现有测试不破）
- [x] #6 触碰的架构 / ADR / NFR / 运营手册同步更新，day0 文档改动进正文不留批注
- [x] #7 结构化日志与运行留痕按 doc-2 §8 落地；迁移 / 配置变更可回滚（1 人可恢复）
- [x] #8 无密钥硬编码；新增依赖真实、锁版本、无高危 CVE
- [x] #9 不违反贯穿性约束与 ADR（偏离须先记 ADR）
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. 前置：置 In Progress + 指派 @lancer（已置）；实测复核存量（probe/validator/web）与计划假设一致，偏差先回来对齐
2. 设计定稿：写 docs/design/TASK-1.01.01-design.md（决策与理由、接口/状态语义、事实源偏差清单；不写代码级细节——防成为代码另一表述），经用户评审后进入实现
3. AC1 行号补齐：loader.py 用 yaml.compose() 建 path→行号映射，ValidationIssue 增 line 字段，加载入口报错含行号；零新依赖
4. AC2 信源页：GET /sources 直读领域包渲染表格（名称/类型/层级/可靠性/频率/启用+操作列）；校验失败渲染错误态（issues 含行号）不 500；base.html 加「信源」导航
5. AC3 页面试抓：POST /sources/{id}/probe 同步执行 probe_source() 直渲染报告四段（成功/失败/未达三态）；robots 拒绝→后续未达；无适配器源显示「适配器未接入」不 500；pih.probe logger JSON lines（doc-2 §8）
6. TDD 先行：unit（行号映射；probe 路由三态）+ contract（sources.html 渲染）+ integration（compose 下列表与 probe 端到端）——红→绿→重构循环
7. CI 骨架（AC 外范围，已获批准）：.github/workflows/ci.yml——ruff + unit + contract（PG service container）；集成/live 不进 CI 注明原因；不变式：CI 可运行集单调增长
8. 文档同步：原型补「可靠性」列、README 补信源页章节+测试分层与 CI 说明；架构级偏离先记 ADR 并与用户确认，小决策进 notes
9. 执行纪律：短循环 TDD，每循环测试绿→--append-notes+细粒度 commit；范围外发现停下问不私扩；每条 AC 证据=测试名/命令+输出摘录（页面类可选截图）
10. finalization：逐 AC 有证据才勾+DoD 逐条核对+总结；沉淀 backlog doc「故事交付包 checklist」（流程/设计文档模板/证据格式/测试分层与 CI 策略）+ CLAUDE.md 加指针，两项此时一并落

11. 立术语表 doc-4（用户裁决新增，指针型防腐化）：只收项目特殊含义/易混淆术语，词条=术语+一句话+代码/配置标识符映射+事实源指针，不复制定义正文；本故事收录种子词条（信源/领域包/试抓取vs采集/reliability vs level/Admiralty码/事件vs情报条目/核实状态机/粗筛与process_status/内容指纹/收件箱/站内信/快照/enabled门控/未达 等）；finalization 时 CLAUDE.md 指针含「术语歧义先查 doc-4」
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
AC1 完成（TDD）：ValidationIssue 增 line 字段（语义：缺必选字段→父映射起始行；值违规→值所在行），loader 经 yaml.compose 回填行号，validator 保持 dict 纯净。执行中发现并修正偏差：schema sources required 漏列 fetch_frequency——以 AC1 必填清单为准补齐，good 夹具与最小包测试同步。证据：tests/unit/test_loader.py::TestIssueLineNumbers（5 例，先红后绿）、test_validator.py::test_fetch_frequency_required_per_ac1、test_schema_self_consistency 参数化 +fetch_frequency；uv run pytest tests/unit → 269 passed；ruff 干净；pack 契约 10 passed；真实包实测报错「sources[0].reliability: 必选字段缺失（第 25 行）」

AC2 完成（TDD）：GET /sources + sources.html（六字段表格+试抓按钮+错误态不半截）+ pack_loader.load_sources_view（三态：pack 有效/校验失败带行号 issues/文件错误）+ base.html 导航。真包冒烟：9 源全列、3 on/6 off，与 pack.yaml 一一对应。事实源偏差闭环：原型信源表补「可靠性」列，且原层级列的 A/B/C 实为可靠性值——已改为 L2/L2/L3/L3 层级码（reliability vs level 混同的实证，入术语表种子）。证据：contract test_templates_render.py::TestSourcesPageTemplate 6 例、unit consume/test_pack_loader.py 3 例（先红后绿）；tests/unit+contract 294 passed；ruff 干净

AC3 完成（TDD，ca9f6c3）：POST /sources/{id}/probe 同步直渲染 + run_probe 编排缝（无适配器 KeyError 与 MinIO 不可达降级「未执行」note 不 500）+ _probe_view 四段三态（robots 拒绝→列表/详情/快照未达）+ pih.probe JSON lines 日志。与计划偏差（记录）：面板不加重复的模板契约类——TestClient 单测已直锁渲染输出（强于模板层契约），AC2 既有契约例继续锁模板对缺失 probe_* 上下文的容错；integration 层验证随 CI 切片后的 compose 演练补。证据：unit consume/test_sources_probe.py 12 例（先红后绿）；uvicorn 冒烟 GET /sources=200、未知源 POST=404「不在领域包中」；tests/unit 284 passed、contract 47 passed（需 compose 起 PG/MinIO）；ruff 干净

CI 骨架完成（计划步 7）：.github/workflows/ci.yml——push(main)/PR 触发，单 job：uv sync --frozen --extra dev → ruff → pytest tests/unit tests/contract；契约层 PG 走 service container（pgvector/pg16，参数同 compose，DSN 复用 .env.defaults 入库默认值）；integration/live 不进 CI（理由写入 yml 注释）；并发去重 + 15min 超时。验证：YAML 解析 OK + 本地逐步等价演练 sync --frozen/ruff/pytest = 331 passed（无 actionlint，语法与步骤等价性以本地复跑为证）。actions 用版本 tag 未锁 SHA——遗留改进项记入交付包 checklist 讨论

integration 层 + 接线修复（计划步 6 收尾）：tests/integration/test_sources_page_e2e.py 3 例先红后绿，暴露单测 monkeypatch 盲区——(a) web 进程适配器注册表为空（web.py 未 import collect.adapters，真实试抓全「适配器未接入」）；(b) 裸 get_adapter(src) 缺 http/snapshots 必参。修复：web.py import adapters 注册 + base.has_adapter 纯查表谓词（预检不实例化，先于 MinIO 判定）。外网抓取在 probe_source 缝打桩（真实站点属 live 层）；真 MinIO 构建出 SnapshotStore、api 型源（xcmg）无适配器不 500 均有回归锁。文档同步（计划步 8）：README 补测试分层表（含「CI 可运行集单调增长」不变式与 LLM 空 key 跳过）+ 信源页章节。证据：integration 3 passed（compose 起 postgres+minio）；unit+contract 331 passed；ruff 干净

finalization（计划步 10/11）：术语表 doc-4（17 词条指针型）+ 交付包 checklist doc-5（标杆蒸馏）落地，CLAUDE.md 加指针（读故事先看 doc-5、术语歧义先查 doc-4、notes 追加实践）。AC 逐条客观验证后勾选——AC1：test_loader/validator 26 passed + 缺字段实测报「sources[0].reliability 必选字段缺失（第 N 行）」且 load_sources_view 返回 (None, issues, None) 不半截；AC2：contract 6 + unit 3 + integration 真包 9 源一一对应；AC3：unit 12（四段渲染/robots→未达×3/pih.probe 日志）+ collect probe 6（robots 早退不发起后续请求）+ integration 3；AC4：单测锁「试抓通过→enabled 指引」文案 + grep 无 YAML 写路径 + run.py enabled 门控 test_run 3 passed（SourceDisabledError）；AC5：/sources 与 collect 均直读同一 pack，改 YAML 刷新即生效、零代码变更（integration 真包验证）。DoD 8/9 项勾选；#4（CI 变绿）留待 push 后 GitHub Actions 实跑确认——本地已等价演练 331 passed，未勾原因是流水线尚未真实执行

验收反馈修复（首轮人类评审，TDD）：(a) 告警聚合——ccma 试抓四段全成功但 robots 软 200 告警埋在 note 小字、结论行「试抓通过」决策点信息不足；修法：ProbeReport.robots_invalid 结构化标志贯穿 + web._probe_warns 聚合 + 结论行「试抓通过（含 N 项告警：…）——建议人工复核」+ pih.probe 日志加 warns 计数字段。证据：collect test_soft200_robots_sets_structured_warn_flag（红=AttributeError）、unit TestProbeWarnAggregation 4 例（含无告警负控）；README 信源页章节补口径。(b) 侧边栏还原（裁决 A）——导航迁右上角偏离原型且未讨论；修法：base.html 按原型 IA 重写（brand+消费区/运营/观察面三组、未上线项 disabled、active 左边条），list/detail/sources/feedback 墰 nav_active 块（base 用 self.nav_active() 取值——块内容非变量，首轮 {% if nav_active == %} 引用未定义变量致 2 例红，属修复内回归）；style.css 重写 .app/.sidebar/.navgroup/.navlink。证据：contract TestSidebarNav 4 例（分组/链接/disabled×4/active 标记互斥）。(c) 流程沉淀——doc-5 增 §5 验收材料包（五问固定结构+客观证据约束+原型 IA 布局级对照附加项），CLAUDE.md 加触发线；ci.yml 引用漂移修正（「doc-2 §6」不实→README+doc-5）。回归：unit+contract 340 passed、integration 待复跑确认

验收反馈修复（二轮，用户视角文案）：页首「配置编辑在仓内 YAML+Git…人是最终环节」说明撤下——实现者术语（YAML/Git/留痕）出现在客户界面（该句源头是原型 source 页 note，用户裁定不要）。修法：sources.html 删 page-note 块 + style.css 删闲置 .page-note 规则 + 原型同步删该句（保留「▶ 流 E 信源管理」流标注）。证据：contract test_customer_page_has_no_implementation_note 负控（先红后绿）；回归 unit+contract 341 passed；live :8000 页面 grep 0 命中。同轮验收识别的更大缺口（表格字段零解释层、报告文案面向实现者、快照存档无指向、结论行仍含「领域包 YAML」内部词）超文案微调量级，按 doc-5 §6 属需排期讨论项——处置待用户裁决（并 TASK-6 或新单，涉及原型升级先行）

验收反馈修复（二轮 b，robots 排查材料分层，用户裁定「本轮撤下只留日志」）：RobotsResult 增 detail 字段（Content-Type+正文前 200 字），note 改纯结论句；ProbeReport.robots_detail 贯穿；CLI 打「（排查，不上页面）」行保留开发者面；pih.probe 日志加 robots_detail 字段（排查材料留日志）；Web 页面不渲染 detail。证据：collect test_ac2_soft200_html_robots_invalid 扩展断言 + test_soft200_robots_detail_layered_out_of_note + web test_robots_detail_not_rendered_on_page（页面负控）/ test_probe_log_carries_robots_detail + cli test_probe_report_prints_robots_detail——4 红 1 负控先行；回归 unit+contract 345 passed、ruff 干净；live 重启 uvicorn 后 POST ccma 实弹：robots 段仅结论句。裁定记录：用户确认深化工作继续在本故事单完成（需求端到端规矩）；遗留同段【告警】后缀与结论行 YAML 措辞并入本故事内「原型改稿建议」讨论（原型先行）
验收反馈修复（三轮，统一含义 + 信源页呈现深化 R1–R6，用户逐项裁定后落地）。前置裁定：层级/可靠性两轴不合并（出身 vs 表现，消费方与标准对齐各异）；赋值口径层删除——只经两途：注册人按官方定义人工初评 + 画像重估（verification_log），无并行规则（「实抓→B」类阶梯废除）；类型词不带状态备注（易过时），适配器接入状态属运行时查注册表渲染。统一含义落地（事实源优先）：doc-2 §6.3 补 Admiralty A–F 官方分档 + 两轴不合并段（含重访条件：level 长期无消费方再议降级）+ §6.4 人工初评落 A/B 口径 + §4/§5 图与表补「变更监控」；doc-4 重写为统一词表（词条=特殊含义/易混淆 + 「呈现」行=UI 标签基线）；schema 层级引用漂移修正（§6.2→§6.3）。R1–R3 清单面：labels.py（类型/频率呈现词 + 字段图例，漂移守卫 test_labels 锁 key 集与 schema 枚举一致）+ sources.html 字段说明折叠图例/呈现词列/未接入徽标/启用停用标签 + 原型清单面同步。R4–R6 报告面（TDD 8 红先行）：ProbeReport.list_count 结构化计数（web 不再解析 note）；_probe_view 用户文案——「robots 合规检查/允许抓取/站点未提供有效 robots 声明…按无限制处理/列表页可达，找到 N 条待抓内容/已抓取 x/y 条正文；示例：『title』/N 份原文快照已存档」；_probe_warns 改「该站点未提供有效 robots 声明，已按无限制处理——请确认可接受」；结论行 R6——通过「启用本信源：在信源配置文件中将 enabled 改为 true 并提交（人工操作，留版本记录）」、失败补「详细排查材料见服务日志（pih.probe）」；R5 报告附 presigned 查看原文链接（MinIO 不可达降级省略，存档事实仍在）。原型报告块与 README 同步。证据：unit+contract 434 passed、ruff 干净；live :8000 实弹 ccma——四段新文案 + 「找到 51 条待抓内容」+ 查看原文链接 curl 200 text/html 25888B（presigned 实开验证；首验 400 系提取未还原 &amp; 实体的假象）。停用断言修正：锁 <span class="tag ok">启用</span> 而非裸文本（表头 <th>启用</th> 误伤）
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
信源注册与信源页试抓取交付（标杆）：AC1 缺字段拒绝含字段名+行号不半截（ValidationIssue.line + yaml.compose 回填，26 单测）；AC2 /sources 六字段清单直读领域包（契约 6+单测 3+integration 真包 9 源一一对应）；AC3 页内试抓四段三态报告 + pih.probe JSON 日志（单测 12+采集层 6+integration 3，先红后绿，顺带修复 web 适配器注册表未初始化与裸 get_adapter 两处接线 bug）；AC4 试抓仅作启用依据、工具零 YAML 写路径、enabled 门控 SourceDisabledError 有测；AC5 页面与采集同源直读 pack 零代码生效。基建沉淀：ci.yml（ruff+unit+contract，PG service container）、doc-4 术语表、doc-5 交付包 checklist、CLAUDE.md 指针。回归 unit+contract 331 passed + integration 3 passed + ruff 干净；DoD#4（CI 实跑变绿）待 push 后确认
<!-- SECTION:FINAL_SUMMARY:END -->
