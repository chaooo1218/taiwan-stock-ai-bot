# modules/indicators.py
import numpy as np
import pandas as pd

def _col(df, prefs):
    for c in prefs:
        if c in df.columns:
            return c
    return None

def detect_cols(df: pd.DataFrame):
    hi = _col(df, ["high", "max", "High"])
    lo = _col(df, ["low", "min", "Low"])
    cl = _col(df, ["close", "Close"])
    vol = _col(df, ["volume", "Volume", "Trading_Volume"])
    return hi, lo, cl, vol

def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    hi, lo, cl, _ = detect_cols(df)
    if not (hi and lo and cl):
        return pd.Series([np.nan]*len(df), index=df.index)
    high = df[hi].astype(float)
    low  = df[lo].astype(float)
    close= df[cl].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low).abs(),
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=n).mean()

def nday_high(df: pd.DataFrame, n: int = 20) -> pd.Series:
    hi, _, _, _ = detect_cols(df)
    if not hi:
        return pd.Series([np.nan]*len(df), index=df.index)
    return df[hi].rolling(n, min_periods=1).max()

def nday_low(df: pd.DataFrame, n: int = 20) -> pd.Series:
    _, lo, _, _ = detect_cols(df)
    if not lo:
        return pd.Series([np.nan]*len(df), index=df.index)
    return df[lo].rolling(n, min_periods=1).min()

def twse_tick(price: float) -> float:
    """台股最小跳動價規則"""
    p = float(price)
    if p < 10:    return 0.01
    if p < 50:    return 0.05
    if p < 100:   return 0.1
    if p < 500:   return 0.5
    if p < 1000:  return 1.0
    return 5.0

def round_to_tick(price: float, mode: str = "nearest") -> float:
    """依跳動價四捨五入/進位/捨去"""
    step = twse_tick(price)
    x = price / step
    if mode == "up":
        y = np.ceil(x)
    elif mode == "down":
        y = np.floor(x)
    else:
        y = np.round(x)
    return float(y * step)
