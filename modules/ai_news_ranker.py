# modules/ai_news_ranker.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import List, Dict, Any

import torch
from transformers import pipeline
from transformers.utils.logging import set_verbosity_error

# 關閉多數 HF 噪音
set_verbosity_error()

# ====== 裝置自動偵測 ======
def _pick_device() -> int:
    try:
        if torch.cuda.is_available():
            return 0  # GPU
    except Exception:
        pass
    return -1  # CPU

DEVICE = _pick_device()

# ====== Pipeline（全域單例）======
# 模型可依你需求替換；這兩個都是中文可用的常見檔
_SUMMARY_MODEL_ID = "uer/t5-base-chinese-cluecorpussmall"
_SENTIMENT_MODEL_ID = "uer/roberta-base-finetuned-jd-binary-chinese"

_summary_pipe = pipeline(
    "summarization",
    model=_SUMMARY_MODEL_ID,
    device=DEVICE,
    framework="pt",
    trust_remote_code=False,
)

_sentiment_pipe = pipeline(
    "sentiment-analysis",
    model=_SENTIMENT_MODEL_ID,
    device=DEVICE,
    framework="pt",
    trust_remote_code=False,
)

# ====== 新聞來源權重 ======
SOURCE_WEIGHTS = {
    "中央社": 1.2,
    "經濟日報": 1.1,
    "聯合新聞網": 1.0,
    "自由時報": 1.0,
    "ETtoday": 0.85,
    "鉅亨網": 0.9,
    "Yahoo新聞": 0.8,
}

# ====== 時間處理 ======
_TIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S%z",
)

def parse_publish_time(time_str: str | None):
    if not time_str:
        return None
    s = str(time_str).strip()
    for fmt in _TIME_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
            # 沒時區就當本地時間
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue
    # 有些來源只給日期
    try:
        dt = datetime.strptime(s[:10], "%Y-%m-%d")
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None

def time_weight(publish_time_str: str | None) -> float:
    """越新權重越高，最少 0.5；以「天」做衰減，但更平滑。"""
    dt = parse_publish_time(publish_time_str)
    if dt is None:
        return 1.0
    now = datetime.now(timezone.utc)
    days = max((now - dt).total_seconds() / 86400.0, 0.0)
    # 前 1 天幾乎不衰減，之後每天 -0.07，最低 0.5
    return max(0.5, 1.0 - 0.07 * days)

# ====== 文本處理 ======
_URL_RE = re.compile(r"https?://\S+")
_WS_RE = re.compile(r"\s+")

def clean_text(text: str | None) -> str:
    if not text:
        return ""
    text = _URL_RE.sub("", text)
    text = text.replace("\u3000", " ")
    text = _WS_RE.sub(" ", text).strip()
    return text

# ====== 摘要與情緒 ======
def summarize_text(text: str) -> str:
    """
    只用 max_new_tokens 避免與 max_length 衝突（消除你的警告）。
    短文直接截斷，不呼叫模型以節省時間。
    """
    txt = clean_text(text)
    if not txt:
        return ""

    # 極短內文直接回傳（避免模型浪費）
    if len(txt) <= 80:
        return txt

    # 粗估中文 token：用字數/2 當近似
    approx_tokens = max(1, len(txt) // 2)
    new_tokens = min(120, max(40, int(approx_tokens * 0.4)))  # 介於 40~120

    try:
        out = _summary_pipe(
            txt,
            max_new_tokens=new_tokens,
            do_sample=False,
            truncation=True,
        )
        return out[0]["summary_text"]
    except Exception:
        # 模型失敗時，回退到截斷
        return txt[:200]

def analyze_sentiment(text: str) -> tuple[str, float]:
    """回傳 (標籤, 分數)，分數以 POSITIVE 可信度為主。"""
    try:
        res = _sentiment_pipe(text[:512])[0]
        label = str(res.get("label", "")).upper()
        score = float(res.get("score", 0.5) or 0.5)
        # 有些模型標籤不是 POSITIVE/NEGATIVE，做個對齊
        if label not in {"POSITIVE", "NEGATIVE"}:
            label = "POSITIVE" if score >= 0.5 else "NEGATIVE"
        return label, score
    except Exception:
        return "NEUTRAL", 0.5

# ====== 主邏輯：打分/排序 ======
def rank_news(news_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    期望輸入每則含：title, content, publish_time, source, url（缺也可）
    產出欄位：
      - summary
      - sentiment（POSITIVE/NEGATIVE/NEUTRAL）
      - sentiment_score（0~1）
      - weighted_score（用於排序）
    """
    ranked: list[dict] = []

    for news in news_list or []:
        title = clean_text(news.get("title", ""))
        content = clean_text(news.get("content", ""))
        source = (news.get("source") or "未知來源").strip()
        publish_time = news.get("publish_time", "")

        full_text = (title + "。 " + content).strip()
        summary = summarize_text(full_text) if full_text else ""
        sentiment, score = analyze_sentiment(summary or title)

        source_w = SOURCE_WEIGHTS.get(source, 0.9)
        time_w = time_weight(publish_time)
        weighted_score = float(score) * float(source_w) * float(time_w)

        rec = dict(news)
        rec["summary"] = summary
        rec["sentiment"] = sentiment
        rec["sentiment_score"] = float(score)
        rec["weighted_score"] = float(weighted_score)
        ranked.append(rec)

    ranked.sort(key=lambda x: x.get("weighted_score", 0.0), reverse=True)
    return ranked

# ====== 獨立測試 ======
if __name__ == "__main__":
    sample_news = [
        {
            "title": "台積電大漲創新高",
            "content": "台積電股價今日大幅上漲，投資人樂觀期待未來發展。",
            "source": "中央社",
            "publish_time": "2025-07-15 14:30:00"
        },
        {
            "title": "半導體需求放緩",
            "content": "分析師警告半導體產業需求可能減弱，股價面臨壓力。",
            "source": "自由時報",
            "publish_time": "2025-07-10 09:00:00"
        },
    ]
    ranked = rank_news(sample_news)
    for n in ranked:
        print(f"{n['title']} - {n['sentiment']}({n['sentiment_score']:.2f}), 加權: {n['weighted_score']:.2f}")
        print(f"摘要: {n['summary']}\n")
