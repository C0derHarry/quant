"""Cross-Sectional Momentum (Jegadeesh-Titman 1993 / AQR).

Ranks all stocks by their trailing 12-month return (skipping the most recent month)
and equal-weights the top-N names. Monthly rebalance.

Reference: Jegadeesh & Titman (1993), "Returns to Buying Winners and Selling Losers"
           AQR Capital — The Case for Momentum Investing (2014)
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from .base import Strategy, ParamSpec


class CrossSectionalMomentum(Strategy):
    id          = "cross_sectional_mom"
    label       = "Cross-Sectional Momentum 12-1"
    description = (
        "Ranks stocks by 12-month trailing return (skip past 1 month) and equal-weights the top-N "
        "performers. Rebalances monthly. One of the most robust equity anomalies in academic "
        "literature — validated across 30+ years and multiple markets."
    )
    reference   = "Jegadeesh & Titman (1993) · AQR Momentum White Paper (2014)"
    REQUIRES_FUNDAMENTALS = False

    BASIC_PARAMS = [
        ParamSpec("lookback_months", "int",   12,       "Lookback window",    "Months of return history used to rank stocks (12 = J-T canonical).", min=3, max=36),
        ParamSpec("top_n",           "int",   10,       "Top-N stocks",       "Number of highest-ranked stocks to hold each period.", min=1, max=50),
        ParamSpec("rebalance_freq",  "enum",  "monthly","Rebalance frequency","How often to re-rank and rebalance the portfolio.", choices=["monthly", "quarterly"]),
    ]

    ADVANCED_PARAMS = [
        ParamSpec("skip_months",     "int",   1,   "Skip months",        "Exclude the most recent N months to avoid short-term reversal noise.", min=0, max=3),
        ParamSpec("weighting",       "enum",  "equal", "Weighting",      "How to size positions among selected stocks.", choices=["equal", "inverse_vol"]),
        ParamSpec("vol_lookback",    "int",   20,  "Volatility window",  "Days for realised-volatility estimation (inverse-vol weighting only).", min=5, max=60),
        ParamSpec("max_weight",      "float", 0.20,"Max position",       "Maximum weight allocated to any single stock (concentration cap).", min=0.05, max=1.0),
    ]

    def generate_signals(
        self,
        prices:       pd.DataFrame,
        fundamentals: dict | None,
        params:       dict,
    ) -> pd.DataFrame:
        lookback   = int(params.get("lookback_months", 12))
        skip       = int(params.get("skip_months",     1))
        top_n      = int(params.get("top_n",           10))
        weighting  = str(params.get("weighting",       "equal"))
        vol_lb     = int(params.get("vol_lookback",    20))
        max_w      = float(params.get("max_weight",    0.20))
        freq       = str(params.get("rebalance_freq",  "monthly"))

        # Rebalance dates: last trading day of each month/quarter
        offset    = "ME" if freq == "monthly" else "QE"
        reb_dates = prices.resample(offset).last().index
        reb_dates = reb_dates[reb_dates >= prices.index[0]]
        reb_dates = reb_dates[reb_dates <= prices.index[-1]]

        # Price lag used for signal: shift(1) to avoid look-ahead on the rebalance day
        lagged = prices.shift(1)

        records = {}
        for rdate in reb_dates:
            # Signal window: [rdate - lookback, rdate - skip]  in calendar approximation
            # get_indexer(..., method="pad") replaces the pandas<2.0 get_loc(method="ffill")
            end_idx = lagged.index.get_indexer([rdate], method="pad")[0]
            if end_idx < 0:
                continue
            skip_days     = skip * 21
            lookback_days = lookback * 21
            start_idx = max(0, end_idx - lookback_days)
            skip_end  = max(0, end_idx - skip_days)

            if skip_end <= start_idx:
                continue

            window  = lagged.iloc[start_idx:skip_end]
            valid   = window.dropna(axis=1, how="any")
            if valid.empty or len(valid) < 10:
                continue

            # Momentum score: total return over window
            mom_score = (valid.iloc[-1] / valid.iloc[0]) - 1.0

            ranked = mom_score.nlargest(top_n)
            winners = ranked.index.tolist()

            if not winners:
                continue

            if weighting == "inverse_vol":
                vol_window = lagged[winners].iloc[max(0, end_idx - vol_lb):end_idx]
                daily_vol  = vol_window.pct_change().std()
                inv_vol    = 1.0 / daily_vol.clip(lower=1e-8)
                raw_w      = inv_vol / inv_vol.sum()
            else:
                n    = len(winners)
                raw_w = pd.Series({t: 1.0 / n for t in winners})

            # Apply max weight cap with renormalisation
            raw_w = raw_w.clip(upper=max_w)
            total = raw_w.sum()
            if total > 0:
                raw_w = raw_w / total

            records[rdate] = raw_w

        if not records:
            return pd.DataFrame()

        weights_df = pd.DataFrame(records).T.reindex(columns=prices.columns).fillna(0.0)
        return weights_df
