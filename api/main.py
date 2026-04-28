import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import market, screener, fundamentals, volatility, portfolio, signals, news, earnings, backtest

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
app.include_router(backtest.router,     prefix="/api/backtest",     tags=["backtest"])


@app.get("/api/health")
def health():
    return {"status": "ok"}
