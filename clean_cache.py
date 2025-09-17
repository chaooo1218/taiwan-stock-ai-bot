# clean_cache.py
import os, shutil

paths = ["cache/price", "cache/lastprice", "cache/twse/twse_stocks.csv"]
for p in paths:
    if os.path.isdir(p):
        shutil.rmtree(p, ignore_errors=True)
        print(f"removed dir: {p}")
    elif os.path.isfile(p):
        try:
            os.remove(p)
            print(f"removed file: {p}")
        except FileNotFoundError:
            pass

# （可選）清 __pycache__
for root, dirs, files in os.walk(".", topdown=False):
    for d in dirs:
        if d == "__pycache__":
            shutil.rmtree(os.path.join(root, d), ignore_errors=True)

print("done.")
