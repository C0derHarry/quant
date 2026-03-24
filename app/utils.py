import streamlit as st
from nsetools import Nse
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.data import fetch_ohlcv_data
from core.stats import CAGR

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