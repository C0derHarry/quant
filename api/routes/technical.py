import numpy as np
import pandas as pd
import yfinance as yf
from fastapi import APIRouter, HTTPException, Query

from core.signals.technical_indicators import (
    MACD, Boll_Bands, RSI, ADX,
    EMA, Stochastic, OBV, VWAP, CCI, ParabolicSAR,
)

router = APIRouter()


def _normalize(ticker: str) -> str:
    if ticker.endswith((".NS", ".BO")) or ticker.startswith("^"):
        return ticker
    return ticker + ".NS"


def _safe_float(val) -> float | None:
    try:
        v = float(val)
        return None if np.isnan(v) or np.isinf(v) else v
    except Exception:
        return None


def _evaluate_indicators(df: pd.DataFrame) -> list[dict]:
    close = df["Close"]
    last  = close.iloc[-1]
    results: list[dict] = []

    # ── 1. EMA Stack ─────────────────────────────────────────────────
    ema20_s  = EMA(df, 20)["EMA20"]
    ema50_s  = EMA(df, 50)["EMA50"]
    ema200_s = EMA(df, 200)["EMA200"]
    e20  = _safe_float(ema20_s.iloc[-1])
    e50  = _safe_float(ema50_s.iloc[-1])
    e200 = _safe_float(ema200_s.iloc[-1])

    if e20 and e50 and e200:
        bull = last > e50 and e50 > e200
        bear = last < e50 and e50 < e200
        sig  = "Bullish" if bull else ("Bearish" if bear else "Neutral")
        desc = (
            f"Price ₹{last:.1f} vs EMA20 ₹{e20:.1f} · EMA50 ₹{e50:.1f} · EMA200 ₹{e200:.1f}. "
            + ("EMA stack aligned bullish — sustained uptrend." if bull
               else "EMA stack aligned bearish — sustained downtrend." if bear
               else "Mixed EMA alignment — no clear trend.")
        )
    else:
        sig, desc = "Neutral", "Insufficient data for EMA Stack."
    results.append({"name": "EMA Stack", "category": "Trend", "signal": sig,
                     "value": f"EMA20 ₹{e20:.1f}" if e20 else "N/A", "description": desc})

    # ── 2. Golden / Death Cross ──────────────────────────────────────
    if e50 and e200:
        bull = e50 > e200
        sig  = "Bullish" if bull else "Bearish"
        spread = abs(e50 - e200) / e200 * 100
        desc = (
            f"EMA50 (₹{e50:.1f}) {'above' if bull else 'below'} EMA200 (₹{e200:.1f}), "
            f"spread {spread:.1f}%. "
            + ("Golden Cross — long-term bullish." if bull else "Death Cross — long-term bearish.")
        )
    else:
        sig, desc = "Neutral", "Insufficient data for Golden/Death Cross (need 200 bars)."
    results.append({"name": "Golden / Death Cross", "category": "Trend", "signal": sig,
                     "value": f"EMA50 {'>' if e50 and e200 and e50 > e200 else '<'} EMA200",
                     "description": desc})

    # ── 3. Parabolic SAR ─────────────────────────────────────────────
    psar = ParabolicSAR(df)
    sar_val   = _safe_float(psar["SAR"].iloc[-1])
    sar_trend = int(psar["Trend"].iloc[-1]) if not pd.isna(psar["Trend"].iloc[-1]) else 1
    if sar_val:
        bull = sar_trend == 1
        sig  = "Bullish" if bull else "Bearish"
        desc = (
            f"SAR at ₹{sar_val:.1f}. "
            + ("Price above SAR dots — uptrend in force." if bull
               else "Price below SAR dots — downtrend in force.")
        )
    else:
        sig, desc = "Neutral", "Insufficient data for Parabolic SAR."
    results.append({"name": "Parabolic SAR", "category": "Trend", "signal": sig,
                     "value": f"SAR ₹{sar_val:.1f}" if sar_val else "N/A", "description": desc})

    # ── 4. MACD Crossover ────────────────────────────────────────────
    macd_df   = MACD(df)
    macd_val  = _safe_float(macd_df["MACD"].iloc[-1])
    sig_val   = _safe_float(macd_df["Signal"].iloc[-1])
    if macd_val is not None and sig_val is not None:
        bull = macd_val > sig_val
        sig  = "Bullish" if bull else "Bearish"
        desc = (
            f"MACD {macd_val:.3f} {'above' if bull else 'below'} Signal {sig_val:.3f}. "
            + ("Bullish crossover — upward momentum." if bull else "Bearish crossover — downward momentum.")
        )
    else:
        sig, desc = "Neutral", "Insufficient data for MACD."
    results.append({"name": "MACD Crossover", "category": "Momentum", "signal": sig,
                     "value": f"MACD {macd_val:.3f}" if macd_val is not None else "N/A",
                     "description": desc})

    # ── 5. MACD Zero Line ────────────────────────────────────────────
    if macd_val is not None:
        bull = macd_val > 0
        sig  = "Bullish" if bull else "Bearish"
        desc = (
            f"MACD at {macd_val:.3f} — "
            + ("above zero, bullish territory." if bull else "below zero, bearish territory.")
        )
    else:
        sig, desc = "Neutral", "Insufficient data for MACD Zero Line."
    results.append({"name": "MACD Zero Line", "category": "Momentum", "signal": sig,
                     "value": f"{macd_val:.3f}" if macd_val is not None else "N/A",
                     "description": desc})

    # ── 6. RSI ───────────────────────────────────────────────────────
    rsi_df  = RSI(df)
    rsi_val = _safe_float(rsi_df["RSI"].iloc[-1])
    if rsi_val is not None:
        if rsi_val > 55:
            sig  = "Bullish"
            desc = f"RSI at {rsi_val:.1f} — above 55, positive momentum."
        elif rsi_val < 45:
            sig  = "Bearish"
            desc = f"RSI at {rsi_val:.1f} — below 45, negative momentum."
        else:
            sig  = "Neutral"
            desc = f"RSI at {rsi_val:.1f} — in neutral zone (45–55), no clear signal."
    else:
        sig, desc = "Neutral", "Insufficient data for RSI."
    results.append({"name": "RSI (14)", "category": "Momentum", "signal": sig,
                     "value": f"{rsi_val:.1f}" if rsi_val is not None else "N/A",
                     "description": desc})

    # ── 7. Stochastic ────────────────────────────────────────────────
    stoch_df = Stochastic(df)
    k_val    = _safe_float(stoch_df["%K"].iloc[-1])
    d_val    = _safe_float(stoch_df["%D"].iloc[-1])
    if k_val is not None and d_val is not None:
        if k_val > 50 and k_val > d_val:
            sig  = "Bullish"
            desc = f"%K {k_val:.1f} above 50 and above %D {d_val:.1f} — bullish momentum."
        elif k_val < 50 and k_val < d_val:
            sig  = "Bearish"
            desc = f"%K {k_val:.1f} below 50 and below %D {d_val:.1f} — bearish momentum."
        else:
            sig  = "Neutral"
            desc = f"%K {k_val:.1f}, %D {d_val:.1f} — mixed stochastic signal."
    else:
        sig, desc = "Neutral", "Insufficient data for Stochastic."
    results.append({"name": "Stochastic (14,3)", "category": "Momentum", "signal": sig,
                     "value": f"%K {k_val:.1f}" if k_val is not None else "N/A",
                     "description": desc})

    # ── 8. CCI ───────────────────────────────────────────────────────
    cci_df  = CCI(df)
    cci_val = _safe_float(cci_df["CCI"].iloc[-1])
    if cci_val is not None:
        bull = cci_val > 0
        sig  = "Bullish" if bull else "Bearish"
        desc = (
            f"CCI at {cci_val:.1f} — "
            + ("above zero, buying pressure." if bull else "below zero, selling pressure.")
        )
    else:
        sig, desc = "Neutral", "Insufficient data for CCI."
    results.append({"name": "CCI (20)", "category": "Momentum", "signal": sig,
                     "value": f"{cci_val:.1f}" if cci_val is not None else "N/A",
                     "description": desc})

    # ── 9. OBV Trend ─────────────────────────────────────────────────
    obv_df    = OBV(df)
    obv_now   = _safe_float(obv_df["OBV"].iloc[-1])
    obv_10ago = _safe_float(obv_df["OBV"].iloc[-10]) if len(obv_df) >= 10 else None
    if obv_now is not None and obv_10ago is not None:
        bull = obv_now > obv_10ago
        sig  = "Bullish" if bull else "Bearish"
        chg  = ((obv_now - obv_10ago) / max(abs(obv_10ago), 1)) * 100
        desc = (
            f"OBV {'rising' if bull else 'falling'} over last 10 bars ({chg:+.1f}%) — "
            + ("volume accumulation (buying)." if bull else "volume distribution (selling).")
        )
    else:
        sig, desc = "Neutral", "Insufficient data for OBV Trend."
    results.append({"name": "OBV Trend", "category": "Volume", "signal": sig,
                     "value": f"{obv_now:,.0f}" if obv_now is not None else "N/A",
                     "description": desc})

    # ── 10. VWAP ─────────────────────────────────────────────────────
    vwap_df  = VWAP(df, period=20)
    vwap_val = _safe_float(vwap_df["VWAP"].iloc[-1])
    if vwap_val is not None:
        bull = last > vwap_val
        sig  = "Bullish" if bull else "Bearish"
        dev  = (last - vwap_val) / vwap_val * 100
        desc = (
            f"Price ₹{last:.1f} {'above' if bull else 'below'} 20-day VWAP ₹{vwap_val:.1f} ({dev:+.1f}%). "
            + ("Institutional buying zone." if bull else "Price below fair value, selling pressure.")
        )
    else:
        sig, desc = "Neutral", "Insufficient data for VWAP."
    results.append({"name": "VWAP (20-day)", "category": "Volume", "signal": sig,
                     "value": f"₹{vwap_val:.1f}" if vwap_val is not None else "N/A",
                     "description": desc})

    # ── 11. Bollinger Band Position ───────────────────────────────────
    bb_df   = Boll_Bands(df, period=20)
    upper   = _safe_float(bb_df["Upper Band"].iloc[-1])
    lower   = _safe_float(bb_df["Lower Band"].iloc[-1])
    mid     = ((upper + lower) / 2) if (upper and lower) else None
    if mid is not None:
        bull = last > mid
        sig  = "Bullish" if bull else "Bearish"
        pct_b = ((last - lower) / (upper - lower) * 100) if upper != lower else 50
        desc = (
            f"Price ₹{last:.1f} {'above' if bull else 'below'} BB midline ₹{mid:.1f} "
            f"(%B {pct_b:.0f}%). "
            + ("Above midline — bullish bias." if bull else "Below midline — bearish bias.")
        )
    else:
        sig, desc = "Neutral", "Insufficient data for Bollinger Bands."
    results.append({"name": "Bollinger Bands (20)", "category": "Volatility", "signal": sig,
                     "value": f"%B {pct_b:.0f}%" if mid is not None else "N/A",
                     "description": desc})

    # ── 12. ADX Directional ───────────────────────────────────────────
    adx_df  = ADX(df)
    adx_val = _safe_float(adx_df["ADX"].iloc[-1])
    di_plus = _safe_float(adx_df["+DI"].iloc[-1])
    di_minus= _safe_float(adx_df["-DI"].iloc[-1])
    if adx_val is not None and di_plus is not None and di_minus is not None:
        if adx_val < 20:
            sig  = "Neutral"
            desc = f"ADX at {adx_val:.1f} — below 20, trend too weak to be directional."
        elif di_plus > di_minus:
            sig  = "Bullish"
            desc = f"ADX {adx_val:.1f} (strong), +DI {di_plus:.1f} > −DI {di_minus:.1f} — confirmed uptrend."
        else:
            sig  = "Bearish"
            desc = f"ADX {adx_val:.1f} (strong), −DI {di_minus:.1f} > +DI {di_plus:.1f} — confirmed downtrend."
    else:
        sig, desc = "Neutral", "Insufficient data for ADX."
    results.append({"name": "ADX (20)", "category": "Trend Strength", "signal": sig,
                     "value": f"{adx_val:.1f}" if adx_val is not None else "N/A",
                     "description": desc})

    return results


