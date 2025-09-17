# modules/notifier.py
import os
import time
import hashlib
import requests

# 優先從 config.py 讀；若沒有/找不到，就用環境變數；最後給預設值
try:
    from config import DISCORD_WEBHOOK as CFG_WEBHOOK, DEDUP_WINDOW_SEC as CFG_DEDUP
except Exception:
    CFG_WEBHOOK = None
    CFG_DEDUP = None

# 去重時間窗（秒）
DEDUP_WINDOW_SEC = int(os.getenv("DEDUP_WINDOW_SEC", str(CFG_DEDUP if CFG_DEDUP is not None else 1800)))

# 記憶體層去重（訊息哈希 -> 最後推送時間戳）
_seen: dict[str, float] = {}


def _hash_msg(msg: str) -> str:
    return hashlib.sha256(msg.encode("utf-8")).hexdigest()


def send_discord_message(message: str, webhook_url: str | None = None):
    """
    發送 Discord 訊息：
    - 可直接傳入 webhook_url（優先）
    - 若未傳入，會依序嘗試：config.DISCORD_WEBHOOK -> 環境變數 DISCORD_WEBHOOK
    - 30 分鐘（預設，可用 DEDUP_WINDOW_SEC 設定）內相同訊息不重覆推播
    """
    # 去重
    h = _hash_msg(message)
    now = time.time()
    last = _seen.get(h, 0.0)
    if now - last < DEDUP_WINDOW_SEC:
        return  # within dedup window, skip
    _seen[h] = now

    # 取得 webhook
    webhook = (
        webhook_url
        or CFG_WEBHOOK
        or os.getenv("DISCORD_WEBHOOK")  # 最後從環境變數拿
    )

    if not webhook:
        # 沒設定就僅印出到終端，不丟例外，避免打斷流程
        print(f"[Discord 未設定] {message}")
        return

    try:
        resp = requests.post(webhook, json={"content": message}, timeout=10)
        if resp.status_code not in (200, 204):
            print(f"Discord 推播失敗: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"Discord 推播例外: {e}")


def print_terminal(message: str):
    """在終端機印出訊息"""
    print(message)
