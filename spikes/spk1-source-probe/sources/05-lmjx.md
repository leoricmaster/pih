# 中国路面机械网（lmjx.net）

- URL：https://www.lmjx.net/（新闻频道 news.lmjx.net）
- 摸底卡编号：05
- 调研日期：2026-08-25
- 调研方式：纸面（浏览器/文档查阅，不抓取）

## 摸底记录

| 字段 | 内容 |
|---|---|
| 类型 | 未确认（列表页 HTML 推测——基于搜索结果摘要"新闻中心提供行业资讯/租赁专题/招标信息"与栏目 URL `List_2.shtml`/`List_97.shtml`；本机实测无法取得页面本体） |
| 采集方式预判 | 未确认（若 WAF 拦截持续：changedetection.io 浏览器渲染模式或放弃） |
| robots 允许度 | 不可得：`https://www.lmjx.net/robots.txt` 返回 HTTP 405 + `Server: BAIDU_WAF` + 验证码页（非真实 robots.txt）。判定：**无法确认**——站点被 WAF 全站前置拦截，robots 语义不可读；实抓前必须先解决"正常浏览器访问能否通过" |
| 反爬观察 | **百度云 WAF（BAIDU_WAF）全站验证码拦截**：www / m / news 三个子域、首页 / robots.txt / 栏目页 / 猜测的文章深层路径，全部返回 HTTP 405 + `<title>安全验证码-独立验证</title>`（803 字节固定页），响应头 `server: BAIDU_WAF`、`bdwaf-request-id: <uuid>`，注入 `BIOC_CONFIG_SCRIPT`（biocOrigin 指向 sec-captcha-waf.baidu.com）。已试并失败：携带返回的 abymg_id Cookie 重访（仍 405）、HTTP 明文（301→HTTPS 后 405）、完整浏览器头（Sec-Fetch/UA 等，仍 405）。**未尝试也不尝试**：执行其验证 JS / 打码（属绕过反爬，违反纪律） |
| 更新频率预估 | 未确认（无法访问页面本体；仅搜索摘要表明站点活跃且是百度/谷歌新闻源） |
| 历史内容可达性 | 未确认（同上） |
| 纸面结论 | **访问失败待复核**——本机网络环境下全站被百度 WAF 拦截（2026-08-25 13:50–13:53 CST 多次实测）。不猜。复核方向：换网络环境/真人浏览器手动访问一次，若真人也遇验证码且过不去则降级为"放弃"；若真人可过，属于"仅机器请求被拦"，采集需走 changedetection.io 类浏览器渲染方案或放弃 |
| 实抓候选 | 否（当前证据下）。理由：HTTP 层全站 405，无可用入口；实抓前置条件（可正常访问）不成立。列为待复核项 |

## 证据摘录（实测）

- `https://www.lmjx.net/robots.txt` → HTTP 405，`Server: BAIDU_WAF`，正文 `<title>安全验证码-独立验证</title>`，含 `window.BIOC_OPTIONS = {ctype: 'b_track_match', biocOrigin: 'https://sec-captcha-waf.baidu.com…'}`
- `https://www.lmjx.net/` → HTTP 405，同上；`set-cookie: abymg_id=…; Secure; SameSite=None`
- 携带 abymg_id Cookie 二次请求 → 仍 405（2026-08-25 13:50 CST）
- `http://www.lmjx.net/` → 跳转 HTTPS 后 405；`https://m.lmjx.net/` → 405；`https://news.lmjx.net/` → 405；`https://news.lmjx.net/List_2.shtml`（搜索摘要给出的业界动态栏目）→ 405
- 完整浏览器头（Accept/Accept-Language/Sec-Fetch-*）重试 → 仍 405（`bdwaf-request-id: f67fed2e-…`）
- Wayback Machine 复核尝试：archive.org 连接超时（30s），未取得存档参照
