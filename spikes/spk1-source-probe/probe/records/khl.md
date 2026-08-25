# KHL 集团站（khl.com）实抓记录

- 日期：2026-08-25 14:28–14:31 CST
- 脚本运行：`PIH_GAP_SECONDS=10 fetch_samples.py khl https://www.khl.com/sitemap-articles-2020-9-36.xml`（另：robots 检查 + sitemap-index + 2 个分片探测的辅助请求，间隔均 ≥10s）
- 间隔：**10s（按 robots `Crawl-Delay: 10` 执行**，PIH_GAP_SECONDS 覆盖默认 2s）｜ 列表页等价物：1 个 News Sitemap 分片 ｜ 详情请求：5 次

| 字段 | 内容 |
|---|---|
| HTTP 状态 | sitemap-index 200；分片 200（2,737 bytes）；详情 5/5 全 200 |
| robots 判定 | `https://www.khl.com/robots.txt` 200：`User-agent: *` Disallow `/account/*`、`/*.rss`、`/rss*`、`/api/*`、`/ajax/*`、`/files/*` 等；**`/sitemap*` 与 `/news/<slug>/<id>.article` 不在禁止列 → 允许**；`Crawl-Delay: 10` 已遵守（10s 间隔） |
| 页面结构 | News Sitemap（XML）作为"列表页"等价物：分片含 `<loc>` 文章 URL + `<news:publication_date>`；详情页 SSR 含成段正文 + schema.org NewsArticle JSON-LD |
| 正文可提取性 | 好。样本 khl-00（《马尼托瓦克公司新总裁表示不支持关税》）约 906 个 CJK 字符（另有英文正文），JSON-LD 结构化元数据齐 |
| 反爬行为 | Cloudflare 前置但无挑战页；页面较慢（详情 ~3.5s/页） |
| 抓取耗时 | 约 66s（1 sitemap 分片 + 5 详情，间隔 10s） |
| 存档条数 | 5 条（khl-00 ~ khl-04，2020-09 发布的行业新闻——中文标题，正文中文） |

## 过程说明（分片选择）

- sitemap-index-articles.xml 共 31 分片（2017-11 ~ 2025-11）。最新分片 2025-11-46 仅 2 条 URL、2025-7-27 仅 3 条——**近期分片条数不足以凑 5 详情**；2020-9-36 分片 7 条、2020-12-50 分片 5 条。
- 选用 2020-9-36（7 条中取 5）。样本发布日期 2020-09——**非近期内容**，如实记录：KHL 集团站 /news 新文章发现节奏慢（sitemap 更新稀疏），且摸底已注明集团站以营销内容为主、行业新闻在登录墙后的子品牌站。
- sitemap URL 含未转义中文路径（如 `/news/马尼托瓦克…/1145960.article`），requests 自动百分号编码后 200 正常。

## 结论

可抓（限集团站 + sitemap 路线），robots 遵守成本高（Crawl-Delay 10 → 单源吞吐 ~6 页/分钟）。情报密度存疑（本轮 5 条样本为 2020 年旧闻，集团站无近期高频更新证据）——建议不进 SPK-1 锁定清单主选，仅作"sitemap 发现路线可行"的技术证据。
