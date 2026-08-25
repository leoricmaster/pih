# 实抓选源（Task 3 · Step 1）

日期：2026-08-25 ｜ 选源人：SPK-1 实施工程师 ｜ 上游：`sources/` 8 张摸底卡（Task 2）

覆盖性要求（brief）：≥1 个 RSS（或 RSSHub 候选）、≥1 个列表页 HTML 解析、≥1 个变更监控候选。

## 选定 5 源

| # | 信源 | 摸底卡 | 类型角色 | 选择理由 |
|---|---|---|---|---|
| 1 | CCMA 协会（cncma.org） | 01 | 列表页 HTML 解析 + 变更监控候选 | L1 权威数据源（月度销售快报是附件 A 核心），无 robots（软 200 陷阱需实抓验证），分页/详情 URL 规则简单 |
| 2 | 三一集团（sanygroup.com） | 02 | 列表页 HTML 解析（SSR）+ 变更监控候选 | 主机厂代表；Nuxt SSR 直出链接；robots 对 /news 无 Disallow；翻页规则简单 |
| 3 | 铁甲网（cehome.com） | 03 | 列表页 HTML 解析 | 垂直媒体代表；robots 23 字节 `allow: /` 全站明确允许；SSR 无反爬；需实抓验证深分页 |
| 4 | 第一工程机械网（news.d1cm.com） | 04 | 列表页 HTML 解析 | 行业媒体；robots 对资讯路径无禁止；需实抓验证栏目翻页深度与软 404 判定 |
| 5 | KHL 集团站（khl.com） | 06 | RSS 替代路线（News Sitemap） | 唯一"RSS 等价物"可行源：robots 禁 /rss* 但主动声明 sitemap-index-articles.xml（邀请抓取入口）；L2 国际媒体代表；Crawl-Delay 10 本源按 10s 间隔执行 |

## 落选说明

- 徐工（卡 02 备选）：AJAX 端点结构已纸面摸清，与三一同属主机厂，覆盖重复——5 源名额下不选。
- 千里马（卡 08）：419 频控需 ≥60s 节流 + 正文 `****` 会员遮蔽，摸底已判定性价比低、候选排末位，前 4 候选顺利即不选。
- lmjx（卡 05）：百度 WAF 全站 405，摸底判定"实抓候选否"。
- CNIPA（卡 07）：专利数据入口瑞数 JS 反爬（412/202），摸底判定"实抓候选否"。
- RSS 覆盖说明：8 源摸底均未发现可用原生 RSS（cehome/d1cm 的 /rss 路径 404 或软 404，KHL robots 禁 /rss*），故以 KHL News Sitemap 承担"RSS（或 RSSHub 候选）"覆盖角色——sitemap 是站点自己在 robots 中声明的发现入口，语义等价于 feed 的新文章发现。
