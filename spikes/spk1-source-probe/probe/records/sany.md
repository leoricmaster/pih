# 三一集团（sanygroup.com）实抓记录

- 日期：2026-08-25 14:24 CST
- 脚本运行：`fetch_samples.py sany https://www.sanygroup.com/news`
- 间隔：2s ｜ 列表页请求：1 个 ｜ 详情请求：5 次（另有一次首轮 5 次详情误抓产品页后作废重抓，见"偏差"）

| 字段 | 内容 |
|---|---|
| HTTP 状态 | 列表页 200（305KB 首轮 / 356KB 二轮）；详情 10/10 全 200 |
| robots 判定 | `https://www.sanygroup.com/robots.txt` 200；`User-agent: *` 下 Disallow 为 `/news/null?imageMogr2/`、`/*.asp`、旧版目录等——`/news`、`/news/<id>.html` 不命中任何 Disallow → 允许 |
| 页面结构 | Nuxt SSR：列表页 HTML 内直接含 `/news/<id>.html` 链接与 `news-date` 日期（无需执行 JS）；详情页 344KB SSR 全文 |
| 正文可提取性 | 好。样本 sany-00（《至高荣誉！三一再获国家科学技术进步二等奖》）约 24,185 个 CJK 字符（页面大：含 __NUXT__ 数据与全站导航） |
| 反爬行为 | 无：无挑战、无频控（间隔 2s 顺畅） |
| 抓取耗时 | 约 17s（1 列表 + 5 详情） |
| 存档条数 | 5 条（sany-00 ~ sany-04，均为 /news/<id>.html 新闻详情） |

## 偏差与处理

首轮运行朴素链接提取把 `/product/<拼音>/` 产品页当详情存了 5 条（非新闻）——已删除并在脚本 `extract_links` 中排除 `/product|about|list|special|search|col/` 路径段后重抓。作废请求共 5 次详情 GET（计入同源请求总量：本源共 11 次页面 GET，间隔均 ≥2s）。

## 结论

直抓可行，列表/详情均 SSR。建议工程化时按 `/news/\d+\.html` 正则取链接、按 `<title>`+`__NUXT__` 结构取正文。
