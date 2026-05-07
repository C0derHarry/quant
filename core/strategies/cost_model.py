"""Indian brokerage transaction cost presets.

All rates verified from official sources (2025-2026).
Slippage is universe-driven (liquidity proxy), not broker-specific.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class BrokerSpec:
    id:              str
    label:           str
    # Delivery brokerage: applied as min(pct * value, flat_max) per trade leg
    delivery_pct:    float   # 0.0 means ₹0
    delivery_flat:   float   # max ₹ cap (0 = no cap applies pct only)
    # STT: 0.1% buy+sell delivery; 0.025% sell-side intraday — strategies always delivery
    stt_delivery:    float = 0.001    # 0.1% on both buy and sell turnover
    exchange_pct:    float = 0.0000307  # NSE 0.00307%
    sebi_per_cr:     float = 10.0       # ₹10 per Cr turnover
    stamp_duty_buy:  float = 0.00015   # 0.015% on buy value
    dp_per_sell:     float = 0.0       # DP charge per delivery sell scrip (₹)
    source_url:      str   = ""

    def to_dict(self) -> dict:
        return {
            "id":           self.id,
            "label":        self.label,
            "delivery_pct": self.delivery_pct,
            "dp_per_sell":  self.dp_per_sell,
            "source_url":   self.source_url,
        }


BROKERAGES: dict[str, BrokerSpec] = {
    "zerodha": BrokerSpec(
        id="zerodha", label="Zerodha",
        delivery_pct=0.0, delivery_flat=0.0,
        dp_per_sell=0.0,
        source_url="https://zerodha.com/charges/",
    ),
    "groww": BrokerSpec(
        id="groww", label="Groww",
        delivery_pct=0.001, delivery_flat=20.0,
        dp_per_sell=3.50,
        source_url="https://groww.in/pricing",
    ),
    "upstox": BrokerSpec(
        id="upstox", label="Upstox",
        delivery_pct=0.0, delivery_flat=20.0,
        dp_per_sell=0.0,
        source_url="https://upstox.com/brokerage-charges/",
    ),
    "angel_one": BrokerSpec(
        id="angel_one", label="Angel One",
        delivery_pct=0.001, delivery_flat=20.0,
        dp_per_sell=20.0,
        source_url="https://www.angelone.in/exchange-transaction-charges",
    ),
    "icici": BrokerSpec(
        id="icici", label="ICICI Direct",
        delivery_pct=0.0029, delivery_flat=0.0,
        dp_per_sell=0.0,
        source_url="https://www.icicidirect.com/charges",
    ),
    "hdfc": BrokerSpec(
        id="hdfc", label="HDFC Securities",
        delivery_pct=0.0032, delivery_flat=0.0,
        dp_per_sell=0.0,
        source_url="https://www.hdfcsec.com/charges",
    ),
}

# Slippage by universe — based on observed bid-ask spreads for liquid NSE stocks (bps)
UNIVERSE_SLIPPAGE_BPS: dict[str, float] = {
    "NIFTY 50":           1.5,
    "NIFTY 100":          3.0,
    "NIFTY MIDCAP 100":   5.0,
    "NIFTY SMALLCAP 100": 8.0,
    "NIFTY BANK":         2.0,
    "NIFTY IT":           2.0,
    "custom":             3.0,  # fallback for extra-ticker universes
}

GST_RATE = 0.18  # 18% on (brokerage + exchange + SEBI)


def _compute_leg_cost(
    value: float,
    side:  str,        # 'buy' | 'sell'
    broker: BrokerSpec,
    slippage_bps: float,
    n_scrips: int = 1,  # for DP charges (1 per unique stock sold)
) -> dict[str, float]:
    """Compute full round-trip cost for one trade leg (₹)."""
    # Brokerage
    if broker.delivery_flat > 0:
        brokerage = min(broker.delivery_pct * value, broker.delivery_flat)
    else:
        brokerage = broker.delivery_pct * value

    # STT: 0.1% on both sides for delivery equity
    stt = broker.stt_delivery * value

    # Exchange transaction charge (NSE)
    exchange = broker.exchange_pct * value

    # SEBI turnover fee: ₹10 per Crore = 0.0000001 * value
    sebi = broker.sebi_per_cr * value / 1e7

    # Stamp duty: 0.015% on buy side only
    stamp = broker.stamp_duty_buy * value if side == 'buy' else 0.0

    # GST: 18% on (brokerage + exchange + SEBI) — NOT on STT
    gst = GST_RATE * (brokerage + exchange + sebi)

    # DP charges on delivery sell (per scrip, fixed ₹)
    dp = broker.dp_per_sell * n_scrips if side == 'sell' else 0.0

    # Slippage: modelled as adverse price movement on execution
    slippage = (slippage_bps / 10_000) * value

    total = brokerage + stt + exchange + sebi + stamp + gst + dp + slippage

    return {
        "brokerage": round(brokerage, 4),
        "stt":       round(stt, 4),
        "exchange":  round(exchange, 4),
        "sebi":      round(sebi, 4),
        "stamp":     round(stamp, 4),
        "gst":       round(gst, 4),
        "dp":        round(dp, 4),
        "slippage":  round(slippage, 4),
        "total":     round(total, 4),
    }


def apply_costs(
    trades_value: pd.Series,    # {ticker: ₹ notional value of trade (signed: +buy, -sell)}
    broker_id: str,
    universe:  str,
    capital:   float,
) -> tuple[float, list[dict]]:
    """
    Apply Indian transaction costs to a rebalance trade batch.

    Returns (total_cost_inr, list_of_trade_cost_records).
    The trade log records include per-leg cost breakdown for UI display.
    """
    broker       = BROKERAGES.get(broker_id, BROKERAGES["zerodha"])
    slippage_bps = UNIVERSE_SLIPPAGE_BPS.get(universe, UNIVERSE_SLIPPAGE_BPS["custom"])

    total_cost = 0.0
    records    = []

    for ticker, raw_value in trades_value.items():
        if abs(raw_value) < 1.0:
            continue
        side  = 'buy' if raw_value > 0 else 'sell'
        value = abs(raw_value)
        cost  = _compute_leg_cost(value, side, broker, slippage_bps)
        total_cost += cost["total"]
        records.append({
            "ticker":         ticker,
            "side":           side,
            "value":          round(value, 2),
            "cost_breakdown": cost,
        })

    return round(total_cost, 4), records


def broker_summary(broker_id: str, universe: str) -> dict:
    """Return a ₹/lakh cost summary for display in BrokeragePicker UI."""
    broker       = BROKERAGES.get(broker_id, BROKERAGES["zerodha"])
    slippage_bps = UNIVERSE_SLIPPAGE_BPS.get(universe, UNIVERSE_SLIPPAGE_BPS["custom"])
    buy_cost  = _compute_leg_cost(100_000, 'buy',  broker, slippage_bps)
    sell_cost = _compute_leg_cost(100_000, 'sell', broker, slippage_bps)
    return {
        "per_lakh_buy":  buy_cost,
        "per_lakh_sell": sell_cost,
        "slippage_bps":  slippage_bps,
    }
