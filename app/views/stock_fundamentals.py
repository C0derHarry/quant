# ─────────────────────────────────────────────────────────────────────────────
# PAGE - STOCK FUNDAMENTALS
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
import sys
import os
import plotly.graph_objects as go
import plotly.express as px
from nsetools import Nse
from plotly.subplots import make_subplots
from concurrent.futures import ThreadPoolExecutor

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.data import fetch_ohlcv_data
from core.stats import (
    CAGR, volatility, Sharpe, max_dd, calmar,
    rolling_sharpe, rolling_calmar, rolling_cagr,
    drawdown_analysis, underwater_periods, stationarity
)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

PERIOD_INTERVAL_MAP: dict[str, list[str]] = {
    "1d":  ["1m", "2m", "5m", "15m", "30m", "60m", "90m"],
    "5d":  ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1d"],
    "1mo": ["30m", "60m", "90m", "1d", "5d", "1wk"],
    "3mo": ["30m", "1h", "1d", "5d", "1wk", "1mo"],
    "6mo": ["1d", "5d", "1wk", "1mo"],
    "1y":  ["1d", "5d", "1wk", "1mo"],
    "2y":  ["1d", "5d", "1wk", "1mo"],
    "5y":  ["1d", "5d", "1wk", "1mo"],
    "10y": ["1d", "5d", "1wk", "1mo"],
    "ytd": ["1d", "5d", "1wk", "1mo"],
    "max": ["1d", "5d", "1wk", "1mo"],
}

PERIOD_LABELS: dict[str, str] = {
    "1d": "1 Day", "5d": "5 Days", "1mo": "1 Month", "3mo": "3 Months",
    "6mo": "6 Months", "1y": "1 Year", "2y": "2 Years", "5y": "5 Years",
    "10y": "10 Years", "ytd": "Year-to-Date", "max": "Maximum",
}

INTERVAL_LABELS: dict[str, str] = {
    "1m": "1 Minute", "2m": "2 Minutes", "5m": "5 Minutes", "15m": "15 Minutes",
    "30m": "30 Minutes", "60m": "60 Minutes", "90m": "90 Minutes",
    "1h": "1 Hour", "1d": "1 Day", "5d": "5 Days", "1wk": "1 Week", "1mo": "1 Month",
}

# period → days mapping for fetch_ohlcv_data
PERIOD_TO_DAYS: dict[str, int] = {
    "1d": 1, "5d": 5, "1mo": 30, "3mo": 90, "6mo": 180,
    "1y": 365, "2y": 730, "5y": 1825, "10y": 3650,
    "ytd": (pd.Timestamp.today() - pd.Timestamp(pd.Timestamp.today().year, 1, 1)).days,
    "max": 7300,
}

# interval → timeframe (bars/year) for KPI annualisation
INTERVAL_TIMEFRAME: dict[str, int] = {
    "1m": 252 * 390, "2m": 252 * 195, "5m": 252 * 78, "15m": 252 * 26,
    "30m": 252 * 13, "60m": 252 * 7, "90m": 252 * 5, "1h": 252 * 7,
    "1d": 252, "5d": 52, "1wk": 52, "1mo": 12,
}

MIN_WINDOW_BARS: dict[tuple[str, str], int] = {
    ("1d",  "1m"):  30,  ("1d",  "5m"):  12,  ("1d",  "15m"): 6,
    ("5d",  "1m"):  60,  ("5d",  "5m"):  24,  ("5d",  "1d"):  3,
    ("1mo", "1d"):   5,  ("1mo", "1wk"):  2,
    ("3mo", "1d"):  10,  ("3mo", "1wk"):  4,  ("3mo", "1mo"): 2,
    ("6mo", "1d"):  21,  ("6mo", "1wk"):  8,  ("6mo", "1mo"): 3,
    ("1y",  "1d"):  63,  ("1y",  "5d"):  13,  ("1y",  "1wk"): 12,  ("1y",  "1mo"): 4,
    ("2y",  "1d"): 126,  ("2y",  "5d"):  26,  ("2y",  "1wk"): 26,  ("2y",  "1mo"): 6,
    ("5y",  "1d"): 252,  ("5y",  "5d"):  52,  ("5y",  "1wk"): 52,  ("5y",  "1mo"): 12,
    ("10y", "1d"): 252,  ("10y", "5d"): 104,  ("10y","1wk"): 104,  ("10y","1mo"): 24,
    ("ytd", "1d"):  21,  ("ytd", "1wk"):  8,  ("ytd", "1mo"): 3,
    ("max", "1d"): 252,  ("max", "5d"): 104,  ("max","1wk"): 104,  ("max","1mo"): 24,
}

