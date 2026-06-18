import numpy as np
import pandas as pd
import yfinance as yf
from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_current_user, AuthUser, get_subscription
from api.routes.technical import _evaluate_indicators, _verdict
from core.scorecard.context import ScoreContext
from core.scorecard.engine import build_scorecard

router = APIRouter()

BENCHMARK  = "^NSEI"
PERIOD     = "2y"
CACHE_DIR  = "api/signal_cache"


def _normalize(ticker: str) -> str:
    if ticker.endswith((".NS", ".BO")) or ticker.startswith("^"):
        return ticker
    return ticker + ".NS"


def _flatten_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten yfinance MultiIndex columns so df['Close'] is always a Series."""
    price_set = {"Open", "High", "Low", "Close", "Volume", "Adj Close"}
    if isinstance(df.columns, pd.MultiIndex):
        chosen = 0
        for level in range(df.columns.nlevels):
            if price_set & set(df.columns.get_level_values(level)):
                chosen = level
                break
        df.columns = df.columns.get_level_values(chosen)
    return df.loc[:, ~df.columns.duplicated()]


def _safe_float(val) -> float | None:
    try:
        v = float(val)
        return None if np.isnan(v) or np.isinf(v) else v
    except Exception:
        return None


def _is_financial(info: dict) -> bool:
    sector = (info.get("sector") or "").lower()
    return "financial" in sector or "bank" in sector


def _fetch_fundamentals(ns: str) -> dict:
    """Return yfinance fundamental data dict or empty dict on failure."""
    try:
        tk = yf.Ticker(ns)
        return {
            "info":          tk.info,
            "financials":    tk.financials,
            "balance_sheet": tk.balance_sheet,
            "cash_flow":     tk.cashflow,
        }
    except Exception:
        return {}


def _fetch_ml_pup(ns: str, ohlcv: pd.DataFrame) -> float | None:
    """
    Load or fit the GBM signal model for this ticker and return calibrated
    P(5-day up). Uses the same joblib cache as api/routes/signals.py.
    Returns None on any failure — engine treats it as missing.
    """
    try:
        import os, joblib
        from core.signals.ml_signals import MLSignalModel

        cache_file = os.path.join(CACHE_DIR, f"{ns.replace('.', '_')}.pkl")
        os.makedirs(CACHE_DIR, exist_ok=True)

        model: MLSignalModel | None = None
        if os.path.exists(cache_file):
            try:
                model = joblib.load(cache_file)
            except Exception:
                model = None

        if model is None:
            model = MLSignalModel()
            model.fit(ohlcv)
            joblib.dump(model, cache_file)

        result = model.latest_signal(ohlcv)
        p_up = result.get("p_up")
        if p_up is None:
            return None
        return float(p_up)
    except Exception:
        return None


@router.get("/{ticker}")
def get_scorecard(
    ticker: str,
    auth: AuthUser = Depends(get_current_user),
):
    """
    Free endpoint — every authenticated user can access the scorecard.
    Premium models are included/excluded based on subscription tier.
    """
    try:
        sub = get_subscription(auth)
        include_premium = sub.get("tier") == "premium"

        ns = _normalize(ticker)

        # ── Download OHLCV for ticker + Nifty benchmark ───────────────────────
        raw = yf.download(
            [ns, BENCHMARK],
            period=PERIOD,
            auto_adjust=True,
            progress=False,
            group_by="ticker",
        )

        if raw.empty:
            raise ValueError(f"No market data returned for {ns}")

        # Split by ticker — handle both multi-index and single-ticker returns
        if isinstance(raw.columns, pd.MultiIndex):
            try:
                ticker_df = _flatten_cols(raw[ns].copy())
            except KeyError:
                raise ValueError(f"Ticker {ns} not found in downloaded data")
            try:
                bench_df = _flatten_cols(raw[BENCHMARK].copy())
            except KeyError:
                bench_df = pd.DataFrame()
        else:
            # Only one ticker returned (shouldn't happen with two symbols but handle it)
            ticker_df = _flatten_cols(raw.copy())
            bench_df = pd.DataFrame()

        ticker_df = ticker_df.dropna(how="all")
        bench_df  = bench_df.dropna(how="all") if not bench_df.empty else bench_df

        if ticker_df.empty:
            raise ValueError(f"No price data available for {ticker}")

        # ── Compute technical summary (pre-compute so engine stays pure) ──────
        tech_summary: dict | None = None
        if len(ticker_df) >= 60:
            try:
                indicators = _evaluate_indicators(ticker_df)
                tech_summary = _verdict(indicators)
            except Exception:
                tech_summary = None

        # ── Fetch fundamentals (single yfinance call; drives info + financials) -
        fundamentals = _fetch_fundamentals(ns)
        tk_info      = fundamentals.get("info") or {}
        is_financial = _is_financial(tk_info)

        # ── Fetch ML P(up) for premium users only ─────────────────────────────
        ml_p_up: float | None = None
        if include_premium and len(ticker_df) >= 60:
            ml_p_up = _fetch_ml_pup(ns, ticker_df)

        # ── Build context and scorecard ────────────────────────────────────────
        ctx = ScoreContext(
            ticker=ticker.upper(),
            ohlcv=ticker_df,
            benchmark_ohlcv=bench_df,
            is_financial=is_financial,
            tech_summary=tech_summary,
            info=tk_info or None,
            financials=fundamentals.get("financials"),
            balance_sheet=fundamentals.get("balance_sheet"),
            cash_flow=fundamentals.get("cash_flow"),
            ml_p_up=ml_p_up,
        )

        card = build_scorecard(ctx, include_premium=include_premium)
        return card.to_dict()

    except HTTPException:
        raise
    except ValueError as exc:
        # Return a degraded scorecard rather than a 500
        from core.scorecard.types import Scorecard, PillarResult
        from core.scorecard.pillars import PILLAR_ORDER, PILLAR_LABELS, VERDICTS
        import datetime as dt
        pillars = [
            PillarResult(
                key=k, label=PILLAR_LABELS[k], score=None, grade="N/A",
                verdict=VERDICTS.get((k, "N/A"), "Data unavailable."),
                models=[], coverage=0.0,
            )
            for k in PILLAR_ORDER
        ]
        sc = Scorecard(
            ticker=ticker.upper(),
            as_of=dt.date.today().isoformat(),
            is_financial=False,
            data_warning=str(exc),
            pillars=pillars,
            overall_score=None,
            overall_grade="N/A",
        )
        return sc.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
