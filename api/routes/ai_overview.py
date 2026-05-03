import hashlib
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from nsetools import Nse

from api.routes.technical import (
    _evaluate_indicators, _verdict, _normalize, _safe_float, _flatten_yf_columns,
)
from api.deps import get_current_user, supabase_client, AuthUser
from core.llm import call_llm

# yfinance .info path is noisy with "Invalid Crumb" 401s — silence those logs.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

router = APIRouter()

CACHE_DIR  = Path(__file__).parent.parent / "ai_cache"
CACHE_DIR.mkdir(exist_ok=True)
CACHE_TTL  = 4 * 3600

ALLOWED_UNIVERSES = [
    "NIFTY 50",
    "NIFTY 100",
    "NIFTY MIDCAP 100",
    "NIFTY SMALLCAP 100",
    "NIFTY BANK",
    "NIFTY IT",
]
LLM_BATCH_SIZE = 25

nse = Nse()


# ── Cache ─────────────────────────────────────────────────────────────────

def _cache_key(universe: str, extras: list[str], provider: str, model: str) -> str:
    raw = f"{universe}|{','.join(sorted(extras))}|{provider}|{model}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def _load_cache(key: str) -> dict | None:
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        if time.time() - data.get("generated_at_ts", 0) < CACHE_TTL:
            return data
    except Exception:
        pass
    return None


def _save_cache(key: str, data: dict) -> None:
    try:
        _cache_path(key).write_text(json.dumps(data, default=str))
    except Exception:
        pass


# ── Stage 1: Universe resolution ──────────────────────────────────────────

def _resolve_universe(name: str, extras: list[str]) -> list[str]:
    if name not in ALLOWED_UNIVERSES:
        raise ValueError(f"Unknown universe: {name}")
    raw = nse.get_stock_quote_in_index(name)
    base = [s["symbol"] for s in raw if s.get("symbol")]
    seen: set[str] = set()
    merged: list[str] = []
    for sym in [*base, *(e.upper() for e in extras)]:
        if sym and sym not in seen:
            seen.add(sym)
            merged.append(sym)
    return merged


# ── Stage 2: Technical enrichment ────────────────────────────────────────

def _safe_info(tk: yf.Ticker) -> dict:
    """Best-effort info fetch. .info fails intermittently with 'Invalid Crumb';
    fall back to fast_info for the few fields we actually need."""
    try:
        info = tk.info
        if info:
            return info
    except Exception:
        pass
    try:
        fi = tk.fast_info
        return {
            "currentPrice":  getattr(fi, "last_price", None),
            "previousClose": getattr(fi, "previous_close", None),
        }
    except Exception:
        return {}


def _safe_roe(tk: yf.Ticker, info: dict) -> float | None:
    try:
        fin_df = tk.financials
        bs_df  = tk.balance_sheet
        if fin_df is None or bs_df is None or fin_df.empty or bs_df.empty:
            raise ValueError("financials unavailable")
        net_inc = float(fin_df.loc["Net Income"].iloc[0])
        eq_row  = "Stockholders Equity" if "Stockholders Equity" in bs_df.index else "Common Stock Equity"
        equity  = float(bs_df.loc[eq_row].iloc[0])
        if equity:
            return round(net_inc / equity * 100, 2)
    except Exception:
        pass
    roe_raw = info.get("returnOnEquity")
    if roe_raw is not None:
        try:
            return round(float(roe_raw) * 100, 2)
        except Exception:
            return None
    return None


def _analyze_one_ticker(symbol: str) -> dict | None:
    ns = _normalize(symbol)
    try:
        raw = yf.download(ns, period="1y", auto_adjust=True, progress=False, actions=False)
        if raw.empty or len(raw) < 60:
            return None
        raw = _flatten_yf_columns(raw)
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

        tk      = yf.Ticker(ns)
        info    = _safe_info(tk)
        price   = _safe_float(info.get("currentPrice") or info.get("previousClose"))
        if price is None:
            try:
                price = _safe_float(raw["Close"].iloc[-1])
            except Exception:
                price = None
        pe      = _safe_float(info.get("forwardPE") or info.get("trailingPE"))
        de_raw  = _safe_float(info.get("debtToEquity"))
        de      = round(de_raw / 100, 2) if de_raw else None
        sector  = info.get("sector", "Unknown")
        company = info.get("shortName") or info.get("longName") or symbol
        roe     = _safe_roe(tk, info)

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


def _stage_technical(candidates: list[str]) -> list[dict]:
    results = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(_analyze_one_ticker, sym): sym for sym in candidates}
        for future in as_completed(futures):
            r = future.result()
            if r is not None:
                results.append(r)
    return results


# ── Stage 3: AI reasoning (provider-agnostic, batched) ───────────────────

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
Analyse the {n} candidate stocks below.

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


def _strip_json_fence(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


def _llm_one_batch(provider: str, model: str, api_key: str, batch: list[dict]) -> dict[str, dict]:
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
        for s in batch
    ]
    user_prompt = USER_PROMPT_TEMPLATE.format(
        n=len(batch),
        stock_json=json.dumps(prompt_data, indent=2),
    )
    raw = call_llm(provider, model, api_key, SYSTEM_PROMPT, user_prompt)
    parsed = json.loads(_strip_json_fence(raw))
    return {a["symbol"]: a for a in parsed.get("analyses", [])}