BENCHMARK_TICKERS: dict[str, str] = {
    "Nifty 50":   "^NSEI",
    "Sensex":     "^BSESN",
    "Nifty Bank": "^NSEBANK",
    "Nifty IT":   "^CNXIT",
}

NSE_SECTORS = [
    "NIFTY 50", "NIFTY BANK", "NIFTY IT", "NIFTY PHARMA",
    "NIFTY AUTO", "NIFTY FMCG", "NIFTY METAL", "NIFTY ENERGY",
    "NIFTY INFRA", "NIFTY FIN SERVICE",
]

BSE_SECTORS: dict[str, list[str]] = {
    "BSE SENSEX": ["RELIANCE", "TCS", "HDFCBANK", "INFY", "HINDUNILVR",
                   "ICICIBANK", "KOTAKBANK", "SBIN", "BAJFINANCE", "BHARTIARTL",
                   "ASIANPAINT", "MARUTI", "LT", "AXISBANK", "TITAN"],
    "BSE IT":     ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM"],
    "BSE PHARMA": ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "APOLLOHOSP"],
}


# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def get_min_window(period: str, interval: str) -> int:
    return MIN_WINDOW_BARS.get((period, interval), 5)


def fetch_name(symbol: str) -> tuple[str, str]:
    suffix = ".NS" if not symbol.endswith((".NS", ".BO")) else ""
    try:
        return symbol, yf.Ticker(f"{symbol}{suffix}").info.get("shortName", symbol)
    except Exception:
        return symbol, symbol


@st.cache_data(ttl=300, show_spinner=False)
def cached_fetch(symbols: tuple[str, ...], days: int, interval: str) -> dict[str, pd.DataFrame]:
    return fetch_ohlcv_data(list(symbols), days, interval)


# ─────────────────────────────────────────────────────────────────────────────
# KPI WRAPPERS  (call your real functions from kpi.py / stationarity.py)
# ─────────────────────────────────────────────────────────────────────────────

def get_static_kpi(df: pd.DataFrame, symbol: str, timeframe: int) -> dict:
    if df.empty or "Close" not in df.columns:
        return {}
    try:
        cagr_val   = CAGR(df, timeframe)
        vol_val    = volatility(df, timeframe)
        sharpe_val = Sharpe(df, timeframe)
        mdd_val    = max_dd(df)
        calmar_val = calmar(df, timeframe)

        prices  = df["Close"].dropna()
        returns = prices.pct_change().dropna()
        skew_val     = float(returns.skew())
        kurt_val     = float(returns.kurt())
        pos_days_pct = (returns > 0).sum() / len(returns) * 100

        diffs = stationarity(df)

        return {
            "CAGR (%)":                  round(cagr_val * 100, 2),
            "Annualised Volatility (%)": round(vol_val * 100, 2),
            "Sharpe Ratio":              round(sharpe_val, 2),
            "Max Drawdown (%)":          round(mdd_val * 100, 2),
            "Calmar Ratio":              round(calmar_val, 2),
            "Skewness":                  round(skew_val, 3),
            "Excess Kurtosis":           round(kurt_val, 3),
            "% Positive Periods":        round(pos_days_pct, 1),
            "Stationarity (diffs)":      int(diffs),
        }
    except Exception as e:
        st.warning(f"KPI error for {symbol}: {e}")
        return {}


def get_rolling_kpi(df: pd.DataFrame, symbol: str, timeframe: int, window: int) -> pd.DataFrame:
    if df.empty or "Close" not in df.columns:
        return pd.DataFrame()
    try:
        roll_cagr   = rolling_cagr(df, timeframe, window)
        roll_sharpe = rolling_sharpe(df, timeframe, window)
        roll_calmar = rolling_calmar(df, timeframe, window)

        dd, _, _ = drawdown_analysis(df)

        out = pd.DataFrame({
            "Rolling CAGR (%)":        roll_cagr * 100,
            "Rolling Sharpe":          roll_sharpe,
            "Rolling Calmar":          roll_calmar,
            "Drawdown (%)":            dd * 100,
        })
        return out.dropna()
    except Exception as e:
        st.warning(f"Rolling KPI error for {symbol}: {e}")
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# UI COMPONENT HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def stationarity_widget_html(diffs: int) -> str:
    if diffs == 0:
        label, css, tip = (
            "✅ Already Stationary (0 differences needed)", "stat-green",
            "The returns series is stationary. No differencing required.",
        )
    elif diffs == 1:
        label, css, tip = (
            "🟡 Near-Stationary (1 difference needed)", "stat-amber",
            "Returns show mild autocorrelation. 1 level of differencing recommended.",
        )
    elif diffs == 2:
        label, css, tip = (
            "🔴 Non-Stationary (2 differences needed)", "stat-red",
            "Strong autocorrelation detected. 2 levels of differencing required.",
        )
    else:
        label, css, tip = (
            "🔴 Highly Non-Stationary (3+ differences needed)", "stat-red",
            "Very high persistence in returns. Consider structural breaks.",
        )
    return (
        f'<div class="stat-widget {css}">{label}'
        f'<br><span style="font-size:11px;font-weight:400;opacity:.8">{tip}</span></div>'
    )


