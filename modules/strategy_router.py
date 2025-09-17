# modules/strategy_router.py
from __future__ import annotations
from typing import List, Dict, Any
import math
import pandas as pd

def _safe_float(x, default=math.nan):
    try:
        return float(x)
    except Exception:
        return default

# ====== 指標與價格建議 ======
from modules.indicators import atr, nday_high, nday_low, round_to_tick

def _build_advice(df, basis: str = "tech"):
    """
    簡易建議價位（可自行替換成更完整版本）：
      - 買進區：MA5 與 MA20 區間
      - 停損：買進區下緣 * 0.98
      - 目標價：近20/60日高
    """
    if df is None or len(df) < 60:
        return None
    today = df.iloc[-1]
    ma5 = float(today.get("MA5", today["close"]))
    ma20 = float(today.get("MA20", today["close"]))
    lo, hi = sorted([ma5, ma20])
    past20_high = float(df["close"].iloc[-21:-1].max())
    past60_high = float(df["close"].iloc[-61:-1].max())
    return {
        "buy_zone": (lo, hi),
        "stop": max(0.0, lo * 0.98),
        "tp1": past20_high,
        "tp2": past60_high,
    }

# ===================== 技術面 ======================
def strategy_technical(df, **kwargs):
    """
    技術面：金叉（MA5 上穿 MA20）＋ 量能放大 ＋ 突破前20日高（不含今天）
    預設：三選二觸發（想嚴格可改回三者皆要）
    """
    if df is None or len(df) < 21:
        return {'strategy': '技術面', 'triggered': False, 'reason': '資料不足'}

    today = df.iloc[-1]
    yesterday = df.iloc[-2]

    # 1) 金叉
    golden_cross = (yesterday['MA5'] < yesterday['MA20']) and (today['MA5'] > today['MA20'])

    # 2) 量能放大（fetch_price 已將 volume/Volume_avg 統一）
    vol_ok = True
    if "Volume_avg" in df.columns and "volume" in df.columns:
        vol_ok = float(today["volume"]) > float(today["Volume_avg"]) * 1.8  # 想更嚴格可調 1.8

    # 3) 突破「前20日」高（不含今天）
    past20_high = float(df['close'].iloc[-21:-1].max())
    breakout_high = float(today['close']) > past20_high

    # ✅ 三選二
    ok_cnt = sum([bool(golden_cross), bool(vol_ok), bool(breakout_high)])
    triggered = bool(golden_cross and vol_ok and breakout_high)
    # 若你要三者皆要成立，改成：
    # triggered = bool(golden_cross and vol_ok and breakout_high)

    reason = (
        f"觸發（滿足 {ok_cnt}/3）：金叉={golden_cross}、量能={vol_ok}、突破高點={breakout_high}"
        if triggered else
        f"未觸發（僅 {ok_cnt}/3）：金叉={golden_cross}、量能={vol_ok}、突破高點={breakout_high}"
    )

    try:
        advice = _build_advice(df, basis='tech') if triggered else None
        return {'strategy': '技術面', 'triggered': triggered, 'reason': reason, 'advice': advice}
    except Exception:
        return {'strategy': '技術面', 'triggered': triggered, 'reason': reason}

# ===================== 法人面 ======================
def strategy_fundamental(fund_data, *args, **kwargs):
    """
    法人策略：最近 3 日三大法人（外資＋投信＋自營商）合計淨買超 > 1500 張
      - 欄位安全：自動 to_numeric，缺欄位當 0
      - None 或筆數不足直接回「資料不足」
    """
    if fund_data is None or len(fund_data) < 3:
        return {'strategy': '法人策略', 'triggered': False, 'reason': '法人資料不足'}

    recent = fund_data.tail(3)

    fi = pd.to_numeric(recent.get('Foreign_Investor'), errors='coerce').fillna(0).sum()
    it = pd.to_numeric(recent.get('Investment_Trust'), errors='coerce').fillna(0).sum()
    ds = pd.to_numeric(recent.get('Dealer_self'), errors='coerce').fillna(0).sum()

    total_buy = float(fi + it + ds)
    triggered = total_buy > 1500.0

    reason = f'三大法人近3日合計淨買超 {total_buy:.0f} 張'
    if not triggered:
        reason += '（未達門檻 1500）'

    try:
        advice = _build_advice(fund_data, basis='fund') if triggered else None
        return {'strategy': '法人策略', 'triggered': triggered, 'reason': reason, 'advice': advice}
    except Exception:
        return {'strategy': '法人策略', 'triggered': triggered, 'reason': reason}

# ===================== 新聞面 ======================
def strategy_news(news_sentiments, pos_threshold: float = 0.80, **kwargs):
    """
    新聞策略：任一則 POSITIVE 且分數 >= 門檻 觸發
      - 同時相容欄位 'sentiment_score' 與 'score'
      - 可擴充 weighted_score 的加權判定
    """
    if not news_sentiments:
        return {'strategy': '新聞策略', 'triggered': False, 'reason': '無新聞資料'}

    def _score(n: dict) -> float:
        if n.get("sentiment_score") is not None:
            try:
                return float(n.get("sentiment_score") or 0.0)
            except Exception:
                return 0.0
        try:
            return float(n.get("score") or 0.0)
        except Exception:
            return 0.0

    pos_items = [n for n in news_sentiments if str(n.get('sentiment', '')).upper() == 'POSITIVE']
    if not pos_items:
        return {'strategy': '新聞策略', 'triggered': False, 'reason': '無正面新聞'}

    best = max((_score(n) for n in pos_items), default=0.0)
    triggered = best >= float(pos_threshold)

    reason = f"最高正面分數={best:.2f}（門檻 {pos_threshold:.2f}）"
    return {'strategy': '新聞策略', 'triggered': triggered, 'reason': reason}

# ===================== 統一路由 =====================
def run_all_strategies(df, fund_data, news_sentiments, **kwargs):
    """
    以 **kwargs 傳遞額外參數（例如 pos_threshold），各策略自行取用；
    不需要的策略忽略即可，避免參數不相容。
    """
    results = []
    results.append(strategy_technical(df, **kwargs))
    results.append(strategy_fundamental(fund_data, **kwargs))
    results.append(strategy_news(
        news_sentiments,
        pos_threshold=kwargs.get('pos_threshold', 0.80),
        **kwargs
    ))
    return results
