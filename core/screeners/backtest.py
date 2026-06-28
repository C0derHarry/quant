"""
Minimal swing-screener expectancy harness (P4 #11).

Walk-forward simulation over available OHLCV history:
  For each stock × bar (from bar 60 onwards after indicator warm-up):
    - Simulate the signal detectors on df[:i]
    - Record (symbol, signal_date, setup_type, entry, forward return at N days)
  Aggregate: win-rate, avg winner, avg loser, expectancy per R.

Usage (standalone, not called by run_scan):

    from core.data.fetcher import fetch_ohlcv_data
    from core.data.universe import get_nifty500
    from core.screeners.backtest import run_expectancy_backtest

    universe   = get_nifty500()
    yf_symbols = [s["yf_symbol"] for s in universe[:50]]  # subset for speed
    ohlcv      = fetch_ohlcv_data(yf_symbols, days=730, interval="1d")
    ohlcv_plain = {k.replace(".NS", ""): v for k, v in ohlcv.items()}
    stats = run_expectancy_backtest(ohlcv_plain, hold_days=10)
    print(stats)
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

from core.screeners.swing import compute_indicators, _trend_ok, _vcp_breakout, _pullback_ema, _ema_cross_trend

logger = logging.getLogger(__name__)

_MIN_WARM_UP = 60   # bars needed before signals can fire


def _simulate_one(df: pd.DataFrame, hold_days: int) -> list[dict]:
    """
    Walk bar-by-bar through df; return a list of trade records.
    Each record: {bar_idx, setup_type, entry, exit, return_pct, win}.
    """
    trades = []
    # We need hold_days bars after the signal, so stop early
    for i in range(_MIN_WARM_UP, len(df) - hold_days):
        window = df.iloc[:i + 1].copy()
        window = compute_indicators(window)

        trend_ok, _ = _trend_ok(window)
        if not trend_ok:
            continue

        setup_type: str | None = None
        pivot: float | None    = None

        vcp_ok, vcp_piv = _vcp_breakout(window)
        if vcp_ok and vcp_piv is not None:
            setup_type, pivot = "breakout", vcp_piv
        else:
            pull_ok, pull_piv = _pullback_ema(window)
            if pull_ok and pull_piv is not None:
                setup_type, pivot = "pullback", pull_piv
            else:
                ema_ok, ema_piv = _ema_cross_trend(window)
                if ema_ok and ema_piv is not None:
                    setup_type, pivot = "trend_continuation", ema_piv

        if setup_type is None:
            continue

        entry  = float(df["Close"].iloc[i])
        future = float(df["Close"].iloc[i + hold_days])
        ret    = (future - entry) / entry

        trades.append({
            "date":       df.index[i],
            "setup_type": setup_type,
            "entry":      entry,
            "exit":       future,
            "return_pct": round(ret * 100, 2),
            "win":        ret > 0,
        })

    return trades


def run_expectancy_backtest(
    ohlcv_plain: dict[str, pd.DataFrame],
    hold_days: int = 10,
) -> dict[str, Any]:
    """
    Aggregate expectancy stats over all stocks and historical bars.

    Returns:
        {
          total_trades, win_rate, avg_win_pct, avg_loss_pct,
          expectancy_pct,            # avg_win*WR - avg_loss*(1-WR)
          by_setup: {setup_type: {count, win_rate, expectancy_pct}}
        }
    """
    all_trades: list[dict] = []

    for sym, df in ohlcv_plain.items():
        if len(df) < _MIN_WARM_UP + hold_days + 10:
            continue
        try:
            trades = _simulate_one(df, hold_days)
            all_trades.extend(trades)
        except Exception as e:
            logger.debug("backtest error for %s: %s", sym, e)

    if not all_trades:
        return {"total_trades": 0, "error": "no trades found"}

    df_t = pd.DataFrame(all_trades)
    wins  = df_t[df_t["win"]]
    losses = df_t[~df_t["win"]]

    wr       = len(wins) / len(df_t)
    avg_win  = float(wins["return_pct"].mean()) if not wins.empty else 0.0
    avg_loss = float(losses["return_pct"].mean()) if not losses.empty else 0.0
    expect   = round(avg_win * wr + avg_loss * (1 - wr), 2)

    by_setup: dict[str, dict] = {}
    for st in df_t["setup_type"].unique():
        sub = df_t[df_t["setup_type"] == st]
        sub_wins = sub[sub["win"]]
        sub_loss = sub[~sub["win"]]
        st_wr   = len(sub_wins) / len(sub)
        st_aw   = float(sub_wins["return_pct"].mean()) if not sub_wins.empty else 0.0
        st_al   = float(sub_loss["return_pct"].mean()) if not sub_loss.empty else 0.0
        by_setup[st] = {
            "count":        len(sub),
            "win_rate":     round(st_wr, 3),
            "expectancy_pct": round(st_aw * st_wr + st_al * (1 - st_wr), 2),
        }

    return {
        "total_trades":  len(df_t),
        "win_rate":      round(wr, 3),
        "avg_win_pct":   round(avg_win, 2),
        "avg_loss_pct":  round(avg_loss, 2),
        "expectancy_pct": expect,
        "by_setup":       by_setup,
    }
