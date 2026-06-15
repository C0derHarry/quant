import io
import time as _time
import requests
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

# ── NSE Archives constituent fetcher ──────────────────────────────────────────
# NSE's live equity-stockIndices API blocks non-browser clients.
# archives.nseindia.com serves the same constituent CSVs without auth or JS.

_ARCHIVES_BASE    = "https://archives.nseindia.com/content/indices/"
_ARCHIVES_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

INDEX_CSV_MAP: dict[str, str] = {
    "NIFTY 50":            "ind_nifty50list.csv",
    "NIFTY NEXT 50":       "ind_niftynext50list.csv",
    "NIFTY 100":           "ind_nifty100list.csv",
    "NIFTY 200":           "ind_nifty200list.csv",
    "NIFTY 500":           "ind_nifty500list.csv",
    "NIFTY MIDCAP 50":     "ind_niftymidcap50list.csv",
    "NIFTY MIDCAP 100":    "ind_niftymidcap100list.csv",
    "NIFTY MIDCAP 150":    "ind_niftymidcap150list.csv",
    "NIFTY SMALLCAP 50":   "ind_niftysmallcap50list.csv",
    "NIFTY SMALLCAP 100":  "ind_niftysmallcap100list.csv",
    "NIFTY SMALLCAP 250":  "ind_niftysmallcap250list.csv",
    "NIFTY BANK":          "ind_niftybanklist.csv",
    "NIFTY IT":            "ind_niftyitlist.csv",
    "NIFTY PHARMA":        "ind_niftypharmalist.csv",
    "NIFTY AUTO":          "ind_niftyautolist.csv",
    "NIFTY FMCG":          "ind_niftyfmcglist.csv",
    "NIFTY METAL":         "ind_niftymetallist.csv",
    "NIFTY ENERGY":        "ind_niftyenergylist.csv",
    "NIFTY INFRA":         "ind_niftyinfralist.csv",
    "NIFTY FIN SERVICE":   "ind_niftyfinancelist.csv",
}

_CONSTITUENT_CACHE: dict[str, tuple[list[dict], float]] = {}
_CONSTITUENT_TTL = 86400  # 24h — index compositions change quarterly


def _fetch_constituents(index_name: str) -> list[dict]:
    """Return [{symbol, name}] for index_name; cached 24 h."""
    now = _time.time()
    if index_name in _CONSTITUENT_CACHE:
        rows, ts = _CONSTITUENT_CACHE[index_name]
        if now - ts < _CONSTITUENT_TTL:
            return rows
    csv_file = INDEX_CSV_MAP.get(index_name)
    if not csv_file:
        raise ValueError(f"No constituent CSV for index '{index_name}'")
    url = _ARCHIVES_BASE + csv_file
    r = requests.get(url, timeout=15, headers=_ARCHIVES_HEADERS)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    rows = [
        {"symbol": str(row["Symbol"]).strip(), "name": str(row["Company Name"]).title()}
        for _, row in df.iterrows()
        if str(row.get("Series", "EQ")).strip() == "EQ"
    ]
    _CONSTITUENT_CACHE[index_name] = (rows, now)
    return rows


def _yf_stock_row(symbol: str, name: str) -> dict | None:
    """Full stock row via yfinance fast_info (price, change, volume, 52-wk range)."""
    try:
        fi      = yf.Ticker(f"{symbol}.NS").fast_info
        price   = float(fi["lastPrice"] or 0)
        prev    = float(fi["previousClose"] or 0)
        change  = round(price - prev, 2)
        pct     = round(change / prev * 100, 3) if prev else 0.0
        return {
            "symbol":     symbol,
            "name":       name,
            "price":      price,
            "change":     change,
            "pct_change": pct,
            "volume":     int(fi["lastVolume"] or 0),
            "year_high":  float(fi["yearHigh"] or 0),
            "year_low":   float(fi["yearLow"] or 0),
        }
    except Exception:
        return None


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


# Maps display name → nsetools get_index_quote() argument
_NSE_INDEX_NAMES: dict[str, str] = {
    "NIFTY 50":          "nifty 50",
    "BANK NIFTY":        "nifty bank",
    "NIFTY BANK":        "nifty bank",
    "FIN NIFTY":         "nifty fin service",
    "NIFTY IT":          "nifty it",
    "NIFTY PHARMA":      "nifty pharma",
    "NIFTY AUTO":        "nifty auto",
    "NIFTY FMCG":        "nifty fmcg",
    "NIFTY METAL":       "nifty metal",
    "NIFTY ENERGY":      "nifty energy",
    "NIFTY INFRA":       "nifty infrastructure",
    "NIFTY FIN SERVICE": "nifty fin service",
}


