import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import market, screener, fundamentals, volatility, portfolio, signals, news, earnings, backtest
from api.routes import user_portfolios, tracker, technical, ai_overview, ai_keys, strategies
from api.routes import legal, subscription, scorecard

app = FastAPI(title="QuantHub API", version="1.0.0", docs_url="/api/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(market.router,       prefix="/api/market",       tags=["market"])
app.include_router(screener.router,     prefix="/api/screener",     tags=["screener"])
app.include_router(fundamentals.router, prefix="/api/fundamentals", tags=["fundamentals"])
app.include_router(volatility.router,   prefix="/api/volatility",   tags=["volatility"])
app.include_router(portfolio.router,    prefix="/api/portfolio",    tags=["portfolio"])
app.include_router(signals.router,      prefix="/api/signals",      tags=["signals"])
app.include_router(news.router,         prefix="/api/news",         tags=["news"])
app.include_router(earnings.router,     prefix="/api/earnings",     tags=["earnings"])
app.include_router(backtest.router,          prefix="/api/backtest",   tags=["backtest"])
app.include_router(user_portfolios.router,   prefix="/api/portfolios", tags=["portfolios"])
app.include_router(tracker.router,           prefix="/api/tracker",    tags=["tracker"])
app.include_router(technical.router,         prefix="/api/technical",  tags=["technical"])
app.include_router(ai_overview.router,       prefix="/api/ai-overview", tags=["ai-overview"])
app.include_router(ai_keys.router,           prefix="/api/ai-keys",    tags=["ai-keys"])
app.include_router(strategies.router,        prefix="/api/strategies",    tags=["strategies"])
app.include_router(legal.router,             prefix="/api/legal",         tags=["legal"])
app.include_router(subscription.router,      prefix="/api/subscription",  tags=["subscription"])
app.include_router(scorecard.router,         prefix="/api/scorecard",     tags=["scorecard"])


@app.get("/api/health")
def health():
    return {"status": "ok"}
