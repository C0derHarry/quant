import yfinance as yf
from fastapi import APIRouter, HTTPException
from nsetools import Nse

router = APIRouter()
nse    = Nse()

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


@router.get("/indices")
def get_indices():
    results = {}
    for name, ticker in INDICES.items():
        try:
            results[name] = _ticker_snapshot(ticker)
        except Exception:
            pass
    return results


@router.get("/sectors")
def get_sectors():
    results = {}
    for name, ticker in SECTORS.items():
        try:
            results[name] = _ticker_snapshot(ticker)
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
                "name":       s.get("meta", {}).get("companyName", ""),
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


@router.get("/symbols")
def get_all_symbols(exchange: str = "NSE"):
    try:
        if exchange == "NSE":
            codes = nse.get_stock_codes()
            if isinstance(codes, dict):
                return [{"symbol": k, "name": v} for k, v in sorted(codes.items())]
            return [{"symbol": s, "name": s} for s in sorted(codes)]
        return []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sector-names")
def get_sector_names():
    return NSE_SECTOR_NAMES
