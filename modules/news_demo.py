from modules.fetch_all_news import fetch_all_news
from modules.ai_news_ranker import rank_news

def main(limit=10):
    # 抓新聞
    raw_news = fetch_all_news()
    if not raw_news:
        print("⚠️ 沒有抓到新聞")
        return

    print(f"抓取到 {len(raw_news)} 篇新聞，準備進行情緒分析與排序...")

    # 排序
    ranked_news = rank_news(raw_news)

    # 輸出前 N 篇
    for news in ranked_news[:limit]:
        source = news.get("source", "未知來源")
        publish_time = news.get("publish_time", "未知時間")
        title = news.get("title", "無標題")
        sentiment = news.get("sentiment", "NEUTRAL")
        score = news.get("sentiment_score", 0.0)
        summary = news.get("summary", "")

        print(f"{source} | {publish_time} | {title}")
        print(f"情緒標籤: {sentiment}，信心分數: {score:.2f}")
        print(f"摘要: {summary}\n")


if __name__ == "__main__":
    main(limit=10)
