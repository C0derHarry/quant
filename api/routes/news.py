import hashlib
import json
import os
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import requests
from fastapi import APIRouter, HTTPException

router = APIRouter()

ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "EDX9QY4BN2YJT3PQ")
AV_BASE = "https://www.alphavantage.co/query"

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


@router.get("/feed")
def get_feed(scope: str = "national", limit: int = 20):
    scope = scope if scope in TOPIC_MAP else "national"

    cache_path = _cache_path(f"feed_{scope}", bucket_minutes=60)
    cached = _load_cache(cache_path)
    if cached:
        return {**cached, "cached": True}

    try:
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
    clean = ticker.replace(".NS", "").replace(".BO", "").replace(".BSE", "").upper()

    cache_path = _cache_path(f"stock_{clean}", bucket_minutes=60)
    cached = _load_cache(cache_path)
    if cached:
        return {**cached, "cached": True}

    try:
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
