from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.data import fetch_ohlcv_data
from core.stats import (
    CAGR, volatility, Sharpe, max_dd, calmar,
    rolling_sharpe, rolling_calmar, rolling_cagr, drawdown_analysis,
)
from core.stats.stationarity import stationarity
import numpy as np
import pandas as pd

router = APIRouter()

PERIOD_TO_DAYS = {
    "1d": 1, "5d": 5, "1mo": 30, "3mo": 90, "6mo": 180,
    "1y": 365, "2y": 730, "5y": 1825, "10y": 3650, "max": 7300,
}
INTERVAL_TIMEFRAME = {
    "1m": 252*390, "2m": 252*195, "5m": 252*78, "15m": 252*26,
    "30m": 252*13, "60m": 252*7, "1h": 252*7,
    "1d": 252, "5d": 52, "1wk": 52, "1mo": 12,
}


class FundamentalsRequest(BaseModel):
    symbols:  list[str]
    period:   str = "1y"
    interval: str = "1d"
    window:   int = 63


def _safe_float(v) -> float:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return 0.0
    return float(v)


@router.post("/ohlcv")
def get_ohlcv(req: FundamentalsRequest):
    days     = PERIOD_TO_DAYS.get(req.period, 365)
    suffix   = ".NS"
    symbols  = [s if s.startswith("^") or "." in s else f"{s}{suffix}"
                for s in req.symbols]
    try:
        data = fetch_ohlcv_data(symbols, days, req.interval)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    result = {}
    for sym, df in data.items():
        # Flatten MultiIndex if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(-1)
        df = df.where(pd.notnull(df), None)
        rows = []
        for ts, row in df.iterrows():
            rows.append({
                "date":   ts.isoformat(),
                "open":   _safe_float(row.get("Open")),
                "high":   _safe_float(row.get("High")),
                "low":    _safe_float(row.get("Low")),
                "close":  _safe_float(row.get("Close")),
                "volume": _safe_float(row.get("Volume")),
            })
        bare = sym.replace(".NS", "").replace(".BO", "")
        result[bare] = rows
    return result


@router.post("/kpis")
def get_kpis(req: FundamentalsRequest):
    days    = PERIOD_TO_DAYS.get(req.period, 365)
    suffix  = ".NS"
    symbols = [s if s.startswith("^") or "." in s else f"{s}{suffix}"
               for s in req.symbols]
    try:
        data = fetch_ohlcv_data(symbols, days, req.interval)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    timeframe = INTERVAL_TIMEFRAME.get(req.interval, 252)
    result    = {}

    for sym, df in data.items():
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(-1)
        if df.empty or "Close" not in df.columns:
            continue
        try:
            returns      = df["Close"].pct_change().dropna()
            skew         = float(returns.skew())
            kurt         = float(returns.kurt())
            pos_pct      = float((returns > 0).sum() / len(returns) * 100)
            diffs        = int(stationarity(df))
            bare = sym.replace(".NS", "").replace(".BO", "")
            result[bare] = {
                "cagr":          round(_safe_float(CAGR(df, timeframe)) * 100, 2),
                "volatility":    round(_safe_float(volatility(df, timeframe)) * 100, 2),
                "sharpe":        round(_safe_float(Sharpe(df, timeframe)), 3),
                "max_drawdown":  round(_safe_float(max_dd(df)) * 100, 2),
                "calmar":        round(_safe_float(calmar(df, timeframe)), 3),
                "skewness":      round(skew, 3),
                "excess_kurtosis": round(kurt, 3),
                "pct_positive":  round(pos_pct, 1),
                "stationarity_diffs": diffs,
            }
        except Exception:
            continue
    return result


@router.post("/rolling-kpis")
def get_rolling_kpis(req: FundamentalsRequest):
    days    = PERIOD_TO_DAYS.get(req.period, 365)
    suffix  = ".NS"
    symbols = [s if s.startswith("^") or "." in s else f"{s}{suffix}"
               for s in req.symbols]
    try:
        data = fetch_ohlcv_data(symbols, days, req.interval)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    timeframe = INTERVAL_TIMEFRAME.get(req.interval, 252)
    result    = {}

    for sym, df in data.items():
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(-1)
        if df.empty or "Close" not in df.columns:
            continue
        try:
            r_cagr   = rolling_cagr(df, timeframe, req.window) * 100
            r_sharpe = rolling_sharpe(df, timeframe, req.window)
            r_calmar = rolling_calmar(df, timeframe, req.window)
            dd, _, _ = drawdown_analysis(df)

            combined = pd.DataFrame({
                "rolling_cagr":   r_cagr,
                "rolling_sharpe": r_sharpe,
                "rolling_calmar": r_calmar,
                "drawdown":       dd * 100,
            }).dropna()
            combined["date"] = combined.index.strftime("%Y-%m-%d")
            combined = combined.reset_index(drop=True)

            bare = sym.replace(".NS", "").replace(".BO", "")
            result[bare] = combined.to_dict(orient="records")
        except Exception as e:
            print(f"rolling-kpis error for {sym}: {e}")
            continue
    return result
