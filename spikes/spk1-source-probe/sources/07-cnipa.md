# 国家知识产权局专利公布（cnipa.gov.cn）

- URL：https://www.cnipa.gov.cn/（政务门户）；专利检索 pss-system.cponline.cnipa.gov.cn；公布公告 epub.cnipa.gov.cn
- 摸底卡编号：07
- 调研日期：2026-08-25
- 调研方式：纸面（curl 单发请求，不批量抓取）

## 摸底记录

| 字段 | 内容 |
|---|---|
| 类型 | 政务门户列表页 HTML（公告公报栏 `/col/col74/`）+ SPA 检索系统（专利数据本体） |
| 采集方式预判 | 政务公告栏：HTTP+解析可行；专利检索系统：**浏览器自动化或放弃**（JS 反爬前置）——不属"纸面可判定直抓" |
| robots 允许度 | `https://www.cnipa.gov.cn/robots.txt` → HTTP 404（nginx 404 页，实测）：**门户未部署 robots.txt**，按未声明处理、低频少量。pss-system 与 epub 子域：robots.txt 请求被反爬层改写（pss 返回 SPA 壳页、cponline 返回 JSON 404），**不可得** |
| 反爬观察 | **专利数据入口有瑞数类 JS 反爬**：`https://pss-system.cponline.cnipa.gov.cn/` → HTTP 412 Precondition Failed，响应注入 `$_ts=window['$_ts']` 混淆 JS 与外链 `…/d8y2r5aICjmZ.1058d2a.js`（瑞数动态令牌特征）；携带其下发 Cookie 重试仍 412（实测 2 次）。`http://epub.cnipa.gov.cn/`（门户"专利公布公告"栏目直指该域）→ HTTP 202 Accepted + 同类 `$_ts` 挑战页（Set-Cookie `WEB=…` 后重试仍 202）。门户静态页（www）无反爬：gzip 响应（需 `--compressed`）、SSR HTML |
| 更新频率预估 | 政务公告栏：周更级（col74 第 1 页条目日期 2026-07-21 ~ 2026-08-12）。专利公布数据本体：每周固定批次（发明专利周公告，公开常识，非实测——标注未确认） |
| 历史内容可达性 | 政务公告栏：`/col/col74/index.html` SSR 列表可达，`/art/2026/8/12/art_74_207698.html` 详情直链 200；更早条目未翻页验证（未确认 ≥3 个月）。专利检索系统：因 412/202 挑战，可达性未确认 |
| 纸面结论 | **部分放弃**：专利公布数据本体（pss-system / epub）在"不绕反爬"纪律下纸面判定不可抓；可抓的是门户公告公报栏（地理标志/公告类政务信息），与"专利公布"情报目标错位 → 该信源对"工程机械专利动态"需求的满足度低。备选路线（仅记录，不实施）：周度专利公布数据有官方批量数据产品（发明专利公告 XML/光盘），属数据采购非爬取范畴 |
| 实抓候选 | 否（当前证据下）。理由：目标内容（专利公布）入口全被 JS 反爬前置；门户公告栏内容类型与需求不匹配。若 Task 3 需要一个"政务站解析"样本可临时借用 col74，但不作为专利情报源 |

## 证据摘录（实测）

- `https://www.cnipa.gov.cn/robots.txt` → 404（nginx 默认 404 页，548 字节）
- `https://www.cnipa.gov.cn/` → 200（需 `--compressed`，解压后 52KB），`<title>国家知识产权局</title>`；页脚导航含 `<a href="http://epub.cnipa.gov.cn/">专利公布公告</a>`、`/col/col74/index.html 公告公报`
- `https://pss-system.cponline.cnipa.gov.cn/` → HTTP 412，`Set-Cookie: dX1xbeyMT58WO=…`，正文含 `$_ts=window['$_ts'];…$_ts.cd="…"`（瑞数特征混淆串）；带 Cookie 重试 → 仍 412
- `https://pss-system.cponline.cnipa.gov.cn/robots.txt` → 200 但 `text/html`，正文为 SPA 壳（`<div id="app">` + noscript 提示"doesn't work properly without JavaScript"）——robots 被 SPA 路由吞掉
- `https://cponline.cnipa.gov.cn/robots.txt` → 404 JSON：`{"code":404,"message":"No handler found for GET /robots.txt"}`
- `http://epub.cnipa.gov.cn/` → HTTP 202，`Server: ******`，正文同为 `$_ts` 挑战页；带 `WEB` Cookie 重试仍 202
- `https://www.cnipa.gov.cn/col/col74/index.html` → 200，`<title>国家知识产权局 公告</title>`，条目 `/art/2026/8/12/art_74_207698.html` 等 5 条（2026-07-21~08-12）
- `https://www.cnipa.gov.cn/art/2026/8/12/art_74_207698.html` → 200，`<title>…地理标志产品认定的公告（第687号）</title>`
