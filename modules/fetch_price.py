# modules/fetch_price.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List

import pandas as pd
import requests
from requests.adapters import HTTPAdapter, Retry
import warnings
from urllib3.exceptions import InsecureRequestWarning

from modules.finmind_client import get_data  # ✅ 統一由這裡取 FinMind（含 Token/限速/重試）

warnings.simplefilter("ignore", InsecureRequestWarning)

# ----------------- 路徑與常數 -----------------
PRICE_CACHE_DIR = "cache/price"
LASTPRICE_DIR = "cache/lastprice"
os.makedirs(PRICE_CACHE_DIR, exist_ok=True)
os.makedirs(LASTPRICE_DIR, exist_ok=True)


# ----------------- HTTP 工具（給 Yahoo 用） -----------------
def _session_with_retries() -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=2,
        backoff_factor=0.3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))
    return s


def _get_with_ssl_fallback(url: str, timeout: int = 10, params: dict | None = None) -> requests.Response:
    """
    先正常請求；遇到 SSLError 時再用 verify=False 重試（僅此請求）。
    """
    s = _session_with_retries()
    try:
        r = s.get(url, timeout=timeout, params=params)
        r.raise_for_status()
        return r
    except requests.exceptions.SSLError:
        r = s.get(url, timeout=timeout, params=params, verify=False)
        r.raise_for_status()
        return r


# ----------------- FinMind: 日K + MA -----------------
def _price_cache_path(stock_id: str) -> str:
    return os.path.join(PRICE_CACHE_DIR, f"{stock_id}.csv")


def _normalize_price_df(df: pd.DataFrame) -> pd.DataFrame | None:
    """
    將 FinMind/TWSE 回傳欄位對齊成統一結構，並補上技術指標。
    需要至少包含 ['date','close']。
    """
    if df is None or df.empty:
        return None

    # 欄位對齊：volume / high / low
    if "volume" not in df.columns and "Trading_Volume" in df.columns:
        df["volume"] = pd.to_numeric(df["Trading_Volume"], errors="coerce").fillna(0)
    if "high" not in df.columns and "max" in df.columns:
        df["high"] = pd.to_numeric(df["max"], errors="coerce")
    if "low" not in df.columns and "min" in df.columns:
        df["low"] = pd.to_numeric(df["min"], errors="coerce")

    if not {"date", "close"}.issubset(df.columns):
        return None

    # 整形
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["close"] = pd.to_numeric(df["close"], errors="coerce")

    if "volume" not in df.columns:
        df["volume"] = 0
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)

    # 指標（若不存在就計算）
    if "MA5" not in df.columns:
        df["MA5"] = df["close"].rolling(window=5, min_periods=1).mean()
    if "MA20" not in df.columns:
        df["MA20"] = df["close"].rolling(window=20, min_periods=1).mean()
    if "Volume_avg" not in df.columns:
        df["Volume_avg"] = df["volume"].rolling(window=20, min_periods=1).mean()

    return df


def get_price_with_ma(stock_id: str, years: int = 3, use_cache: bool = True) -> pd.DataFrame | None:
    """
    從 FinMind 抓台股日K並計算 MA 指標。
    - 使用 finmind_client.get_data()（自動帶 Token/限速/重試）
    - 本地 CSV 快取：cache/price/{stock_id}.csv
    """
    cache_file = _price_cache_path(stock_id)

    # 先讀快取（速度快）
    if use_cache and os.path.exists(cache_file):
        try:
            df_cached = pd.read_csv(cache_file)
            df_cached = _normalize_price_df(df_cached)
            if df_cached is not None:
                return df_cached
        except Exception:
            pass  # 壞快取就當沒看到

    # 抓取區間
    end_date = datetime.today().strftime("%Y-%m-%d")
    start_date = (datetime.today() - timedelta(days=365 * max(1, int(years)))).strftime("%Y-%m-%d")

    # ✅ 用 finmind_client.get_data（帶 Token/限速/重試）
    data = get_data(
        dataset="TaiwanStockPrice",
        data_id=stock_id,
        start_date=start_date,
        end_date=end_date,
    )
    if not data:
        return None

    df = pd.DataFrame(data)
    df = _normalize_price_df(df)
    if df is None:
        return None

    # 寫入快取
    try:
        df.to_csv(cache_file, index=False, encoding="utf-8")
    except Exception:
        pass

    return df