def kpi_card_html(label: str, value: str, color_class: str = "kpi-neu") -> str:
    return f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value {color_class}">{value}</div>
    </div>"""


def color_class_for(label: str, value) -> str:
    pos_kpis = {"CAGR (%)", "Sharpe Ratio", "Calmar Ratio", "% Positive Periods"}
    neg_kpis = {"Max Drawdown (%)", "Annualised Volatility (%)"}
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "kpi-neu"
    if label in pos_kpis:
        return "kpi-pos" if v > 0 else "kpi-neg"
    if label in neg_kpis:
        return "kpi-neg" if v < 0 else "kpi-pos"
    return "kpi-neu"


def build_price_chart(datasets: dict[str, pd.DataFrame], title: str) -> go.Figure:
    fig    = go.Figure()
    colors = ["#58a6ff", "#3fb950", "#d29922", "#f85149", "#bc8cff", "#ff7b72", "#39d353", "#ffa657"]
    for idx, (name, df) in enumerate(datasets.items()):
        if df.empty or "Close" not in df.columns:
            continue
        prices     = df["Close"].dropna()
        normalised = prices / prices.iloc[0] * 100
        fig.add_trace(go.Scatter(
            x=normalised.index, y=normalised, name=name,
            line=dict(color=colors[idx % len(colors)], width=1.8),
            hovertemplate=f"<b>{name}</b><br>%{{x}}<br>%{{y:.1f}}<extra></extra>",
        ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color="#e6edf3")),
        paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
        font=dict(color="#8b949e", size=12),
        xaxis=dict(gridcolor="#21262d", zeroline=False),
        yaxis=dict(gridcolor="#21262d", zeroline=False, title="Normalised (base = 100)"),
        legend=dict(bgcolor="#161b22", bordercolor="#30363d", borderwidth=1),
        margin=dict(l=10, r=10, t=40, b=10),
        hovermode="x unified",
    )
    return fig


def build_rolling_chart(rolling_df: pd.DataFrame) -> go.Figure:
    cols   = rolling_df.columns.tolist()
    fig    = make_subplots(rows=len(cols), cols=1, shared_xaxes=True,
                           subplot_titles=cols, vertical_spacing=0.06)
    colors = ["#58a6ff", "#3fb950", "#d29922", "#f85149"]
    for i, col in enumerate(cols, start=1):
        fig.add_trace(go.Scatter(
            x=rolling_df.index, y=rolling_df[col], name=col,
            line=dict(color=colors[(i - 1) % len(colors)], width=1.6),
            fill="tozeroy" if i == 1 else None,
            fillcolor="rgba(88,166,255,0.07)" if i == 1 else None,
            hovertemplate=f"<b>{col}</b>: %{{y:.2f}}<extra></extra>",
        ), row=i, col=1)
    fig.update_layout(
        height=240 * len(cols),
        paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
        font=dict(color="#8b949e", size=12),
        showlegend=False,
        margin=dict(l=10, r=10, t=30, b=10),
    )
    for i in range(1, len(cols) + 1):
        fig.update_xaxes(gridcolor="#21262d", row=i, col=1)
        fig.update_yaxes(gridcolor="#21262d", row=i, col=1)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PAGE FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def get_fundamentals():

    nse = Nse()

    # ── CSS ──────────────────────────────────────────────────────────────────
    st.markdown("""
    <style>
        [data-testid="stAppViewContainer"] { background: #0d1117; color: #e6edf3; }
        [data-testid="stSidebar"]          { background: #161b22; border-right: 1px solid #30363d; }
        [data-testid="stHeader"]           { background: transparent; }

        .strategy-banner {
            background: linear-gradient(135deg, #1a2332 0%, #0d1b2a 100%);
            border: 1px solid #2d4a6e;
            border-left: 4px solid #1f6feb;
            border-radius: 8px;
            padding: 14px 20px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .strategy-banner .icon { font-size: 22px; }
        .strategy-banner .text { font-size: 14px; color: #8b949e; line-height: 1.5; }
        .strategy-banner .text b { color: #58a6ff; }
        .strategy-banner .link  { color: #1f6feb; font-weight: 600; text-decoration: none; }

        .section-header {
            font-size: 13px; font-weight: 700; letter-spacing: 0.08em;
            text-transform: uppercase; color: #8b949e;
            padding: 8px 0 4px 0; border-bottom: 1px solid #21262d; margin-bottom: 12px;
        }

        .kpi-card {
            background: #161b22; border: 1px solid #30363d; border-radius: 10px;
            padding: 16px 18px; text-align: center; transition: border-color 0.2s;
        }
        .kpi-card:hover { border-color: #58a6ff; }
        .kpi-label { font-size: 11px; font-weight: 600; letter-spacing: 0.06em;
                     text-transform: uppercase; color: #8b949e; margin-bottom: 6px; }
        .kpi-value { font-size: 22px; font-weight: 700; color: #e6edf3; }
        .kpi-pos   { color: #3fb950; }
        .kpi-neg   { color: #f85149; }
        .kpi-neu   { color: #d29922; }

        .stat-widget {
            border-radius: 10px; padding: 18px 20px; text-align: center;
            font-weight: 700; font-size: 14px; border: 1px solid; letter-spacing: 0.04em;
        }
        .stat-green { background: #0d2e1a; border-color: #3fb950; color: #3fb950; }
        .stat-amber { background: #2d2008; border-color: #d29922; color: #d29922; }
        .stat-red   { background: #2d0f0f; border-color: #f85149; color: #f85149; }

        .info-box {
            background: #161b22; border: 1px solid #30363d; border-radius: 8px;
            padding: 12px 16px; font-size: 13px; color: #8b949e;
        }

        #MainMenu { visibility: hidden; }
        footer    { visibility: hidden; }
    </style>
    """, unsafe_allow_html=True)

    # ── Session state ─────────────────────────────────────────────────────────
    for key, default in [
        ("selected_stocks", []),
        ("exchange", "NSE"),
        ("current_page", 0),
        ("selected_sector", None),
        ("search_query", ""),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    # ── Strategy banner ───────────────────────────────────────────────────────
    st.markdown("""
    <div class="strategy-banner">
        <div class="icon">📌</div>
        <div class="text">
            <b>Buy &amp; Hold Strategy</b> &nbsp;—&nbsp; All KPIs on this page assume a simple
            buy-and-hold approach. No rebalancing, no active signals.
            Want to test momentum, mean-reversion, or factor strategies?
            &nbsp;<a class="link" href="#">→ Go to Backtesting Strategies</a>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("## 📈 Stock Deep-Dive Analysis")
    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 1 — STOCK BROWSER
    # ─────────────────────────────────────────────────────────────────────────
    st.markdown("### 🔍 Browse & Select Stocks")

    col1, col2, col3 = st.columns([1, 2, 3])

    with col1:
        exchange = st.radio(
            "Exchange", ["NSE", "BSE"], horizontal=True,
            index=0 if st.session_state.exchange == "NSE" else 1,
        )
        if exchange != st.session_state.exchange:
            st.session_state.exchange        = exchange
            st.session_state.current_page   = 0
            st.session_state.selected_sector = None
            st.session_state.search_query   = ""
            st.rerun()

    with col2:
        sectors        = NSE_SECTORS if st.session_state.exchange == "NSE" else list(BSE_SECTORS.keys())
        sector_options = [None] + sectors
        sector = st.selectbox(
            "Sector / Index", options=sector_options, index=0,
            format_func=lambda x: "All stocks" if x is None else x,
        )
        if sector != st.session_state.selected_sector:
            st.session_state.selected_sector = sector
            st.session_state.current_page   = 0
            st.session_state.search_query   = ""
            st.rerun()

    with col3:
        search_query = st.text_input("", placeholder="Search stock symbol…",
                                     value=st.session_state.search_query)
        if search_query != st.session_state.search_query:
            st.session_state.search_query = search_query
            st.session_state.current_page = 0
            st.rerun()

    # Resolve symbol list
    @st.cache_data(ttl=86400)
    def get_nse_symbols() -> list[str]:
        try:
            from nsetools import Nse
            return sorted(nse.get_stock_codes().keys())
        except Exception:
            return []

    @st.cache_data(ttl=86400)
    def get_bse_symbols() -> list[str]:
        return sorted({s for stocks in BSE_SECTORS.values() for s in stocks})

    def get_sector_symbols(exchange: str, sector: str) -> list[str]:
        if exchange == "NSE":
            try:
                from nsetools import Nse
                return nse.get_stocks_in_index(sector)
            except Exception:
                return []
        return BSE_SECTORS.get(sector, [])

    if st.session_state.selected_sector:
        all_symbols = get_sector_symbols(st.session_state.exchange, st.session_state.selected_sector)
    elif st.session_state.exchange == "NSE":
        all_symbols = get_nse_symbols()
    else:
        all_symbols = get_bse_symbols()

    if st.session_state.search_query:
        q = st.session_state.search_query.upper()
        all_symbols = [s for s in all_symbols if q in s.upper()]

    # Paginated list
    PAGE_SIZE    = 10
    total_pages  = max(1, -(-len(all_symbols) // PAGE_SIZE))
    current_page = min(st.session_state.current_page, total_pages - 1)
    page_symbols = all_symbols[current_page * PAGE_SIZE: (current_page + 1) * PAGE_SIZE]

    st.caption(
        f"Showing {current_page * PAGE_SIZE + 1}–"
        f"{min((current_page + 1) * PAGE_SIZE, len(all_symbols))} of {len(all_symbols)} stocks"
    )

    h1, h2, h3 = st.columns([2, 5, 2])
    h1.markdown("**Symbol**")
    h2.markdown("**Name**")
    h3.markdown("**Action**")
    st.markdown("<hr style='margin:4px 0'>", unsafe_allow_html=True)

    with ThreadPoolExecutor(max_workers=10) as ex:
        name_map = dict(ex.map(fetch_name, page_symbols))

    for symbol in page_symbols:
        c1, c2, c3 = st.columns([2, 5, 2])
        c1.markdown(f"`{symbol}`")
        c2.markdown(name_map.get(symbol, symbol))
        with c3:
            already = symbol in st.session_state.selected_stocks
            if already:
                st.button("✓ Added", key=f"add_{symbol}", disabled=True, use_container_width=True)
            else:
                if st.button("+ Add", key=f"add_{symbol}", use_container_width=True):
                    st.session_state.selected_stocks.append(symbol)
                    st.rerun()

    st.markdown("<hr style='margin:4px 0'>", unsafe_allow_html=True)

    p1, p2, p3 = st.columns([1, 3, 1])
    with p1:
        if st.button("← Prev", disabled=current_page == 0, use_container_width=True):
            st.session_state.current_page -= 1
            st.rerun()
    with p2:
        st.markdown(
            f"<p style='text-align:center;padding-top:8px;'>Page {current_page + 1} of {total_pages}</p>",
            unsafe_allow_html=True,
        )
    with p3:
        if st.button("Next →", disabled=current_page >= total_pages - 1, use_container_width=True):
            st.session_state.current_page += 1
            st.rerun()

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 2 — SELECTED STOCKS & CONFIGURATION
    # ─────────────────────────────────────────────────────────────────────────
    st.markdown("### ⚙️ Configuration")

    # Selected stocks chips with remove buttons
    if st.session_state.selected_stocks:
        st.markdown(f"**Selected Stocks ({len(st.session_state.selected_stocks)})**")
        chip_cols = st.columns(min(len(st.session_state.selected_stocks), 6))
        for i, symbol in enumerate(st.session_state.selected_stocks):
            with chip_cols[i % 6]:
                if st.button(f"✕ {symbol}", key=f"remove_{symbol}", use_container_width=True):
                    st.session_state.selected_stocks.remove(symbol)
                    st.rerun()
        if st.button("Clear All", type="secondary"):
            st.session_state.selected_stocks = []
            st.rerun()
    else:
        st.info("No stocks selected yet. Add stocks from the browser above.")
        st.stop()

    st.markdown("")

    # Primary stock selector (from selected_stocks only)
    cfg1, cfg2, cfg3 = st.columns(3)

    with cfg1:
        primary_symbol = st.selectbox(
            "Primary Stock (for deep-dive)",
            options=st.session_state.selected_stocks,
            index=0,
            key="primary_stock_select",
        )

    # Time period
    with cfg2:
        period_options = list(PERIOD_LABELS.keys())
        period_display = list(PERIOD_LABELS.values())
        selected_period_label = st.selectbox(
            "Time Period", options=period_display, index=period_options.index("1y"),
        )
        selected_period = period_options[period_display.index(selected_period_label)]

    # Interval (filtered by period)
    with cfg3:
        valid_intervals       = PERIOD_INTERVAL_MAP.get(selected_period, ["1d"])
        valid_interval_labels = [INTERVAL_LABELS[i] for i in valid_intervals if i in INTERVAL_LABELS]
        default_int_idx = 0
        if "1d" in valid_intervals and selected_period in ("6mo", "1y", "2y", "5y", "10y", "max", "ytd"):
            default_int_idx = valid_intervals.index("1d")
        selected_interval_label = st.selectbox(
            "Interval", options=valid_interval_labels, index=default_int_idx,
        )
        selected_interval = valid_intervals[valid_interval_labels.index(selected_interval_label)]

    timeframe = INTERVAL_TIMEFRAME.get(selected_interval, 252)

    # KPI mode + rolling window
    kpi_col, bench_col = st.columns([2, 2])

    with kpi_col:
        st.markdown('<div class="section-header">KPI Mode</div>', unsafe_allow_html=True)
        kpi_mode = st.radio("View", options=["Static KPIs", "Rolling KPIs"], horizontal=True)

        rolling_window = None
        if kpi_mode == "Rolling KPIs":
            min_win      = get_min_window(selected_period, selected_interval)
            win_unit_hint = {
                "1m": "minutes", "2m": "minutes", "5m": "minutes", "15m": "minutes",
                "30m": "minutes", "60m": "minutes", "90m": "minutes", "1h": "hours",
                "1d": "trading days", "5d": "weeks", "1wk": "weeks", "1mo": "months",
            }.get(selected_interval, "bars")
            rolling_window = st.slider(
                f"Rolling Window ({win_unit_hint})",
                min_value=min_win,
                max_value=max(min_win * 6, min_win + 10),
                value=min_win,
                step=1,
                help=f"Minimum {min_win} {win_unit_hint} for this period/interval combination.",
            )
            st.markdown(
                f'<div class="info-box">🔒 Minimum window locked to <b>{min_win}</b> {win_unit_hint} '
                f'for statistical robustness.</div>',
                unsafe_allow_html=True,
            )

    with bench_col:
        st.markdown('<div class="section-header">Benchmarks</div>', unsafe_allow_html=True)
        show_benchmarks = st.toggle("Compare with indices", value=False)
        selected_benchmarks: list[str] = []
        if show_benchmarks:
            selected_benchmarks = st.multiselect(
                "Select Benchmarks",
                options=list(BENCHMARK_TICKERS.keys()),
                default=["Nifty 50"],
            )

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 3 — FETCH DATA
    # ─────────────────────────────────────────────────────────────────────────

    # yfinance intraday history limits (calendar days)
    INTERVAL_MAX_DAYS: dict[str, int] = {
        "1m": 7, "2m": 60, "5m": 60, "15m": 60,
        "30m": 60, "60m": 730, "90m": 60, "1h": 730,
        "1d": 36500, "5d": 36500, "1wk": 36500, "1mo": 36500,
    }
    requested_days = PERIOD_TO_DAYS.get(selected_period, 365)
    max_days       = INTERVAL_MAX_DAYS.get(selected_interval, 36500)
    days           = min(requested_days, max_days)

    # Append exchange suffix so yfinance can resolve the ticker.
    # Benchmarks (^NSEI etc.) already have their own prefix — leave them as-is.
    suffix = ".NS" if st.session_state.exchange == "NSE" else ".BO"

    def to_yf_symbol(sym: str) -> str:
        if sym.startswith("^") or sym.endswith((".NS", ".BO")):
            return sym
        return f"{sym}{suffix}"

    # Build fetch list (yfinance symbols) and reverse map back to bare symbols
    stock_yf_symbols = [to_yf_symbol(s) for s in st.session_state.selected_stocks]
    yf_to_bare       = {to_yf_symbol(s): s for s in st.session_state.selected_stocks}

    bench_yf_symbols = [BENCHMARK_TICKERS[b] for b in selected_benchmarks] if show_benchmarks else []

    all_symbols_to_fetch = stock_yf_symbols + bench_yf_symbols

    with st.spinner("Fetching market data…"):
        raw_data = cached_fetch(tuple(all_symbols_to_fetch), days, selected_interval)

    # Split portfolio vs benchmark data, keyed by bare symbol / benchmark name
    stock_data: dict[str, pd.DataFrame] = {
        yf_to_bare[yf_sym]: raw_data[yf_sym]
        for yf_sym in stock_yf_symbols
        if yf_sym in raw_data
    }
    benchmark_data: dict[str, pd.DataFrame] = {
        bname: raw_data[BENCHMARK_TICKERS[bname]]
        for bname in selected_benchmarks
        if BENCHMARK_TICKERS[bname] in raw_data
    } if show_benchmarks else {}

    if primary_symbol not in stock_data:
        st.error(
            f"⚠️  Could not fetch data for `{primary_symbol}` ({to_yf_symbol(primary_symbol)}). "
            "Try a different period/interval combination."
        )
        st.stop()

    primary_df = stock_data[primary_symbol]

    print(primary_df)

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 4 — STOCK HEADER
    # ─────────────────────────────────────────────────────────────────────────
    
    if isinstance(primary_df.columns, pd.MultiIndex):
        primary_df.columns = primary_df.columns.get_level_values(-1)    

    latest_close = primary_df["Close"].iloc[-1]
    prev_close   = primary_df["Close"].iloc[-2] if len(primary_df) > 1 else latest_close
    day_chg      = latest_close - prev_close
    day_chg_pct  = day_chg / prev_close * 100 if prev_close else 0
    chg_color    = "#3fb950" if day_chg >= 0 else "#f85149"
    chg_arrow    = "▲" if day_chg >= 0 else "▼"
    last_dt      = primary_df.index[-1]
    last_dt_str  = (
        last_dt.strftime("%d %b %Y %H:%M")
        if selected_interval not in ("1d", "5d", "1wk", "1mo")
        else last_dt.strftime("%d %b %Y")
    )

    st.markdown(f"""
    <div style="display:flex;align-items:baseline;gap:16px;margin-bottom:4px;">
        <span style="font-size:26px;font-weight:700;color:#e6edf3;">{primary_symbol}</span>
        <span style="font-size:13px;color:#8b949e;background:#21262d;
                     border-radius:4px;padding:2px 8px;">
            {st.session_state.exchange} · {selected_period_label} · {selected_interval_label}
        </span>
    </div>
    <div style="display:flex;align-items:baseline;gap:12px;margin-bottom:20px;">
        <span style="font-size:28px;font-weight:700;color:#e6edf3;">₹{latest_close:,.2f}</span>
        <span style="font-size:16px;font-weight:600;color:{chg_color};">
            {chg_arrow} ₹{abs(day_chg):,.2f} ({abs(day_chg_pct):.2f}%)
        </span>
        <span style="font-size:12px;color:#8b949e;">{last_dt_str}</span>
    </div>
    """, unsafe_allow_html=True)

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 5 — PRICE CHART
    # ─────────────────────────────────────────────────────────────────────────
    chart_datasets: dict[str, pd.DataFrame] = {**stock_data, **benchmark_data}

    tab_price, tab_volume = st.tabs(["📊 Price (Normalised)", "📦 Volume"])

    with tab_price:
        st.plotly_chart(
            build_price_chart(chart_datasets, f"Normalised Price — {selected_period_label}"),
            use_container_width=True,
            config={"displayModeBar": False},
        )

    with tab_volume:
        if "Volume" in primary_df.columns:
            fig_vol = go.Figure()
            fig_vol.add_trace(go.Bar(
                x=primary_df.index, y=primary_df["Volume"],
                marker_color="#1f6feb", name="Volume",
                hovertemplate="Date: %{x}<br>Volume: %{y:,.0f}<extra></extra>",
            ))
            fig_vol.update_layout(
                paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                font=dict(color="#8b949e"), margin=dict(l=10, r=10, t=10, b=10),
                xaxis=dict(gridcolor="#21262d"), yaxis=dict(gridcolor="#21262d"),
            )
            st.plotly_chart(fig_vol, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("Volume data not available for this symbol.")

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 6 — KPIs
    # ─────────────────────────────────────────────────────────────────────────
    st.divider()
    mode_icon = "🔄" if kpi_mode == "Rolling KPIs" else "📌"
    st.markdown(f"### {mode_icon} {kpi_mode} — {primary_symbol}")

    if kpi_mode == "Static KPIs":
        static_kpis = get_static_kpi(primary_df, primary_symbol, timeframe)

        if static_kpis:
            # Stationarity widget
            diffs_needed = int(static_kpis.pop("Stationarity (diffs)", 0))
            st.markdown('<div class="section-header">Stationarity</div>', unsafe_allow_html=True)
            sw_col, info_col = st.columns([2, 3])
            with sw_col:
                st.markdown(stationarity_widget_html(diffs_needed), unsafe_allow_html=True)
            with info_col:
                st.markdown("""
                <div class="info-box">
                    <b>How to read this:</b><br>
                    Measures how many times the returns series must be differenced to become
                    stationary (constant mean &amp; variance), using ADF + KPSS tests.<br><br>
                    <b>Green</b> → Already stationary &nbsp;|&nbsp;
                    <b>Amber</b> → 1 difference &nbsp;|&nbsp;
                    <b>Red</b> → 2–3 differences needed
                </div>
                """, unsafe_allow_html=True)

            st.markdown("")
            st.markdown('<div class="section-header">Performance KPIs</div>', unsafe_allow_html=True)

            kpi_items = list(static_kpis.items())
            cols      = st.columns(4)
            for i, (label, val) in enumerate(kpi_items):
                formatted = f"{float(val):,.2f}" if label != "Stationarity (diffs)" else str(int(val))
                clr       = color_class_for(label, val)
                with cols[i % 4]:
                    st.markdown(kpi_card_html(label, formatted, clr), unsafe_allow_html=True)
        else:
            st.warning("Could not compute KPIs — insufficient data for the selected period/interval.")

    else:  # Rolling KPIs
        rolling_df = get_rolling_kpi(primary_df, primary_symbol, timeframe, rolling_window)

        # Always show stationarity alongside rolling
        static_tmp   = get_static_kpi(primary_df, primary_symbol, timeframe)
        diffs_needed = int(static_tmp.get("Stationarity (diffs)", 0))
        st.markdown('<div class="section-header">Stationarity (full series)</div>', unsafe_allow_html=True)
        sw_col, _ = st.columns([2, 3])
        with sw_col:
            st.markdown(stationarity_widget_html(diffs_needed), unsafe_allow_html=True)
        st.markdown("")

        if not rolling_df.empty:
            st.markdown(
                f'<div class="section-header">Rolling charts — window = {rolling_window} bars</div>',
                unsafe_allow_html=True,
            )
            st.plotly_chart(
                build_rolling_chart(rolling_df),
                use_container_width=True,
                config={"displayModeBar": False},
            )
            with st.expander("📋 Rolling KPI Summary Statistics"):
                st.dataframe(
                    rolling_df.describe().T.style.format("{:.2f}")
                        .background_gradient(cmap="RdYlGn", axis=0),
                    use_container_width=True,
                )
        else:
            st.warning("Not enough data for the chosen window. Try a shorter window or longer period.")

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 7 — PORTFOLIO COMPARISON
    # ─────────────────────────────────────────────────────────────────────────
    if len(stock_data) > 1:
        st.divider()
        st.markdown("### 💼 Portfolio Comparison")

        rows = []
        for sym, df in stock_data.items():
            kpis = get_static_kpi(df, sym, timeframe)
            if kpis:
                kpis.pop("Stationarity (diffs)", None)
                rows.append({"Stock": sym, **kpis})

        if rows:
            cmp_df = pd.DataFrame(rows).set_index("Stock")
            st.dataframe(
                cmp_df.style.format("{:.2f}")
                    .background_gradient(subset=["CAGR (%)"],        cmap="RdYlGn")
                    .background_gradient(subset=["Sharpe Ratio"],    cmap="RdYlGn")
                    .background_gradient(subset=["Max Drawdown (%)"], cmap="RdYlGn_r"),
                use_container_width=True,
            )

            cmp_metric = st.selectbox("Compare by", options=cmp_df.columns.tolist(),
                                      index=0, key="compare_metric")
            bar_data = cmp_df[cmp_metric].reset_index()
            fig_bar  = px.bar(
                bar_data, x="Stock", y=cmp_metric,
                color=cmp_metric,
                color_continuous_scale=["#f85149", "#d29922", "#3fb950"],
                template="plotly_dark",
            )
            fig_bar.update_layout(
                paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                font=dict(color="#8b949e"), coloraxis_showscale=False,
                margin=dict(l=10, r=10, t=30, b=10),
            )
            st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 8 — BENCHMARK COMPARISON
    # ─────────────────────────────────────────────────────────────────────────
    if show_benchmarks and benchmark_data:
        st.divider()
        st.markdown("### 🏛️ Benchmark Comparison")

        combined: dict[str, pd.DataFrame] = {**stock_data, **benchmark_data}
        st.plotly_chart(
            build_price_chart(combined, f"Portfolio vs Benchmarks — {selected_period_label}"),
            use_container_width=True,
            config={"displayModeBar": False},
        )

        bm_rows = []
        for sym, df in combined.items():
            k = get_static_kpi(df, sym, timeframe)
            if k:
                bm_rows.append({
                    "Name":              sym,
                    "Type":              "Benchmark" if sym in benchmark_data else "Portfolio",
                    "CAGR (%)":          k.get("CAGR (%)", np.nan),
                    "Sharpe Ratio":      k.get("Sharpe Ratio", np.nan),
                    "Max Drawdown (%)":  k.get("Max Drawdown (%)", np.nan),
                })
        if bm_rows:
            bm_df = pd.DataFrame(bm_rows).set_index("Name")
            st.dataframe(
                bm_df.style.format({"CAGR (%)": "{:.2f}", "Sharpe Ratio": "{:.2f}",
                                     "Max Drawdown (%)": "{:.2f}"})
                           .background_gradient(subset=["CAGR (%)"], cmap="RdYlGn"),
                use_container_width=True,
            )

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 9 — RAW DATA
    # ─────────────────────────────────────────────────────────────────────────
    with st.expander("🗂  Raw Price Data"):
        disp_df = primary_df.copy()
        fmt     = "%Y-%m-%d %H:%M" if selected_interval not in ("1d", "5d", "1wk", "1mo") else "%Y-%m-%d"
        disp_df.index = disp_df.index.strftime(fmt)
        st.dataframe(disp_df.round(2), use_container_width=True)
        st.download_button(
            "⬇  Download CSV",
            data=primary_df.to_csv().encode("utf-8"),
            file_name=f"{primary_symbol}_{selected_period}_{selected_interval}.csv",
            mime="text/csv",
        )