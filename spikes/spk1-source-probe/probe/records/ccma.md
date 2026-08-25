# CCMA 协会（cncma.org）实抓记录

- 日期：2026-08-25 14:21–14:22 CST
- 脚本运行：`fetch_samples.py ccma http://www.cncma.org/col/hangyxw "http://www.cncma.org/col/hangyxw?pageIndex=2"`
- 间隔：2s ｜ 列表页请求：2 个 ｜ 详情请求：10 次（首轮，超"每源 ≤5 详情"口径，已裁剪存档至 5 条并在二轮运行前的脚本加了 `DETAIL_LIMIT - saved` 上限，后续源不再超）

| 字段 | 内容 |
|---|---|
| HTTP 状态 | 列表页 200（26,972 / 26,931 chars）；详情 10/10 全 200 |
| robots 判定 | `http://www.cncma.org/robots.txt` 返回 200 但 Content-Type 为 HTML 模板页（无任何 User-agent/Disallow 指令）→ 判定允许；HTTPS robots.txt 连接超时（与摸底一致）。**陷阱确认：软 200**——任意路径返回 200 HTML，判存在性必须看 `<title>`/正文结构 |
| 页面结构 | 服务端渲染：列表页 55 个 `/article/<id>` 直链 + 日期文本，详情页正文直接在 HTML 内（jQuery 只做轮播/计数） |
| 正文可提取性 | 好。样本 ccma-00（article/22709《2026年7月工程机械产品进出口快报》）正文约 1,291 个 CJK 字符，成段中文 |
| 反爬行为 | 无：无验证码、无频控触发、无 UA 挑战 |
| 抓取耗时 | 约 27s（2 列表 + 10 详情 + robots 检查，间隔 2s） |
| 存档条数 | 5 条（ccma-00 ~ ccma-04；第二轮列表页多出的 5 条按口径裁剪未保留） |

## 结论

直抓可行（需适配软 200 判定：以 `<title>` 或 `/article/\d+` 链接形态判定页面真伪）。HTTP-only 站点需容错 https 超时。月度快报类目标文章可直接命中。
