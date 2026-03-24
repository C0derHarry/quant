# ══════════════════════════════════════════════════════════════════════
# PAGE: SECTOR DETAIL
# ══════════════════════════════════════════════════════════════════════

import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import date, time
from utils import fetch_stocks

def show_sectors():
    selected = st.session_state.selected

    if st.button("← Back to Market Sectors"):
        st.session_state.page = "home"
        st.rerun()

    st.title(selected)
    st.caption("Click refresh to update · All prices in INR")
    st.markdown("---")

    def is_market_open():
        now = datetime.now().time()
        market_start = time(9, 15)
        market_end = time(15, 30)
        return market_start <= now <= market_end

    refresh_interval = 5 if is_market_open() else None

    @st.fragment(run_every=refresh_interval)
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