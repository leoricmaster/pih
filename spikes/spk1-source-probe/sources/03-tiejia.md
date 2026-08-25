# 铁甲网（铁甲工程机械网 cehome.com）

- URL：https://www.cehome.com/（资讯频道 `/news/`，行业频道 `/news/hangye/`）
- 摸底卡编号：03
- 调研日期：2026-08-25
- 调研方式：纸面（浏览器/文档查阅，不抓取）

## 摸底记录

| 字段 | 内容 |
|---|---|
| 类型 | 列表页 HTML（静态 .shtml 列表 + 详情） |
| 采集方式预判 | HTTP+解析；changedetection.io 备选 |
| robots 允许度 | `https://www.cehome.com/robots.txt`（200，`text/plain`，实测全文 2 行）：`User-agent: *` / `allow: /` → 全站明确允许 |
| 反爬观察 | 无登录墙（资讯正文匿名可看，页面右上角有 `class="login fr"` 登录入口但不遮挡内容）；无验证码；无频控触发；页面 SSR（无 React/Vue 空壳迹象，列表链接直接在 HTML 中）。域名注意：brief 起点线索 toujian.com 实测为弃置域名——`https://www.toujian.com` TLS 握手失败（OpenSSL error: tlsv1 unrecognized name，IP 203.12.200.78），`http://www.toujian.com/` 返回 `<title>网站建设中</title>`（4,850 字节占位页），其 robots.txt 为 `User-agent: *  Disallow: /`；`www.tiejia.com` 同样 TLS 失败。经搜索核实（来源：搜索结果摘要，见报告），铁甲系资讯主站为 cehome.com、公司域 tiejia.com.cn、二手平台 tiebaobei.com |
| 更新频率预估 | 日更（列表第 1 页最新条目日期前缀 20260825，与调研日同日；第 2 页为 20260818~23） |
| 历史内容可达性 | 可回溯：`/news/hangye/` 频道分页 `/<page>/`，页脚显示"共12127页"（末页链接 `/news/hangye/12127/`）；实测 page 1（20260825 条目）与 page 6（20260824 条目，19 条中 9 条为新）内容确实不同。注意：page 30/200 返回的主列表条目与 page 6 相同（未确认深页是否被截断/缓存，标注需实抓验证）；侧栏"编辑推荐"区显示 2021–2022 年旧文（缓存内容，非主列表） |
| 纸面结论 | 需适配（toujian.com 域名失效需换成 cehome.com；结构本身接近直抓） |
| 实抓候选 | 是。理由：① robots 明确 `allow: /`；② SSR 列表+详情、无反爬迹象；③ 作为垂直媒体代表；④ 需实抓验证深分页行为与正文完整性（详情页 `/news/20260825/390909.shtml` 200，19KB，含"日期：2026-08-25"字段） |

## 证据摘录（实测）

- `https://www.cehome.com/robots.txt` → 200，正文（23 字节）：`User-agent: *` / `allow: /`
- `https://www.toujian.com/robots.txt` → curl (35) `OpenSSL::tlsv1 unrecognized name`；`http://www.toujian.com/robots.txt` → 200，正文：`User-agent: *` / `Disallow: /`
- `http://www.toujian.com/` → 200，`<title>网站建设中</title>`（占位页）
- `https://www.cehome.com/` → 200，`<title>铁甲工程机械网-用心服务中国工程机械行业用户、推动工程机械行业进步！</title>`（93KB）
- `https://www.cehome.com/news/` → 200，`<title>工程机械资讯_工程机械新闻_工程机械热点动态_铁甲工程机械网</title>`，59 个 `/news/<YYYYMMDD>/<id>.shtml` 链接，最新 `20260825/390905~390909.shtml`
- `https://www.cehome.com/news/hangye/` → 200，19 条链接；页脚 `共12127页`，下一页 `href=".../news/hangye/2/" class="nextPage"`
- `https://www.cehome.com/news/20260825/390909.shtml` → 200，`<title>澳洲上市 Global Lithium Resources Limited（ASX:GL1）深度分析报告_铁甲工程机械网</title>`，正文含"日期：2026-08-25"
- `/rss`、`/rss.xml`、`/feed`、`/sitemap.xml` → 均 404（无 RSS）
