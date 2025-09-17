import os
import json
from datetime import datetime

def load_json(filepath):
    """讀取 JSON 檔案"""
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ JSON 讀取失敗 {filepath}: {e}")
        return None

def save_json(filepath, data):
    """寫入 JSON 檔案"""
    try:
        dir_path = os.path.dirname(filepath)
        if dir_path:
            ensure_dir_exists(dir_path)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ JSON 寫入失敗 {filepath}: {e}")

def current_timestamp(fmt="%Y-%m-%d %H:%M:%S"):
    """取得目前時間字串"""
    return datetime.now().strftime(fmt)

def ensure_dir_exists(dir_path):
    """確保資料夾存在，若無則建立"""
    if not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)


if __name__ == "__main__":
    # 測試
    test_path = "cache/test.json"
    save_json(test_path, {"time": current_timestamp(), "msg": "Hello"})
    print(load_json(test_path))
