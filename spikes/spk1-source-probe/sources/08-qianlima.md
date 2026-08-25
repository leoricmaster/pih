# 千里马招标网（qianlima.com）

- URL：https://www.qianlima.com/（首页聚合 + `/zb/area_<N>/` 区域门户）
- 摸底卡编号：08
- 调研日期：2026-08-25
- 调研方式：纸面（浏览器/文档查阅，不抓取）

## 摸底记录

| 字段 | 内容 |
|---|---|
| 类型 | 列表页 HTML（GBK 编码！区域门户列表 + `/bid-<id>.html` 详情；首页聚合 30 条最新招标） |
| 采集方式预判 | HTTP+解析（requests + BeautifulSoup，注意 `resp.encoding='gbk'`）；changedetection.io 备选（低频监控区域门户页） |
| robots 允许度 | `https://www.qianlima.com/robots.txt`（200，实测 2,597 字节，节选）：`User-agent: *` 下 Disallow 大量搜索/会员/后台路径（`/common/search.*`、`/search.jsp?q=*`、`/sou_*`、`/article/`、`/area_*`、`/html/*`、`/institution*`、`/crm*` 等）。**关键判定：`/bid-*.html` 详情页与 `/zb/` 不在 Disallow 列（实测 robots 全文 grep 'bid' 计数 0）→ 允许**。但注意 `/area_*` 被 Disallow，而区域门户实际路径是 `/zb/area_6/`（前缀 `/zb/`，非顶层 `/area_6`），规则匹配上不命中 Disallow `/area_*`（该规则匹配根级路径）——此判定按 robots 通配语义成立，实抓时保留该解释依据 |
| 反爬观察 | **华为云 WAF 频控/验证码**：连续请求详情页数秒内触发 HTTP 419 + `<title>Access Verification</title>`（`meta Server: HuaweiCloudWAF`，表单 action `/verifydwhzqcp-captcha`，含 captcha.jpg）——实测连续访问 2~3 个详情页即触发；静置 30~60s 后单发恢复 200。正文**会员遮蔽**：详情页正文可用但关键信息以 `****` 替代，页面明示"下文中****为隐藏内容，仅对千里马会员开放"。列表页（首页/区域门户）未见触发。页面同时含 noscript"doesn't work properly without JavaScript"（Vue 壳），但列表与详情正文均在 SSR HTML 内 |
| 更新频率预估 | 高频日更多波次（首页招标 id 已到 625086115；区域门户 area_6（广西）50 条，id 范围 488913593~625040502，最新当日） |
| 历史内容可达性 | 受限：区域门户分页 `index_2.html` 实测 301 → `/40x.html`（404 页），未发现可用翻页；robots Disallow `/history/2010~2018/*.html`（历史库存在但禁抓）。**增量可行、回溯 ≥3 个月不可行**（列表仅首页窗口 + 历史 404/禁抓） |
| 纸面结论 | 需适配（增量采集可行：低频（≥60s 间隔）轮询区域门户/首页 + 详情直抓；正文 `****` 遮蔽使"事实描述"类字段残缺，情报价值打折） |
| 实抓候选 | 备选。理由：① robots 允许 /bid 路径；② 列表 SSR 可解析；③ 招标/中标公告是 L3 机会类情报独有来源；④ 但 419 频控（需 ≥60s 节流）+ 会员遮蔽降低性价比——实抓候选排末位，若前 4 候选（CCMA/三一/cehome/d1cm）顺利可不选；若选，验证点=频控阈值与遮蔽后正文剩余信息量 |

## 证据摘录（实测）

- `robots.txt` 关键行（节选）：`Disallow: /sou_*`、`Disallow: /area_*`、`Disallow: /article/`、`Disallow: /search.jsp?q=*`、`Disallow: /history/2010/*.html`…`/history/2018/*.html`（全文无 `/bid` 相关规则）
- `https://www.qianlima.com/` → 200，`Content-Type: text/html; charset=gbk`，`<title>千里马-千里马招标网|招投标|国内招标行业门户网站</title>`（331KB），首页 30 条 `/bid-2-<id>.html`
- `https://www.qianlima.com/zb/area_6/` → 200，`<title>广西招标网_广西招标采购网_广西工程建设招标网</title>`，50 条 `/bid-<id>.html`（如"广西灵山恒福工程咨询有限责任公司关于2026年…"）
- `https://www.qianlima.com/bid-625028512.html` → 200（121KB），`<title>广西壮族自治区妇幼保健院…论证会报名公告-千里马招标网</title>`，正文含"下文中****为隐藏内容，仅对千里马会员开放"，可见部分含截止时间/地点（部分 `****` 化）
- 连续访问第 2~3 个详情 → HTTP 419 `Access Verification`（`meta http-equiv="Server" content="HuaweiCloudWAF"`；表单 `action="/verifydwhzqcp-captcha"`、`captcha.jpg`）；带首页 Cookie 无效；静置 30s 与 60s 后单发均恢复 200（2026-08-25 13:57~14:02 CST 实测）
- `https://www.qianlima.com/zb/area_6/index_2.html` → 200 但 `Location: https://www.qianlima.com/40x.html`（软跳 404，无可用翻页）
