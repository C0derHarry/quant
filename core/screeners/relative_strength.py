"""
Relative Strength (RS) ranking vs NIFTY 50.

Each stock's composite RS ratio = weighted average of (stock_return / nifty_return)
over 1-month / 3-month / 6-month windows. Cross-sectional percentile rank is computed
across all liquid universe members and used as both a hard filter (≥ 60) and the
dominant term in the composite score.
"""

import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_WINDOWS  = [21, 63, 126]   # 1m, 3m, 6m in trading days
_WEIGHTS  = [0.2, 0.35, 0.45]  # longer periods weigh more — sustained leaders


def _period_return(df: pd.DataFrame, window: int) -> float | None:
    closes = df["Close"].dropna()
    if len(closes) < window + 1:
        return None
    return float(closes.iloc[-1] / closes.iloc[-(window + 1)] - 1)


def compute_rs_scores(
    ohlcv_plain: dict[str, pd.DataFrame],
    nifty_df: pd.DataFrame | None,
) -> dict[str, dict]:
    """
    Return {symbol: {"rs_ratio": float, "rs_rank": float (0–100)}}.

    If nifty_df is None (data unavailable), rs_ratio = stock's own composite
    return (still enables cross-sectional ranking, but without benchmark context).
    """
    if nifty_df is None:
        logger.warning("NIFTY benchmark unavailable — RS computed as absolute momentum")

    nifty_returns: dict[int, float | None] = {}
    if nifty_df is not None:
        for w in _WINDOWS:
            nifty_returns[w] = _period_return(nifty_df, w)

    raw_scores: dict[str, float] = {}

    for sym, df in ohlcv_plain.items():
        if sym == "^NSEI":
            continue
        composite = 0.0
        total_weight = 0.0
        for w, wt in zip(_WINDOWS, _WEIGHTS):
            sr = _period_return(df, w)
            if sr is None:
                continue
            if nifty_df is not None:
                nr = nifty_returns.get(w)
                if nr is None or nr == 0:
                    continue
                composite += wt * (sr / abs(nr))
            else:
                composite += wt * sr
            total_weight += wt
        if total_weight > 0:
            raw_scores[sym] = composite / total_weight

    if not raw_scores:
        return {}

    vals = np.array(list(raw_scores.values()))

    return {
        sym: {
            "rs_ratio": round(score, 4),
            "rs_rank": round(float(np.mean(vals <= score) * 100), 1),
        }
        for sym, score in raw_scores.items()
    }
