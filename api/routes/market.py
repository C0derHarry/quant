import time as _time
import pandas as pd
import yfinance as yf
import pandas_market_calendars as mcal
from datetime import datetime, time, timedelta, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from nsetools import Nse
from concurrent.futures import ThreadPoolExecutor
from growwapi import GrowwAPI
from core.data.groww_client import GrowwError, GROWW_SNAPSHOTS, get_groww_client, ticker_snapshot_from_quote

router   = APIRouter()
nse      = Nse()
_nse_cal = mcal.get_calendar('NSE')
_IST     = timezone(timedelta(hours=5, minutes=30))

INDICES = {
    "NIFTY 50":   "^NSEI",
    "SENSEX":     "^BSESN",
    "BANK NIFTY": "^NSEBANK",
    "FIN NIFTY":  "^CNXFIN",
}

SECTORS = {
    "NIFTY IT":      "^CNXIT",
    "NIFTY PHARMA":  "^CNXPHARMA",
    "NIFTY AUTO":    "^CNXAUTO",
    "NIFTY FMCG":    "^CNXFMCG",
    "NIFTY METAL":   "^CNXMETAL",
    "NIFTY ENERGY":  "^CNXENERGY",
    "NIFTY INFRA":   "^CNXINFRA",
    "NIFTY BANK":    "^NSEBANK",
}

NSE_SECTOR_NAMES = [
    "NIFTY 50", "NIFTY BANK", "NIFTY IT", "NIFTY PHARMA",
    "NIFTY AUTO", "NIFTY FMCG", "NIFTY METAL", "NIFTY ENERGY",
    "NIFTY INFRA", "NIFTY FIN SERVICE",
]


def _ticker_snapshot(ticker: str) -> dict:
    info = yf.Ticker(ticker).fast_info
    price = float(info["last_price"])
    prev  = float(info["previous_close"])
    return {
        "price":      price,
        "prev_close": prev,
        "change":     round(price - prev, 2),
        "pct_change": round((price - prev) / prev * 100, 3),
    }


def _groww_snapshot(name: str) -> dict:
    """Real-time snapshot from Groww Quote API. Raises GrowwError on failure."""
    exchange, segment, symbol = GROWW_SNAPSHOTS[name]
    payload = get_groww_client().get_quote(trading_symbol=symbol, exchange=exchange, segment=segment)
    return ticker_snapshot_from_quote(payload)


def _snapshot(name: str, yf_ticker: str) -> dict:
    """Groww-first snapshot with automatic yfinance fallback."""
    if name in GROWW_SNAPSHOTS:
        try:
            return _groww_snapshot(name)
        except GrowwError:
            pass
    return _ticker_snapshot(yf_ticker)


@router.get("/indices")
def get_indices():
    results = {}
    for name, ticker in INDICES.items():
        try:
            results[name] = _snapshot(name, ticker)
        except Exception:
            pass
    return results


@router.get("/sectors")
def get_sectors():
    results = {}
    for name, ticker in SECTORS.items():
        try:
            results[name] = _snapshot(name, ticker)
        except Exception:
            pass
    return results


