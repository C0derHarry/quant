# ══════════════════════════════════════════════════════════════════════
# PAGE: MAGIC RANK
# ══════════════════════════════════════════════════════════════════════
import streamlit as st
import time
from nsetools import Nse
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.screeners import magic_formula_rank, qarp_screener

nse = Nse()

def value_investing():
    # ── Session state init ────────────────────────────────────────────────
    if "selected_stocks" not in st.session_state:
        st.session_state.selected_stocks = []
    if "exchange" not in st.session_state:
        st.session_state.exchange = "NSE"
    if "current_page" not in st.session_state:
        st.session_state.current_page = 0
    if "selected_sector" not in st.session_state:
        st.session_state.selected_sector = None
    if "search_query" not in st.session_state:
        st.session_state.search_query = ""

    NSE_SECTORS = [
        "NIFTY 50", "NIFTY BANK", "NIFTY IT", "NIFTY PHARMA",
        "NIFTY AUTO", "NIFTY FMCG", "NIFTY METAL", "NIFTY ENERGY",
        "NIFTY INFRA", "NIFTY FIN SERVICE"
    ]

    BSE_SECTORS = {
        "BSE SENSEX":  ["RELIANCE", "TCS", "HDFCBANK", "INFY", "HINDUNILVR",
                        "ICICIBANK", "KOTAKBANK", "SBIN", "BAJFINANCE", "BHARTIARTL",
                        "ASIANPAINT", "MARUTI", "LT", "AXISBANK", "TITAN"],
        "BSE IT":      ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM"],
        "BSE PHARMA":  ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "APOLLOHOSP"],
    }

    @st.cache_data
    def get_all_nse_symbols():
        return sorted(nse.get_stock_codes())

    @st.cache_data
    def get_all_bse_symbols():
        return sorted(set(s for stocks in BSE_SECTORS.values() for s in stocks))

    def get_all_symbols(exchange):
        return get_all_nse_symbols() if exchange == "NSE" else get_all_bse_symbols()
    
    def fetch_name(symbol):
        try:
            return symbol, yf.Ticker(f"{symbol}.NS").info["shortName"]
        except:
            return symbol, symbol

    def get_sector_symbols(exchange, sector):
        if exchange == "NSE":
            try:
                return nse.get_stocks_in_index(sector)
            except:
                return []
        else:
            return BSE_SECTORS.get(sector, [])

    def add_stock(symbol):
        if symbol not in st.session_state.selected_stocks:
            st.session_state.selected_stocks.append(symbol)

    def remove_stock(symbol):
        st.session_state.selected_stocks.remove(symbol)

    # ── Selected stocks panel ─────────────────────────────────────────────
    st.title("Magic Rank")

    if st.session_state.selected_stocks:
        st.subheader(f"Selected Stocks ({len(st.session_state.selected_stocks)})")
        cols = st.columns(6)
        for i, symbol in enumerate(st.session_state.selected_stocks):
            with cols[i % 6]:
                if st.button(f"✕ {symbol}", key=f"remove_{symbol}", use_container_width=True):
                    remove_stock(symbol)
                    st.rerun()
        if st.button("Clear All", type="secondary"):
            st.session_state.selected_stocks = []
            st.rerun()
    else:
        st.info("No stocks selected yet. Add stocks from the list below.")

    st.markdown("---")

    # ── Exchange toggle ───────────────────────────────────────────────────
    col1, col2, col3 = st.columns([1, 2, 3])

    with col1:
        exchange = st.radio("Exchange", ["NSE", "BSE"], horizontal=True,
                            index=0 if st.session_state.exchange == "NSE" else 1)
        if exchange != st.session_state.exchange:
            st.session_state.exchange        = exchange
            st.session_state.current_page    = 0
            st.session_state.selected_sector = None
            st.session_state.search_query    = ""
            st.rerun()

    # ── Sector selector ───────────────────────────────────────────────────
    sectors = NSE_SECTORS if st.session_state.exchange == "NSE" else list(BSE_SECTORS.keys())

    with col2:
        sector_options = [None] + sectors
        sector = st.selectbox(
            "Sector / Index",
            options=sector_options,
            index=0,
            format_func=lambda x: "Select sector-wise stocks" if x is None else x,
        )
        if sector != st.session_state.selected_sector:
            st.session_state.selected_sector = sector
            st.session_state.current_page    = 0
            st.session_state.search_query    = ""
            st.rerun()

    # ── Search bar ────────────────────────────────────────────────────────
    with col3:
        search_query = st.text_input("", placeholder="Search stock",
                                    value=st.session_state.search_query)
        if search_query != st.session_state.search_query:
            st.session_state.search_query = search_query
            st.session_state.current_page = 0
            st.rerun()

    # ── Resolve which symbols to show ─────────────────────────────────────
    if st.session_state.selected_sector:
        all_symbols = get_sector_symbols(st.session_state.exchange, st.session_state.selected_sector)
    else:
        all_symbols = get_all_symbols(st.session_state.exchange)

    # Apply search filter
    if st.session_state.search_query:
        q = st.session_state.search_query.upper()
        all_symbols = [s for s in all_symbols if q in s.upper()]

    # ── Select all sector button (only when a sector is chosen) ───────────
    if st.session_state.selected_sector:
        raw_sector_symbols = get_sector_symbols(st.session_state.exchange,
                                                st.session_state.selected_sector)
        if st.button(f"+ Add all {st.session_state.selected_sector} stocks ({len(raw_sector_symbols)})"):
            for s in raw_sector_symbols:
                add_stock(s)
            st.rerun()

    st.markdown("---")

    # ── Paginated stock list ──────────────────────────────────────────────
    PAGE_SIZE   = 10
    total_pages = max(1, -(-len(all_symbols) // PAGE_SIZE))
    current_page = min(st.session_state.current_page, total_pages - 1)
    page_symbols = all_symbols[current_page * PAGE_SIZE : (current_page + 1) * PAGE_SIZE]

    st.caption(f"Showing {current_page * PAGE_SIZE + 1}–{min((current_page + 1) * PAGE_SIZE, len(all_symbols))} of {len(all_symbols)} stocks")

    h1, h2, h3 = st.columns([2, 5, 2])
    h1.markdown("**Symbol**")
    h2.markdown("**Name**")
    h3.markdown("**Action**")
    st.markdown("<hr style='margin:4px 0'>", unsafe_allow_html=True)

    with ThreadPoolExecutor(max_workers=10) as executor:
        name_map = dict(executor.map(fetch_name, page_symbols))

    for symbol in page_symbols:
        c1, c2, c3 = st.columns([2, 5, 2])
        c1.markdown(f"`{symbol}`")
        c2.markdown(name_map.get(symbol, symbol))
        with c3:
            already = symbol in st.session_state.selected_stocks
            if already:
                st.button("✓ Added", key=f"add_{symbol}", disabled=True,
                        use_container_width=True)
            else:
                if st.button("+ Add", key=f"add_{symbol}", use_container_width=True):
                    add_stock(symbol)
                    st.rerun()

    st.markdown("<hr style='margin:4px 0'>", unsafe_allow_html=True)

    # ── Pagination controls ───────────────────────────────────────────────
    p1, p2, p3 = st.columns([1, 3, 1])
    with p1:
        if st.button("← Prev", disabled=current_page == 0, use_container_width=True):
            st.session_state.current_page -= 1
            st.rerun()
    with p2:
        st.markdown(f"<p style='text-align:center; padding-top:8px;'>Page {current_page + 1} of {total_pages}</p>",
                    unsafe_allow_html=True)
    with p3:
        if st.button("Next →", disabled=current_page >= total_pages - 1,
                    use_container_width=True):
            st.session_state.current_page += 1
            st.rerun()

    st.markdown("---")

    # ── Get Rankings button ───────────────────────────────────────────────
    if st.button("📊Joel Greenblat's Magic Rankings", type="secondary", use_container_width=True,
                disabled=len(st.session_state.selected_stocks) == 0):
        with st.spinner("Calculating magic formula rankings..."):
            results_df = magic_formula_rank(st.session_state.selected_stocks)
            st.dataframe(results_df, hide_index=True)
            
    elif st.button("Quality Stocks at Reasonable Price", type="secondary", use_container_width=True, disabled=len(st.session_state.selected_stocks) == 0):
        with st.spinner("Running QARP screener..."):
            results_df = qarp_screener(st.session_state.selected_stocks)
            st.dataframe(results_df, hide_index=True)