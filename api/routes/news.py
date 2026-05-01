import hashlib
import json
import os
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import requests
from fastapi import APIRouter, HTTPException

router = APIRouter()

ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "EDX9QY4BN2YJT3PQ")
AV_BASE           = "https://www.alphavantage.co/query"

MARKETAUX_KEY = os.getenv("MARKETAUX_API_KEY", "")
MX_BASE       = "https://api.marketaux.com/v1/news/all"

CACHE_DIR = Path(__file__).parent.parent / "news_cache"
CACHE_DIR.mkdir(exist_ok=True)

TOPIC_MAP = {
    "national":      "economy_fiscal,economy_monetary,economy_macro,finance",
    "international": "technology,financial_markets,earnings,mergers_and_acquisitions",
}

IST = timezone(timedelta(hours=5, minutes=30))


def _is_market_open() -> bool:
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    return time(9, 15) <= now.time() <= time(15, 30)


def _cache_path(key: str, bucket_minutes: int = 60) -> Path:
    now = datetime.utcnow()
    slot = (now.minute // bucket_minutes) * bucket_minutes
    bucket = now.replace(minute=slot, second=0, microsecond=0)
    tag = bucket.strftime("%Y%m%d_%H%M")
    return CACHE_DIR / f"{key}_{tag}.json"


def _load_cache(path: Path):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return None


def _save_cache(path: Path, data: dict):
    try:
        path.write_text(json.dumps(data))
    except Exception:
        pass


def _parse_av_time(ts: str) -> str:
    """Convert YYYYMMDDTHHMMSS to ISO-8601."""
    try:
        return datetime.strptime(ts, "%Y%m%dT%H%M%S").isoformat()
    except Exception:
        return ts


# ── AlphaVantage helpers ──────────────────────────────────────────────────────

def _normalize(item: dict) -> dict:
    url = item.get("url", "")
    return {
        "id":              hashlib.md5(url.encode()).hexdigest(),
        "title":           item.get("title", ""),
        "summary":         item.get("summary", ""),
        "url":             url,
        "source":          item.get("source", ""),
        "published_at":    _parse_av_time(item.get("time_published", "")),
        "banner_image":    item.get("banner_image") or None,
        "sentiment_score": float(item.get("overall_sentiment_score", 0)),
        "sentiment_label": item.get("overall_sentiment_label", "Neutral"),
        "tickers": [
            {
                "ticker":          t.get("ticker", ""),
                "sentiment_score": float(t.get("ticker_sentiment_score", 0)),
                "sentiment_label": t.get("ticker_sentiment_label", "Neutral"),
            }
            for t in item.get("ticker_sentiment", [])
        ],
        "topics": [
            {
                "topic":           t.get("topic", ""),
                "relevance_score": float(t.get("relevance_score", 0)),
            }
            for t in item.get("topics", [])
        ],
    }


def _fetch_av(params: dict) -> list[dict]:
    params["apikey"] = ALPHA_VANTAGE_KEY
    resp = requests.get(AV_BASE, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    for key in ("Error Message", "Note", "Information"):
        if key in data:
            raise ValueError(data[key])

    return [_normalize(item) for item in data.get("feed", [])]


# ── Marketaux helpers ─────────────────────────────────────────────────────────

def _mx_sentiment_score(sentiment: str) -> float:
    return {"positive": 0.5, "negative": -0.5}.get(sentiment, 0.0)


def _mx_sentiment_label(sentiment: str) -> str:
    return {"positive": "Bullish", "negative": "Bearish"}.get(sentiment, "Neutral")


def _mx_entity_label(score: float) -> str:
    if score > 0.35:  return "Bullish"
    if score > 0.1:   return "Somewhat-Bullish"
    if score > -0.1:  return "Neutral"
    if score > -0.35: return "Somewhat-Bearish"
    return "Bearish"


def _normalize_mx(item: dict) -> dict:
    url       = item.get("url", "")
    sentiment = item.get("sentiment", "neutral")
    entities  = item.get("entities", [])

    tickers = [
        {
            "ticker":          e.get("symbol", ""),
            "sentiment_score": float(e.get("sentiment_score", 0)),
            "sentiment_label": _mx_entity_label(float(e.get("sentiment_score", 0))),
        }
        for e in entities if e.get("symbol")
    ]

    seen_topics: dict[str, float] = {}
    for e in entities:
        industry = e.get("industry")
        if industry:
            score = float(e.get("match_score", 0)) / 100.0
            if industry not in seen_topics or score > seen_topics[industry]:
                seen_topics[industry] = score
    topics = [{"topic": k, "relevance_score": v} for k, v in seen_topics.items()]
    if not topics:
        topics = [{"topic": "india_market", "relevance_score": 1.0}]

    try:
        pub = datetime.fromisoformat(
            item.get("published_at", "").replace("Z", "+00:00")
        ).isoformat()
    except Exception:
        pub = item.get("published_at", "")

    return {
        "id":              hashlib.md5(url.encode()).hexdigest(),
        "title":           item.get("title", ""),
        "summary":         item.get("description") or item.get("snippet", ""),
        "url":             url,
        "source":          item.get("source", ""),
        "published_at":    pub,
        "banner_image":    item.get("image_url") or None,
        "sentiment_score": _mx_sentiment_score(sentiment),
        "sentiment_label": _mx_sentiment_label(sentiment),
        "tickers":         tickers,
        "topics":          topics,
    }


def _fetch_mx(params: dict, limit: int = 20) -> list[dict]:
    full_params = {
        "api_token":       MARKETAUX_KEY,
        "language":        "en",
        "filter_entities": "true",
        "limit":           min(limit, 50),
        **params,
    }
    resp = requests.get(MX_BASE, params=full_params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise ValueError(data["error"].get("message", "Marketaux API error"))
    return [_normalize_mx(item) for item in data.get("data", [])]


def _is_indian_ticker(raw: str) -> bool:
    return raw.upper().endswith((".NS", ".BO", ".BSE"))


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/feed")
def get_feed(scope: str = "national", limit: int = 20):
    scope = scope if scope in TOPIC_MAP else "national"

    cache_path = _cache_path(f"feed_{scope}", bucket_minutes=60)
    cached = _load_cache(cache_path)
    if cached:
        return {**cached, "cached": True}

    try:
        if scope == "national":
            articles = _fetch_mx({"countries": "in"}, limit=limit)
        else:
            articles = _fetch_av({
                "function": "NEWS_SENTIMENT",
                "topics":   TOPIC_MAP[scope],
                "sort":     "LATEST",
                "limit":    min(limit, 50),
            })
        result = {"articles": articles[:limit]}
        _save_cache(cache_path, result)
        return {**result, "cached": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock")
def get_stock_news(ticker: str, limit: int = 10):
    is_indian = _is_indian_ticker(ticker)
    clean = ticker.replace(".NS", "").replace(".BO", "").replace(".BSE", "").upper()

    cache_path = _cache_path(f"stock_{clean}", bucket_minutes=60)
    cached = _load_cache(cache_path)
    if cached:
        return {**cached, "cached": True}

    try:
        if is_indian:
            articles = _fetch_mx({"symbols": clean}, limit=limit)
        else:
            articles = _fetch_av({
                "function": "NEWS_SENTIMENT",
                "tickers":  clean,
                "sort":     "LATEST",
                "limit":    min(limit, 50),
            })
        result = {"articles": articles[:limit]}
        _save_cache(cache_path, result)
        return {**result, "cached": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolio")
def get_portfolio_news(tickers: str, limit: int = 15):
    """tickers: comma-separated, may include .NS/.BO suffixes (e.g. 'TCS.NS,INFY.NS')"""
    raw_list   = [t.strip() for t in tickers.split(",") if t.strip()]
    clean_list = sorted({
        t.replace(".NS", "").replace(".BO", "").replace(".BSE", "").upper()
        for t in raw_list
    })
    if not clean_list:
        raise HTTPException(status_code=400, detail="No tickers provided")

    symbols_key = "_".join(clean_list)
    cache_key   = f"portfolio_{hashlib.md5(symbols_key.encode()).hexdigest()[:8]}"
    cache_path  = _cache_path(cache_key, bucket_minutes=60)
    cached = _load_cache(cache_path)
    if cached:
        return {**cached, "cached": True}

    try:
        articles = _fetch_mx({"symbols": ",".join(clean_list)}, limit=limit)

        ticker_scores: dict[str, list[float]] = {t: [] for t in clean_list}
        for art in articles:
            for ent in art["tickers"]:
                sym = ent["ticker"].upper()
                if sym in ticker_scores:
                    ticker_scores[sym].append(ent["sentiment_score"])

        ticker_sentiment = []
        for sym, scores in ticker_scores.items():
            if scores:
                avg   = sum(scores) / len(scores)
                label = _mx_entity_label(avg)
            else:
                avg   = 0.0
                label = "Neutral"
            ticker_sentiment.append({
                "ticker":        sym,
                "avg_score":     round(avg, 4),
                "label":         label,
                "article_count": len(scores),
            })

        result = {"articles": articles[:limit], "ticker_sentiment": ticker_sentiment}
        _save_cache(cache_path, result)
        return {**result, "cached": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/impact")
def get_impact(ticker: str, published_at: str):
    if not _is_market_open():
        return {"market_open": False}

    clean = ticker.replace(".NS", "").replace(".BO", "").upper()

    cache_path = _cache_path(f"quote_{clean}", bucket_minutes=5)
    cached = _load_cache(cache_path)
    if cached:
        return {**cached, "cached": True}

    try:
        resp = requests.get(AV_BASE, params={
            "function": "GLOBAL_QUOTE",
            "symbol":   clean,
            "apikey":   ALPHA_VANTAGE_KEY,
        }, timeout=10)
        resp.raise_for_status()
        quote = resp.json().get("Global Quote", {})

        price_str = quote.get("05. price", "")
        if not price_str:
            return {"market_open": False}

        change_pct_raw = quote.get("10. change percent", "0%").replace("%", "")
        result = {
            "market_open":   True,
            "current_price": float(price_str),
            "change":         float(quote.get("09. change", 0)),
            "change_pct":     float(change_pct_raw),
            "quote_time":     datetime.now(IST).strftime("%H:%M IST"),
        }
        _save_cache(cache_path, result)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
