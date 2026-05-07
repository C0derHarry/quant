"""Strategy backtesting API — catalog, run stream, export, saved runs."""
from __future__ import annotations
import json
import logging
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..deps import get_current_user, supabase_client, AuthUser

router = APIRouter()
log    = logging.getLogger(__name__)

MAX_YEARS = 15


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"


def _validate_dates(start_date: str, end_date: str) -> None:
    try:
        s = date.fromisoformat(start_date)
        e = date.fromisoformat(end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    if s >= e:
        raise HTTPException(status_code=400, detail="start_date must be before end_date.")
    if (e - s).days > MAX_YEARS * 365:
        raise HTTPException(status_code=400, detail=f"Date range cannot exceed {MAX_YEARS} years.")


# ── Catalog + brokerages ──────────────────────────────────────────────────────

@router.get("/catalog")
def get_catalog():
    from core.strategies import CATALOG
    return [cls.catalog_entry() for cls in CATALOG.values()]


@router.get("/brokerages")
def get_brokerages():
    from core.strategies.cost_model import BROKERAGES
    return [b.to_dict() for b in BROKERAGES.values()]


@router.get("/brokerages/{broker_id}/summary")
def get_broker_summary(broker_id: str, universe: str = Query("NIFTY 50")):
    from core.strategies.cost_model import broker_summary, BROKERAGES
    if broker_id not in BROKERAGES:
        raise HTTPException(status_code=404, detail=f"Unknown broker: {broker_id}")
    return broker_summary(broker_id, universe)


# ── Run stream (SSE) ──────────────────────────────────────────────────────────

@router.get("/run/stream")
def stream_backtest(
    strategy_id: str   = Query(...),
    params_json: str   = Query("{}"),
    broker_id:   str   = Query("zerodha"),
    universe:    str   = Query("NIFTY 50"),
    start_date:  str   = Query(...),
    end_date:    str   = Query(...),
    capital:     float = Query(1_000_000),
    portfolio_id: str | None = Query(None),
    auth: AuthUser = Depends(get_current_user),
):
    from core.strategies import CATALOG
    from core.strategies.cost_model import BROKERAGES
    from core.strategies.data_loader import (
        resolve_universe, fetch_prices, ALLOWED_UNIVERSES,
    )
    from core.strategies.runner import run_strategy
    from core.strategies.exporter import export_filename

    _validate_dates(start_date, end_date)

    if strategy_id not in CATALOG:
        raise HTTPException(status_code=400, detail=f"Unknown strategy: {strategy_id}")
    if broker_id not in BROKERAGES:
        raise HTTPException(status_code=400, detail=f"Unknown broker: {broker_id}")
    if capital < 10_000:
        raise HTTPException(status_code=400, detail="Capital must be at least ₹10,000.")

    try:
        params = json.loads(params_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid params JSON.")

    def _gen():
        try:
            # Stage 1: resolve universe + fetch data
            yield _sse({"type": "stage", "stage": 1, "status": "running", "label": "Fetching price data"})
            if universe in ALLOWED_UNIVERSES:
                try:
                    raw_tickers = resolve_universe(universe)
                except Exception as exc:
                    log.warning("nsetools universe resolution failed: %s", exc)
                    raw_tickers = []
            else:
                raw_tickers = []

            if not raw_tickers:
                yield _sse({"type": "error", "message": f"Could not resolve universe: {universe}"})
                return

            prices, benchmark = fetch_prices(raw_tickers, start_date, end_date)
            if prices.empty:
                yield _sse({"type": "error", "message": "No price data available for selected range."})
                return
            yield _sse({"type": "stage", "stage": 1, "status": "done", "n_tickers": len(prices.columns)})

            # Stage 2: generate signals
            yield _sse({"type": "stage", "stage": 2, "status": "running", "label": "Generating signals"})
            strategy_cls = CATALOG[strategy_id]
            strategy     = strategy_cls()
            weights_df   = strategy.generate_signals(prices, None, params)
            if weights_df.empty:
                yield _sse({"type": "error", "message": "Strategy produced no signals for this date range."})
                return
            yield _sse({"type": "stage", "stage": 2, "status": "done", "n_rebalances": len(weights_df)})

            # Stage 3: simulate + costs
            yield _sse({"type": "stage", "stage": 3, "status": "running", "label": "Simulating with costs"})
            result = run_strategy(
                strategy   = strategy,
                params     = params,
                prices     = prices,
                benchmark  = benchmark,
                capital    = capital,
                broker_id  = broker_id,
                universe   = universe,
                start_date = start_date,
                end_date   = end_date,
            )
            yield _sse({"type": "stage", "stage": 3, "status": "done"})

            # Stage 4: compute KPIs + persist
            yield _sse({"type": "stage", "stage": 4, "status": "running", "label": "Computing KPIs"})
            result_dict = {
                "strategy_id":     result.strategy_id,
                "equity_curve":    result.equity_curve,
                "benchmark_curve": result.benchmark_curve,
                "drawdown_curve":  result.drawdown_curve,
                "trade_log":       result.trade_log[:500],   # cap for SSE payload
                "kpis":            result.kpis,
                "params":          result.params,
                "universe":        result.universe,
                "start_date":      result.start_date,
                "end_date":        result.end_date,
                "brokerage_id":    result.brokerage_id,
                "total_cost":      result.total_cost,
                "survivorship_bias_warning": result.survivorship_bias_warning,
                "tickers":         list(prices.columns),
            }

            # Auto-save to Supabase
            try:
                sb  = supabase_client(auth)
                row = {
                    "user_id":      auth.user_id,
                    "portfolio_id": portfolio_id,
                    "strategy_id":  strategy_id,
                    "params":       params,
                    "brokerage_id": broker_id,
                    "universe":     universe,
                    "start_date":   start_date,
                    "end_date":     end_date,
                    "result":       result_dict,
                }
                saved = sb.table("strategy_runs").insert(row).execute()
                if saved.data:
                    result_dict["run_id"] = saved.data[0]["id"]
            except Exception as exc:
                log.warning("Failed to save strategy run: %s", exc)

            yield _sse({"type": "stage", "stage": 4, "status": "done"})
            yield _sse({"type": "result", "data": result_dict})

        except Exception as exc:
            log.exception("Backtest stream error")
            yield _sse({"type": "error", "message": str(exc)})

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":  "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Code export ───────────────────────────────────────────────────────────────

class ExportRequest(BaseModel):
    strategy_id: str
    params:      dict
    broker_id:   str
    tickers:     list[str]
    start_date:  str
    end_date:    str
    kpis:        dict


@router.post("/export")
def export_strategy(body: ExportRequest, auth: AuthUser = Depends(get_current_user)):
    from core.strategies.exporter import render_standalone, export_filename
    try:
        content  = render_standalone(
            strategy_id = body.strategy_id,
            params      = body.params,
            broker_id   = body.broker_id,
            tickers     = body.tickers,
            start_date  = body.start_date,
            end_date    = body.end_date,
            kpis        = body.kpis,
        )
        filename = export_filename(body.strategy_id, body.start_date, body.end_date)
        return {"filename": filename, "content": content}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Saved runs ────────────────────────────────────────────────────────────────

@router.get("/runs")
def list_runs(
    limit: int = Query(20, ge=1, le=100),
    auth: AuthUser = Depends(get_current_user),
):
    sb = supabase_client(auth)
    res = (sb.table("strategy_runs")
             .select("id, strategy_id, universe, start_date, end_date, brokerage_id, created_at, result->kpis")
             .order("created_at", desc=True)
             .limit(limit)
             .execute())
    return res.data or []


@router.get("/runs/{run_id}")
def get_run(run_id: str, auth: AuthUser = Depends(get_current_user)):
    sb  = supabase_client(auth)
    res = sb.table("strategy_runs").select("*").eq("id", run_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Run not found.")
    return res.data
