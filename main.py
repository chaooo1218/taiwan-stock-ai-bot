# main.py
# -*- coding: utf-8 -*-
import asyncio
import time

from config import (
    DISCORD_WEBHOOK, MAX_SIGNAL_PER_STOCK, MAX_SIGNAL_TOTAL,
    SCAN_LIMIT, BATCH_SIZE, SLEEP_SECONDS, YEARS_HISTORY
)
from utils.stock_list import get_stocks_under_1500, get_all_stocks
from modules.fetch_price import get_price_with_ma
from modules.fetch_fundamental import get_fund_flow
from modules.fetch_udn_news import fetch_udn_news
from modules.fetch_cnyes_headlines import fetch_cnyes_headlines
from modules.ai_news_ranker import rank_news
from modules.strategy_router import run_all_strategies
from modules.notifier import send_discord_message, print_terminal
from storage.signals_db import log_signal, today_summary
from modules.news_linker import build_aliases, link_news_to_stock

# 紀錄今日各股推播次數
sent_today = {}  # {stock_id: count}


def safe_send(msg: str):
    """同時印到終端與 Discord（若已設定 Webhook）。"""
    if not msg:
        return
    print_terminal(msg)
    if DISCORD_WEBHOOK:
        try:
            send_discord_message(msg, DISCORD_WEBHOOK)
        except Exception:
            pass


async def process_stock(stock_id: str, stock_name: str, news_all: list, aliases_map: dict):
    """單檔股票處理流程：抓價→法人→新聞→策略→可能推播與紀錄"""
    count = sent_today.get(stock_id, 0)
    total = sum(sent_today.values())
    if count >= MAX_SIGNAL_PER_STOCK or total >= MAX_SIGNAL_TOTAL:
        return

    try:
        # 1) 價格 & 指標（縮年限加速）
        df = get_price_with_ma(stock_id, years=YEARS_HISTORY, use_cache=True)
        if df is None or len(df) < 20:
            return

        # 2) 法人（若額度不足，函式會回 None，策略會自動略過法人）
        fund_data = get_fund_flow(stock_id)

        # 3) 全市場新聞 -> 過濾出與該股相關
        news_for_stock = link_news_to_stock(news_all, stock_id, aliases_map)
        news_ranked = rank_news(news_for_stock) if news_for_stock else []

        # 4) 跑策略
        strategies = run_all_strategies(df, fund_data, news_ranked, pos_threshold=0.80)
        triggers = [s for s in strategies if s.get("triggered")]
        if not triggers:
            return

        # 5) 整理推播訊息
        strategy_names = "、".join(dict.fromkeys([t["strategy"] for t in triggers]))
        reasons = "；".join(dict.fromkeys([t.get("reason", "") for t in triggers if t.get("reason")]))

        price = float(df.iloc[-1]["close"])
        message = (
            f"📈【{strategy_names} 進場】{stock_id} {stock_name} 第 {count + 1}/{MAX_SIGNAL_PER_STOCK} 次\n"
            f"價格約：{price:.2f} 元\n"
            f"說明：{reasons or '觸發條件成立'}"
        )
        safe_send(message)

        # 6) 記錄
        log_signal(stock_id, stock_name, strategy_names, price, count + 1, "波段", reasons)
        sent_today[stock_id] = count + 1

    except Exception as e:
        print(f"❌ [ERROR] {stock_id} {stock_name}: {e}")


async def scan_loop():
    """一輪一輪地抓新聞/清單→預篩→並發處理→摘要"""
    # 1) 抓全市場新聞（共享給所有股票用）
    t0 = time.perf_counter()
    print("📰 抓全市場新聞中…")
    news_all = (fetch_udn_news() or []) + (fetch_cnyes_headlines() or [])
    print(f"📰 新聞數：{len(news_all)}，耗時 {time.perf_counter() - t0:.1f}s")

    # 2) 抓上市（或使用內建清單）
    t1 = time.perf_counter()
    print("📃 抓上市清單中…")
    stock_list = get_all_stocks(use_cache=False)  # 這裡可能回內建 10 檔（已在 utils/stock_list 處理）
    print(f"📃 上市清單：{len(stock_list)} 檔，耗時 {time.perf_counter() - t1:.1f}s")

    # 3) 建立公司別名（做新聞→個股對應）
    aliases_map = build_aliases(stock_list)

    # 4) ✅ 用「同一份 stock_list」做快速價預篩
    t2 = time.perf_counter()
    print("⚡ 用快速價預篩中…")
    stocks = get_stocks_under_1500(
        stock_list=stock_list,   # ←← 關鍵修改：把剛抓到的清單丟進去
        max_price=1500.0,
        limit=SCAN_LIMIT,
        max_checks=300,
        debug=True
    )
    print(f"✅ 本輪掃描股票數：{len(stocks)}，耗時 {time.perf_counter() - t2:.1f}s")

    # 可選：每 N 輪刷新新聞/清單，避免陳舊
    REFRESH_EVERY = 10
    loop_idx = 0

    while True:
        loop_start = time.perf_counter()

        # 分批併發處理
        tasks = [process_stock(sid, sname, news_all, aliases_map) for sid, sname in stocks]
        for i in range(0, len(tasks), BATCH_SIZE):
            await asyncio.gather(*tasks[i:i + BATCH_SIZE])

        # 輸出本輪統計
        dur = time.perf_counter() - loop_start
        page_size = min(len(stocks), BATCH_SIZE)  # 只是展示用途
        print(f"⏱️ 本輪完成，用時 {dur:.1f}s（本頁 {page_size} 檔）")

        # 每輪結束發一次摘要（失敗不終止）
        try:
            safe_send(today_summary())
        except Exception as e:
            print(f"摘要推送失敗：{e}")

        loop_idx += 1
        # 週期性刷新新聞與清單
        if loop_idx % REFRESH_EVERY == 0:
            try:
                print("🔁 週期性刷新新聞與清單…")
                tN = time.perf_counter()
                news_all = (fetch_udn_news() or []) + (fetch_cnyes_headlines() or [])
                stock_list = get_all_stocks()  # 這裡可用快取
                aliases_map = build_aliases(stock_list)
                print(f"🔁 刷新完成，新聞 {len(news_all)} 則；耗時 {time.perf_counter() - tN:.1f}s")
                # 刷新後也重做一次預篩
                stocks = get_stocks_under_1500(
                    stock_list=stock_list,
                    max_price=1500.0,
                    limit=SCAN_LIMIT,
                    max_checks=300,
                    debug=False
                )
                print(f"🔁 刷新後候選：{len(stocks)} 檔")
            except Exception as e:
                print(f"刷新新聞/清單失敗：{e}")

        await asyncio.sleep(SLEEP_SECONDS)


async def main():
    print("🚀 台股 AI 偵測系統啟動中...")
    await scan_loop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 系統手動中止")
        try:
            safe_send(today_summary())
        except Exception:
            pass
