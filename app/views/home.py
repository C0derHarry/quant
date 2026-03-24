# ══════════════════════════════════════════════════════════════════════
# PAGE: HOME
# ══════════════════════════════════════════════════════════════════════
import streamlit as st
import time
import yfinance as yf
from utils import fetch_all, render_card, INDICES, SECTORS

def show_home():
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