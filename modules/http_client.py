# modules/http_client.py
import os
import warnings
import requests
from urllib3.exceptions import InsecureRequestWarning
from requests.adapters import HTTPAdapter, Retry

def get_session():
    s = requests.Session()
    retries = Retry(total=3, backoff_factor=0.5,
                    status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s

def get_json(url: str, timeout=15, params=None):
    """
    1) verify=True → 2) verify=<CA from env> → 3) verify=False（靜音）
    回傳 .json()；失敗則丟出例外讓呼叫端處理
    """
    sess = get_session()
    ca_bundle = os.getenv("TWSE_CA_BUNDLE") or os.getenv("REQUESTS_CA_BUNDLE")

    try:
        r = sess.get(url, timeout=timeout, params=params)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.SSLError:
        pass

    if ca_bundle and os.path.exists(ca_bundle):
        try:
            r = sess.get(url, timeout=timeout, params=params, verify=ca_bundle)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.SSLError:
            pass

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", InsecureRequestWarning)
        r = sess.get(url, timeout=timeout, params=params, verify=False)
        r.raise_for_status()
        return r.json()
