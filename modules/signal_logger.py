import csv
import os
from datetime import datetime

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "signal_log.csv")

def log_signal(stock_id, stock_name, strategy_name, price, trigger_count, signal_type, reason="", profit=None):
    """
    紀錄單筆交易訊號到 CSV 檔案
    """
    os.makedirs(LOG_DIR, exist_ok=True)  # 確保 logs 目錄存在
    file_exists = os.path.isfile(LOG_FILE)

    with open(LOG_FILE, mode="a", newline="", encoding="utf-8") as f:
        fieldnames = [
            "datetime", "stock_id", "stock_name", "strategy_name",
            "price", "trigger_count", "signal_type", "reason", "profit"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        # 如果檔案不存在，寫入標頭
        if not file_exists:
            writer.writeheader()

        writer.writerow({
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "stock_id": stock_id,
            "stock_name": stock_name,
            "strategy_name": strategy_name,
            "price": price,
            "trigger_count": trigger_count,
            "signal_type": signal_type,
            "reason": reason,
            "profit": profit if profit is not None else ""
        })


def read_signals():
    """
    讀取所有已紀錄的交易訊號
    """
    if not os.path.isfile(LOG_FILE):
        return []

    with open(LOG_FILE, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


if __name__ == "__main__":
    # 測試寫入與讀取
    log_signal("2330", "台積電", "技術面", 600, 1, "波段", "黃金交叉觸發", profit=0.05)
    signals = read_signals()
    for s in signals:
        print(s)
