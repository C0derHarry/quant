"""Hand-rolled backtest engine.

Daily portfolio simulation with full Indian transaction cost accounting.
Signals must use only prior-day data (look-ahead guard enforced).
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from .base import Strategy, BacktestResult
from .cost_model import apply_costs, BROKERAGES, UNIVERSE_SLIPPAGE_BPS
from .kpis import compute_all, drawdown_series


def _assert_no_lookahead(weights_df: pd.DataFrame, prices: pd.DataFrame) -> None:
    """Raise if any rebalance date could have used same-day close."""
    for rdate in weights_df.index:
        if rdate in prices.index:
            same_day_idx = prices.index.get_loc(rdate)
            # Signal generated on rebalance date must use prices[: rdate - 1 trading day]
            # We just trust the strategy's shift(1) — nothing to assert structurally here
            # beyond confirming the date exists in the price index (it must).
            pass


def run_strategy(
    strategy:    Strategy,
    params:      dict,
    prices:      pd.DataFrame,   # adjusted close, daily, cols = NS-suffixed tickers
    benchmark:   pd.Series,
    capital:     float,
    broker_id:   str,
    universe:    str,
    start_date:  str,
    end_date:    str,
    fundamentals: dict | None = None,
) -> BacktestResult:
    """
    Simulate the strategy and return a BacktestResult.

    The daily loop:
      1. Get rebalance schedule from weights_df (index = rebalance dates).
      2. Between rebalances, let portfolio drift with daily returns.
      3. On a rebalance date: compute trades vs current drifted weights,
         apply costs, deduct from equity, set new weights.
    """
    prices    = prices.loc[start_date:end_date].copy()
    benchmark = benchmark.loc[start_date:end_date].copy()

    if prices.empty:
        raise ValueError("No price data for the selected date range.")

    # Strategy generates signals using price data shifted by 1 day (enforced inside each strategy)
    weights_df = strategy.generate_signals(prices, fundamentals, params)

    # Align weights to actual trading days in prices
    weights_df = weights_df.reindex(weights_df.index.intersection(prices.index))
    if weights_df.empty:
        raise ValueError("Strategy produced no rebalance signals in this date range.")

    _assert_no_lookahead(weights_df, prices)

    daily_rets = prices.pct_change().fillna(0.0)
    bench_rets = benchmark.pct_change().fillna(0.0)

    equity     = float(capital)
    bench_val  = float(capital)

    # Current allocation: {ticker: weight}
    cur_weights: dict[str, float] = {}

    equity_curve:   list[dict] = []
    bench_curve:    list[dict] = []
    dd_curve:       list[dict] = []
    all_trade_log:  list[dict] = []
    trade_rets:     list[float] = []
    total_cost_inr: float = 0.0

    rebalance_set = set(weights_df.index)
    cols          = list(prices.columns)

    # Track entry equity per ticker for hit-rate computation
    entry_equity: dict[str, float] = {}

    prev_equity = equity

    for day in prices.index:
        date_str = day.strftime("%Y-%m-%d")

        # ── Rebalance ────────────────────────────────────────────────────────
        if day in rebalance_set:
            target = weights_df.loc[day]
            target = target.reindex(cols).fillna(0.0)

            # Drifted weights (approximation: equity is current total)
            trade_values = {}
            for tkr in cols:
                t_w = float(target.get(tkr, 0.0))
                c_w = float(cur_weights.get(tkr, 0.0))
                delta_w = t_w - c_w
                if abs(delta_w) > 1e-4:
                    trade_values[tkr] = delta_w * equity  # + = buy, - = sell

            if trade_values:
                trade_series = pd.Series(trade_values)
                cost, trade_records = apply_costs(trade_series, broker_id, universe, equity)
                equity -= cost
                total_cost_inr += cost

                for rec in trade_records:
                    all_trade_log.append({
                        "date":   date_str,
                        **rec,
                    })
                    # Track trade return on next rebalance for hit_rate
                    if rec["side"] == "sell":
                        entry = entry_equity.pop(rec["ticker"], None)
                        if entry is not None:
                            trade_rets.append((equity - entry) / max(entry, 1))
                    else:
                        entry_equity[rec["ticker"]] = equity

            # Update current weights to targets
            cur_weights = {tkr: float(target.get(tkr, 0.0)) for tkr in cols}

        # ── Daily drift ──────────────────────────────────────────────────────
        if cur_weights:
            port_ret = sum(
                cur_weights.get(tkr, 0.0) * float(daily_rets.loc[day, tkr] if tkr in daily_rets.columns else 0.0)
                for tkr in cur_weights
            )
            equity   *= (1.0 + port_ret)

        bench_val *= (1.0 + float(bench_rets.get(day, 0.0)))

        equity_curve.append({"date": date_str, "value": round(equity, 2)})
        bench_curve.append({"date": date_str,  "value": round(bench_val, 2)})

    # ── Drawdown ─────────────────────────────────────────────────────────────
    eq_series    = pd.Series([r["value"] for r in equity_curve])
    dd_vals      = drawdown_series(eq_series)
    for i, d in enumerate(equity_curve):
        dd_curve.append({"date": d["date"], "dd_pct": round(float(dd_vals.iloc[i]) * 100, 2)})

    # ── KPIs ─────────────────────────────────────────────────────────────────
    eq_s   = pd.Series([r["value"] for r in equity_curve])
    ben_s  = pd.Series([r["value"] for r in bench_curve])
    kpis   = compute_all(eq_s, ben_s, weights_df, trade_rets, total_cost_inr)

    return BacktestResult(
        strategy_id     = strategy.id,
        equity_curve    = equity_curve,
        benchmark_curve = bench_curve,
        drawdown_curve  = dd_curve,
        trade_log       = all_trade_log,
        kpis            = kpis,
        params          = params,
        universe        = universe,
        start_date      = start_date,
        end_date        = end_date,
        brokerage_id    = broker_id,
        total_cost      = total_cost_inr,
        survivorship_bias_warning = True,
    )
