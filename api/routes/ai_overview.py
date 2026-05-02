import json
import os
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from google import genai
from google.genai import types as genai_types
import numpy as np
import pandas as pd
import yfinance as yf
from fastapi import APIRouter, HTTPException
from nsetools import Nse

from core.screeners import magic_formula_rank, qarp_screener
from api.routes.technical import _evaluate_indicators, _verdict, _normalize, _safe_float

router = APIRouter()

CACHE_DIR  = Path(__file__).parent.parent / "ai_cache"
CACHE_DIR.mkdir(exist_ok=True)
CACHE_FILE = CACHE_DIR / "ai_overview.json"
CACHE_TTL  = 4 * 3600

nse = Nse()


# ── Cache ─────────────────────────────────────────────────────────────────

def _load_cache() -> dict | None:
    if not CACHE_FILE.exists():
        return None
    try:
        data = json.loads(CACHE_FILE.read_text())
        if time.time() - data.get("generated_at_ts", 0) < CACHE_TTL:
            return data
    except Exception:
        pass
    return None


def _save_cache(data: dict) -> None:
    try:
        CACHE_FILE.write_text(json.dumps(data, default=str))
    except Exception:
        pass


# ── Stage 1: Screening ────────────────────────────────────────────────────

def _get_nifty100_tickers() -> list[str]:
    raw = nse.get_stock_quote_in_index("NIFTY 100")
    return [s["symbol"] for s in raw if s.get("symbol")]


def _stage1_screen(universe: list[str]) -> list[str]:
    qarp_buys: set[str] = set()
    mf_top: set[str] = set()

    try:
        qarp_df = qarp_screener(universe)
        if not qarp_df.empty and "Verdict" in qarp_df.columns:
            qarp_buys = set(
                qarp_df[qarp_df["Verdict"] == "BUY"]["Ticker"]
                .str.replace(".NS", "", regex=False)
                .tolist()
            )
    except Exception as e:
        print(f"QARP screener error: {e}")

    try:
        mf_df = magic_formula_rank(universe)
        if not mf_df.empty:
            top_n = max(1, len(mf_df) // 4)
            mf_top = set(
                mf_df.head(top_n)["Ticker"]
                .str.replace(".NS", "", regex=False)
                .tolist()
            )
    except Exception as e:
        print(f"Magic Formula error: {e}")

    candidates = list(qarp_buys | mf_top)
    return candidates[:25]


# ── Stage 2: Technical enrichment ────────────────────────────────────────

def _analyze_one_ticker(symbol: str) -> dict | None:
    ns = _normalize(symbol)
    try:
        raw = yf.download(ns, period="1y", auto_adjust=True, progress=False, actions=False)
        if raw.empty or len(raw) < 60:
            return None
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        for col in ("Open", "High", "Low", "Close", "Volume"):
            if col not in raw.columns:
                return None

        indicators = _evaluate_indicators(raw)
        summary    = _verdict(indicators)

        def _get_ind(name: str) -> dict:
            return next((i for i in indicators if i["name"] == name), {})

        rsi_ind  = _get_ind("RSI (14)")
        macd_ind = _get_ind("MACD Crossover")
        ema_ind  = _get_ind("EMA Stack")
        adx_ind  = _get_ind("ADX (20)")
        bb_ind   = _get_ind("Bollinger Bands (20)")

        rsi_val = None
        try:
            rsi_val = float(rsi_ind.get("value", "").replace("RSI ", "").split()[0])
        except Exception:
            pass

        info    = yf.Ticker(ns).info or {}
        price   = _safe_float(info.get("currentPrice") or info.get("previousClose"))
        pe      = _safe_float(info.get("forwardPE") or info.get("trailingPE"))
        de_raw  = _safe_float(info.get("debtToEquity"))
        de      = round(de_raw / 100, 2) if de_raw else None
        sector  = info.get("sector", "Unknown")
        company = info.get("shortName", symbol)

        roe = None
        try:
            tk     = yf.Ticker(ns)
            fin_df = tk.financials
            bs_df  = tk.balance_sheet
            net_inc = float(fin_df.loc["Net Income"].iloc[0])
            eq_row  = "Stockholders Equity" if "Stockholders Equity" in bs_df.index else "Common Stock Equity"
            equity  = float(bs_df.loc[eq_row].iloc[0])
            if equity and equity != 0:
                roe = round(net_inc / equity * 100, 2)
        except Exception:
            roe_raw = info.get("returnOnEquity")
            if roe_raw is not None:
                roe = round(float(roe_raw) * 100, 2)

        return {
            "symbol":        symbol,
            "company_name":  company,
            "sector":        sector,
            "current_price": round(price, 2) if price else None,
            "pe":            round(pe, 2) if pe else None,
            "roe":           roe,
            "de":            de,
            "tech_verdict":  summary["verdict"],
            "bullish_count": summary["bullish"],
            "bearish_count": summary["bearish"],
            "neutral_count": summary["neutral"],
            "rsi":           round(rsi_val, 1) if rsi_val else None,
            "macd_signal":   macd_ind.get("signal", "Neutral"),
            "ema_signal":    ema_ind.get("signal", "Neutral"),
            "adx_signal":    adx_ind.get("signal", "Neutral"),
            "bb_signal":     bb_ind.get("signal", "Neutral"),
        }
    except Exception as e:
        print(f"Technical analysis failed for {symbol}: {e}")
        return None


def _stage2_technical(candidates: list[str]) -> list[dict]:
    results = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(_analyze_one_ticker, sym): sym for sym in candidates}
        for future in as_completed(futures):
            r = future.result()
            if r is not None:
                results.append(r)
    return results


