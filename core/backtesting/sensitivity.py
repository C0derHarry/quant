"""
Parameter sensitivity grid — no ML or regime filter so results are fast (~10–15 sec).
Sweeps ATR stop multiplier × round-trip transaction cost and records Sharpe.
"""

import warnings
import numpy as np
import pandas as pd
import yfinance as yf
from core.backtesting.engine import run_backtest

warnings.filterwarnings("ignore")

ATR_MULTS = [1.0, 1.5, 2.0, 2.5, 3.0]
COST_BPS  = [5, 10, 15, 20]


def sensitivity_grid(tickers: list[str], weights: dict[str, float], period: str = "2y") -> dict:
    grid: list[list[float]] = []

    for cost in COST_BPS:
        row: list[float] = []
        for atr in ATR_MULTS:
            try:
                result = run_backtest(
                    tickers       = tickers,
                    weights       = weights,
                    period        = period,
                    cost_bps      = cost,
                    atr_stop_mult = atr,
                    ml_signals_df = None,
                    regime_series = None,
                )
                row.append(round(result["metrics"]["sharpe"], 3))
            except Exception:
                row.append(0.0)
        grid.append(row)

    return {
        "x_param":    "atr_mult",
        "x_values":   ATR_MULTS,
        "y_param":    "cost_bps",
        "y_values":   COST_BPS,
        "sharpe_grid": grid,
    }
