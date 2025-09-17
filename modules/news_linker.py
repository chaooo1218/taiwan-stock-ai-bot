# modules/news_linker.py（覆蓋）
import re

_EN_ALIAS = {
    "2330": ["tsmc", "taiwan semiconductor"],
    "2317": ["hon hai", "foxconn"],
    "2454": ["mediatek"],
    "2303": ["umc", "united microelectronics"],
}

def _clean(s: str) -> str:
    return (s or "").lower().strip()

def build_aliases(stocks):
    aliases = {}
    for sid, name in stocks:
        nm = (name or "").strip()
        nm_base = re.sub(r"(股份)?有(限)?公司", "", nm).strip()
        arr = {sid, nm, nm_base, f"{nm}（{sid}）", f"{nm}({sid})"}
        for en in _EN_ALIAS.get(sid, []):
            arr.add(en)
        aliases[sid] = [a.lower() for a in arr if a]
    return aliases

def link_news_to_stock(news_list, stock_id, aliases_map):
    kws = aliases_map.get(stock_id, [])
    res = []
    for n in news_list or []:
        title = _clean(n.get("title"))
        content = _clean(n.get("content"))
        hit = False
        for kw in kws:
            if kw in title or kw in content:
                hit = True
                break
        if hit:
            res.append(n)
    return res