def _parse_num(v) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return float(str(v).replace(",", "") or 0)


def _nse_snapshot(name: str) -> dict:
    """nsetools index snapshot. Raises ValueError if mapping or data missing."""
    nse_name = _NSE_INDEX_NAMES.get(name)
    if not nse_name:
        raise ValueError(f"No nsetools mapping for '{name}'")
    q = nse.get_index_quote(nse_name)
    if not q:
        raise ValueError(f"nsetools returned empty for '{nse_name}'")
    price  = _parse_num(q.get("last", 0))
    prev   = _parse_num(q.get("previousClose", 0))
    change = _parse_num(q.get("variation", 0))
    pct    = _parse_num(q.get("percentChange", 0))
    return {
        "price":      round(price, 2),
        "prev_close": round(prev, 2),
        "change":     round(change, 2),
        "pct_change": round(pct, 3),
    }


def _groww_snapshot(name: str) -> dict:
    """Real-time snapshot from Groww Quote API. Raises GrowwError on failure."""
    exchange, segment, symbol = GROWW_SNAPSHOTS[name]
    payload = get_groww_client().get_quote(trading_symbol=symbol, exchange=exchange, segment=segment)
    return ticker_snapshot_from_quote(payload)


def _snapshot(name: str, yf_ticker: str) -> dict:
    """3-tier snapshot: Groww → nsetools → yfinance."""
    if name in GROWW_SNAPSHOTS:
        try:
            return _groww_snapshot(name)
        except Exception:
            pass
    try:
        return _nse_snapshot(name)
    except Exception:
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
        constituents = _fetch_constituents(sector_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    rows = []
    with ThreadPoolExecutor(max_workers=20) as ex:
        futures = {ex.submit(_yf_stock_row, c["symbol"], c["name"]): c for c in constituents}
        for fut in futures:
            r = fut.result()
            if r is not None:
                rows.append(r)
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
    constituents = _fetch_constituents(sector_name)

    def _get_prev(c: dict) -> tuple[str, float]:
        try:
            fi = yf.Ticker(f"{c['symbol']}.NS").fast_info
            return c["symbol"], float(fi["previousClose"] or 0)
        except Exception:
            return c["symbol"], 0.0

    pc: dict[str, float] = {}
    with ThreadPoolExecutor(max_workers=16) as ex:
        for sym, prev in ex.map(_get_prev, constituents):
            if prev:
                pc[sym] = prev
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


def _yf_quotes_fallback(sector_name: str) -> dict[str, dict]:
    """yfinance fallback for sector quotes when Groww is unavailable."""
    try:
        constituents = _fetch_constituents(sector_name)
    except Exception:
        return {}

    def _one(c: dict) -> tuple[str, dict | None]:
        row = _yf_stock_row(c["symbol"], c["name"])
        if row is None:
            return c["symbol"], None
        return c["symbol"], {
            "price":      row["price"],
            "change":     row["change"],
            "pct_change": row["pct_change"],
            "volume":     row["volume"],
        }

    quotes: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=16) as ex:
        for sym, q in ex.map(_one, constituents):
            if q is not None:
                quotes[sym] = q
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
        return _yf_quotes_fallback(sector_name)


_ENRICH_INDICES = [
    "NIFTY 50", "NIFTY NEXT 50", "NIFTY 100", "NIFTY 200", "NIFTY 500",
    "NIFTY MIDCAP 50", "NIFTY MIDCAP 100", "NIFTY MIDCAP 150",
    "NIFTY SMALLCAP 50", "NIFTY SMALLCAP 100", "NIFTY SMALLCAP 250",
    "NIFTY BANK", "NIFTY IT", "NIFTY PHARMA", "NIFTY AUTO",
    "NIFTY FMCG", "NIFTY METAL", "NIFTY ENERGY", "NIFTY INFRA",
    "NIFTY FIN SERVICE",
]


def _fetch_name_map() -> dict[str, str]:
    """Fetch symbol→companyName from multiple indices in parallel via archives CSVs."""
    def _one(idx: str) -> dict[str, str]:
        try:
            return {c["symbol"]: c["name"] for c in _fetch_constituents(idx)}
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
        return _fetch_constituents(sector_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        constituents = _fetch_constituents(index_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    rows = []
    with ThreadPoolExecutor(max_workers=20) as ex:
        futures = {ex.submit(_yf_stock_row, c["symbol"], c["name"]): c for c in constituents}
        for fut in futures:
            r = fut.result()
            if r is not None:
                rows.append(r)
    return sorted(rows, key=lambda x: x["pct_change"], reverse=True)
