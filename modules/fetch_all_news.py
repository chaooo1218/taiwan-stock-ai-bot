# modules/fetch_all_news.py（覆蓋）
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from config import NEWS_RSS_FEEDS

from modules.fetch_udn_news import fetch_udn_news
from modules.fetch_cnyes_headlines import fetch_cnyes_headlines

def _fetch_rss(url):
    out = []
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "xml")
        for item in soup.find_all("item"):
            title = item.title.text if item.title else ""
            link  = item.link.text  if item.link else ""
            pub   = item.pubDate.text if item.pubDate else ""
            out.append({
                "title": title, "content": "", "publish_time": pub,
                "source": "RSS", "url": link
            })
    except Exception:
        pass
    return out

def fetch_all_news(pages: int = 2) -> list[dict]:
    news = []
    news.extend(fetch_cnyes_headlines(pages=pages, limit=30))
    news.extend(fetch_udn_news(pages=pages))
    return news

if __name__ == "__main__":
    items = fetch_all_news(pages=2)
    print("總新聞數：", len(items))
    for n in items[:10]:
        print(f"{n['source']} | {n['publish_time']} | {n['title']} | {n['url']}")