def _verdict(indicators: list[dict]) -> dict:
    bull  = sum(1 for i in indicators if i["signal"] == "Bullish")
    bear  = sum(1 for i in indicators if i["signal"] == "Bearish")
    neut  = sum(1 for i in indicators if i["signal"] == "Neutral")
    total = len(indicators)
    decisive = bull + bear
    ratio = bull / decisive if decisive > 0 else 0.0

    if decisive == 0:
        verdict = "NEUTRAL"
    elif ratio >= 0.70:
        verdict = "STRONG BUY"
    elif ratio >= 0.55:
        verdict = "BUY"
    elif ratio <= 0.30:
        verdict = "STRONG SELL"
    elif ratio <= 0.45:
        verdict = "SELL"
    else:
        verdict = "NEUTRAL"

    return {
        "bullish":    bull,
        "bearish":    bear,
        "neutral":    neut,
        "total":      total,
        "verdict":    verdict,
        "bull_ratio": round(ratio, 4),
    }


@router.get("/analyze")
def analyze(ticker: str = Query(...), period: str = Query("1y")):
    ns = _normalize(ticker)
    try:
        raw = yf.download(ns, period=period, auto_adjust=True, progress=False)
        if raw.empty:
            raise ValueError(f"No data returned for {ns}")

        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)

        if len(raw) < 60:
            raise ValueError(f"Need at least 60 bars; got {len(raw)} for {ns}")

        indicators = _evaluate_indicators(raw)
        summary    = _verdict(indicators)
        return {"ticker": ticker, "period": period, "indicators": indicators, "summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
