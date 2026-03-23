import streamlit as st
import time
import yfinance as yf
import pandas as pd
from nsetools import Nse
from concurrent.futures import ThreadPoolExecutor
from utils.stock_utils import fetch_ohlcv_data
from utils.value import magic_formula_rank

st.set_page_config(page_title="StockHub", layout="wide")

nse = Nse()

INDICES = ["NIFTY 50", "NIFTY BANK", "NIFTY FINANCIAL SERVICES", "NIFTY 500"]

SECTORS = ["NIFTY BANK", "NIFTY IT",
          "NIFTY PHARMA", "NIFTY AUTO", "NIFTY FMCG", "NIFTY METAL",
          "NIFTY REALTY", "NIFTY ENERGY"]

def fetch_all():
    raw = nse.get_all_index_quote()
    return {idx["index"]: idx for idx in raw
            if idx["index"] in set(INDICES + SECTORS)}

def fetch_stocks(index_name):
    stocks = nse.get_stock_quote_in_index(index_name)
    return stocks

def fetch_quote(symbol):
    try:
        q = nse.get_quote(symbol)
        return {
            "Symbol":   symbol,
            "Price":    q["lastPrice"],
            "Change":   q["change"],
            "Change %": q["pChange"],
        }
    except:
        return None  # skip if a single stock fails

def render_card(col, name, idx):
    price  = idx["last"]
    change = idx["variation"]
    pct    = idx["percentChange"]
    up     = change >= 0
    
    # Dynamic Colors
    bg_color = '#eaf3de' if up else '#fcebeb'
    hover_bg = '#dce9cb' if up else '#f9dada'
    border_color = '#3B6D11' if up else '#A32D2D'
    text_main = '#173404' if up else '#501313'
    arrow = "↗" if up else "↘"
    sign = "+" if up else ""

    with col:
        card_html = f"""
        <div id="card_{name}" style="
            background-color: {bg_color};
            border: 1.5px solid {border_color};
            border-radius: 12px;
            padding: 1.25rem;
            cursor: pointer;
            transition: all 0.2s ease-in-out;
            color: {text_main};
            margin-bottom: 10px;
        " 
        onmouseover="this.style.backgroundColor='{hover_bg}'; this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(0,0,0,0.1)';"
        onmouseout="this.style.backgroundColor='{bg_color}'; this.style.transform='translateY(0)'; this.style.boxShadow='none';"
        >
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-weight:600; font-size:16px;">{name}</span>
                <span style="font-size:18px;">{arrow}</span>
            </div>
            <div style="font-size:26px; font-weight:700; margin: 10px 0;">
                ₹{price:,.2f}
            </div>
            <div style="font-size:13px; font-weight:500; opacity: 0.8;">
                {sign}{change:,.2f} ({sign}{pct:.2f}%)
            </div>
        </div>
        """
        
        # Display the card
        st.markdown(card_html, unsafe_allow_html=True)
        
        if st.button("View Details", key=f"btn_{name}", use_container_width=True):
            st.session_state.page = "sector"
            st.session_state.selected = name
            st.rerun()

# ── Session state init ────────────────────────────────────────────────
if "page"     not in st.session_state: st.session_state.page     = "home"
if "selected" not in st.session_state: st.session_state.selected = None

# ── Sidebar ───────────────────────────────────────────────────────────
st.sidebar.title("📈 StockHub")
st.sidebar.markdown("---")
if st.sidebar.button("🏠 Market Sectors"):
    st.session_state.page = "home"
    st.rerun()
st.sidebar.markdown("**Value Investing**")
if st.sidebar.button("Magic Rank"):
    st.session_state.page = "magic_rank"
    st.rerun()
st.sidebar.button("QARP Screener")
st.sidebar.button("Defensive Screen")

