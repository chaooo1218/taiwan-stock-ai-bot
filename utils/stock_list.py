# utils/stock_list.py
# -*- coding: utf-8 -*-
"""
取得上市清單 + 快速預篩（批次查價 + 流動性）：
- 主清單來源：FinMind TaiwanStockInfo（無需權杖）
- 備援：TWSE OpenAPI（SSL 失敗會 verify=False 單次回退）
- 每日快取：cache/twse/twse_stocks.csv
- 預篩：優先用 Yahoo v7 quote 批次（極快）；若環境沒提供批次函式則回退逐檔查價
"""

from __future__ import annotations
import os
import requests
import pandas as pd
from datetime import datetime
import warnings
from urllib3.exceptions import InsecureRequestWarning
from math import isfinite

warnings.simplefilter("ignore", InsecureRequestWarning)

# ---- 快取設定 ----
CACHE_DIR = "cache/twse"
CACHE_FILE = os.path.join(CACHE_DIR, "twse_stocks.csv")

# ---- 清單來源 ----
FINMIND_INFO_URL = "https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInfo"
TWSE_OPENAPI_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"

# ---- 從 config 載預設參數（若缺少就給安全預設）----
try:
    from config import (
        PRICE_CEILING, PREFETCH_MAX_CHECKS, QUOTE_BATCH_SIZE, MIN_AVG_VOL_SHARES
    )
except Exception:
    PRICE_CEILING = 1500.0
    PREFETCH_MAX_CHECKS = 1000
    QUOTE_BATCH_SIZE = 80
    MIN_AVG_VOL_SHARES = 150_000  # 三月均量(股)


# ----------------- 清單快取 -----------------
def _load_cache_today():
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        df = pd.read_csv(CACHE_FILE, dtype={"stock_id": str, "stock_name": str})
        if df.empty:
            return None
        cache_day = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE)).strftime("%Y-%m-%d")
        if cache_day == datetime.today().strftime("%Y-%m-%d"):
            return list(df[["stock_id", "stock_name"]].itertuples(index=False, name=None))
    except Exception:
        return None
    return None


def _save_cache(stocks):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        pd.DataFrame(stocks, columns=["stock_id", "stock_name"]).to_csv(
            CACHE_FILE, index=False, encoding="utf-8-sig"
        )
    except Exception:
        pass


# ----------------- 清單來源 -----------------
def _fetch_from_finmind():
    try:
        r = requests.get(FINMIND_INFO_URL, timeout=20)
        r.raise_for_status()
        data = r.json().get("data", [])
        if not data:
            return []
        df = pd.DataFrame(data)
        id_col = "stock_id" if "stock_id" in df.columns else None
        name_col = "stock_name" if "stock_name" in df.columns else None
        type_col = "type" if "type" in df.columns else None
        if not (id_col and name_col):
            return []
        if type_col:
            df = df[df[type_col].astype(str).str.lower().isin(["twse", "tse", "上市"])]
        df = df[df[id_col].astype(str).str.isdigit()]
        return list(df[[id_col, name_col]].itertuples(index=False, name=None))
    except Exception:
        return []


def _fetch_from_twse_openapi():
    try:
        try:
            r = requests.get(TWSE_OPENAPI_URL, timeout=15)
            r.raise_for_status()
        except requests.exceptions.SSLError:
            r = requests.get(TWSE_OPENAPI_URL, timeout=15, verify=False)
            r.raise_for_status()

        data = r.json()
        if not data:
            return []
        rows = []
        for row in data:
            code = (row.get("有價證券代號") or "").strip()
            name = (row.get("有價證券名稱") or "").strip()
            market = (row.get("市場別") or "").strip()
            if code.isdigit() and ("上市" in market):
                rows.append((code, name))
        return rows
    except Exception:
        return []


def get_all_stocks(use_cache: bool = True):
    """
    取得上市股票清單，優先用 FinMind，失敗再用 TWSE OpenAPI。
    全部失敗則回傳內建測試清單。
    """
    if use_cache:
        cached = _load_cache_today()
        if cached is not None:
            return cached

    stocks = _fetch_from_finmind()
    if not stocks:
        stocks = _fetch_from_twse_openapi()

    if stocks:
        _save_cache(stocks)
        return stocks

    print("⚠️ 無法取得上市清單，使用內建測試清單。")
    return [
        ("2330", "台積電"),
        ("2317", "鴻海"),
        ("2454", "聯發科"),
        ("2303", "聯電"),
        ("2881", "富邦金"),
        ("2882", "國泰金"),
        ("2603", "長榮"),
        ("2609", "陽明"),
        ("2615", "萬海"),
        ("1303", "南亞"),
    ]