# ----------------- Yahoo: 單檔最近收盤 -----------------
def _yahoo_latest_close(symbol: str, timeout: int = 6) -> float | None:
    """
    從 Yahoo v8 chart API 取最近一筆有效收盤價。
    """
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"range": "1mo", "interval": "1d"}
    try:
        r = _get_with_ssl_fallback(url, timeout=timeout, params=params)
        j = r.json()
        res = j.get("chart", {}).get("result", [])
        if not res:
            return None
        q = res[0]
        closes = q.get("indicators", {}).get("quote", [{}])[0].get("close", [])
        # 由後往前找第一個非 None
        for v in reversed(closes or []):
            if v is not None:
                return float(v)
        return None
    except Exception:
        return None


def get_latest_close_fast(stock_id: str, prefer_suffix: str = ".TW", timeout: int = 6, use_cache: bool = True) -> float | None:
    """
    以 Yahoo v8 chart 快速取得最近收盤價，先打 prefer_suffix，不行才回退另一個市場。
    當天結果快取於 cache/lastprice/{stock_id}.json
    """
    cache_file = os.path.join(LASTPRICE_DIR, f"{stock_id}.json")
    today = datetime.today().strftime("%Y-%m-%d")

    # 讀快取
    if use_cache and os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                obj = json.load(f)
            if obj.get("date") == today:
                return float(obj.get("close"))
        except Exception:
            pass

    # 先上市
    price = _yahoo_latest_close(f"{stock_id}{prefer_suffix}", timeout=timeout)
    # 回退另一市場
    if price is None:
        fallback_suffix = ".TWO" if prefer_suffix == ".TW" else ".TW"
        price = _yahoo_latest_close(f"{stock_id}{fallback_suffix}", timeout=timeout)

    # 寫快取
    if price is not None:
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({"date": today, "close": float(price)}, f, ensure_ascii=False)
        except Exception:
            pass

    return price


# ----------------- Yahoo: 批次 quote（極快） -----------------
def get_quote_batch(stock_ids: List[str], suffix: str = ".TW", timeout: int = 6, batch_size: int = 80) -> Dict[str, dict]:
    """
    Yahoo v7 quote 批次查價。
    回傳：
      { sid: { 'price': float, 'vol': int, 'avgvol3m': int, 'avgvol10d': int } }
    欄位缺失時自動用 previousClose、10Day 或當日量補位。
    """
    out: Dict[str, dict] = {}
    if not stock_ids:
        return out

    base = "https://query1.finance.yahoo.com/v7/finance/quote"

    for i in range(0, len(stock_ids), batch_size):
        chunk = stock_ids[i:i + batch_size]
        symbols = ",".join(f"{sid}{suffix}" for sid in chunk)
        try:
            r = _get_with_ssl_fallback(base, timeout=timeout, params={"symbols": symbols})
            if r is None:
                continue
            j = r.json()
            results = (j.get("quoteResponse") or {}).get("result") or []
            for item in results:
                sym = item.get("symbol", "")
                sid = sym.split(".")[0] if "." in sym else sym

                price = item.get("regularMarketPrice")
                if price is None:
                    price = item.get("regularMarketPreviousClose")

                vol = item.get("regularMarketVolume") or 0
                avg3 = item.get("averageDailyVolume3Month") or 0
                avg10 = item.get("averageDailyVolume10Day") or 0

                if price is None:
                    continue

                out[sid] = {
                    "price": float(price),
                    "vol": int(vol),
                    "avgvol3m": int(avg3),
                    "avgvol10d": int(avg10),
                }
        except Exception:
            # 單批失敗就跳過，避免整體卡住
            continue

    return out
