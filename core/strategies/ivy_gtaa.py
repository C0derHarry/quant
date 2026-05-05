"""Ivy Portfolio / GTAA — Faber 10-Month Moving Average.

Each month, hold an asset only if its price is above its N-month simple moving average.
Otherwise, hold cash/bonds. Equal weight among qualifying assets.

Reference: Faber, Mebane T. (2007) — "A Quantitative Approach to Tactical Asset Allocation"
           SSRN: https://ssrn.com/abstract=962461
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from .base import Strategy, ParamSpec

# Default 5-asset universe (used when tickers not overridden)
DEFAULT_ASSETS = [
    "^NSEI",       # NIFTY 50 (Indian large-cap equity)
    "NIFTYMID150.NS",  # NIFTY Midcap 150
    "GOLDBEES.NS", # Gold ETF (Nippon India)
    "LIQUIDBEES.NS",   # Liquid BeES (money market proxy)
    "JUNIORBEES.NS",   # NIFTY Next 50
]


class IvyGTAA(Strategy):
    id          = "ivy_gtaa"
    label       = "Ivy Portfolio / GTAA"
    description = (
        "Holds a fixed set of diversified assets equally weighted when each is above its "
        "10-month moving average; moves to cash otherwise. Inspired by Harvard and Yale "
        "endowment asset allocation. Delivers equity-like returns with much lower drawdowns."
    )
    reference   = "Faber (2007) — SSRN 962461 · Cambria GTAA ETF"
    REQUIRES_FUNDAMENTALS = False

    BASIC_PARAMS = [
        ParamSpec("ma_months",   "int",  10,       "MA period (months)", "Simple moving average lookback in months. Faber's canonical value is 10.", min=3, max=24),
        ParamSpec("check_freq",  "enum", "monthly","Check frequency",     "How often to compare price to MA and potentially rebalance.", choices=["monthly", "weekly"]),
    ]

    ADVANCED_PARAMS = [
        ParamSpec("cash_ticker",  "enum", "LIQUIDBEES.NS", "Cash proxy",
                  "Asset to hold when a position is moved to cash.",
                  choices=["LIQUIDBEES.NS", "CGSIBF.NS", "^NSEI"]),
        ParamSpec("assets",       "enum", "default", "Asset universe",
                  "Comma-separated list of tickers. Use 'default' for the 5-asset Faber set.",
                  choices=["default"]),
        ParamSpec("min_assets_in", "int", 1, "Minimum assets in",
                  "Minimum number of assets that must be above the MA to deploy capital (else go all-cash).",
                  min=1, max=5),
    ]

    def generate_signals(
        self,
        prices:       pd.DataFrame,
        fundamentals: dict | None,
        params:       dict,
    ) -> pd.DataFrame:
        ma_months    = int(params.get("ma_months",    10))
        check_freq   = str(params.get("check_freq",   "monthly"))
        cash_ticker  = str(params.get("cash_ticker",  "LIQUIDBEES.NS"))
        min_in       = int(params.get("min_assets_in", 1))

        ma_days = ma_months * 21  # approximate trading days per month

        # Rebalance / check dates
        offset    = "ME" if check_freq == "monthly" else "W-FRI"
        reb_dates = prices.resample(offset).last().index
        reb_dates = reb_dates[reb_dates >= prices.index[0]]
        reb_dates = reb_dates[reb_dates <= prices.index[-1]]

        # Asset columns available in price data (exclude cash proxy if not in prices)
        asset_cols = [c for c in prices.columns if c != cash_ticker]

        # Signal uses previous day's price to avoid look-ahead
        lagged = prices.shift(1)

        records = {}
        for rdate in reb_dates:
            idx = lagged.index.get_indexer([rdate], method="pad")[0]
            if idx < 0:
                continue

            if idx < ma_days:
                continue

            row   = lagged.iloc[idx]
            ma_w  = lagged.iloc[max(0, idx - ma_days):idx]

            assets_in = []
            for col in asset_cols:
                if col not in row.index or pd.isna(row[col]):
                    continue
                if len(ma_w[col].dropna()) < ma_days // 2:
                    continue
                sma = ma_w[col].mean()
                if row[col] > sma:
                    assets_in.append(col)

            target: dict[str, float] = {}

            if len(assets_in) < min_in:
                # All-cash: put everything in cash proxy if available
                if cash_ticker in prices.columns:
                    target[cash_ticker] = 1.0
            else:
                eq_w = 1.0 / len(asset_cols)  # equal weight across the full basket
                for col in asset_cols:
                    if col in assets_in:
                        target[col] = eq_w
                    elif cash_ticker in prices.columns:
                        target[cash_ticker] = target.get(cash_ticker, 0.0) + eq_w

            records[rdate] = pd.Series(target)

        if not records:
            return pd.DataFrame()

        weights_df = pd.DataFrame(records).T.reindex(columns=prices.columns).fillna(0.0)
        return weights_df
