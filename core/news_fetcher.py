"""
竹雨ROCOM小助手 - TapTap资讯获取模块
从TapTap官方社区爬取最新帖子
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError


TAPTAP_URL = "https://www.taptap.cn/group/228326/group-label/2332786"


class NewsFetcher:
    """TapTap资讯获取器"""

    def __init__(self, cache_dir=None):
        if cache_dir is None:
            cache_dir = Path(__file__).parent.parent / "output"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_file = self.cache_dir / "news_cache.json"
        self._cache = self._load_cache()

    def _load_cache(self):
        if self._cache_file.exists():
            try:
                with open(self._cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"last_update": "", "news": []}

    def _save_cache(self):
        with open(self._cache_file, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, ensure_ascii=False, indent=2)

    def _http_get(self, url, timeout=15):
        """简单的HTTP GET请求"""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        req = Request(url, headers=headers)
        try:
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                for enc in ["utf-8", "gbk", "gb2312"]:
                    try:
                        return raw.decode(enc)
                    except UnicodeDecodeError:
                        continue
                return raw.decode("utf-8", errors="replace")
        except URLError:
            return None

    def _parse_taptap_html(self, html):
        """从TapTap HTML中提取帖子信息"""
        news_list = []

        # 匹配帖子链接：/group/228326/topic/xxxxx
        topic_pattern = re.compile(
            r'<a[^>]*href="(/group/\d+/topic/\d+)"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )

        # 匹配标题文本
        title_pattern = re.compile(
            r'<(?:h[2-3]|span|div)[^>]*class="[^"]*(?:title|topic-title|card-title|heading)[^"]*"[^>]*>(.*?)</(?:h[2-3]|span|div)>',
            re.DOTALL | re.IGNORECASE,
        )

        links = topic_pattern.findall(html)
        seen_urls = set()
        for href, inner_html in links:
            url = f"https://www.taptap.cn{href}"
            if url in seen_urls:
                continue
            seen_urls.add(url)

            title = re.sub(r'<[^>]+>', '', inner_html).strip()
            if not title or len(title) < 2:
                continue

            date_match = re.search(
                r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
                html[max(0, html.find(href) - 500):html.find(href) + 500],
            )
            date_str = date_match.group(1) if date_match else datetime.now().strftime("%Y-%m-%d")

            news_list.append({
                "title": title[:100],
                "url": url,
                "date": date_str,
                "source": "TapTap",
                "type": "资讯",
                "description": title[:100],
            })

        # 兜底：用标题模式匹配
        if not news_list:
            titles = title_pattern.findall(html)
            for title_html in titles:
                title = re.sub(r'<[^>]+>', '', title_html).strip()
                if title and len(title) >= 2 and len(title) <= 200:
                    news_list.append({
                        "title": title[:100],
                        "url": TAPTAP_URL,
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "source": "TapTap",
                        "type": "资讯",
                        "description": title[:100],
                    })

        return news_list

    def fetch_all_news(self, force_refresh=False):
        """获取TapTap社区资讯，5分钟内缓存有效"""
        if not force_refresh and self._cache.get("last_update"):
            try:
                last = datetime.fromisoformat(self._cache["last_update"])
                if (datetime.now() - last).total_seconds() < 300:
                    return self._cache.get("news", [])
            except (ValueError, TypeError):
                pass

        all_news = []

        try:
            html = self._http_get(TAPTAP_URL)
            if html:
                all_news = self._parse_taptap_html(html)
        except Exception:
            pass

        if not all_news:
            cached = self._cache.get("news", [])
            if cached:
                return cached
            return []

        all_news.sort(key=lambda x: x.get("date", ""), reverse=True)
        self._cache = {
            "last_update": datetime.now().isoformat(),
            "news": all_news,
        }
        self._save_cache()
        return all_news

    def get_news_by_type(self, news_type):
        all_news = self.fetch_all_news()
        return [n for n in all_news if n.get("type") == news_type]

    def search_news(self, keyword):
        all_news = self.fetch_all_news()
        keyword = keyword.lower()
        return [
            n for n in all_news
            if keyword in n.get("title", "").lower()
            or keyword in n.get("description", "").lower()
        ]