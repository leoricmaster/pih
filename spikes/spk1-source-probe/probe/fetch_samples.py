"""SPK-1 实抓脚本：对选定信源抓 1–3 页列表页 + 3–5 条详情，存档样本。

用法：python fetch_samples.py <信源名> <列表页URL> [<更多列表页URL>...]
纪律：robots 先行；同源请求间隔 ≥2s；每次运行打印逐请求日志。
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from _lib.probe import fetch_robots_ok, polite_get

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "samples"
DETAIL_LIMIT = 5
# 默认 2s；站点 robots 声明 Crawl-Delay 更大时用环境变量 PIH_GAP_SECONDS 覆盖（如 KHL=10）
REQUEST_GAP_SECONDS = float(os.environ.get("PIH_GAP_SECONDS", "2"))


def decode_body(resp) -> str:
    """按响应头 charset 或 HTML meta 声明解码（requests 无 charset 头时默认 ISO-8859-1，会乱码 GBK 页）。"""
    content_type = resp.headers.get("Content-Type", "")
    charset = None
    for part in content_type.split(";"):
        part = part.strip()
        if part.lower().startswith("charset="):
            charset = part.split("=", 1)[1].strip('" ').lower()
            break
    if not charset or charset in ("iso-8859-1", "ascii"):
        import re

        m = re.search(rb'charset\s*=\s*["\']?([\w-]+)', resp.content[:2048])
        if m:
            meta_charset = m.group(1).decode("ascii", "ignore").lower()
            if meta_charset not in ("iso-8859-1", "ascii"):
                charset = meta_charset
    if not charset or charset in ("iso-8859-1", "ascii"):
        # 仍未知：中文站多为 utf-8 或 gbk，用严格解码试探
        for cand in ("utf-8", "gbk"):
            try:
                resp.content.decode(cand)
                charset = cand
                break
            except UnicodeDecodeError:
                continue
        if charset is None:
            charset = "utf-8"
    try:
        return resp.content.decode(charset, errors="replace")
    except LookupError:
        return resp.content.decode("utf-8", errors="replace")


def extract_links(html: str, base_url: str) -> list[str]:
    """从列表页 HTML（或 News Sitemap XML）提取详情链接（朴素正则，Spike 够用）。

    规则：同源（netloc 一致）+ 详情页 URL 形态（/article/<id>、.shtml、.html、
    .article、末段含数字的裸路径）——排除 css/js/图片与栏目页。
    News Sitemap（XML <loc>）作为列表页等价物时从中取 <loc>。
    """
    import re
    from urllib.parse import urljoin, urlsplit

    base_host = urlsplit(base_url).netloc
    skip_ext = (".css", ".js", ".jpg", ".png", ".gif", ".ico", ".pdf")
    if "<urlset" in html[:2000].lower():
        hrefs = re.findall(r"<loc>([^<]+)</loc>", html)
    else:
        hrefs = re.findall(r'href=["\']([^"\']+)["\']', html)
    seen, links = set(), []
    for h in hrefs:
        if h.startswith(("javascript:", "#", "mailto:", "tel:")):
            continue
        full = urljoin(base_url, h)
        if urlsplit(full).netloc != base_host:
            continue
        if full in seen:
            continue
        path = urlsplit(full).path
        if path.endswith(skip_ext):
            continue
        last = path.rstrip("/").rsplit("/", 1)[-1]
        # 日期前缀命名的详情页（如 d1cm /20260825191920.shtml、cehome /news/<date>/<id>.shtml）
        if re.search(r"/20\d{6,}", path):
            is_detail = True
        elif (
            bool(re.fullmatch(r"/article/\d+", path))
            or re.search(r"/news/[0-9]+", path)
            or re.search(r"-detail-?\d+", path)
            or bool(re.fullmatch(r"/bid-\d+\.html?", path))
            or bool(re.fullmatch(r"/art/\d{4}/\d{1,2}/\d{1,2}/art_\d+_\d+\.html", path))
            or path.endswith(".article")
        ):
            is_detail = True
        else:
            is_detail = False
        if not is_detail:
            continue
        # 排除导航/栏目/产品页等非新闻详情
        if re.search(r"/(col|special|search|product|about|list)/", path):
            continue
        seen.add(full)
        links.append(full)
    return links


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    source_name, list_urls = sys.argv[1], sys.argv[2:]
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    saved = 0
    print(f"[配置] 请求间隔 {REQUEST_GAP_SECONDS}s，每列表页详情上限 {DETAIL_LIMIT}")
    for list_url in list_urls[:3]:
        ok, note = fetch_robots_ok(list_url)
        print(f"[robots] {list_url} -> {ok} ({note})")
        if not ok:
            print("  跳过（robots 不允许）——如实记录，不绕过")
            continue
        time.sleep(REQUEST_GAP_SECONDS)
        try:
            resp = polite_get(list_url)
        except Exception as exc:  # noqa: BLE001 —— Spike 记录一切网络异常
            print(f"  [失败] {type(exc).__name__}: {exc}")
            continue
        print(f"  [列表页] HTTP {resp.status_code}, {len(resp.content)} bytes")
        if resp.status_code != 200:
            continue
        for link in extract_links(decode_body(resp), list_url)[: DETAIL_LIMIT - saved if saved < DETAIL_LIMIT else 0]:
            ok2, note2 = fetch_robots_ok(link)
            if not ok2:
                print(f"  [robots 禁止] {link}")
                continue
            time.sleep(REQUEST_GAP_SECONDS)
            try:
                detail = polite_get(link)
            except Exception as exc:  # noqa: BLE001
                print(f"  [失败] {link} {type(exc).__name__}: {exc}")
                continue
            if detail.status_code != 200:
                print(f"  [详情非200] {link} HTTP {detail.status_code}")
                continue
            fname = SAMPLES_DIR / f"{source_name}-{saved:02d}.md"
            fname.write_text(
                f"---\nsource: {source_name}\nurl: {link}\n"
                f"fetched_at: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n"
                f"http_status: {detail.status_code}\n---\n\n{decode_body(detail)}",
                encoding="utf-8",
            )
            saved += 1
            print(f"  [存档] {fname.name}")
    print(f"完成：{source_name} 存档 {saved} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
