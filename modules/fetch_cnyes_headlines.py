import time
import requests
from datetime import datetime

API = "https://api.cnyes.com/media/api/v1/newslist/category/headline"

HEADERS = {
    "Origin": "https://news.cnyes.com",
    "Referer": "https://news.cnyes.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
}

def _ts_to_str(ts: int) -> str:
    # 轉換 Unix 秒為 YYYY-MM-DD HH:MM:SS（台北時間）
    return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")

def fetch_cnyes_headlines(pages: int = 2, limit: int = 30) -> list[dict]:
    out = []
    for page in range(1, pages + 1):
        params = {"page": page, "limit": limit, "isCategoryHeadline": 1}
        try:
            r = requests.get(API, headers=HEADERS, params=params, timeout=12)
            r.raise_for_status()
            items = r.json().get("items", {})
            for it in items.get("data", []):
                nid = it.get("newsId")
                out.append({
                    "title": (it.get("title") or "").strip(),
                    "content": (it.get("summary") or "").strip(),
                    "publish_time": _ts_to_str(it.get("publishAt")) if it.get("publishAt") else "",
                    "source": "鉅亨網",
                    "url": f"https://news.cnyes.com/news/id/{nid}" if nid else "",
                })
            time.sleep(0.5)
        except requests.exceptions.SSLError:
            r = requests.get(API, headers=HEADERS, params=params, timeout=12, verify=False)
            r.raise_for_status()
            items = r.json().get("items", {})
            for it in items.get("data", []):
                nid = it.get("newsId")
                out.append({
                    "title": (it.get("title") or "").strip(),
                    "content": (it.get("summary") or "").strip(),
                    "publish_time": _ts_to_str(it.get("publishAt")) if it.get("publishAt") else "",
                    "source": "鉅亨網",
                    "url": f"https://news.cnyes.com/news/id/{nid}" if nid else "",
                })
        except Exception as e:
            print(f"⚠️ 鉅亨抓取第 {page} 頁失敗：{e}")
    return out

if __name__ == "__main__":
    data = fetch_cnyes_headlines()
    print("CNYES 筆數：", len(data))
    for n in data[:5]:
        print(n["publish_time"], n["title"], n["url"])
