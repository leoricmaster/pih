# KHL（国际工程媒体集团 khl.com）

- URL：https://www.khl.com/（集团站，含 /news/）；子品牌站见下
- 摸底卡编号：06
- 调研日期：2026-08-25
- 调研方式：纸面（curl 单发请求，不批量抓取）

## 摸底记录

| 字段 | 内容 |
|---|---|
| 类型 | 列表页 HTML + News Sitemap（XML）；子品牌（Construction Briefing 等）为登录墙后 SPA/API |
| 采集方式预判 | 集团站文章：HTTP+解析（robots 未禁 /news/ 路径）；发现新文章优先走 `sitemap-index-articles.xml`（站点自己在 robots 中声明 Sitemap，属邀请抓取的入口）。注意 `/rss*`、`/*.rss`、`/api/*`、`/ajax/*` 均 Disallow，RSS 路线不可用 |
| robots 允许度 | `https://www.khl.com/robots.txt`（200，实测全文 617 字节）：`User-agent: *` 下 Disallow 含 `/account/*`、`/*.rss`、`/api/*`、`/rss*`、`/ajax/*`、`/files/*`、`/*.pdf$` 等；**`/news/…` 与 `/sitemap*` 不在禁止列**，且末尾声明 `Sitemap: https://www.khl.com/sitemap-index.xml` 与 `google-news-sitemap.xml`，另有 `Crawl-Delay: 10`（对全部 UA，实抓须遵守 ≥10s 间隔） |
| 反爬观察 | 集团站文章页：无登录墙，正文完整内联（实测 2 篇文章 HTML 内含成段 `<p>` 正文与 schema.org NewsArticle JSON-LD）。子品牌站：`constructionbriefing.com` 首页 HTTP 302 → `https://khl.auth.zephr.com/zephr/sso?siteRequestUrl=…`（Zephr 付费墙 SSO），robots 亦 Disallow `zephr.*`——**明确登录墙，不碰**。Cloudflare 前置（IP 104.26.10.170），页面较慢（首页 3.5s）但无挑战页。google-news-sitemap.xml 实测返回空 `<urlset/>`（0 条，未确认是否动态填充） |
| 更新频率预估 | 日更（sitemap-articles 索引按"年-周"分片，如 `sitemap-articles-2025-7-27.xml`、`2025-11-46.xml`；集团 /news/ 最新文章 id 8127851/8128645，测试文章发布日期 2025-07-08——集团站新闻为营销内容，行业新闻在子品牌，频率结论"日更"基于子品牌媒体属性推断+搜索常识，标注：集团站本体频率未精确统计） |
| 历史内容可达性 | 优：`sitemap-index-articles.xml` 列出 2020-2025 多个年度分片（实测见到 2020-05/06/09/12、2025-07/11 分片），单分片内含 `<loc>`+`<news:publication_date>`，可回溯多年；文章 URL 稳定 `/news/<slug>/<id>.article` |
| 纸面结论 | 需适配（限定范围：仅集团站 + sitemap 发现；子品牌站因 Zephr 登录墙放弃——这正是"付费/登录深层内容不测"边界） |
| 实抓候选 | 备选（是，但有条件）。理由：① robots 允许 /news/ 且主动提供 sitemap，Crawl-Delay 10 可遵守；② 正文 SSR 完整、适合 L2 国际媒体样本；③ 但内容以集团营销文为主，工程机械行业情报密度存疑——建议实抓仅做 1 页 sitemap 分片验证，若情报价值低则不进锁定清单 |

## 证据摘录（实测）

- `robots.txt` 关键行（节选）：`Disallow: /rss*`、`Disallow: /*.rss`、`Disallow: /api/*`、`Disallow: /ajax/*`、`Sitemap: https://www.khl.com/sitemap-index.xml`、`Crawl-Delay: 10`
- `https://www.khl.com/` → 200（3.5s），`<title>KHL Group - Home - KHL Group</title>`，首页链接 `/news/beyond-the-logo-…/8127851.article` 等
- `https://www.khl.com/news` → 200，`<title>News - KHL Group</title>`，正文为"Click on any link to see the latest news from our Construction & Power industry brands"的品牌导航页（无文章列表）
- `https://www.khl.com/news/unlocking-ais-potential-in-b2b-marketing-and-sales/8127073.article` → 200（95KB），HTML 内含成段正文（如"46% of B2B buyers are using generative AI tools…"）与 `{"@context":"https://schema.org","@type":"NewsArticle"` JSON-LD
- `https://www.constructionbriefing.com/` → HTTP 302，`location: https://khl.auth.zephr.com/zephr/sso?siteRequestUrl=https%3A%2F%2Fwww.constructionbriefing.com%2F`（登录墙证据）
- `https://www.khl.com/google-news-sitemap.xml` → 200 `text/xml`，正文 `<?xml…?><urlset …/>`（空）
- `https://www.khl.com/sitemap-index-articles.xml` → 200，含 `sitemap-articles-2025-7-27.xml`、`sitemap-articles-2020-12-50.xml` 等分片；`sitemap-articles-2025-7-27.xml` → 200，含 3 条 `<url>`（news:publication_date 2025-07-08）
- `https://www.internationalconstruction.com/` → 200 但正文仅 114 字节 JS 跳转 `/lander`（域名停放迹象，非可用新闻源）