# ── Stage 3: Claude reasoning ─────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a senior equity analyst specialising in Indian markets (NSE/BSE).
You evaluate stocks using fundamental quality metrics and technical conditions.

STRICT RULES:
1. Never hallucinate prices. Only reference current_price values given to you.
2. Entry/stop/target must be short (under 10 words) and expressed relative to current_price
   (e.g. "entry near ₹1,240, ~2% below current").
3. quality_verdict must be exactly one of: Genuinely Discounted | Value Trap | Overvalued | Watch
4. conviction must be exactly one of: High | Medium | Low
5. reasoning must be 2-3 sentences maximum.
6. Return ONLY valid JSON with no markdown fences, no preamble.
"""

USER_PROMPT_TEMPLATE = """\
Analyse the {n} candidate stocks below. Each has passed QARP (ROE>20%, D/E<0.5, P/E<15) \
and/or Magic Formula (top EBIT/EV + ROC quartile) quantitative screens.

{stock_json}

Return exactly this JSON structure (include ALL {n} symbols):
{{
  "analyses": [
    {{
      "symbol": "TICKER",
      "quality_verdict": "Genuinely Discounted|Value Trap|Overvalued|Watch",
      "conviction": "High|Medium|Low",
      "entry_comment": "entry near ₹X ...",
      "stop_comment": "stop at ₹Y ...",
      "target_comment": "target ₹Z ...",
      "reasoning": "2-3 sentence analysis."
    }}
  ]
}}
"""


def _stage3_claude(enriched: list[dict]) -> list[dict]:
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in environment")

    prompt_data = [
        {
            "symbol":        s["symbol"],
            "company_name":  s["company_name"],
            "sector":        s["sector"],
            "current_price": s["current_price"],
            "pe":            s["pe"],
            "roe_pct":       s["roe"],
            "de_ratio":      s["de"],
            "tech_verdict":  s["tech_verdict"],
            "rsi":           s["rsi"],
            "macd":          s["macd_signal"],
            "ema_stack":     s["ema_signal"],
            "adx":           s["adx_signal"],
        }
        for s in enriched
    ]

    user_prompt = USER_PROMPT_TEMPLATE.format(
        n=len(enriched),
        stock_json=json.dumps(prompt_data, indent=2),
    )

    client = genai.Client(api_key=api_key)
    # Retry up to 3 times with exponential backoff for rate limit errors
    last_err = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=user_prompt,
                config=genai_types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                ),
            )
            break
        except Exception as e:
            last_err = e
            if attempt < 2 and "429" in str(e):
                wait = 45 + random.randint(0, 10)
                print(f"Gemini 429 on attempt {attempt + 1}, retrying in {wait}s…")
                time.sleep(wait)
            else:
                raise
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    ai_resp   = json.loads(raw)
    ai_by_sym = {a["symbol"]: a for a in ai_resp.get("analyses", [])}

    merged = []
    for stock in enriched:
        ai = ai_by_sym.get(stock["symbol"], {})
        merged.append({
            **stock,
            "quality_verdict": ai.get("quality_verdict", "Watch"),
            "conviction":      ai.get("conviction", "Low"),
            "entry_comment":   ai.get("entry_comment", "—"),
            "stop_comment":    ai.get("stop_comment", "—"),
            "target_comment":  ai.get("target_comment", "—"),
            "reasoning":       ai.get("reasoning", "Insufficient data for AI analysis."),
        })
    return merged


# ── Endpoint ──────────────────────────────────────────────────────────────

@router.get("/analyze")
def run_ai_overview(force: bool = False, check_only: bool = False):
    # check_only: return cached data or 404 — never trigger the pipeline
    if check_only:
        cached = _load_cache()
        if cached:
            return {**cached, "from_cache": True}
        raise HTTPException(status_code=404, detail="No cached analysis available")

    if not force:
        cached = _load_cache()
        if cached:
            return {**cached, "from_cache": True}

    try:
        universe = _get_nifty100_tickers()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch NIFTY 100: {e}")

    if not universe:
        raise HTTPException(status_code=500, detail="NIFTY 100 ticker list is empty")

    try:
        candidates = _stage1_screen(universe)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Screening failed: {e}")

    if not candidates:
        raise HTTPException(status_code=500, detail="No candidates passed value screens")

    try:
        enriched = _stage2_technical(candidates)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Technical analysis failed: {e}")

    if not enriched:
        raise HTTPException(status_code=500, detail="All candidates failed technical analysis")

    try:
        final = _stage3_claude(enriched)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Claude analysis failed: {e}")

    now = datetime.now(timezone.utc)
    result = {
        "stocks":          final,
        "generated_at":    now.isoformat(),
        "generated_at_ts": now.timestamp(),
        "candidate_count": len(final),
        "universe_size":   len(universe),
        "from_cache":      False,
    }
    _save_cache(result)
    return result
