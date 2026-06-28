"""
Swing-trade screener engine v2 — methodology overhaul.

Pipeline:
  1.  Fetch NIFTY 500 constituents.
  2.  Download OHLCV (300 days) for all symbols + ^NSEI benchmark in one batch.
  3.  Liquidity filter: avg daily turnover (close × volume, 20-day) > ₹10 Cr;
      price floor > ₹20.                                           [P3 #10]
  4.  Relative Strength: composite RS vs NIFTY over 21/63/126 days;
      hard floor RS percentile ≥ 60.                               [P1 #1]
  5.  Compute indicators: EMA9/20/21/50/200, RSI14, MACD, ATR14, ADX20,
      Bollinger Bandwidth, vol_avg20.                              [P2 #5]
  6.  Trend filter: price > EMA20 > EMA50 (slope up), ADX > 20.  [P2 #5]
  7.  Signal detection — one primary archetype per stock:
        • breakout          VCP-style contracting base + pivot close on volume
        • pullback          Pullback to rising EMA20, volume dry-up + reclaim bar
        • trend_continuation EMA9/21 cross on volume surge + MACD hist positive
                                                                   [P2 #4, P3 #7, P3 #8]
  8.  Risk: ATR-based stop (entry − 2×ATR), target (+3×ATR), R:R ≥ 1.5;
      reject if close > pivot + 1×ATR (too extended).             [P1 #3]
  9.  Earnings flag: report within 10 trading days → flag, still surface.[P1 #2]
  10. Composite score 1–10 weighted by RS rank, trend quality,
      setup type, R:R.                                             [P3 #9]
  11. Rank by score desc.
"""

import logging
import random
import time
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

from core.data.fetcher import fetch_ohlcv_data
from core.data.universe import get_nifty500
from core.screeners.relative_strength import compute_rs_scores
from core.signals.technical_indicators import ATR, ADX, EMA, RSI, MACD

logger = logging.getLogger(__name__)

NIFTY_TICKER = "^NSEI"

