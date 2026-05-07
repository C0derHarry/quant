"""Fetch OHLCV data for backtesting with caching."""
from __future__ import annotations
import hashlib
import json
import os
import warnings
from datetime import datetime

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "signal_cache", "bt_ohlcv")
os.makedirs(CACHE_DIR, exist_ok=True)

ALLOWED_UNIVERSES = [
    "NIFTY 50", "NIFTY 100", "NIFTY MIDCAP 100",
    "NIFTY SMALLCAP 100", "NIFTY BANK", "NIFTY IT",
]


def _cache_path(key: str) -> str:
    return os.path.join(CACHE_DIR, f"{key}.parquet")


def _cache_key(tickers: list[str], start: str, end: str) -> str:
    raw = f"{','.join(sorted(tickers))}|{start}|{end}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def resolve_universe(universe: str) -> list[str]:
    """Return NSE ticker list (no .NS suffix yet) for a named index."""
    from nsetools import Nse
    nse = Nse()
    stocks = nse.get_stock_quote_in_index(universe) or []
    # nsetools returns a list[dict] (each has 'symbol') or occasionally a dict keyed by symbol
    if isinstance(stocks, dict):
        return [s.upper() for s in stocks.keys() if s]
    if isinstance(stocks, list):
        out = []
        for item in stocks:
            if isinstance(item, dict):
                sym = item.get("symbol", "")
            else:
                sym = str(item)
            if sym:
                out.append(sym.upper())
        return out
    return []


def fetch_prices(
    tickers:    list[str],   # bare NSE symbols, no .NS
    start_date: str,         # "YYYY-MM-DD"
    end_date:   str,
    benchmark:  str = "^NSEI",
    max_missing_pct: float = 0.2,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Return (prices_df, benchmark_series) with adjusted close prices.
    prices_df columns = NS-suffixed tickers present with < max_missing_pct missing.
    benchmark_series = daily adjusted close for ^NSEI.
    """
    ns_tickers  = [f"{t}.NS" if not t.startswith("^") and "." not in t else t for t in tickers]
    all_tickers = list(set(ns_tickers + [benchmark]))

    ck   = _cache_key(all_tickers, start_date, end_date)
    path = _cache_path(ck)

    if os.path.exists(path):
        try:
            df = pd.read_parquet(path)
        except Exception:
            df = None
    else:
        df = None

    if df is None:
        raw = yf.download(
            all_tickers,
            start=start_date,
            end=end_date,
            auto_adjust=True,
            progress=False,
        )
        if isinstance(raw.columns, pd.MultiIndex):
            # yfinance returns MultiIndex (field, ticker); we want Close
            df = raw["Close"] if "Close" in raw.columns.get_level_values(0) else raw.xs("Close", axis=1, level=0)
        else:
            df = raw[["Close"]] if "Close" in raw.columns else raw
        df = df.copy()
        try:
            df.to_parquet(path)
        except Exception:
            pass

    # Separate benchmark
    bench = df[benchmark].copy() if benchmark in df.columns else pd.Series(dtype=float)
    price_cols = [c for c in df.columns if c != benchmark]

    prices = df[price_cols].copy()
    prices = prices.ffill(limit=5)

    # Drop tickers with too many missing values
    threshold = max_missing_pct * len(prices)
    prices    = prices.dropna(axis=1, thresh=int(len(prices) - threshold))

    return prices, bench


def survivorship_warning() -> str:
    return (
        "Results reflect current index constituents only. "
        "Stocks delisted or removed during the backtest period are excluded, "
        "which may overstate returns by ~1–2% CAGR (survivorship bias)."
    )