# ----------------- 預篩（批次） -----------------
def get_stocks_under_1500(stock_list: list[tuple[str, str]] | None = None,
                          max_price: float = 1500.0,
                          limit: int | None = None,
                          max_checks: int = 300,
                          debug: bool = False):
    """
    用「快速價」做啟動預篩（Yahoo）。
    - 只使用『傳進來的 stock_list』；若沒傳，再呼叫 get_all_stocks()
    - Yahoo 批次失敗 → 逐檔慢速查價
    - 全失敗 → 回退為「傳入清單的前 limit 檔」，不再莫名其妙塞 1000 檔
    """
    from modules.fetch_price import get_quote_batch, get_latest_close_fast

    # 1) 來源清單：優先用呼叫端傳入，否則自己抓
    stocks = stock_list if stock_list is not None else get_all_stocks()
    if not stocks:
        return []

    # 只留數字代碼（上市/上櫃），並保持順序
    cand = [(sid, sname) for sid, sname in stocks if str(sid).isdigit()]
    target = limit if limit else len(cand)

    if debug:
        print(f"   ↪ 預篩候選：{len(cand)} 檔（由呼叫端提供={stock_list is not None}）")

    # 2) 先試 Yahoo 批次（.TW，再補 .TWO）
    try:
        if debug:
            print(f"   ↪ 批次查價（.TW）候選 {len(cand)} 檔，batch=80")
        batch_tw = get_quote_batch([sid for sid, _ in cand], suffix=".TW", timeout=6, batch_size=80)

        missing = [sid for sid, _ in cand if sid not in batch_tw]
        if missing and debug:
            print(f"   ↪ 補查（.TWO）{len(missing)} 檔…")
        batch_two = get_quote_batch(missing, suffix=".TWO", timeout=6, batch_size=80) if missing else {}

        price_map = {**batch_tw, **batch_two}  # {sid: {'price': ...}, ...}

        filtered = []
        for sid, sname in cand:
            info = price_map.get(sid)
            if info and (info.get("price") is not None) and float(info["price"]) < max_price:
                filtered.append((sid, sname))
            if len(filtered) >= target:
                break

        if filtered:
            return filtered[:target]
        # 批次成功但沒有符合價位 → 直接回空或取前 target？
        # 這裡回空，讓策略層去跑；若你想至少有東西，可改成 cand[:target]
    except Exception:
        if debug:
            print("   ⚠ Yahoo 批次查價失敗，改用逐檔慢速查價")

    # 3) 逐檔慢速查價（保底）
    filtered = []
    checks = 0
    for idx, (sid, sname) in enumerate(cand):
        try:
            p = get_latest_close_fast(sid, prefer_suffix=".TW", timeout=6)
            if p is None:
                p = get_latest_close_fast(sid, prefer_suffix=".TWO", timeout=6)
        except TypeError:
            # 舊版簽名相容
            p = get_latest_close_fast(sid)
        if p is not None and p < max_price:
            filtered.append((sid, sname))
        checks += 1
        if debug and (idx + 1) % 25 == 0:
            print(f"      · 進度：{idx + 1}/{len(cand)}，符合 {len(filtered)} 檔")
        if len(filtered) >= target or checks >= max_checks:
            break

    if filtered:
        return filtered[:target]

    # 4) 全部預篩都失敗 → 回退為『傳入清單的前 target 檔』
    if debug:
        print("   ⚠ 預篩失敗（Yahoo/逐檔皆不可用），回退為呼叫端清單的前幾檔")
    return cand[:target]


# ----------------- 單檔測試 -----------------
if __name__ == "__main__":
    s = get_all_stocks()
    print(f"上市股票數：{len(s)}，前10：{s[:10]}")
    print("低於 ceiling（前 50 檔內篩）：", get_stocks_under_1500(limit=20, max_checks=50))
