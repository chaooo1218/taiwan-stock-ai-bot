# modules/fetch_fundamental.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import pandas as pd
from datetime import datetime, timedelta

from modules.finmind_client import get_data  # ✅ 統一由這裡打 FinMind（含 Token/限速/重試）
from config import FUND_FLOW_ENABLED

CACHE_DIR = "cache/fund"
os.makedirs(CACHE_DIR, exist_ok=True)


def _cache_path(stock_id: str) -> str:
    return os.path.join(CACHE_DIR, f"{stock_id}.csv")


def _net(raw: pd.DataFrame, b: str, s: str) -> pd.Series:
    """以買-賣計算淨買賣；缺值視為 0。"""
    buy = pd.to_numeric(raw.get(b), errors="coerce").fillna(0)
    sell = pd.to_numeric(raw.get(s), errors="coerce").fillna(0)
    return buy - sell


def get_fund_flow(
    stock_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame | None:
    """
    強韌版「三大法人」資料取得：
    - 來源：FinMind dataset = TaiwanStockInstitutionalInvestorsBuySell
    - 欄位名異動自動對齊（*_Buy/Sell、*_NetBuySell、彙總欄位等）
    - 失敗或額度不足（402 等）回 None，策略層可自行略過
    - 本地 CSV 快取：cache/fund/{stock_id}.csv
    回傳欄位固定為：
      ['date', 'Foreign_Investor', 'Investment_Trust', 'Dealer_self']
    其中值皆為「淨買賣」張數（買 - 賣）。
    """
    if not FUND_FLOW_ENABLED:
        return None

    if end_date is None:
        end_date = datetime.today().strftime("%Y-%m-%d")
    if start_date is None:
        start_date = (datetime.today() - timedelta(days=365 * 2)).strftime("%Y-%m-%d")

    # 先讀快取
    cfile = _cache_path(stock_id)
    if use_cache and os.path.exists(cfile):
        try:
            df = pd.read_csv(cfile)
            if not df.empty and "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                return df
        except Exception:
            pass  # 壞快取就當無

    # 從 FinMind 抓資料（get_data 內建 Token/限速/重試）
    data = get_data(
        dataset="TaiwanStockInstitutionalInvestorsBuySell",
        data_id=stock_id,
        start_date=start_date,
        end_date=end_date,
    )
    if not data:
        # 各種失敗（含 402 額度不足）一律回 None，讓策略略過法人
        return None

    raw = pd.DataFrame(data)
    if raw.empty or "date" not in raw.columns:
        return None

    cols = set(raw.columns)

    # ---------- 外資 ----------
    if {"Foreign_Investor_Buy", "Foreign_Investor_Sell"} <= cols:
        foreign = _net(raw, "Foreign_Investor_Buy", "Foreign_Investor_Sell")
    elif "Foreign_Investor_NetBuySell" in cols:
        foreign = pd.to_numeric(raw["Foreign_Investor_NetBuySell"], errors="coerce").fillna(0)
    elif "Foreign_Investor" in cols:
        foreign = pd.to_numeric(raw["Foreign_Investor"], errors="coerce").fillna(0)
    else:
        foreign = pd.Series(0, index=raw.index)

    # ---------- 投信 ----------
    if {"Investment_Trust_Buy", "Investment_Trust_Sell"} <= cols:
        investment = _net(raw, "Investment_Trust_Buy", "Investment_Trust_Sell")
    elif "Investment_Trust_NetBuySell" in cols:
        investment = pd.to_numeric(raw["Investment_Trust_NetBuySell"], errors="coerce").fillna(0)
    elif "Investment_Trust" in cols:
        investment = pd.to_numeric(raw["Investment_Trust"], errors="coerce").fillna(0)
    else:
        investment = pd.Series(0, index=raw.index)

    # ---------- 自營商（名稱常變動，盡量涵蓋） ----------
    dealer = pd.Series(0, index=raw.index)
    # 總自營
    if {"Dealer_Buy", "Dealer_Sell"} <= cols:
        dealer += _net(raw, "Dealer_Buy", "Dealer_Sell")
    if "Dealer" in cols:
        dealer += pd.to_numeric(raw["Dealer"], errors="coerce").fillna(0)

    # 自營自營/避險細項
    if {"Dealer_Self_Buy", "Dealer_Self_Sell"} <= cols:
        dealer += _net(raw, "Dealer_Self_Buy", "Dealer_Self_Sell")
    if "Dealer_Self" in cols:
        dealer += pd.to_numeric(raw["Dealer_Self"], errors="coerce").fillna(0)

    # 某些版本用 Securities_Firm 指自營商
    if "Securities_Firm" in cols:
        dealer += pd.to_numeric(raw["Securities_Firm"], errors="coerce").fillna(0)

    out = pd.DataFrame(
        {
            "date": pd.to_datetime(raw["date"]),
            "Foreign_Investor": foreign,
            "Investment_Trust": investment,
            "Dealer_self": dealer,
        }
    ).sort_values("date").reset_index(drop=True)

    # 寫回快取
    try:
        out.to_csv(cfile, index=False, encoding="utf-8")
    except Exception:
        pass

    return out
