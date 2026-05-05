"""Generate a self-contained Python backtest script from a strategy run."""
from __future__ import annotations
import json
import os
import textwrap
from datetime import date


BROKER_STUBS: dict[str, str] = {
    "zerodha": textwrap.dedent("""\
        # ── Zerodha Kite Connect integration (fill in your credentials) ─────────
        # pip install kiteconnect
        # from kiteconnect import KiteConnect
        # kite = KiteConnect(api_key="YOUR_API_KEY")
        # kite.set_access_token("YOUR_ACCESS_TOKEN")
        # For each buy signal:
        #   kite.place_order(tradingsymbol=ticker, exchange="NSE", transaction_type="BUY",
        #                    quantity=qty, order_type="MARKET", product="CNC", variety="regular")
        # Zerodha charges: ₹0 brokerage on delivery; 0.1% STT; DP charges nil.
    """),
    "groww": textwrap.dedent("""\
        # ── Groww Trade API integration (fill in your credentials) ───────────────
        # pip install growwapi   (or use the Groww REST API directly)
        # from growwapi import GrowwAPI
        # client = GrowwAPI(api_key="YOUR_GROWW_API_KEY", secret="YOUR_SECRET")
        # For each buy signal: client.place_order(symbol=ticker, qty=qty, side="BUY", ...)
        # Groww charges: min(₹20, 0.1% × trade value) brokerage + ₹3.50 DP on delivery sell.
    """),
    "upstox": textwrap.dedent("""\
        # ── Upstox API integration ───────────────────────────────────────────────
        # pip install upstox-python-sdk
        # import upstox_client; upstox_client.configuration.access_token = "YOUR_TOKEN"
        # Upstox charges: ₹20 flat brokerage on delivery orders.
    """),
    "angel_one": textwrap.dedent("""\
        # ── Angel One SmartAPI integration ───────────────────────────────────────
        # pip install smartapi-python
        # from SmartApi import SmartConnect; api = SmartConnect(api_key="YOUR_KEY")
        # session = api.generateSession("YOUR_CLIENT", "YOUR_PIN", "YOUR_TOTP")
        # Angel One charges: ₹20 flat + ₹20 DP charge per delivery sell scrip.
    """),
    "icici": textwrap.dedent("""\
        # ── ICICI Direct Breeze API integration ──────────────────────────────────
        # pip install breeze-connect
        # from breeze_connect import BreezeConnect; api = BreezeConnect(api_key="YOUR_KEY")
        # api.generate_session(api_secret="YOUR_SECRET", session_token="YOUR_SESSION")
        # ICICI charges: 0.29% brokerage (MoneySaver plan).
    """),
    "hdfc": textwrap.dedent("""\
        # ── HDFC Securities API integration ──────────────────────────────────────
        # Contact HDFC Securities for API access: https://www.hdfcsec.com/api
        # HDFC charges: 0.32% brokerage (min ₹25).
    """),
}


def render_standalone(
    strategy_id: str,
    params:      dict,
    broker_id:   str,
    tickers:     list[str],
    start_date:  str,
    end_date:    str,
    kpis:        dict,
) -> str:
    """Generate a fully standalone Python file for the given strategy + params."""
    tmpl_path = os.path.join(os.path.dirname(__file__), "templates", f"{strategy_id}.py.tmpl")
    if not os.path.exists(tmpl_path):
        raise FileNotFoundError(f"No template found for strategy: {strategy_id}")

    with open(tmpl_path) as f:
        template = f.read()

    broker_stub = BROKER_STUBS.get(broker_id, "# No broker stub available for this broker.")
    kpi_lines   = "\n".join(f"#   {k}: {v}" for k, v in kpis.items())
    generated   = date.today().isoformat()

    result = (
        template
        .replace("{{STRATEGY_ID}}", strategy_id)
        .replace("{{PARAMS}}", json.dumps(params, indent=4))
        .replace("{{TICKERS}}", json.dumps(tickers))
        .replace("{{START_DATE}}", start_date)
        .replace("{{END_DATE}}", end_date)
        .replace("{{BROKER_ID}}", broker_id)
        .replace("{{BROKER_STUB}}", broker_stub)
        .replace("{{KPI_LINES}}", kpi_lines)
        .replace("{{GENERATED_DATE}}", generated)
    )
    return result


def export_filename(strategy_id: str, start_date: str, end_date: str) -> str:
    return f"{strategy_id}_{start_date}_{end_date}.py"
