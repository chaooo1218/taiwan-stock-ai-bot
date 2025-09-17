# modules/finmind_client.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import time
import threading
import requests
from requests.adapters import HTTPAdapter, Retry

from config import FINMIND_TOKEN, FINMIND_QPS, FINMIND_RETRY

BASE = "https://api.finmindtrade.com/api/v4/data"

# 簡單的節流（全域共用）：確保平均每秒不超過 FINMIND_QPS
class _RateLimiter:
    def __init__(self, qps: float):
        self.min_interval = 1.0 / max(qps, 0.1)
        self.lock = threading.Lock()
        self._last = 0.0

    def wait(self):
        with self.lock:
            now = time.time()
            dt = now - self._last
            if dt < self.min_interval:
                time.sleep(self.min_interval - dt)
            self._last = time.time()

_limiter = _RateLimiter(FINMIND_QPS)

def _session() -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=FINMIND_RETRY,
        backoff_factor=0.4,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))
    return s

_sess = _session()

def get_data(dataset: str, data_id: str | None = None,
             start_date: str | None = None, end_date: str | None = None,
             extra_params: dict | None = None, timeout: int = 12) -> list[dict]:
    """
    取 FinMind dataset；自動帶 token、限速、重試。
    回傳 list(dict)；失敗回 []。
    """
    params = {"dataset": dataset}
    if data_id:
        params["data_id"] = data_id
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    if FINMIND_TOKEN:
        params["token"] = FINMIND_TOKEN
    if extra_params:
        params.update(extra_params)

    try:
        _limiter.wait()
        r = _sess.get(BASE, params=params, timeout=timeout)
        # 402/429/5xx 這邊不拋出例外，由呼叫端判斷
        if r.status_code == 402:
            # 額度不足 / 未帶 token / token 無效
            return []
        r.raise_for_status()
        j = r.json()
        return j.get("data", []) or []
    except requests.exceptions.SSLError:
        # 很少見，但備一手
        _limiter.wait()
        r = _sess.get(BASE, params=params, timeout=timeout, verify=False)
        if r.status_code == 402:
            return []
        r.raise_for_status()
        j = r.json()
        return j.get("data", []) or []
    except Exception:
        return []