@router.get("/sector/{sector_name}/stocks")
def get_sector_stocks(sector_name: str):
    try:
        raw = nse.get_stock_quote_in_index(sector_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    rows = []
    for s in raw:
        try:
            rows.append({
                "symbol":     s.get("symbol", ""),
                "name":       s.get("meta", {}).get("companyName", "").title(),
                "price":      float(s.get("lastPrice", 0)),
                "change":     float(s.get("change", 0)),
                "pct_change": float(s.get("pChange", 0)),
                "volume":     s.get("totalTradedVolume", 0),
                "year_high":  float(s.get("yearHigh", 0)),
                "year_low":   float(s.get("yearLow", 0)),
            })
        except Exception:
            continue
    return sorted(rows, key=lambda x: x["pct_change"], reverse=True)


# ── Live quotes via Groww bulk LTP ─────────────────────────────────────
#
# Strategy: Groww's get_ltp() is the lightest live-data API (up to 50 symbols
# per call, returns just the last traded price). We pair it with a per-sector
# prev_close cache (refreshed hourly via nsetools) so we can compute
# change / pct_change server-side without hitting NSE every poll.

_PREV_CLOSE_TTL = 3600                                # 1h
_prev_close_cache: dict[str, dict[str, float]] = {}   # sector → {sym: prev_close}
_prev_close_ts:    dict[str, float]            = {}   # sector → last refresh ts


def _refresh_prev_close(sector_name: str) -> dict[str, float]:
    raw = nse.get_stock_quote_in_index(sector_name)
    pc: dict[str, float] = {}
    for s in raw:
        sym = s.get("symbol", "")
        if not sym:
            continue
        try:
            last = float(s.get("lastPrice", 0))
            pct  = float(s.get("pChange", 0))
            denom = 1 + pct / 100
            if last and denom:
                pc[sym] = last / denom
        except Exception:
            continue
    return pc


def _get_prev_close(sector_name: str) -> dict[str, float]:
    now = _time.time()
    if (sector_name not in _prev_close_cache
        or now - _prev_close_ts.get(sector_name, 0) > _PREV_CLOSE_TTL):
        _prev_close_cache[sector_name] = _refresh_prev_close(sector_name)
        _prev_close_ts[sector_name]    = now
    return _prev_close_cache[sector_name]


def _groww_quote_one(sym: str) -> dict | None:
    """Single-symbol live quote via Groww. Returns price/change/pct/volume."""
    try:
        client  = get_groww_client()
        payload = client.get_quote(
            trading_symbol=sym,
            exchange=GrowwAPI.EXCHANGE_NSE,
            segment=GrowwAPI.SEGMENT_CASH,
        )
        return {
            "price":      float(payload.get("last_price", 0)),
            "change":     float(payload.get("day_change", 0)),
            "pct_change": float(payload.get("day_change_perc", 0)),
            "volume":     int(payload.get("volume", 0) or 0),
        }
    except Exception:
        return None


def _groww_quotes_bulk(symbols: list[str], max_workers: int = 16) -> dict[str, dict]:
    """Parallel get_quote() across symbols. Returns {symbol: {price, change, pct, volume}}.

    Each get_quote payload includes day_change/day_change_perc and volume directly,
    so no prev_close cache is needed on this path. Raises if every call fails."""
    out: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_groww_quote_one, s): s for s in symbols}
        for fut in futures:
            sym = futures[fut]
            r   = fut.result()
            if r is not None:
                out[sym] = r
    if not out:
        raise GrowwError("All Groww get_quote calls failed")
    return out


def _nsetools_quotes_fallback(sector_name: str) -> dict[str, dict]:
    raw = nse.get_stock_quote_in_index(sector_name)
    quotes: dict[str, dict] = {}
    for s in raw:
        sym = s.get("symbol", "")
        if not sym:
            continue
        try:
            quotes[sym] = {
                "price":      float(s.get("lastPrice", 0)),
                "change":     float(s.get("change", 0)),
                "pct_change": float(s.get("pChange", 0)),
                "volume":     int(s.get("totalTradedVolume", 0) or 0),
            }
        except Exception:
            continue
    return quotes


@router.get("/sector/{sector_name}/quotes")
def get_sector_quotes(sector_name: str):
    """Live quotes for polling. Returns {symbol: {price, change, pct_change, volume}}.

    Primary: Groww parallel get_quote() (full live data including volume).
    Fallback: nsetools (used if Groww auth fails / network errors / rate-limited)."""
    try:
        prev_close = _get_prev_close(sector_name)  # universe resolution + 1h cache
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if not prev_close:
        return {}

    try:
        return _groww_quotes_bulk(list(prev_close.keys()))
    except Exception:
        return _nsetools_quotes_fallback(sector_name)


_ENRICH_INDICES = [
    "NIFTY 50", "NIFTY NEXT 50", "NIFTY 100", "NIFTY 200", "NIFTY 500",
    "NIFTY MIDCAP 50", "NIFTY MIDCAP 100", "NIFTY MIDCAP 150",
    "NIFTY SMALLCAP 50", "NIFTY SMALLCAP 100", "NIFTY SMALLCAP 250",
    "NIFTY BANK", "NIFTY IT", "NIFTY PHARMA", "NIFTY AUTO",
    "NIFTY FMCG", "NIFTY METAL", "NIFTY ENERGY", "NIFTY INFRA",
    "NIFTY FIN SERVICE",
]


def _fetch_name_map() -> dict[str, str]:
    """Fetch symbol→companyName from multiple indices in parallel."""
    def _one(idx: str) -> dict[str, str]:
        try:
            rows = nse.get_stock_quote_in_index(idx)
            return {
                r["symbol"]: r.get("meta", {}).get("companyName", "").title()
                for r in rows if r.get("symbol")
            }
        except Exception:
            return {}

    name_map: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        for partial in ex.map(_one, _ENRICH_INDICES):
            name_map.update(partial)
    return name_map


