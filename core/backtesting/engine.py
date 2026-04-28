"""
Vectorised backtest engine.
All signal/weight computation is done as DataFrame column operations — no row loops.
"""

import numpy as np
import pandas as pd
import yfinance as yf
import warnings
from core.signals.technical_indicators import ATR

warnings.filterwarnings("ignore")
BENCHMARK_TICKER = "^NSEI"


def _download_ohlcv(tickers: list[str], period: str) -> dict[str, pd.DataFrame]:
    """Download OHLCV per ticker; returns {ticker: OHLCV DataFrame}."""
    all_tickers = list(set(tickers + [BENCHMARK_TICKER]))
    raw = yf.download(all_tickers, period=period, auto_adjust=True, progress=False)
    result = {}
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col not in raw.columns.get_level_values(0):
            continue
    for ticker in all_tickers:
        try:
            if isinstance(raw.columns, pd.MultiIndex):
                df = raw.xs(ticker, axis=1, level=1).dropna(how="all")
            else:
                df = raw.dropna(how="all")
            if not df.empty:
                result[ticker] = df
        except Exception:
            pass
    return result


def _atr_stops(ohlcv: pd.DataFrame, mult: float, lookback: int = 20) -> pd.Series:
    """Returns a boolean Series: True on days the ATR stop is triggered."""
    if ohlcv.empty or len(ohlcv) < 15:
        return pd.Series(False, index=ohlcv.index)
    atr_df   = ATR(ohlcv, period=14)
    atr_vals = atr_df["ATR"].reindex(ohlcv.index).ffill()
    high_water = ohlcv["Close"].rolling(lookback, min_periods=1).max()
    stopped    = ohlcv["Close"] < (high_water - mult * atr_vals)
    return stopped.fillna(False)


def run_backtest(
    tickers:        list[str],
    weights:        dict[str, float],
    period:         str   = "2y",
    cost_bps:       int   = 10,
    atr_stop_mult:  float = 2.0,
    ml_signals_df:  pd.DataFrame | None = None,   # date × ticker, P(up) values
    regime_series:  pd.Series   | None = None,    # date → regime label string
) -> dict:
    ohlcv_map = _download_ohlcv(tickers, period)

    # Align close prices
    close_frames = {}
    for t in tickers:
        if t in ohlcv_map:
            close_frames[t] = ohlcv_map[t]["Close"]
    if not close_frames:
        raise ValueError("No price data available for backtesting.")

    prices   = pd.DataFrame(close_frames).dropna(how="all").ffill().dropna()
    log_rets = np.log(prices / prices.shift(1)).dropna()

    # Benchmark
    bench_ret = pd.Series(dtype=float)
    if BENCHMARK_TICKER in ohlcv_map:
        bp = ohlcv_map[BENCHMARK_TICKER]["Close"].reindex(log_rets.index).ffill()
        bench_ret = np.log(bp / bp.shift(1)).fillna(0)

    # Build weight matrix (date × ticker)
    w_raw   = {t: weights.get(t, 0.0) for t in tickers if t in log_rets.columns}
    w_total = sum(w_raw.values())
    w_norm  = {t: v / w_total for t, v in w_raw.items()} if w_total > 0 else w_raw
    w_mat   = pd.DataFrame(
        {t: w_norm.get(t, 0.0) for t in log_rets.columns},
        index=log_rets.index,
    )

    # Apply ML signal filter: zero weight when P(up) < 0.50
    if ml_signals_df is not None:
        ml_align = ml_signals_df.reindex(index=log_rets.index, columns=log_rets.columns).ffill().fillna(0.5)
        w_mat    = w_mat.where(ml_align >= 0.50, 0.0)

    # Apply regime filter: go to cash on Bear regime days
    days_in_cash = 0
    if regime_series is not None:
        bear_mask = regime_series.reindex(log_rets.index).ffill() == "Bear"
        w_mat[bear_mask] = 0.0
        days_in_cash = int(bear_mask.sum())

    # ATR-based stops per ticker
    days_stopped = 0
    for t in log_rets.columns:
        if t not in ohlcv_map:
            continue
        stop_mask = _atr_stops(ohlcv_map[t].reindex(log_rets.index).ffill(), atr_stop_mult)
        # Once stopped, stay out for 5 days
        stop_expanded = stop_mask.copy()
        for shift in range(1, 5):
            stop_expanded = stop_expanded | stop_mask.shift(shift, fill_value=False)
        w_mat.loc[stop_expanded, t] = 0.0
        days_stopped += int(stop_expanded.sum())

    # Compute portfolio daily returns
    port_ret = (w_mat * log_rets).sum(axis=1)

    # Transaction costs: charge on days where effective weight changes significantly
    prev_w   = w_mat.shift(1).fillna(0)
    turnover = (w_mat - prev_w).abs().sum(axis=1)
    cost_day = (turnover > 0.01) * (cost_bps / 10000)
    port_ret = port_ret - cost_day

    # Equity curves (normalised to 100)
    equity    = 100 * np.exp(port_ret.cumsum())
    bench_cum = 100 * np.exp(bench_ret.reindex(port_ret.index).fillna(0).cumsum())

    # Drawdown
    running_max = equity.cummax()
    drawdown    = (equity - running_max) / running_max * 100

    # Metrics
    n_days      = len(port_ret)
    total_ret   = float(equity.iloc[-1] / 100 - 1) * 100
    annual_ret  = float(port_ret.mean() * 252) * 100
    annual_vol  = float(port_ret.std() * np.sqrt(252)) * 100
    rf          = 6.5  # annualised %
    sharpe      = (annual_ret - rf) / annual_vol if annual_vol > 0 else 0.0
    max_dd      = float(drawdown.min())
    calmar      = annual_ret / abs(max_dd) if max_dd != 0 else 0.0
    bench_total = float(bench_cum.iloc[-1] / 100 - 1) * 100
    alpha       = total_ret - bench_total

    equity_curve = [
        {"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 2), "benchmark": round(float(bench_cum.get(d, 100)), 2)}
        for d, v in equity.items()
    ]
    dd_series = [
        {"date": d.strftime("%Y-%m-%d"), "drawdown_pct": round(float(v), 3)}
        for d, v in drawdown.items()
    ]

    return {
        "equity_curve": equity_curve,
        "drawdown":     dd_series,
        "metrics": {
            "total_return":     round(total_ret, 2),
            "annual_return":    round(annual_ret, 2),
            "annual_vol":       round(annual_vol, 2),
            "sharpe":           round(sharpe, 3),
            "max_drawdown":     round(max_dd, 2),
            "calmar":           round(calmar, 3),
            "benchmark_return": round(bench_total, 2),
            "alpha":            round(alpha, 2),
        },
        "trades": {
            "days_in_cash_pct":  round(days_in_cash / n_days * 100, 1) if n_days else 0,
            "days_stopped_pct":  round(days_stopped / (n_days * len(tickers)) * 100, 1) if n_days else 0,
            "turnover_pct":      round(float(turnover.mean()) * 100, 2),
        },
    }
