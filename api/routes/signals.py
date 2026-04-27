import os
from datetime import date

import joblib
import numpy as np
import pandas as pd
import yfinance as yf
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sklearn.calibration import calibration_curve

from core.signals.ml_signals import MLSignalModel

router = APIRouter()

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "signal_cache")
os.makedirs(CACHE_DIR, exist_ok=True)


class SignalRequest(BaseModel):
    tickers:         list[str]
    period:          str   = "2y"
    long_threshold:  float = 0.60
    short_threshold: float = 0.40


def _normalize(ticker: str) -> str:
    if ticker.endswith((".NS", ".BO")) or ticker.startswith("^"):
        return ticker
    return ticker + ".NS"


def _cache_path(ticker_ns: str) -> str:
    tag = ticker_ns.replace(".", "_")
    return os.path.join(CACHE_DIR, f"{tag}_{date.today().isoformat()}.joblib")


def _confidence_bin(p_up: float, long_thr: float, short_thr: float) -> str:
    if p_up >= 0.70:
        return "High Conviction Long"
    if p_up >= long_thr:
        return "Long"
    if p_up <= 0.30:
        return "High Conviction Short"
    if p_up <= short_thr:
        return "Short"
    return "Neutral"


def _fit_or_load(ticker_ns: str, df: pd.DataFrame) -> MLSignalModel:
    path = _cache_path(ticker_ns)
    if os.path.exists(path):
        try:
            return joblib.load(path)
        except Exception:
            pass
    model = MLSignalModel()
    model.fit(df, verbose=False)
    try:
        joblib.dump(model, path)
    except Exception:
        pass
    return model


@router.post("/analyze")
def analyze(req: SignalRequest):
    if not req.tickers:
        raise HTTPException(status_code=400, detail="At least one ticker required")

    results = {}

    for raw_ticker in req.tickers:
        ticker_ns   = _normalize(raw_ticker)
        ticker_bare = raw_ticker.replace(".NS", "").replace(".BO", "")

        try:
            df = yf.download(ticker_ns, period=req.period, auto_adjust=True, progress=False)
            if df.empty:
                raise ValueError(f"No data returned for {ticker_ns}")

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            model = _fit_or_load(ticker_ns, df)

            sig_df  = model.signal(df, req.long_threshold, req.short_threshold)
            latest  = model.latest_signal(df)
            fi      = model.feature_importance(top_n=10)

            # Calibration curve
            prob_true, prob_pred = calibration_curve(
                model._y_test, model._test_proba, n_bins=10, strategy="uniform"
            )
            calibration = [
                {"predicted": float(pp), "actual": float(pt)}
                for pp, pt in zip(prob_pred, prob_true)
            ]

            # Feature importances
            importances = [
                {"feature": feat, "importance": round(float(imp), 5)}
                for feat, imp in fi.items()
            ]

            # Signal history - last 30 rows
            hist = sig_df.tail(30).copy()
            hist.index = hist.index.strftime("%Y-%m-%d")
            history = [
                {
                    "date":   idx,
                    "p_up":   round(float(row["p_up"]), 4),
                    "signal": int(row["signal"]),
                    "regime": row["regime"],
                }
                for idx, row in hist.iterrows()
            ]

            results[ticker_bare] = {
                "p_up":                round(float(latest["p_up"]), 4),
                "signal":              int(latest["signal"]),
                "regime":              latest["regime"],
                "confidence_bin":      _confidence_bin(latest["p_up"], req.long_threshold, req.short_threshold),
                "metrics":             model.metrics,
                "feature_importances": importances,
                "calibration":         calibration,
                "signal_history":      history,
            }

        except Exception as e:
            print(f"signals error for {raw_ticker}: {e}")
            results[ticker_bare] = {"error": str(e)}

    return results
