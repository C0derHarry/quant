import base64
import json
import os
import time
from threading import Lock

from growwapi import GrowwAPI
from growwapi.groww.exceptions import GrowwAPIException


class GrowwError(Exception):
    pass


# Indices available via Groww CASH segment.
# Key = display name used in market.py; value = (exchange, segment, trading_symbol).
GROWW_SNAPSHOTS: dict[str, tuple[str, str, str]] = {
    "NIFTY 50":   (GrowwAPI.EXCHANGE_NSE, GrowwAPI.SEGMENT_CASH, "NIFTY"),
    "SENSEX":     (GrowwAPI.EXCHANGE_BSE, GrowwAPI.SEGMENT_CASH, "SENSEX"),
    "BANK NIFTY": (GrowwAPI.EXCHANGE_NSE, GrowwAPI.SEGMENT_CASH, "BANKNIFTY"),
    "FIN NIFTY":  (GrowwAPI.EXCHANGE_NSE, GrowwAPI.SEGMENT_CASH, "FINNIFTY"),
    # Same underlying as BANK NIFTY — appears in sectors under this name
    "NIFTY BANK": (GrowwAPI.EXCHANGE_NSE, GrowwAPI.SEGMENT_CASH, "BANKNIFTY"),
}


def _token_valid(token: str) -> bool:
    """Return True if the JWT access token is still valid (>5 min remaining)."""
    try:
        part = token.split(".")[1]
        part += "=" * (4 - len(part) % 4)
        exp = json.loads(base64.b64decode(part)).get("exp", 0)
        return exp > time.time() + 300
    except Exception:
        return False


def _make_client() -> tuple[GrowwAPI, str]:
    """
    Return (GrowwAPI instance, token_string).

    Priority:
    1. GROWW_ACCESS_TOKEN env var (if still valid)
    2. Generate a fresh token using GROWW_API (api_key) + GROWW_SECRET
    """
    access_token = os.getenv("GROWW_ACCESS_TOKEN", "")
    if access_token and _token_valid(access_token):
        return GrowwAPI(access_token), access_token

    api_key = os.getenv("GROWW_API", "")
    secret  = os.getenv("GROWW_SECRET", "")
    if not api_key or not secret:
        raise GrowwError(
            "Groww credentials not found. Set GROWW_ACCESS_TOKEN or "
            "both GROWW_API and GROWW_SECRET in .env"
        )
    try:
        new_token = GrowwAPI.get_access_token(api_key=api_key, secret=secret)
        return GrowwAPI(new_token), new_token
    except GrowwAPIException as exc:
        raise GrowwError(f"Failed to generate Groww access token: {exc}") from exc


_lock:       Lock            = Lock()
_client:     GrowwAPI | None = None
_token_str:  str             = ""  # JWT belonging to _client; re-checked on every access


def get_groww_client() -> GrowwAPI:
    """Return the module-level GrowwAPI singleton.

    Re-creates the client whenever the stored token is within 5 min of expiry
    (or already expired), so a daily 6am token rotation is handled automatically.
    Raises GrowwError if no valid credentials are available.
    """
    global _client, _token_str
    with _lock:
        if _client is None or not _token_valid(_token_str):
            _client, _token_str = _make_client()
        return _client


def ticker_snapshot_from_quote(payload: dict) -> dict:
    """Convert a get_quote() payload to our standard TickerSnapshot dict."""
    price  = float(payload.get("last_price", 0))
    change = float(payload.get("day_change", 0))
    pct    = float(payload.get("day_change_perc", 0))
    return {
        "price":      round(price, 2),
        "prev_close": round(price - change, 2),
        "change":     round(change, 2),
        "pct_change": round(pct, 3),
    }
