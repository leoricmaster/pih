# 铁甲网（cehome.com）实抓记录

- 日期：2026-08-25 14:26 CST
- 脚本运行：`fetch_samples.py cehome https://www.cehome.com/news/hangye/`
- 间隔：2s ｜ 列表页请求：1 个 ｜ 详情请求：5 次（首轮 5 次详情因编码乱码作废重抓，见"偏差"）

| 字段 | 内容 |
|---|---|
| HTTP 状态 | 列表页 200（21,352 bytes）；详情 10/10 全 200 |
| robots 判定 | `https://www.cehome.com/robots.txt` 200，全文 2 行：`User-agent: *` / `allow: /` → 全站明确允许（与摸底 23 字节口径一致） |
| 页面结构 | 服务端渲染：频道页 19 条 `/news/<YYYYMMDD>/<id>.shtml` 直链 + 分页 `/<N>/`；详情页正文直接在 HTML |
| 正文可提取性 | 好。样本 cehome-00（《铭德—升降驾驶室改装解锁高空视野》）约 1,769 个 CJK 字符，含"日期：2026-08-25"字段 |
| 反爬行为 | 无：无挑战、无频控 |
| 抓取耗时 | 约 14s（1 列表 + 5 详情） |
| 存档条数 | 5 条（cehome-00 ~ cehome-04，均为 20260825 当日文章） |

## 偏差与处理

**编码陷阱（工程化要点）**：cehome 响应头无 charset，requests 将 GBK 页面按 ISO-8859-1 解码成乱码（首轮 5 条样本 title 全乱码）——脚本增加 `decode_body()`（响应头 charset → HTML meta charset → utf-8/gbk 严格试探）后重抓，全部正常。作废 5 次详情 GET（本源共 11 次页面 GET，间隔均 ≥2s）。

## 结论

直抓可行。深分页（共 12,127 页）行为未在本轮验证（仅取第 1 页），留作 SPK-1 报告的已知未验证项。
