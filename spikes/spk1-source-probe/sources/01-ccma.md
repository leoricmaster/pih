# CCMA 协会（中国工程机械工业协会官网）

- URL：http://www.cncma.org/（HTTPS 不可用，见下）
- 摸底卡编号：01
- 调研日期：2026-08-25
- 调研方式：纸面（浏览器/文档查阅，不抓取）

## 摸底记录

| 字段 | 内容 |
|---|---|
| 类型 | 列表页 HTML（`/col/<栏目码>` 列表 + `/article/<id>` 详情） |
| 采集方式预判 | HTTP+解析（requests + BeautifulSoup 即可）；也可作 changedetection.io 变更监控候选 |
| robots 允许度 | 无有效 robots.txt：`https://www.cncma.org/robots.txt` 连接超时（curl 28，25s，2026-08-25 13:41 CST）；`http://www.cncma.org/robots.txt` 返回 HTTP 200 但 Content-Type 为 `text/html;charset=UTF-8`，正文是站点通用模板页（无任何 User-agent/Disallow 指令）。判定：站点未提供有效 robots.txt，按"未声明即不限制"处理，但需在实抓阶段低频、少量取样 |
| 反爬观察 | 无登录墙（新闻栏目匿名可看）；无验证码；页面为服务端渲染 HTML（jQuery 仅做轮播/访问计数，正文不依赖 JS）；`/article/22651` 等详情页直接 200。注意：`/rss`、`/sitemap.xml` 等任意路径均被改写返回 HTTP 200 的 HTML 页（软 200），不能以状态码判断存在性 |
| 更新频率预估 | 日更~周更（行业资讯栏目第 1 页覆盖 2026-07 至 2026-08-21，约 22 条/2 个月；协会"月度快报"类文章确认存在：站内搜索"月报"命中《2026年7月工程机械市场指数快报》《2026年7月工程机械行业主要产品销售快报二》《2026年7月工程机械产品进出口快报》，均为月度发布） |
| 历史内容可达性 | 可回溯：`/col/hangyxw?pageIndex=2` 返回 2026-02~03 内容，分页控件显示共 44 页（每页 30 条）→ 可回溯远超 3 个月。翻页是 GET 参数 `?pageIndex=N`（页面上的 `javascript:_gotPage(2,30)` 对应此参数，已实测） |
| 纸面结论 | 需适配（HTTP-only + 列表/详情 URL 规则简单，但需绕开"软 200"陷阱：以页面 `<title>` 或正文结构判断真伪） |
| 实抓候选 | 是。理由：① 月度销售快报是 L1 级权威数据，附件 A 核心信源；② 无反爬、分页明确、详情页 SSR；③ 实抓需验证 HTTPS 不可用（仅 http）与软 200 误判问题 |

## 证据摘录（实测）

- `https://www.cncma.org/robots.txt` → curl (28) Connection timed out after 25001ms（2026-08-25 13:41 CST）
- `http://www.cncma.org/robots.txt` → 200，`Server: nginx/1.13.7`，`Content-Type: text/html;charset=UTF-8`，正文为含"中国工程机械工业协会"页头的通用模板
- `http://www.cncma.org/col/hangyxw` → 200，`<title>行业资讯</title>`，55 个 `/article/<id>` 链接，日期 2026-05-28 ~ 2026-08-21
- 分页标记：`<a href="javascript:_gotPage(2,30);">2</a>` … `<a href="javascript:_gotPage(44,30);">` → 共 44 页
- `http://www.cncma.org/col/hangyxw?pageIndex=2` → 200，内容变为 2026-02-27 ~ 2026-03-10（分页参数实测有效）
- `http://www.cncma.org/article/22504` → 200，`<title>中国机械联发布《关于对2026年度"机械工业科学技术奖"受理项目进行公示的公告》</title>`
- 站内搜索 `/search/article?keyWord=月报` → 200，命中 25 条，含《2026年7月工程机械市场指数快报》/article/22696 等