# ══════════════════════════════════════════════════════════════════════
# PAGE: SECTOR DETAIL
# ══════════════════════════════════════════════════════════════════════
if st.session_state.page == "sector":
    selected = st.session_state.selected

    if st.button("← Back to Market Sectors"):
        st.session_state.page = "home"
        st.rerun()

    st.title(selected)
    st.caption("Click refresh to update · All prices in INR")
    st.markdown("---")

    @st.fragment(run_every=5)
    def sector_detail():
        with st.spinner("Fetching stocks..."):
            stocks = fetch_stocks(selected)

        if not stocks:
            st.error("No data returned for this index.")
            return


        df = pd.DataFrame(stocks).sort_values("change", ascending=False)
        print(df.to_string(index=False))

        rows = []
        for s in stocks:
            try:
                price  = float(s.get("lastPrice", 0))
                change = float(s.get("change", 0))
                pct    = float(s.get("pChange", 0))
                rows.append({
                    "Symbol":   s.get("symbol", ""),
                    "Name":     s.get("meta").get("companyName"),
                    "Price":    price,
                    "Change":   change,
                    "Change %": pct,
                })
            except:
                continue

        rows.sort(key=lambda x: x["Change %"], reverse=True)

        # Build HTML table
        rows_html = ""
        for r in rows:
            up    = r["Change"] >= 0
            sign  = "+" if up else ""
            bg    = "#eaf3de" if up else "#fcebeb"
            color = "#27500A" if up else "#791F1F"
            rows_html += f"""
            <tr style="background:{bg}; color:{color};">
                <td style="padding:10px 12px; font-family:monospace; font-weight:500;">{r['Symbol']}</td>
                <td style="padding:10px 12px; text-align:left;">{r['Name']}</td>
                <td style="padding:10px 12px; text-align:right;">₹{r['Price']:,.2f}</td>
                <td style="padding:10px 12px; text-align:right;">{sign}{r['Change']:,.2f}</td>
                <td style="padding:10px 12px; text-align:right;">{sign}{r['Change %']:.2f}%</td>
            </tr>"""

        st.markdown(f"""
        <table style="width:100%; border-collapse:collapse; font-size:14px;">
            <thead>
                <tr style="border-bottom: 1.5px solid #ccc;">
                    <th style="padding:10px 12px; text-align:left;">Symbol</th>
                    <th style="padding:10px 12px; text-align:left;">Name</th>
                    <th style="padding:10px 12px; text-align:right;">Price</th>
                    <th style="padding:10px 12px; text-align:right;">Change</th>
                    <th style="padding:10px 12px; text-align:right;">Change %</th>
                </tr>
            </thead>
            <tbody>{rows_html}</tbody>
        </table>
        """, unsafe_allow_html=True)

        st.caption(f"Last updated: {time.strftime('%H:%M:%S')} · {len(rows)} stocks")

    sector_detail()

# ══════════════════════════════════════════════════════════════════════
# PAGE: MAGIC RANK
# ══════════════════════════════════════════════════════════════════════
elif st.session_state.page == 'magic_rank':

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
    if st.button("📊 Get Rankings", type="primary", use_container_width=True,
                disabled=len(st.session_state.selected_stocks) == 0):
        with st.spinner("Calculating magic formula rankings..."):
            results_df = magic_formula_rank(st.session_state.selected_stocks)
            st.dataframe(results_df, hide_index=True, use_container_width=True)
            # st.success("Call magic_formula(st.session_state.selected_stocks) here")

# ══════════════════════════════════════════════════════════════════════
# PAGE: HOME
# ══════════════════════════════════════════════════════════════════════
else:
    st.title("Market Sectors")
    st.caption("Click on any sector to view stocks")
    st.markdown("---")

    @st.fragment(run_every=10)
    def live_dashboard():
        data = fetch_all()

        sensex_info = yf.Ticker("^BSESN").fast_info
        sensex = {
            "last":          sensex_info["last_price"],
            "change":        sensex_info["last_price"] - sensex_info["previous_close"],
            "percentChange": ((sensex_info["last_price"] - sensex_info["previous_close"])
                              / sensex_info["previous_close"]) * 100
        }

        # Index metrics row
        index_cols = st.columns(4)
        for col, name in zip(index_cols, INDICES):
            if name in data:
                idx = data[name]
                col.metric(label=name,
                           value=f"₹{idx['last']:,.2f}",
                           delta=f"{idx['percentChange']:+.2f}%")

        st.markdown("---")
        st.subheader("Sector Performance")

        sector_cols = st.columns(2)
        for i, name in enumerate(SECTORS):
            if name in data:
                render_card(sector_cols[i % 2], name, data[name])

        st.caption(f"Last updated: {time.strftime('%H:%M:%S')}")

    live_dashboard()