# ── Helpers shared with endpoints ────────────────────────────────────────

def _read_user_key(auth: AuthUser) -> tuple[str, str, str]:
    sb  = supabase_client(auth)
    res = (sb.table("user_ai_keys")
             .select("provider, model, api_key")
             .eq("user_id", auth.user_id)
             .limit(1)
             .execute())
    if not res.data:
        raise HTTPException(status_code=400, detail="No AI provider configured. Save an API key first.")
    row = res.data[0]
    return row["provider"], row["model"], row["api_key"]


def _parse_extras(extras: str | None) -> list[str]:
    if not extras:
        return []
    return [e.strip().upper() for e in extras.split(",") if e.strip()]


# ── Endpoints ────────────────────────────────────────────────────────────

@router.get("/universes")
def list_universes():
    return ALLOWED_UNIVERSES


@router.get("/cached")
def get_cached(
    universe: str = Query(...),
    extras:   str | None = Query(None),
    auth: AuthUser = Depends(get_current_user),
):
    """Return cached result for a (universe, extras, provider, model) combo, or 404."""
    if universe not in ALLOWED_UNIVERSES:
        raise HTTPException(status_code=400, detail=f"Unknown universe: {universe}")
    provider, model, _ = _read_user_key(auth)
    key = _cache_key(universe, _parse_extras(extras), provider, model)
    cached = _load_cache(key)
    if cached:
        return {**cached, "from_cache": True}
    raise HTTPException(status_code=404, detail="No cached analysis available")


@router.get("/stream")
def stream_ai_overview(
    universe: str = Query(...),
    extras:   str | None = Query(None),
    force:    bool = False,
    auth: AuthUser = Depends(get_current_user),
):
    """SSE stream of pipeline progress and final result.

    Events:
      {"type":"stage","stage":N,"status":"running|done"}
      {"type":"batch","done":i,"total":t}
      {"type":"result","data":{...}}
      {"type":"error","message":"..."}
    """
    if universe not in ALLOWED_UNIVERSES:
        raise HTTPException(status_code=400, detail=f"Unknown universe: {universe}")

    provider, model, api_key = _read_user_key(auth)
    extras_list = _parse_extras(extras)
    key = _cache_key(universe, extras_list, provider, model)

    def _sse(payload: dict) -> str:
        return f"data: {json.dumps(payload, default=str)}\n\n"

    def _gen():
        if not force:
            cached = _load_cache(key)
            if cached:
                for n in (1, 2, 3):
                    yield _sse({"type": "stage", "stage": n, "status": "done"})
                yield _sse({"type": "result", "data": {**cached, "from_cache": True}})
                return

        try:
            yield _sse({"type": "stage", "stage": 1, "status": "running"})
            tickers = _resolve_universe(universe, extras_list)
            if not tickers:
                yield _sse({"type": "error", "message": "Universe is empty"})
                return
            yield _sse({"type": "stage", "stage": 1, "status": "done"})

            yield _sse({"type": "stage", "stage": 2, "status": "running"})
            enriched = _stage_technical(tickers)
            if not enriched:
                yield _sse({"type": "error", "message": "All tickers failed technical analysis"})
                return
            yield _sse({"type": "stage", "stage": 2, "status": "done"})

            yield _sse({"type": "stage", "stage": 3, "status": "running"})
            total_batches = (len(enriched) + LLM_BATCH_SIZE - 1) // LLM_BATCH_SIZE
            yield _sse({"type": "batch", "done": 0, "total": total_batches})

            ai_by_sym: dict[str, dict] = {}
            for idx in range(total_batches):
                batch = enriched[idx * LLM_BATCH_SIZE : (idx + 1) * LLM_BATCH_SIZE]
                ai_by_sym.update(_llm_one_batch(provider, model, api_key, batch))
                yield _sse({"type": "batch", "done": idx + 1, "total": total_batches})

            final = []
            for stock in enriched:
                ai = ai_by_sym.get(stock["symbol"], {})
                final.append({
                    **stock,
                    "quality_verdict": ai.get("quality_verdict", "Watch"),
                    "conviction":      ai.get("conviction", "Low"),
                    "entry_comment":   ai.get("entry_comment", "—"),
                    "stop_comment":    ai.get("stop_comment", "—"),
                    "target_comment":  ai.get("target_comment", "—"),
                    "reasoning":       ai.get("reasoning", "Insufficient data for AI analysis."),
                })
            yield _sse({"type": "stage", "stage": 3, "status": "done"})

            now = datetime.now(timezone.utc)
            result = {
                "stocks":          final,
                "generated_at":    now.isoformat(),
                "generated_at_ts": now.timestamp(),
                "candidate_count": len(final),
                "universe":        universe,
                "extras":          extras_list,
                "provider":        provider,
                "model":           model,
                "from_cache":      False,
            }
            _save_cache(key, result)
            yield _sse({"type": "result", "data": result})
        except Exception as e:
            yield _sse({"type": "error", "message": str(e)})

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )
