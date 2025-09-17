# storage/signals_db.py
import os
import sqlite3
from datetime import datetime

DB_DIR = "storage"
DB_PATH = os.path.join(DB_DIR, "signals.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  stock_id TEXT NOT NULL,
  stock_name TEXT NOT NULL,
  strategy_name TEXT NOT NULL,
  price REAL NOT NULL,
  trigger_count INTEGER NOT NULL,
  signal_type TEXT NOT NULL,
  reason TEXT
);
"""

def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(SCHEMA)
        conn.commit()

def log_signal(stock_id, stock_name, strategy_name, price, trigger_count, signal_type, reason=""):
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO signals (ts, stock_id, stock_name, strategy_name, price, trigger_count, signal_type, reason) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), stock_id, stock_name, strategy_name,
             float(price), int(trigger_count), signal_type, reason)
        )
        conn.commit()

def today_summary():
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT stock_id, stock_name, COUNT(*) as cnt
            FROM signals
            WHERE date(ts) = date('now','localtime')
            GROUP BY stock_id, stock_name
            ORDER BY cnt DESC
            LIMIT 5
        """)
        top = cur.fetchall()
        cur.execute("""
            SELECT COUNT(*)
            FROM signals
            WHERE date(ts) = date('now','localtime')
        """)
        total = cur.fetchone()[0]
    msg = f"📊 今日訊號數：{total}\n📈 推播前五名：\n"
    for sid, sname, cnt in top:
        msg += f"{sid} {sname}：{cnt} 次\n"
    return msg.strip()
