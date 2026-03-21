import streamlit as st
import time
import yfinance as yf
from nsetools import Nse
from concurrent.futures import ThreadPoolExecutor
from utils.stock_utils import fetch_ohlcv_data

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
    stocks = nse.get_stocks_in_index(index_name)
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
st.sidebar.button("Magic Rank")
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

        with ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(fetch_quote, stocks))

        rows = [r for r in results if r is not None]

        # df = pd.DataFrame(rows).sort_values("Change", ascending=False)
        # print(df.to_string(index=False))

        # rows = []
        # for s in data:
        #     try:
        #         price  = float(s.get("lastPrice", 0))
        #         change = float(s.get("change", 0))
        #         pct    = float(s.get("pChange", 0))
        #         rows.append({
        #             "Symbol":   s.get("symbol", ""),
        #             "Name":     s.get("meta", {}).get("companyName", s.get("symbol", "")),
        #             "Price":    price,
        #             "Change":   change,
        #             "Change %": pct,
        #         })
        #     except:
        #         continue

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
                <td style="padding:10px 12px; text-align:right;">₹{r['Price']:,.2f}</td>
                <td style="padding:10px 12px; text-align:right;">{sign}{r['Change']:,.2f}</td>
                <td style="padding:10px 12px; text-align:right;">{sign}{r['Change %']:.2f}%</td>
            </tr>"""

        st.markdown(f"""
        <table style="width:100%; border-collapse:collapse; font-size:14px;">
            <thead>
                <tr style="border-bottom: 1.5px solid #ccc;">
                    <th style="padding:10px 12px; text-align:left;">Symbol</th>
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