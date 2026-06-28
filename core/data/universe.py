import io
import time
import requests
import pandas as pd

_ARCHIVES_BASE = "https://archives.nseindia.com/content/indices/"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
_CSV_FILE = "ind_nifty500list.csv"
_CACHE: tuple[list[dict], float] | None = None
_TTL = 86400  # 24 h — index composition changes quarterly


def get_nifty500() -> list[dict]:
    """Return [{symbol, name, yf_symbol}] for NIFTY 500 EQ constituents; cached 24 h."""
    global _CACHE
    now = time.time()
    if _CACHE and now - _CACHE[1] < _TTL:
        return _CACHE[0]

    url = _ARCHIVES_BASE + _CSV_FILE
    r = requests.get(url, timeout=15, headers=_HEADERS)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))

    rows = []
    for _, row in df.iterrows():
        series = str(row.get("Series", "EQ")).strip()
        if series != "EQ":
            continue
        symbol = str(row["Symbol"]).strip()
        name = str(row["Company Name"]).title()
        rows.append({
            "symbol": symbol,
            "name": name,
            "yf_symbol": f"{symbol}.NS",
        })

    _CACHE = (rows, now)
    return rows
