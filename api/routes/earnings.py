import pandas as pd
import yfinance as yf
from fastapi import APIRouter, HTTPException

router = APIRouter()


def _safe_float(val) -> float | None:
    try:
        f = float(val)
        return None if (f != f) else round(f, 4)
    except Exception:
        return None


@router.get("/surprise")
def earnings_surprise(ticker: str, quarters: int = 8):
    ns = ticker if ticker.endswith((".NS", ".BO")) else ticker + ".NS"
    stock = yf.Ticker(ns)
    rows = []

    # Primary: earnings_history has epsActual, epsEstimate, surprisePercent
    try:
        eh = stock.earnings_history
        if eh is not None and not eh.empty:
            now  = pd.Timestamp.now()
            past = eh[eh.index <= now].sort_index(ascending=False).head(quarters)
            for date, row in past.iterrows():
                actual   = _safe_float(row.get("epsActual"))
                est      = _safe_float(row.get("epsEstimate"))
                surp_raw = _safe_float(row.get("surprisePercent"))
                surp     = round(surp_raw * 100, 2) if surp_raw is not None else None
                beat     = (actual >= est) if (actual is not None and est is not None) else None
                rows.append({
                    "quarter":       date.strftime("%b '%y"),
                    "actual_eps":    actual,
                    "estimated_eps": est,
                    "surprise_pct":  surp,
                    "beat":          beat,
                })
    except Exception:
        pass

    # Fallback: derive EPS from quarterly income stmt + shares outstanding
    if not rows:
        try:
            qi     = stock.quarterly_income_stmt
            ni_key = next((k for k in qi.index if "Net Income" in str(k)), None)
            info   = stock.info
            shares = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
            if ni_key and shares:
                for date, val in list(qi.loc[ni_key].items())[:quarters]:
                    if pd.notna(val):
                        rows.append({
                            "quarter":       date.strftime("%b '%y"),
                            "actual_eps":    round(float(val) / float(shares), 4),
                            "estimated_eps": None,
                            "surprise_pct":  None,
                            "beat":          None,
                        })
        except Exception:
            pass

    # Oldest quarter first (left-to-right on chart)
    rows = list(reversed(rows))

    beat_vals = [r["beat"] for r in rows if r["beat"] is not None]
    beat_rate = round(sum(beat_vals) / len(beat_vals) * 100) if beat_vals else None

    surprises = [r["surprise_pct"] for r in rows if r["surprise_pct"] is not None]
    avg_surp  = round(sum(surprises) / len(surprises), 2) if surprises else None

    latest = rows[-1] if rows else {}
    return {
        "quarters":           rows,
        "beat_rate":          beat_rate,
        "avg_surprise_pct":   avg_surp,
        "has_estimates":      any(r["estimated_eps"] is not None for r in rows),
        "latest_beat":        latest.get("beat"),
        "latest_surprise_pct": latest.get("surprise_pct"),
    }
