# ══════════════════════════════════════════════════════════════════════
# PAGE: HOME
# ══════════════════════════════════════════════════════════════════════
import streamlit as st
import time
import yfinance as yf
from datetime import datetime, time
from utils import fetch_all, render_card, INDICES, SECTORS

def show_home():
    st.title("Market Sectors")
    st.caption("Click on any sector to view stocks")
    st.markdown("---")

    def is_market_open():
        """Returns True if current time is between 09:15 and 15:30 IST."""
        now = datetime.now().time()
        market_start = time(9, 15)
        market_end = time(15, 30)
        return market_start <= now <= market_end

    # Determine refresh interval: 5 seconds if open, None (off) if closed
    refresh_interval = 5 if is_market_open() else None

    @st.fragment(run_every=refresh_interval)
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

        st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

    live_dashboard()