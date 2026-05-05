import math
import numpy as np
import pandas as pd
import yfinance as yf
from fastapi import APIRouter, Depends, HTTPException
from ..deps import get_current_user, supabase_client, AuthUser

router = APIRouter()


def _safe(v):
    """Recursively replace nan/inf with None so JSON serialisation never throws."""
    if isinstance(v, float):
        return None if (math.isnan(v) or math.isinf(v)) else v
    if isinstance(v, (np.floating, np.integer)):
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(v, dict):
        return {k: _safe(vv) for k, vv in v.items()}
    if isinstance(v, list):
        return [_safe(i) for i in v]
    return v


def _safe_num(v, default: float = 0.0) -> float:
    """Return 0.0 (or default) for NaN/inf/None — for numeric metrics sent to the frontend."""
    try:
        f = float(v) if v is not None else default
        return default if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return default


@router.get("/{portfolio_id}")
def get_tracker(portfolio_id: str, auth: AuthUser = Depends(get_current_user)):
    sb = supabase_client(auth)
    port = sb.table("portfolios").select("*").eq("id", portfolio_id).single().execute()
    if not port.data:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    data          = port.data
    tickers: list = data["tickers"]
    weights: dict = data["weights"] or {}
    capital: float | None = data.get("capital")
    invested_at   = data.get("invested_at") or data.get("created_at")
    if not invested_at:
        raise HTTPException(status_code=400, detail="Portfolio has no investment date.")
    start_date    = pd.Timestamp(invested_at).tz_localize(None).normalize()
    end_date      = pd.Timestamp.utcnow().tz_localize(None).normalize()

    if (end_date - start_date).days < 1:
        raise HTTPException(status_code=400, detail="Portfolio was just created — check back tomorrow for performance data.")

    # Fetch prices + NIFTY 50 benchmark
    # Add .NS suffix for NSE stocks that don't already have an exchange suffix
    def _ns(sym: str) -> str:
        return sym if (sym.startswith("^") or "." in sym) else f"{sym}.NS"

    ns_map     = {_ns(t): t for t in tickers}   # NS ticker → original name
    dl_tickers = list(ns_map.keys()) + ["^NSEI"]

    def _extract_close(df) -> pd.DataFrame:
        if isinstance(df.columns, pd.MultiIndex):
            lvl0 = df.columns.get_level_values(0)
            field = "Close" if "Close" in lvl0 else ("Adj Close" if "Adj Close" in lvl0 else None)
            if field:
                return df[field].copy()
        if "Close" in df.columns:
            return df["Close"].to_frame() if isinstance(df["Close"], pd.Series) else df[["Close"]]
        return df.copy()

    # yfinance end is exclusive — add 2 extra days so today's close is always included
    dl_end = end_date + pd.Timedelta(days=2)

    # Try date-range download first; fall back to period="5d" for very fresh portfolios
    days_held = (end_date - start_date).days
    if days_held >= 5:
        raw = yf.download(dl_tickers, start=start_date, end=dl_end,
                          auto_adjust=True, progress=False)
    else:
        raw = yf.download(dl_tickers, period="5d", auto_adjust=True, progress=False)

    raw = _extract_close(raw).dropna(how="all").ffill(limit=5)

    # Rename .NS tickers back to original names so weight lookup works
    raw.rename(columns={k: v for k, v in ns_map.items() if k in raw.columns}, inplace=True)

    port_tickers = [t for t in tickers if t in raw.columns]
    if not port_tickers:
        raise HTTPException(status_code=500, detail="No price data available for portfolio tickers.")

    prices = raw[port_tickers].dropna(how="all")
    if prices.empty:
        raise HTTPException(status_code=500, detail="Price data returned empty.")

    # Normalise to 1 at first observation and compute weighted portfolio value
    norm = prices / prices.iloc[0]
    w    = np.array([weights.get(t, 0.0) for t in port_tickers], dtype=float)
    if w.sum() == 0:  # fallback to equal weight when portfolio was saved without optimizer
        w = np.ones(len(port_tickers), dtype=float)
    w   /= w.sum()
    port_values = (norm * w).sum(axis=1)

    # Benchmark normalised series
    bench_col = None
    if "^NSEI" in raw.columns:
        bench = raw["^NSEI"].reindex(prices.index).ffill().bfill()
        b0    = float(bench.iloc[0]) if not bench.empty else 0.0
        if b0 and not math.isnan(b0):
            bench_col = [(float(v) / b0) if not math.isnan(float(v)) else None
                         for v in bench.values]

    # Performance metrics
    log_ret      = np.log(port_values / port_values.shift(1)).dropna().values
    n_days       = len(log_ret)
    total_ret    = _safe_num(float(port_values.iloc[-1]) - 1.0)
    roll_max     = port_values.cummax()
    max_drawdown = _safe_num(float(((port_values - roll_max) / roll_max).min()))

    # Annualised metrics require at least 30 trading days to be meaningful
    if n_days >= 30:
        ann_factor = 252 / n_days
        cagr       = _safe_num(float((1 + total_ret) ** ann_factor - 1))
        ann_vol    = _safe_num(float(log_ret.std() * np.sqrt(252)))
        sharpe     = round(cagr / ann_vol, 3) if ann_vol > 0 else None
    else:
        cagr    = None
        ann_vol = None
        sharpe  = None

    # Per-ticker breakdown
    def _ticker_return(t: str) -> float:
        p0 = float(prices[t].iloc[0])
        p1 = float(prices[t].iloc[-1])
        if p0 == 0 or math.isnan(p0) or math.isnan(p1):
            return 0.0
        return round((p1 / p0 - 1) * 100, 2)

    # Build final weight map (normalised, equal-fallback applied)
    final_weights = dict(zip(port_tickers, w.tolist()))

    ticker_perf = [
        {
            "ticker":     t,
            "return":     _ticker_return(t),
            "weight":     round(final_weights[t] * 100, 2),
            "allocation": round(capital * final_weights[t]) if capital else None,
        }
        for t in port_tickers
    ]

    series = [
        {
            "date":      str(idx.date()),
            "portfolio": round(float(pv), 4),
            "benchmark": round(float(bv), 4) if bv is not None else None,
        }
        for idx, pv, bv in zip(
            port_values.index,
            port_values.values,
            bench_col if bench_col else [None] * len(port_values),
        )
    ]

    return _safe({
        "portfolio_name": data["name"],
        "invested_at":    data["invested_at"],
        "capital":        capital,
        "tickers":        port_tickers,
        "series":         series,
        "metrics": {
            "total_return": round(total_ret * 100, 2),
            "cagr":         round(cagr * 100, 2) if cagr is not None else None,
            "annual_vol":   round(ann_vol * 100, 2) if ann_vol is not None else None,
            "sharpe":       sharpe,
            "max_drawdown": round(max_drawdown * 100, 2),
            "days_held":    n_days,
        },
        "ticker_performance": ticker_perf,
    })