# ── Indicator computation ──────────────────────────────────────────────────────

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add all required indicator columns.

    New vs v1: EMA20, EMA200, ATR14, ADX20, Bandwidth (Boll), vol_avg20.
    EMA200 will be NaN for the first ~200 bars (data-limited) — treated as
    optional in _trend_ok.
    """
    df = df.copy()
    df["vol_avg20"] = df["Volume"].rolling(20).mean()

    for p in [9, 20, 21, 50, 200]:
        df[f"EMA{p}"] = EMA(df, p)[f"EMA{p}"]

    rsi_df   = RSI(df, 14)
    macd_df  = MACD(df, 12, 26, 9)
    atr_df   = ATR(df, 14)
    adx_df   = ADX(df, 20)

    df["RSI14"]     = rsi_df["RSI"]
    df["MACD_hist"] = macd_df["MACD"] - macd_df["Signal"]
    df["ATR14"]     = atr_df["ATR"]
    df["ADX"]       = adx_df["ADX"]

    # Bollinger bandwidth as base-tightness proxy
    bw = df["Close"].rolling(20).std(ddof=0) * 2 / df["Close"].rolling(20).mean()
    df["BB_width"] = bw

    return df


# ── Liquidity & price filter ───────────────────────────────────────────────────

def _passes_liquidity(df: pd.DataFrame) -> bool:
    """Avg daily turnover (close × volume) over last 20 days > ₹10 Cr AND price > ₹20."""  # P3 #10
    if len(df) < 20:
        return False
    turnover = (df["Close"] * df["Volume"]).tail(20).mean()
    price = float(df["Close"].dropna().iloc[-1])
    return float(turnover) > 1e8 and price > 20.0


# ── Trend filter ───────────────────────────────────────────────────────────────

def _trend_ok(df: pd.DataFrame) -> tuple[bool, int]:
    """
    Returns (passes: bool, trend_score: int 0–3).

    Score breakdown (P2 #5):
      +1  price > EMA20 > EMA50
      +1  EMA50 slope upward (today vs 5 bars ago)
      +1  ADX > 20
    EMA200 is checked only when available (warm-up).
    """
    needed = ["Close", "EMA20", "EMA50", "ADX"]
    sub = df[needed].dropna()
    if len(sub) < 6:
        return False, 0

    last = sub.iloc[-1]
    score = 0

    # price > EMA20 > EMA50
    if float(last["Close"]) > float(last["EMA20"]) > float(last["EMA50"]):
        score += 1

    # EMA50 sloping up
    if float(sub["EMA50"].iloc[-1]) > float(sub["EMA50"].iloc[-6]):
        score += 1

    # Trend strength
    if float(last["ADX"]) > 20:
        score += 1

    # EMA200 above-water check (optional — only penalises if data exists and fails)
    if "EMA200" in df.columns:
        ema200_sub = df["EMA200"].dropna()
        if len(ema200_sub) > 0:
            ema200_last = float(ema200_sub.iloc[-1])
            if float(last["Close"]) < ema200_last:
                score = max(0, score - 1)  # soft penalty for being below 200 EMA

    passes = score >= 2
    return passes, score


# ── Signal detectors ───────────────────────────────────────────────────────────

def _vcp_breakout(df: pd.DataFrame) -> tuple[bool, float | None]:
    """
    VCP-style breakout (P3 #7): two contracting price ranges with volume dry-up,
    followed by a pivot close on above-average volume.

    Returns (fired, pivot_price).
    """
    needed = ["High", "Low", "Close", "Volume", "vol_avg20"]
    sub = df[needed].dropna()
    if len(sub) < 50:
        return False, None

    base = sub.iloc[-41:-1]   # 40 bars before today
    if len(base) < 30:
        return False, None

    mid = len(base) // 2
    first_half  = base.iloc[:mid]
    second_half = base.iloc[mid:]

    range1 = float(first_half["High"].max()  - first_half["Low"].min())
    range2 = float(second_half["High"].max() - second_half["Low"].min())

    if range1 == 0 or range2 >= range1 * 0.80:   # second half must be ≥20% tighter
        return False, None

    vol1 = float(first_half["Volume"].mean())
    vol2 = float(second_half["Volume"].mean())
    if vol1 == 0 or vol2 >= vol1 * 0.90:          # volume must dry up ≥10%
        return False, None

    pivot = float(second_half["High"].max())
    today = sub.iloc[-1]
    avg   = float(today["vol_avg20"]) if not pd.isna(today["vol_avg20"]) else 0

    closed_above = float(today["Close"]) > pivot
    vol_ok       = avg > 0 and float(today["Volume"]) > 1.5 * avg   # P2 #6 — volume expansion

    if closed_above and vol_ok:
        return True, pivot
    return False, None


def _pullback_ema(df: pd.DataFrame) -> tuple[bool, float | None]:
    """
    Pullback to rising EMA20 with volume dry-up + reclaim bar (P3 #8).

    Returns (fired, pivot) where pivot = EMA20 at reclaim.
    """
    needed = ["Close", "Low", "EMA20", "Volume", "vol_avg20"]
    sub = df[needed].dropna()
    if len(sub) < 10:
        return False, None

    # EMA20 must be rising
    if float(sub["EMA20"].iloc[-1]) <= float(sub["EMA20"].iloc[-6]):
        return False, None

    # Last 1–5 bars before today: at least 1 touched/dipped within 2% of EMA20
    recent = sub.iloc[-6:-1]
    touched = any(
        float(row["Low"]) <= float(row["EMA20"]) * 1.02
        for _, row in recent.iterrows()
    )
    if not touched:
        return False, None

    # Volume dry-up during pullback (P2 #6)
    avg_vol = float(sub.iloc[-1]["vol_avg20"]) if not pd.isna(sub.iloc[-1]["vol_avg20"]) else 0
    pullback_vol = float(sub.iloc[-4:-1]["Volume"].mean())
    if avg_vol > 0 and pullback_vol >= avg_vol * 0.85:
        return False, None

    # Reclaim bar: today closes above EMA20
    today = sub.iloc[-1]
    if float(today["Close"]) > float(today["EMA20"]):
        return True, float(today["EMA20"])
    return False, None


def _ema_cross_trend(df: pd.DataFrame) -> tuple[bool, float | None]:
    """
    EMA9 crosses above EMA21 in last 5 bars on volume surge AND MACD hist > 0.

    Returns (fired, pivot) where pivot = EMA21 at cross bar.
    """
    needed = ["EMA9", "EMA21", "Volume", "vol_avg20", "MACD_hist"]
    sub = df[needed].dropna()
    if len(sub) < 6:
        return False, None

    for i in range(-5, 0):
        prev = sub.iloc[i - 1]
        curr = sub.iloc[i]
        crossed = (float(prev["EMA9"]) <= float(prev["EMA21"]) and
                   float(curr["EMA9"]) > float(curr["EMA21"]))
        if not crossed:
            continue
        avg = float(curr["vol_avg20"]) if not pd.isna(curr["vol_avg20"]) else 0
        vol_ok  = avg > 0 and float(curr["Volume"]) > 1.5 * avg   # P2 #6
        macd_ok = float(sub["MACD_hist"].iloc[-1]) > 0
        if vol_ok and macd_ok:
            return True, float(curr["EMA21"])

    return False, None


# ── Risk parameters ────────────────────────────────────────────────────────────

def _compute_risk(df: pd.DataFrame, pivot: float) -> dict | None:
    """
    ATR-based entry risk for the setup (P1 #3).

    stop   = pivot − 2 × ATR14
    target = pivot + 3 × ATR14  → ~1.5 R:R
    rr     = (target − pivot) / (pivot − stop)

    Returns None if too extended (close > pivot + 1×ATR) or R:R < 1.0.
    """
    atr_sub = df["ATR14"].dropna()
    if atr_sub.empty or pivot <= 0:
        return None

    atr   = float(atr_sub.iloc[-1])
    close = float(df["Close"].dropna().iloc[-1])

    if atr <= 0:
        return None

    # Reject if price is too far extended past the pivot
    if close > pivot + 1.0 * atr:
        return None

    stop   = pivot - 2.0 * atr
    target = pivot + 3.0 * atr
    rr     = (target - pivot) / (pivot - stop) if pivot > stop else 0.0

    if rr < 1.0:
        return None

    return {
        "entry_pivot": round(pivot, 2),
        "stop":        round(stop, 2),
        "target":      round(target, 2),
        "rr":          round(rr, 2),
        "atr":         round(atr, 2),
    }


# ── Earnings flag ──────────────────────────────────────────────────────────────

def _earnings_within_days(symbol: str, days: int = 10) -> bool:
    """
    Returns True if the stock has an earnings release within the next `days`
    trading days.  Best-effort; defaults to False on any failure.     [P1 #2]
    """
    try:
        cal = yf.Ticker(f"{symbol}.NS").calendar
        if cal is None or cal.empty:
            return False
        # yfinance may return datetime index or a 'Earnings Date' column
        if isinstance(cal.index, pd.DatetimeIndex):
            dates = cal.index
        elif "Earnings Date" in cal.columns:
            dates = pd.to_datetime(cal["Earnings Date"], errors="coerce").dropna()
        else:
            dates = pd.to_datetime(cal.iloc[0], errors="coerce").dropna()
        cutoff = pd.Timestamp(date.today() + timedelta(days=days))
        today  = pd.Timestamp(date.today())
        return any(today <= d <= cutoff for d in dates)
    except Exception:
        return False


# ── Composite score ────────────────────────────────────────────────────────────

def _compute_score(
    rs_rank: float,
    trend_score: int,
    rr: float,
    setup_type: str,
) -> int:
    """
    Weighted 1–10 score (P3 #9).

    RS rank (dominant):   max 4 pts
    Trend quality:        max 2 pts
    Setup type quality:   max 2 pts
    R:R quality:          max 2 pts
    """
    pts = 0

    # RS rank
    if rs_rank >= 85:   pts += 4
    elif rs_rank >= 70: pts += 3
    elif rs_rank >= 60: pts += 2
    else:               pts += 1

    # Trend quality
    pts += min(trend_score, 2)

    # Setup type
    if setup_type == "breakout":            pts += 2
    elif setup_type == "pullback":          pts += 2
    elif setup_type == "trend_continuation": pts += 1

    # R:R
    if rr >= 2.5:   pts += 2
    elif rr >= 1.5: pts += 1

    return min(10, max(1, pts))


# ── Per-stock scoring ──────────────────────────────────────────────────────────

def score_stock(
    df: pd.DataFrame,
    symbol: str,
    rs_rank: float,
    rs_ratio: float,
    trend_score: int,
) -> dict | None:
    """
    Run all signal detectors, pick primary archetype, compute risk params,
    and return a result dict — or None if no qualifying setup.
    """
    # Priority: breakout > pullback > trend_continuation
    vcp_ok, vcp_pivot   = _vcp_breakout(df)
    pull_ok, pull_pivot = _pullback_ema(df)
    ema_ok, ema_pivot   = _ema_cross_trend(df)

    setup_type: str | None = None
    pivot: float | None     = None

    if vcp_ok and vcp_pivot is not None:
        setup_type, pivot = "breakout", vcp_pivot
    elif pull_ok and pull_pivot is not None:
        setup_type, pivot = "pullback", pull_pivot
    elif ema_ok and ema_pivot is not None:
        setup_type, pivot = "trend_continuation", ema_pivot

    # Require RS ≥ 70 for single-signal pass, else need 2 archetypes (belt-and-suspenders)
    signals_count = sum([vcp_ok, pull_ok, ema_ok])
    if setup_type is None:
        return None
    if rs_rank < 70 and signals_count < 2:
        return None

    risk = _compute_risk(df, pivot)
    if risk is None:
        return None

    # P4 #12: use last OHLCV close — not .info currentPrice
    close_sub = df["Close"].dropna()
    last_close = float(close_sub.iloc[-1]) if not close_sub.empty else None

    week52_high = float(df["High"].tail(252).max()) if len(df) >= 50 else None
    week52_low  = float(df["Low"].tail(252).min())  if len(df) >= 50 else None
    avg_vol20   = float(df["vol_avg20"].dropna().iloc[-1]) if "vol_avg20" in df.columns else None
    avg_turnover = last_close * avg_vol20 if last_close and avg_vol20 else None

    adx_sub = df["ADX"].dropna()
    adx_val = float(adx_sub.iloc[-1]) if not adx_sub.empty else None

    score = _compute_score(rs_rank, trend_score, risk["rr"], setup_type)

    return {
        "score":            score,
        "setup_type":       setup_type,
        "signals_triggered": [setup_type],
        "rs_ratio":         rs_ratio,
        "rs_rank":          rs_rank,
        "trend_score":      trend_score,
        "adx":              round(adx_val, 1) if adx_val else None,
        "entry_pivot":      risk["entry_pivot"],
        "stop":             risk["stop"],
        "target":           risk["target"],
        "rr":               risk["rr"],
        "atr":              risk["atr"],
        "last_close":       round(last_close, 2) if last_close else None,
        "week52_high":      round(week52_high, 2) if week52_high else None,
        "week52_low":       round(week52_low, 2)  if week52_low  else None,
        "avg_turnover":     round(avg_turnover, 0) if avg_turnover else None,
    }


# ── Top-level run_scan ─────────────────────────────────────────────────────────

def run_scan(progress_cb=None) -> list[dict]:
    """
    Run a full NIFTY 500 swing scan and return ranked results.

    Each returned dict: {symbol, name, score, setup_type, signals_triggered,
    rs_ratio, rs_rank, trend_score, adx, entry_pivot, stop, target, rr, atr,
    earnings_flag, last_close, week52_high, week52_low, avg_turnover}.
    """
    logger.info("run_scan: fetching universe")
    universe   = get_nifty500()
    all_symbols = [s["symbol"] for s in universe]
    name_map    = {s["symbol"]: s["name"] for s in universe}
    yf_symbols  = [s["yf_symbol"] for s in universe] + [NIFTY_TICKER]
    total       = len(universe)

    logger.info("run_scan: downloading OHLCV for %d symbols + benchmark", total)
    # 300 calendar days ≈ 207 trading days — enough for EMA200 warm-up    [P3 #10]
    ohlcv = fetch_ohlcv_data(yf_symbols, days=300, interval="1d")

    # Remap to plain symbol keys (strip .NS; ^NSEI has no suffix)
    ohlcv_plain: dict[str, pd.DataFrame] = {}
    for k, v in ohlcv.items():
        plain = k.replace(".NS", "")
        ohlcv_plain[plain] = v

    nifty_df = ohlcv_plain.get(NIFTY_TICKER)
    if nifty_df is None:
        logger.warning("NIFTY 50 data unavailable — RS will be relative momentum only")

    # ── Liquidity filter ──────────────────────────────────────────────────────
    liquid_symbols = [
        s for s in all_symbols
        if s in ohlcv_plain and _passes_liquidity(ohlcv_plain[s])
    ]
    logger.info(
        "run_scan: %d / %d passed liquidity filter", len(liquid_symbols), total
    )

    if progress_cb:
        progress_cb(scanned=len(liquid_symbols), total=total)

    # ── Relative Strength ─────────────────────────────────────────────────────  [P1 #1]
    liquid_ohlcv = {s: ohlcv_plain[s] for s in liquid_symbols}
    rs_map = compute_rs_scores(liquid_ohlcv, nifty_df)

    rs_filtered = [s for s in liquid_symbols if rs_map.get(s, {}).get("rs_rank", 0) >= 60]
    logger.info(
        "run_scan: %d / %d passed RS filter (≥60th pct)", len(rs_filtered), len(liquid_symbols)
    )

    if progress_cb:
        progress_cb(scanned=len(rs_filtered), total=total)

    # ── Per-symbol scoring ────────────────────────────────────────────────────
    results: list[dict] = []
    scanned = 0

    for symbol in rs_filtered:
        scanned += 1
        df = ohlcv_plain[symbol]

        if len(df) < 60:
            continue

        df = compute_indicators(df)

        trend_passes, trend_score = _trend_ok(df)        # P2 #5
        if not trend_passes:
            if progress_cb and scanned % 10 == 0:
                progress_cb(scanned=scanned, total=total)
            continue

        rs_data   = rs_map[symbol]
        rs_rank   = rs_data["rs_rank"]
        rs_ratio  = rs_data["rs_ratio"]

        result = score_stock(df, symbol, rs_rank, rs_ratio, trend_score)
        if result is None:
            if progress_cb and scanned % 10 == 0:
                progress_cb(scanned=scanned, total=total)
            continue

        # Earnings flag (best-effort, non-blocking)         [P1 #2]
        result["earnings_flag"] = _earnings_within_days(symbol)

        result["symbol"] = symbol
        result["name"]   = name_map.get(symbol, symbol)
        results.append(result)

        if progress_cb and scanned % 10 == 0:
            progress_cb(scanned=scanned, total=total)

    results.sort(key=lambda r: r["score"], reverse=True)
    logger.info("run_scan: done — %d setups found", len(results))
    return results
