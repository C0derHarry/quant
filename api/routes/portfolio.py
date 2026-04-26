from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.portfolio import run_optimizer
import numpy as np
import pandas as pd

router = APIRouter()


class OptimizeRequest(BaseModel):
    tickers:              list[str]
    capital:              float = 1_000_000
    user_target_annual:   float = 0.18
    risk_appetite_monthly: float = 0.05
    allow_short:          bool  = False
    invest_mode:          str   = "lump_sum"
    dca_months:           int   = 6
    stop_loss_k:          float = 1.5
    use_ml_signals:       bool  = False


def _safe(v):
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)) and (np.isnan(v) or np.isinf(v)):
        return 0.0
    if isinstance(v, np.floating):
        return float(v)
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, pd.DataFrame):
        return v.fillna(0).to_dict(orient="records")
    if isinstance(v, pd.Series):
        return v.fillna(0).tolist()
    if isinstance(v, dict):
        return {k: _safe(vv) for k, vv in v.items()}
    if isinstance(v, list):
        return [_safe(i) for i in v]
    return v


def _build_ml_views(tickers_ns: list[str]) -> dict:
    """Fetch cached ML model or train fresh; return {ticker_ns: p_up}."""
    import os, joblib, yfinance as yf
    from datetime import date
    from core.signals.ml_signals import MLSignalModel

    cache_dir = os.path.join(os.path.dirname(__file__), "..", "signal_cache")
    os.makedirs(cache_dir, exist_ok=True)
    views = {}

    for ticker_ns in tickers_ns:
        if ticker_ns.startswith("^"):
            continue
        tag  = ticker_ns.replace(".", "_")
        path = os.path.join(cache_dir, f"{tag}_{date.today().isoformat()}.joblib")
        try:
            df = yf.download(ticker_ns, period="2y", auto_adjust=True, progress=False)
            if df.empty:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            if os.path.exists(path):
                model = joblib.load(path)
            else:
                model = MLSignalModel()
                model.fit(df, verbose=False)
                try:
                    joblib.dump(model, path)
                except Exception:
                    pass

            views[ticker_ns] = model.latest_signal(df)["p_up"]
        except Exception as e:
            print(f"ml_views error for {ticker_ns}: {e}")

    return views


@router.post("/optimize")
def optimize(req: OptimizeRequest):
    try:
        tickers = [t if t.startswith("^") or "." in t else f"{t}.NS" for t in req.tickers]

        ml_views = None
        if req.use_ml_signals:
            try:
                ml_views = _build_ml_views(tickers)
            except Exception as e:
                print(f"ML views failed, proceeding without: {e}")

        raw = run_optimizer(
            tickers               = tickers,
            capital               = req.capital,
            user_target_annual    = req.user_target_annual,
            risk_appetite_monthly = req.risk_appetite_monthly,
            allow_short           = req.allow_short,
            invest_mode           = req.invest_mode,
            dca_months            = req.dca_months,
            stop_loss_k           = req.stop_loss_k,
            ml_views              = ml_views,
        )

        # Build stop loss table
        stop_rows = []
        for ticker, sd in raw["stop_data"].items():
            regime      = raw["regimes"][ticker]["regime"]
            regime_probs = raw["regimes"][ticker].get("regime_probs", {})
            bl_ret      = float(raw["bl_returns"].get(ticker, 0))
            stop_rows.append({
                "ticker":      ticker,
                "regime":      regime,
                "regime_probs": _safe(regime_probs),
                "bl_return":   round(bl_ret * 100, 2),
                "weight":      round(float(sd["weight_pct"]), 2),
                "allocation":  round(float(sd["allocation"]), 0),
                "shares":      round(float(sd["shares"]), 4),
                "entry_price": round(float(sd["entry_price"]), 2),
                "stop_price":  round(float(sd["stop_price"]), 2),
                "stop_pct":    round(float(sd["stop_pct"]), 3),
                "daily_sigma": round(float(sd["daily_sigma_pct"]), 3),
                "at_risk":     round(float(sd["risk_per_position"]), 0),
                "is_short":    bool(sd["is_short"]),
            })

        # Regime warnings
        warnings = []
        for ticker in req.tickers:
            r       = raw["regimes"].get(ticker, {})
            current = r.get("regime", "")
            trans   = r.get("transition_probs", {})
            others  = {k: v for k, v in trans.items() if k != current}
            if others:
                top_shift = max(others, key=others.get)
                if others[top_shift] > 0.25:
                    warnings.append({
                        "ticker":     ticker,
                        "current":    current,
                        "shift_to":   top_shift,
                        "probability": round(others[top_shift], 3),
                    })

        # DCA schedule
        dca_rows = []
        if raw["dca_df"] is not None:
            dca_rows = _safe(raw["dca_df"])

        pm = raw["portfolio_metrics"]
        return {
            "metrics": {
                "annual_return":  round(float(pm["annual_return"]) * 100, 2),
                "annual_vol":     round(float(pm["annual_vol"]) * 100, 2),
                "sharpe":         round(float(pm["sharpe"]), 3),
                "monthly_var_95": round(float(pm["monthly_var_95"]) * 100, 2),
                "mc_var":         round(abs(float(pm["mc_var"])) * 100, 2),
                "mc_cvar":        round(abs(float(pm["mc_cvar"])) * 100, 2),
                "t_df":           round(float(pm["t_df"]), 2),
            },
            "weights":       _safe(raw["weights"]),
            "stop_table":    stop_rows,
            "warnings":      warnings,
            "dca_schedule":  dca_rows,
            "dcc_a":         round(float(raw["dcc"]["dcc_a"]), 4),
            "dcc_b":         round(float(raw["dcc"]["dcc_b"]), 4),
            "ml_adjusted":   ml_views is not None and len(ml_views) > 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
