"""KPI calculations for backtest results."""
from __future__ import annotations
import numpy as np
import pandas as pd


def _annual_factor(returns: pd.Series) -> float:
    """Infer annualisation factor from return frequency (assumed daily trading days)."""
    return 252.0


def cagr(equity: pd.Series) -> float:
    if len(equity) < 2:
        return 0.0
    years = len(equity) / 252.0
    if years <= 0:
        return 0.0
    ratio = equity.iloc[-1] / equity.iloc[0]
    if ratio <= 0:
        return -1.0
    return float(ratio ** (1 / years) - 1)


def sharpe(returns: pd.Series, rfr: float = 0.065) -> float:
    """Sharpe ratio assuming daily returns, rfr is annualised Indian risk-free rate."""
    if returns.std() == 0 or len(returns) < 20:
        return 0.0
    daily_rfr = rfr / 252
    excess    = returns - daily_rfr
    return float(np.sqrt(252) * excess.mean() / excess.std())


def sortino(returns: pd.Series, rfr: float = 0.065) -> float:
    if len(returns) < 20:
        return 0.0
    daily_rfr  = rfr / 252
    excess     = returns - daily_rfr
    downside   = excess[excess < 0]
    if len(downside) < 5 or downside.std() == 0:
        return 0.0
    return float(np.sqrt(252) * excess.mean() / downside.std())


def max_drawdown(equity: pd.Series) -> float:
    roll_max = equity.cummax()
    dd       = (equity - roll_max) / roll_max
    return float(dd.min())


def drawdown_series(equity: pd.Series) -> pd.Series:
    roll_max = equity.cummax()
    return (equity - roll_max) / roll_max


def hit_rate(trade_rets: list[float]) -> float:
    if not trade_rets:
        return 0.0
    return float(sum(r > 0 for r in trade_rets) / len(trade_rets))


def turnover(weights_df: pd.DataFrame) -> float:
    """Average one-way turnover per rebalance."""
    if len(weights_df) < 2:
        return 0.0
    diffs = weights_df.diff().iloc[1:].abs().sum(axis=1)
    return float(diffs.mean())


def compute_all(
    equity:     pd.Series,
    benchmark:  pd.Series,
    weights_df: pd.DataFrame,
    trade_rets: list[float],
    total_cost: float,
) -> dict:
    returns   = equity.pct_change().dropna()
    bench_ret = benchmark.pct_change().dropna()

    alpha = float(cagr(equity) - cagr(benchmark))

    # Calmar ratio
    mdd = max_drawdown(equity)
    calmar = float(cagr(equity) / abs(mdd)) if mdd < 0 else 0.0

    return {
        "cagr":           round(cagr(equity) * 100, 2),
        "benchmark_cagr": round(cagr(benchmark) * 100, 2),
        "alpha":          round(alpha * 100, 2),
        "sharpe":         round(sharpe(returns), 3),
        "sortino":        round(sortino(returns), 3),
        "calmar":         round(calmar, 3),
        "max_drawdown":   round(mdd * 100, 2),
        "hit_rate":       round(hit_rate(trade_rets) * 100, 1),
        "avg_turnover":   round(turnover(weights_df) * 100, 2),
        "total_cost_inr": round(total_cost, 2),
        "n_trades":       len(trade_rets),
        "n_rebalances":   len(weights_df),
    }