@router.get("/symbols")
def get_all_symbols(exchange: str = "NSE"):
    try:
        if exchange != "NSE":
            return []

        codes = nse.get_stock_codes()
        if isinstance(codes, dict):
            symbols = sorted(codes.keys())
            base_names: dict[str, str] = codes
        else:
            symbols = sorted(codes)
            base_names = {}

        name_map = _fetch_name_map()

        return [
            {"symbol": s, "name": name_map.get(s) or base_names.get(s) or s}
            for s in symbols
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sector-names")
def get_sector_names():
    return NSE_SECTOR_NAMES


@router.get("/sector/{sector_name}/symbols")
def get_sector_symbols(sector_name: str):
    try:
        raw = nse.get_stock_quote_in_index(sector_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return [
        {
            "symbol": s.get("symbol", ""),
            "name":   s.get("meta", {}).get("companyName", s.get("symbol", "")).title(),
        }
        for s in raw
        if s.get("symbol")
    ]


class SymbolList(BaseModel):
    symbols: list[str]


def _fetch_name(symbol: str) -> tuple[str, str]:
    suffix = ".NS" if not symbol.endswith((".NS", ".BO")) else ""
    try:
        name = yf.Ticker(f"{symbol}{suffix}").info.get("shortName", symbol)
        return symbol, name.title() if isinstance(name, str) else symbol
    except Exception:
        return symbol, symbol


@router.post("/stock-names")
def get_stock_names(body: SymbolList):
    with ThreadPoolExecutor(max_workers=10) as ex:
        results = dict(ex.map(_fetch_name, body.symbols))
    return results


@router.get("/status")
def get_market_status():
    now  = datetime.now(_IST)
    date = now.date().strftime("%Y-%m-%d")
    try:
        schedule = _nse_cal.schedule(start_date=date, end_date=date)
        is_trading_day = not schedule.empty
    except Exception:
        is_trading_day = now.weekday() < 5
    is_open = is_trading_day and time(9, 15) <= now.time() <= time(15, 30)
    return {"is_open": is_open, "is_trading_day": is_trading_day}


@router.get("/index-list")
def get_index_list():
    try:
        indices = nse.get_index_list()
        return sorted(indices) if isinstance(indices, list) else []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


ASSET_TICKERS = {
    "NIFTY 50":  "^NSEI",
    "Gold":      "GOLDBEES.NS",
    "IT Sector": "^CNXIT",
    "Banking":   "^NSEBANK",
    "Midcap":    "^NSEMDCP50",
    "USD/INR":   "USDINR=X",
}

PERIOD_MAP = {"1m": "1mo", "3m": "3mo", "6m": "6mo", "1y": "1y", "3y": "3y"}


@router.get("/asset-compare")
def asset_compare(period: str = "1y"):
    av_period = PERIOD_MAP.get(period, "1y")
    tickers = list(ASSET_TICKERS.values())
    try:
        raw = yf.download(tickers, period=av_period, auto_adjust=True, progress=False)
        closes = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw
        if isinstance(closes, pd.Series):
            closes = closes.to_frame(tickers[0])
        result = {}
        for label, ticker in ASSET_TICKERS.items():
            col = ticker if ticker in closes.columns else None
            if col is None:
                continue
            series = closes[col].dropna()
            if series.empty:
                continue
            base = float(series.iloc[0])
            if base == 0:
                continue
            result[label] = [
                {"date": d.strftime("%Y-%m-%d"), "value": round(float(v) / base * 100, 2)}
                for d, v in series.items()
            ]
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/index/{index_name}/stocks")
def get_index_stocks(index_name: str):
    try:
        raw = nse.get_stock_quote_in_index(index_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    rows = []
    for s in raw:
        try:
            rows.append({
                "symbol":     s.get("symbol", ""),
                "name":       s.get("meta", {}).get("companyName", "").title(),
                "price":      float(s.get("lastPrice", 0)),
                "change":     float(s.get("change", 0)),
                "pct_change": float(s.get("pChange", 0)),
                "volume":     s.get("totalTradedVolume", 0),
                "year_high":  float(s.get("yearHigh", 0)),
                "year_low":   float(s.get("yearLow", 0)),
            })
        except Exception:
            continue
    return sorted(rows, key=lambda x: x["pct_change"], reverse=True)
