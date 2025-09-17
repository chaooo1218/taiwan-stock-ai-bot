import csv
from collections import defaultdict
from datetime import datetime

LOG_FILE = "signal_log.csv"

def analyze_signals_log(today_only=True):
    """
    分析 signal_log.csv，計算勝率與推播排行榜摘要
    - today_only: 是否只分析今天的紀錄
    """
    try:
        with open(LOG_FILE, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            signals = list(reader)
    except FileNotFoundError:
        return "無交易訊號紀錄"

    if not signals:
        return "無交易訊號紀錄"

    today_str = datetime.today().strftime("%Y-%m-%d")

    win_count = 0
    total_count = 0
    stock_counter = defaultdict(int)
    total_profit = 0.0

    for signal in signals:
        # 如果只看今日，過濾日期
        if today_only:
            dt_str = signal.get("datetime", "")
            if not dt_str.startswith(today_str):
                continue

        total_count += 1
        stock_id = signal.get("stock_id", "未知")
        stock_counter[stock_id] += 1

        # 判斷勝負，使用 profit 欄位
        try:
            profit = float(signal.get("profit", 0))
        except ValueError:
            profit = 0

        total_profit += profit
        if profit > 0:
            win_count += 1

    if total_count == 0:
        return "今日無交易訊號"

    win_rate = win_count / total_count
    avg_profit = total_profit / total_count

    # 排序出推播次數最多前五名股票
    top_stocks = sorted(stock_counter.items(), key=lambda x: x[1], reverse=True)[:5]

    msg = f"📊 今日交易總數：{total_count}\n"
    msg += f"✅ 勝率：{win_rate:.2%}\n"
    msg += f"💰 平均報酬率：{avg_profit:.2%}\n"
    msg += "📈 推播前五名股票：\n"
    for stock_id, count in top_stocks:
        msg += f"{stock_id}：{count} 次\n"

    return msg


if __name__ == "__main__":
    summary = analyze_signals_log(today_only=True)
    print(summary)
