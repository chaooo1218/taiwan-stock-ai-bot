# config.py
import os


FINMIND_TOKEN   = os.getenv("FINMIND_TOKEN", "")   # ← 把你的 Token 放這或用環境變數
FUND_FLOW_ENABLED = int(os.getenv("FUND_FLOW_ENABLED", "1"))  # 想暫時關法人可設 0
FINMIND_QPS     = float(os.getenv("FINMIND_QPS", "4"))  # 每秒請求數上限（保守一點）
FINMIND_RETRY   = int(os.getenv("FINMIND_RETRY", "2"))  # 失敗重試次數

# --- 通知 ---
DISCORD_WEBHOOK = os.getenv("https://discord.com/api/webhooks/1395039433358839880/pOzuyz8R-_MKqw6dDox8hQT0sanzmWfoJwZUder6qPUd4C0iMwS7E7H6qRjX1fB7iU0u", "")   # 建議用環境變數；或填你的 URL 字串

# --- 掃描控制 ---
SCAN_LIMIT = int(os.getenv("SCAN_LIMIT", "1000"))    # 總候選檔數（啟動預篩上限）
PAGE_SIZE  = int(os.getenv("PAGE_SIZE",  "120"))     # 每一輪實際處理幾檔（分頁跑）
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))      # 併發處理的協程數
SLEEP_SECONDS  = int(os.getenv("SLEEP_SECONDS", "20"))
YEARS_HISTORY  = int(os.getenv("YEARS_HISTORY", "2"))  # 冷啟先 2 年，快取好再拉 3~5 年

# --- 預篩（批次查價 + 流動性）---
PREFETCH_MAX_CHECKS = int(os.getenv("PREFETCH_MAX_CHECKS", "1800"))  # 預篩最多檢查多少檔
QUOTE_BATCH_SIZE    = int(os.getenv("QUOTE_BATCH_SIZE",    "80"))    # 每批查多少檔（Yahoo v7 quote）
PRICE_CEILING       = float(os.getenv("PRICE_CEILING",     "1500"))  # 單價上限
MIN_AVG_VOL_SHARES  = int(os.getenv("MIN_AVG_VOL_SHARES",  "150000"))# 三月均量(股)門檻(避免冷門股)

# --- 推播限制/去重 ---
MAX_SIGNAL_PER_STOCK = int(os.getenv("MAX_SIGNAL_PER_STOCK", "20"))
MAX_SIGNAL_TOTAL     = int(os.getenv("MAX_SIGNAL_TOTAL",     "200"))
DEDUP_WINDOW_SEC     = int(os.getenv("DEDUP_WINDOW_SEC",     "1200"))

# --- 新聞策略 ---
NEWS_POS_THRESHOLD   = float(os.getenv("NEWS_POS_THRESHOLD", "0.80"))

# --- 新聞來源（可自行增減；留空不會報錯）---
NEWS_RSS_FEEDS = []
