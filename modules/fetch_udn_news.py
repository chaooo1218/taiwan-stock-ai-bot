# modules/fetch_udn_news.py
import time
import requests

API = "https://udn.com/api/more"
HEADERS = {
    "Referer": "https://udn.com/news/breaknews/1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
}

def fetch_udn_news(pages: int = 2, keywords: list[str] | None = None) -> list[dict]:
    """
    透過 UDN 的 Ajax JSON 介面抓「即時」列表（全站即時）。
    回傳每則：{title, content, publish_time, source, url}
    可選 keywords 做財經/股市關鍵字過濾。
    """
    out: list[dict] = []
    for page in range(1, pages + 1):
        params = {
            "page": page,
            "channelId": 1,   # news
            "cate_id": 0,     # 不分類（全部即時）
            "type": "breaknews"
        }
        try:
            r = requests.get(API, headers=HEADERS, params=params, timeout=12)
            r.raise_for_status()
            data = r.json()
        except requests.exceptions.SSLError:
            # 極少數環境 SSL 例外時，僅此請求關閉驗證
            r = requests.get(API, headers=HEADERS, params=params, timeout=12, verify=False)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"⚠️ UDN 抓取第 {page} 頁失敗：{e}")
            continue

        for item in data.get("lists", []):
            title = (item.get("title") or "").strip()
            para = (item.get("paragraph") or "").strip()
            tobj = item.get("time", {}) or {}
            publish_time = (tobj.get("date") or "").strip()
            link = item.get("titleLink") or ""
            if link and not link.startswith("http"):
                link = "https://udn.com" + link

            rec = {
                "title": title,
                "content": para,
                "publish_time": publish_time,
                "source": "聯合新聞網",  # 這是 UDN 總站；若你一定要標「經濟日報」，可改成 "經濟日報"
                "url": link
            }

            if keywords:
                text = f"{title} {para}".lower()
                if not any(k.lower() in text for k in keywords):
                    continue

            out.append(rec)

        time.sleep(0.5)  # 禮貌性間隔，避免被限流
    return out

if __name__ == "__main__":
    data = fetch_udn_news(pages=2, keywords=None)  # 可放 keywords=["股", "台股", "半導體", "財經"]
    print("UDN 筆數：", len(data))
    for n in data[:5]:
        print(n["publish_time"], n["title"], n["url"])
