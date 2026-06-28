"""
Swing-trade screener routes.

Endpoints
---------
POST /api/screener/run              Start a scan; returns {run_id}.
GET  /api/screener/run/{id}/status  Poll scan progress.
GET  /api/screener/results          Latest completed run's results (ranked).
GET  /api/screener/stock/{symbol}   90-day OHLCV + indicator series for chart.
"""

import logging
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from api.db import get_supabase
from core.screeners.swing import compute_indicators, run_scan

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Pydantic models ────────────────────────────────────────────────────────────

class RunResponse(BaseModel):
    run_id: str


class RunStatus(BaseModel):
    run_id: str
    status: str
    total: int
    scanned: int
    passed: int
    error: str | None = None


class ScreenerResult(BaseModel):
    id: str
    run_id: str
    symbol: str
    name: str | None
    score: int
    setup_type: str | None
    signals_triggered: list[str]
    rs_ratio: float | None
    rs_rank: float | None
    trend_score: int | None
    adx: float | None
    entry_pivot: float | None
    stop: float | None
    target: float | None
    rr: float | None
    atr: float | None
    earnings_flag: bool | None
    last_close: float | None
    week52_high: float | None
    week52_low: float | None
    avg_turnover: float | None


class CandleBar(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class IndicatorSeries(BaseModel):
    time: int
    value: float


class StockDetail(BaseModel):
    symbol: str
    candles: list[CandleBar]
    ema9: list[IndicatorSeries]
    ema21: list[IndicatorSeries]
    ema50: list[IndicatorSeries]
    rsi: list[IndicatorSeries]
    macd_hist: list[IndicatorSeries]


# ── Background scan task ───────────────────────────────────────────────────────

def _do_scan(run_id: str) -> None:
    sb = get_supabase()

    def progress_cb(scanned: int, total: int) -> None:
        try:
            sb.table("screener_runs").update({
                "scanned": scanned,
                "total": total,
            }).eq("id", run_id).execute()
        except Exception:
            pass

    try:
        results = run_scan(progress_cb=progress_cb)

        # Fetch current total so we can store it accurately
        run_row = sb.table("screener_runs").select("total").eq("id", run_id).execute()
        current_total = run_row.data[0]["total"] if run_row.data else 0

        rows = [
            {
                "run_id":            run_id,
                "symbol":            r["symbol"],
                "name":              r.get("name"),
                "score":             r["score"],
                "setup_type":        r.get("setup_type"),
                "signals_triggered": r["signals_triggered"],
                "rs_ratio":          r.get("rs_ratio"),
                "rs_rank":           r.get("rs_rank"),
                "trend_score":       r.get("trend_score"),
                "adx":               r.get("adx"),
                "entry_pivot":       r.get("entry_pivot"),
                "stop":              r.get("stop"),
                "target":            r.get("target"),
                "rr":                r.get("rr"),
                "atr":               r.get("atr"),
                "earnings_flag":     r.get("earnings_flag", False),
                "last_close":        r.get("last_close"),
                "week52_high":       r.get("week52_high"),
                "week52_low":        r.get("week52_low"),
                "avg_turnover":      r.get("avg_turnover"),
            }
            for r in results
        ]

        if rows:
            sb.table("screener_results").insert(rows).execute()

        sb.table("screener_runs").update({
            "status": "done",
            "passed": len(results),
            "total": current_total,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", run_id).execute()

    except Exception as exc:
        logger.exception("Scan %s failed", run_id)
        try:
            sb.table("screener_runs").update({
                "status": "error",
                "error": str(exc),
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", run_id).execute()
        except Exception:
            pass


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/run", response_model=RunResponse)
def start_scan(background_tasks: BackgroundTasks):
    sb = get_supabase()
    res = sb.table("screener_runs").insert({
        "status": "running",
        "universe": "NIFTY 500",
        "total": 0,
        "scanned": 0,
        "passed": 0,
    }).execute()

    run_id = res.data[0]["id"]
    background_tasks.add_task(_do_scan, run_id)
    return RunResponse(run_id=run_id)


@router.get("/run/{run_id}/status", response_model=RunStatus)
def get_run_status(run_id: str):
    sb = get_supabase()
    res = sb.table("screener_runs").select("*").eq("id", run_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Run not found")
    row = res.data[0]
    return RunStatus(
        run_id=run_id,
        status=row["status"],
        total=row.get("total") or 0,
        scanned=row.get("scanned") or 0,
        passed=row.get("passed") or 0,
        error=row.get("error"),
    )


@router.get("/results", response_model=list[ScreenerResult])
def get_results():
    sb = get_supabase()
    run_res = (sb.table("screener_runs")
                 .select("id")
                 .eq("status", "done")
                 .order("finished_at", desc=True)
                 .limit(1)
                 .execute())
    if not run_res.data:
        return []
    run_id = run_res.data[0]["id"]

    results_res = (sb.table("screener_results")
                     .select("*")
                     .eq("run_id", run_id)
                     .order("score", desc=True)
                     .execute())
    return results_res.data or []


@router.get("/stock/{symbol}", response_model=StockDetail)
def get_stock_detail(symbol: str):
    yf_ticker = f"{symbol.upper()}.NS"
    try:
        df = yf.download(yf_ticker, period="90d", interval="1d", progress=False)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Data fetch failed: {exc}")

    if df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {symbol}")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = compute_indicators(df)
    df = df.dropna(subset=["Close"])

    def _series(col: str) -> list[IndicatorSeries]:
        sub = df[[col]].dropna()
        return [
            IndicatorSeries(
                time=int(idx.timestamp()),
                value=round(float(sub[col].iloc[i]), 4),
            )
            for i, idx in enumerate(sub.index)
        ]

    candles = []
    for idx, row in df.iterrows():
        if any(pd.isna(row[c]) for c in ["Open", "High", "Low", "Close"]):
            continue
        candles.append(CandleBar(
            time=int(idx.timestamp()),
            open=round(float(row["Open"]), 4),
            high=round(float(row["High"]), 4),
            low=round(float(row["Low"]), 4),
            close=round(float(row["Close"]), 4),
            volume=float(row.get("Volume", 0) or 0),
        ))

    return StockDetail(
        symbol=symbol.upper(),
        candles=candles,
        ema9=_series("EMA9"),
        ema21=_series("EMA21"),
        ema50=_series("EMA50"),
        rsi=_series("RSI14"),
        macd_hist=_series("MACD_hist"),
    )
