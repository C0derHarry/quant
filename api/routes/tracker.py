import numpy as np
import pandas as pd
import yfinance as yf
from fastapi import APIRouter, Depends, HTTPException
from ..deps import get_current_user, supabase_client, AuthUser

router = APIRouter()


@router.get("/{portfolio_id}")
def get_tracker(portfolio_id: str, auth: AuthUser = Depends(get_current_user)):
    sb = supabase_client(auth)
    port = sb.table("portfolios").select("*").eq("id", portfolio_id).single().execute()
    if not port.data:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    data          = port.data
    tickers: list = data["tickers"]
    weights: dict = data["weights"]
    start_date    = pd.Timestamp(data["invested_at"]).tz_localize(None).normalize()
    end_date      = pd.Timestamp.utcnow().tz_localize(None).normalize()

    if (end_date - start_date).days < 1:
        return {"message": "Portfolio was just created — check back tomorrow for performance data."}

    # Fetch prices + NIFTY 50 benchmark
    all_tickers = list(tickers) + ["^NSEI"]
    raw = yf.download(all_tickers, start=start_date, end=end_date,
                      auto_adjust=True, progress=False)["Close"]
    if isinstance(raw, pd.Series):
        raw = raw.to_frame(all_tickers[0])
    raw = raw.dropna(how="all").ffill(limit=5)

    port_tickers = [t for t in tickers if t in raw.columns]
    if not port_tickers:
        raise HTTPException(status_code=500, detail="No price data available for portfolio tickers.")

    prices = raw[port_tickers].dropna(how="all")
    if prices.empty:
        raise HTTPException(status_code=500, detail="Price data returned empty.")

    # Normalise to 1 at first observation and compute weighted portfolio value
    norm = prices / prices.iloc[0]
    w    = np.array([weights.get(t, 0.0) for t in port_tickers], dtype=float)
    w   /= w.sum()
    port_values = (norm * w).sum(axis=1)

    # Benchmark normalised series
    bench_col = None
    if "^NSEI" in raw.columns:
        bench     = raw["^NSEI"].reindex(prices.index).ffill()
        bench_col = (bench / bench.iloc[0]).values.tolist()

    # Performance metrics
    log_ret      = np.log(port_values / port_values.shift(1)).dropna().values
    n_days       = len(log_ret)
    total_ret    = float(port_values.iloc[-1]) - 1.0
    ann_factor   = 252 / n_days if n_days > 0 else 1.0
    cagr         = float((1 + total_ret) ** ann_factor - 1) if n_days > 0 else 0.0
    ann_vol      = float(log_ret.std() * np.sqrt(252)) if n_days > 1 else 0.0
    sharpe       = round(cagr / ann_vol, 3) if ann_vol > 0 else 0.0
    roll_max     = port_values.cummax()
    max_drawdown = float(((port_values - roll_max) / roll_max).min())

    # Per-ticker breakdown
    ticker_perf = [
        {
            "ticker": t,
            "return": round(float(prices[t].iloc[-1] / prices[t].iloc[0] - 1) * 100, 2),
            "weight": round(float(weights.get(t, 0)) * 100, 2),
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

    return {
        "portfolio_name": data["name"],
        "invested_at":    data["invested_at"],
        "tickers":        port_tickers,
        "series":         series,
        "metrics": {
            "total_return": round(total_ret * 100, 2),
            "cagr":         round(cagr * 100, 2),
            "annual_vol":   round(ann_vol * 100, 2),
            "sharpe":       sharpe,
            "max_drawdown": round(max_drawdown * 100, 2),
            "days_held":    n_days,
        },
        "ticker_performance": ticker_perf,
    }
