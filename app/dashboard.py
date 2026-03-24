import streamlit as st
import time
import yfinance as yf
import pandas as pd
from nsetools import Nse
from concurrent.futures import ThreadPoolExecutor
from views import home, magic_rank, sector_detail

st.set_page_config(page_title="StockHub", layout="wide")


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

# ── Router Logic ──────────────────────────────────────────────────────

if st.session_state.page == "home":
    home.show_home()
elif st.session_state.page == "sector":
    sector_detail.show_sectors()
elif st.session_state.page == "magic_rank":
    magic_rank.run_magic_rank()