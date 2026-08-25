# 主机厂官网新闻页（三一集团 / 徐工集团）

- URL：https://www.sanygroup.com/news ；https://www.xcmg.com/aboutus/news.htm
- 摸底卡编号：02（一卡覆盖 2 家，均为实测）
- 调研日期：2026-08-25
- 调研方式：纸面（浏览器/文档查阅，不抓取）

## 摸底记录

| 字段 | 内容 |
|---|---|
| 类型 | 列表页 HTML（三一：SSR 列表+静态详情；徐工：列表壳页 + AJAX HTML 片段端点） |
| 采集方式预判 | 三一：HTTP+解析（直抓列表即可）；徐工：HTTP+解析（调用其公开 AJAX 端点，等价于浏览器行为）；均可做 changedetection.io 候选 |
| robots 允许度 | 三一 `https://www.sanygroup.com/robots.txt`（200，实测全文 58 行）：`User-agent: *` 下 Disallow 均为图片处理/旧版目录（`/xwzx/`、`/sjzc/`、`/mtsj/`、`/e/`、`/etc/`、`/comparison/` 及大量 `null?imageMogr2/`），**`/news`、`/industryNews`、`/newsCollection` 均不在 Disallow 之列** → 允许。徐工 `https://www.xcmg.com/robots.txt`（200，全文 3 行）：`User-agent: *` / `Disallow:`（空，即全站允许）/ `Sitemap: https://www.xcmg.com/sitemap.xml` |
| 反爬观察 | 两家均无登录墙、无验证码、无频控触发（单次摸底）。三一：Nuxt SSR（HTML 内含 `__NUXT__` 数据与完整链接、日期文本），列表第 1 页含 `news-date` 类日期（2026.08.04 等）。徐工：列表壳页 `news.htm` 本身不含新闻条目（`news-detail` 计数 0），条目由 `seajs` 模块 `js/news_list.js` 通过 GET `/ext/ajax_news.jsp?flag=getdata&pageNo=N&channelId=22519` 异步注入（读 JS 源码确认，实测该端点直接 200 返回 HTML 片段，含 12 条 `/aboutus/news-detail-<id>.htm` 链接与日期） |
| 更新频率预估 | 三一日更~周更（列表第 1 页最新日期 2026.08.13，翻页 `?page=0..5&size=6`）；徐工近日更（2026/08/05~08/07 密集出现，详情页 `<title>喜报！徐工孔雀系列叉车荣获"紫金奖"优秀奖-集团新闻-徐工官网`） |
| 历史内容可达性 | 三一：列表翻页 `?page=N&size=6`（第 1 页可见 page 0–5；未确认最深页数，标注需实抓验证）；详情 URL `/news/<id>.html`，`<id>` 为全局自增序（16476~16563 连续），可按 id 回溯。徐工：AJAX 端点带 `year`/`month` 参数，`/ext/control/ajax_getMonth.jsp?flag=getyear` 返回 `<li>2026</li>…<li>2022</li>`（5 个年份），`flag=getmonth&year=2024` 返回 12 个月 → 按"年-月"归档可回溯 ≥3 个月（实测 2024-03 返回 2024.03.30~04.02 条目） |
| 纸面结论 | 三一：直抓候选；徐工：需适配（须走 AJAX 端点而非壳页） |
| 实抓候选 | 三一：是（SSR、robots 允许、翻页规则简单，作"列表页 HTML 解析"代表）。徐工：备选（结构清晰但 pageNo 在未带 year 参数时返回相同内容——实测 pageNo=1/2/3/4/8 返回同一批 id，需带 year&month 才能翻页，实抓需验证该行为；`/ext/` 与 `/ext/control/` 不在 robots Disallow 中，但以浏览器同等请求方式少量调用为限） |

## 证据摘录（实测）

三一：
- `robots.txt` 关键行：`Disallow: /xwzx/`、`Disallow: /mtsj/`、`Disallow: /sjzc/`（旧站目录）；无 `/news` 相关 Disallow
- `/news` → 200，`<title>三一集团最新新闻_三一集团官网</title>`，351KB，含 `"/news/16476.html"`…`"/news/16563.html"` 与 `href="/news?page=0&amp;size=6"`…`page=5`
- 列表项日期：`class="news-date">2026.08.04` 等；页面含 `__NUXT__`（Nuxt SSR 标记）
- `/news/16563.html` → 200，`<title>中南大学党委书记安实率队走访三一集团_三一集团官网</title>`（346KB SSR 全文）

徐工：
- `robots.txt` 全文：`User-agent: *` / `Disallow:` / `Sitemap: https://www.xcmg.com/sitemap.xml`
- `/aboutus/news.htm` → 200，`<title>集团新闻-徐工官网</title>`，112KB，但 `news-detail` 链接计数 = 0（条目异步加载）；壳页含 `<input type="hidden" value="22519" id="channelId" />`
- `js/news_list.js` 源码节选：`url: "/ext/ajax_news.jsp", data: {year, month, keys, flag: "getdata", pageNo: nowPage, channelId}`，`pageSize = 4`，滚动加载
- `/ext/ajax_news.jsp?flag=getdata&pageNo=1&channelId=22519` → 200，15KB HTML 片段，12 个 `href="/aboutus/news-detail-1128931.htm"` 等，日期 2026/08/05~08/07
- `/ext/control/ajax_getMonth.jsp?flag=getyear&channelId=22519` → `<li>2026</li><li>2025</li><li>2024</li><li>2023</li><li>2022</li>`
- `/ext/ajax_news.jsp?...&year=2024&month=3` → 返回 `news-detail-1128065` 等，日期 2024.03.30~04.02（历史归档可达）
- 异常观察：不带 year/month 时 pageNo=1~8 返回相同 id 集合（1128917~1128934），原因未确认——需实抓验证翻页逻辑
