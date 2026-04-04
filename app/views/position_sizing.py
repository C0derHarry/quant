"""
pages/position_sizing.py
─────────────────────────────────────────────────────────────────
Position Sizing Dashboard
Integrates: GARCH + DCC-GARCH + HMM + Black-Litterman MVO
─────────────────────────────────────────────────────────────────
"""

import warnings
warnings.filterwarnings("ignore")

import sys, os
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ── Import sizing pipeline ─────────────────────────────────────
# Assumes sizing.py is one level up from this pages/ folder.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.portfolio import run_optimizer

# ── Page config ───────────────────────────────────────────────
st.set_page_config(
    page_title="Position Sizing",
    page_icon="⚖️",
    layout="wide",
)

# ── Styling ───────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
}
h1, h2, h3 { font-family: 'IBM Plex Mono', monospace; }

.metric-card {
    background: #0e1117;
    border: 1px solid #2d3748;
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 8px;
}
.metric-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    color: #718096;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 4px;
}
.metric-value {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 20px;
    font-weight: 600;
    color: #e2e8f0;
}
.metric-delta {
    font-size: 12px;
    color: #68d391;
    margin-top: 2px;
}
.section-header {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 13px;
    font-weight: 600;
    color: #a0aec0;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    border-bottom: 1px solid #2d3748;
    padding-bottom: 8px;
    margin: 24px 0 16px 0;
}
.alloc-card {
    background: linear-gradient(135deg, #141923 0%, #0e1117 100%);
    border: 1px solid #4a5568;
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 10px;
}
.regime-bull  { color: #68d391; font-weight: 600; }
.regime-bear  { color: #fc8181; font-weight: 600; }
.regime-side  { color: #f6e05e; font-weight: 600; }
.warning-box {
    background: #2d1f0e;
    border: 1px solid #dd6b20;
    border-left: 3px solid #ed8936;
    border-radius: 6px;
    padding: 10px 14px;
    margin: 8px 0;
    font-size: 13px;
    color: #fbd38d;
}
.info-box {
    background: #0e1a2d;
    border: 1px solid #2b6cb0;
    border-left: 3px solid #63b3ed;
    border-radius: 6px;
    padding: 10px 14px;
    margin: 8px 0;
    font-size: 13px;
    color: #bee3f8;
}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# PLOT HELPERS
# ═══════════════════════════════════════════════════════════════

def plot_allocation_bar(weights: dict) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8, 4))
    fig.patch.set_facecolor("#0e1117")
    ax.set_facecolor("#141923")

    tickers = list(weights.keys())
    values = list(weights.values())

    ax.bar(tickers, values)
    ax.axhline(0)  # critical for long/short

    ax.set_title("Portfolio Weights (Long/Short)", color="white")
    ax.tick_params(colors="#718096")

    return fig


def plot_dca_schedule(dca_df: pd.DataFrame) -> plt.Figure:
    months = dca_df["Month"].tolist()
    deployments = dca_df["Deploy (₹)"].tolist()
    tickers = [c for c in dca_df.columns if c not in ["Month", "Deploy (₹)"]]

    fig, ax = plt.subplots(figsize=(10, 4))
    fig.patch.set_facecolor("#0e1117")
    ax.set_facecolor("#141923")
    ax.spines[:].set_color("#2d3748")
    ax.tick_params(colors="#718096", labelsize=9)

    colors = plt.cm.Set2(np.linspace(0, 1, len(tickers)))
    x = np.arange(len(months))
    bar_w = 0.6

    bottom = np.zeros(len(months))
    for i, ticker in enumerate(tickers):
        vals = dca_df[ticker].values
        ax.bar(x, vals, bar_w, bottom=bottom, color=colors[i],
               label=ticker, edgecolor="#0e1117", linewidth=0.5)
        bottom += vals

    ax.set_xticks(x)
    ax.set_xticklabels(months, color="#718096", fontsize=9)
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda v, _: f"₹{v/1e5:.1f}L")
    )
    ax.set_ylabel("Deployment (₹)", color="#718096", fontsize=9)
    ax.legend(fontsize=8, facecolor="#0e1117", labelcolor="white")
    ax.set_title("DCA Monthly Deployment Schedule", color="#e2e8f0",
                 fontfamily="monospace", pad=10)
    fig.tight_layout()
    return fig


def plot_regime_transitions(regimes: dict) -> plt.Figure:
    tickers = list(regimes.keys())
    regime_labels = ["Bear", "Sideways", "Bull"]
    regime_colors = {"Bear": "#fc8181", "Sideways": "#f6e05e", "Bull": "#68d391"}

    n = len(tickers)
    fig, axes = plt.subplots(1, n, figsize=(4 * n, 3.5), squeeze=False)
    fig.patch.set_facecolor("#0e1117")

    for idx, ticker in enumerate(tickers):
        ax = axes[0][idx]
        ax.set_facecolor("#141923")
        ax.spines[:].set_color("#2d3748")
        ax.tick_params(colors="#718096", labelsize=8)

        r = regimes[ticker]
        current = r["regime"]
        trans = r["transition_probs"]

        probs = [trans.get(rl, 0.0) for rl in regime_labels]
        colors = [regime_colors[rl] for rl in regime_labels]
        bars = ax.barh(regime_labels, probs, color=colors, edgecolor="#0e1117",
                       height=0.5)

        for bar, prob, label in zip(bars, probs, regime_labels):
            ax.text(min(prob + 0.01, 0.85), bar.get_y() + bar.get_height() / 2,
                    f"{prob:.1%}", va="center", ha="left",
                    color="#e2e8f0", fontsize=8,
                    fontfamily="monospace")

        ax.set_xlim(0, 1.05)
        current_color = regime_colors.get(current, "#a0aec0")
        ax.set_title(
            f"{ticker}\n"
            f"Current: ",
            color="#718096", fontsize=8, fontfamily="monospace", pad=4,
        )
        ax.text(0.5, 1.0, f"{ticker}", transform=ax.transAxes,
                ha="center", va="bottom", color="#e2e8f0",
                fontsize=10, fontfamily="monospace", fontweight="bold")
        ax.text(0.5, 0.92, f"Current regime: ",
                transform=ax.transAxes, ha="center", va="bottom",
                color="#718096", fontsize=8)
        ax.text(0.5, 0.86, current,
                transform=ax.transAxes, ha="center", va="bottom",
                color=current_color, fontsize=10, fontweight="bold",
                fontfamily="monospace")

        ax.set_xlabel("Transition probability", color="#718096", fontsize=8)

    fig.suptitle("Regime Transition Probabilities (HMM)",
                 color="#e2e8f0", fontfamily="monospace", fontsize=11, y=1.02)
    fig.tight_layout()
    return fig

def run_pos_sizing():

    # ═══════════════════════════════════════════════════════════════
    # SESSION STATE
    # ═══════════════════════════════════════════════════════════════

    if "sizing_results" not in st.session_state:
        st.session_state["sizing_results"] = None
    if "sizing_params" not in st.session_state:
        st.session_state["sizing_params"] = {}


    # ═══════════════════════════════════════════════════════════════
    # UI — HEADER
    # ═══════════════════════════════════════════════════════════════

    st.title("⚖️ Position Sizing")
    st.markdown(
        "<p style='color:#718096; font-size:14px; margin-top:-10px;'>"
        "GARCH · DCC-GARCH · HMM Regime Detection · Black-Litterman MVO"
        "</p>",
        unsafe_allow_html=True,
    )

    # ═══════════════════════════════════════════════════════════════
    # SECTION 1 — STOCK SELECTION
    # ═══════════════════════════════════════════════════════════════

    st.markdown('<div class="section-header">① Stock Selection</div>', unsafe_allow_html=True)

    ticker_input = st.text_input(
        "Enter NSE / BSE ticker(s) — comma-separated",
        value="RELIANCE.NS, TCS.NS, HDFCBANK.NS",
        placeholder="e.g. RELIANCE.NS, TCS.NS, HDFCBANK.NS",
        help="Provide at least one ticker. Multi-stock portfolios use DCC-GARCH for correlations.",
    )
    tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]

    if len(tickers) == 1:
        st.markdown(
            '<div class="info-box">Single-stock mode — univariate GARCH(1,1) will be used.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="info-box">Multi-stock mode ({len(tickers)} assets) — '
            f'DCC-GARCH will model time-varying correlations.</div>',
            unsafe_allow_html=True,
        )

    # ═══════════════════════════════════════════════════════════════
    # SECTION 2 — PARAMETERS
    # ═══════════════════════════════════════════════════════════════

    st.markdown('<div class="section-header">② Portfolio Parameters</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        capital = st.number_input(
            "Capital (₹)",
            min_value=10_000,
            max_value=100_000_000,
            value=1_000_000,
            step=10_000,
            format="%d",
            help="Total capital to deploy",
        )
        user_target_annual = st.slider(
            "Target annual return (%)",
            min_value=5, max_value=50, value=18, step=1,
            help="Your desired annual return. The model blends this with regime + momentum signals.",
        ) / 100.0

    with col2:
        risk_appetite_monthly = st.slider(
            "Monthly risk appetite (% max loss)",
            min_value=1, max_value=20, value=5, step=1,
            help="Maximum % of portfolio you're willing to lose in any given month (95% VaR constraint).",
        ) / 100.0
        allow_short = st.toggle(
            "Allow short selling",
            value=False,
            help="If enabled, positions up to -30% per stock are allowed.",
        )

    with col3:
        invest_mode = st.radio(
            "Investment mode",
            options=["lump_sum", "dca"],
            format_func=lambda x: "Lump Sum" if x == "lump_sum" else "Dollar-Cost Averaging (DCA)",
            index=0,
            help="Lump sum deploys all capital now. DCA spreads deployment over N months (front-loaded).",
        )
        dca_months = None
        if invest_mode == "dca":
            dca_months = st.slider(
                "DCA period (months)",
                min_value=2, max_value=12, value=6, step=1,
            )
    # # Market caps — optional advanced expander
    # with st.expander("⚙️ Advanced: Market Caps for Black-Litterman Prior (₹ Cr)"):
    #     st.markdown(
    #         "_Used to compute implied equilibrium returns. Defaults are approximate NSE values._"
    #     )
    #     mcap_cols = st.columns(max(len(tickers), 1))
    #     market_caps = {}
    #     default_mcaps = {
    #         "RELIANCE.NS": 2_000_000, "TCS.NS": 1_400_000,
    #         "HDFCBANK.NS": 1_200_000, "INFY.NS": 700_000,
    #         "ICICIBANK.NS": 800_000,  "WIPRO.NS": 250_000,
    #     }
    #     for i, ticker in enumerate(tickers):
    #         with mcap_cols[i % len(mcap_cols)]:
    #             market_caps[ticker] = st.number_input(
    #                 f"{ticker} MCap (₹ Cr)",
    #                 value=default_mcaps.get(ticker, 500_000),
    #                 min_value=1_000,
    #                 step=10_000,
    #                 key=f"mcap_{ticker}",
    #             )

    # ── Summary before run ─────────────────────────────────────────
    st.markdown("---")
    param_cols = st.columns(5)
    param_items = [
        ("Capital", f"₹{capital:,.0f}"),
        ("Target Return", f"{user_target_annual*100:.0f}% p.a."),
        ("Risk Appetite", f"{risk_appetite_monthly*100:.0f}%/mo"),
        ("Short Selling", "✅ Yes" if allow_short else "❌ No"),
        ("Mode", "DCA" if invest_mode == "dca" else "Lump Sum"),
    ]
    for col, (label, val) in zip(param_cols, param_items):
        with col:
            st.markdown(
                f'<div class="metric-card">'
                f'<div class="metric-label">{label}</div>'
                f'<div class="metric-value" style="font-size:16px">{val}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    run_btn = st.button(
        "🚀 Run Optimizer",
        type="primary",
        disabled=not bool(tickers),
    )

    # ═══════════════════════════════════════════════════════════════
    # SECTION 3 — RUN + RESULTS
    # ═══════════════════════════════════════════════════════════════

    if run_btn and tickers:
        with st.spinner("Running full pipeline: GARCH → DCC → HMM → BL-MVO… (this may take ~30s)"):
            try:
                results = run_optimizer(
                    tickers=tickers,
                    capital=capital,
                    user_target_annual=user_target_annual,
                    risk_appetite_monthly=risk_appetite_monthly,
                    allow_short=allow_short,
                    invest_mode=invest_mode,
                    dca_months=dca_months if invest_mode == "dca" else 6,
                    stop_loss_k=1.5,
                )
                st.session_state["sizing_results"] = results
                st.session_state["sizing_params"] = {
                    "capital": capital,
                    "invest_mode": invest_mode,
                    "dca_months": dca_months,
                    "tickers": tickers,
                    "user_target_annual": user_target_annual,
                    "risk_appetite_monthly": risk_appetite_monthly,
                }
            except Exception as e:
                st.error(f"Optimizer error: {e}")
                st.exception(e)
                st.stop()

    # ── Display results ─────────────────────────────────────────────
    if st.session_state["sizing_results"] is not None:
        results = st.session_state["sizing_results"]
        params  = st.session_state["sizing_params"]

        weights      = results["weights"]
        stop_data    = results["stop_data"]
        regimes      = results["regimes"]
        port_metrics = results["portfolio_metrics"]
        dcc          = results["dcc"]
        bl_returns   = results["bl_returns"]
        capital_used = params["capital"]
        invest_mode  = params["invest_mode"]
        dca_months   = params["dca_months"]

        # ── Portfolio metrics bar ──────────────────────────────────
        st.markdown('<div class="section-header">③ Final Allocation Summary</div>',
                    unsafe_allow_html=True)

        pm1, pm2, pm3, pm4 = st.columns(4)
        with pm1:
            st.markdown(f"""<div class="metric-card">
            <div class="metric-label">Expected Return</div>
            <div class="metric-value">{port_metrics['annual_return']*100:.2f}%</div>
            <div class="metric-delta">per annum</div>
            </div>""", unsafe_allow_html=True)
        with pm2:
            st.markdown(f"""<div class="metric-card">
            <div class="metric-label">Portfolio Volatility</div>
            <div class="metric-value">{port_metrics['annual_vol']*100:.2f}%</div>
            <div class="metric-delta">per annum</div>
            </div>""", unsafe_allow_html=True)
        with pm3:
            st.markdown(f"""<div class="metric-card">
            <div class="metric-label">Sharpe Ratio</div>
            <div class="metric-value">{port_metrics['sharpe']:.2f}</div>
            <div class="metric-delta">risk-free = 7%</div>
            </div>""", unsafe_allow_html=True)
        with pm4:
            st.markdown(f"""<div class="metric-card">
            <div class="metric-label">Monthly VaR (95%)</div>
            <div class="metric-value">{port_metrics['monthly_var_95']*100:.2f}%</div>
            <div class="metric-delta">= ₹{capital_used * port_metrics['monthly_var_95']:,.0f}</div>
            </div>""", unsafe_allow_html=True)

        # ── Allocation table + pie ─────────────────────────────────
        alloc_col, pie_col = st.columns([3, 2])

        with alloc_col:
            st.markdown("**Per-Stock Allocation**")
            alloc_rows = []
            for ticker in params["tickers"]:
                sd = stop_data[ticker]
                regime_label = regimes[ticker]["regime"]
                regime_class = {
                    "Bull": "regime-bull", "Bear": "regime-bear", "Sideways": "regime-side"
                }.get(regime_label, "")
                alloc_rows.append({
                    "Stock":           ticker,
                    "Entry Price":     f"₹{sd['entry_price']:,.2f}",
                    "Weight":          f"{sd['weight_pct']:.1f}%",
                    "Allocation":      f"₹{sd['allocation']:,.0f}",
                    "Shares":          f"{sd['shares']:.3f}",
                    "Capital at Risk": f"₹{sd['risk_per_position']:,.0f}",
                    "BL Return":       f"{bl_returns[ticker]*100:.1f}%",
                    "Regime":          regime_label,
                })
            alloc_df = pd.DataFrame(alloc_rows)

            def color_regime(val):
                colors_map = {"Bull": "#1a3a2a", "Bear": "#3a1a1a", "Sideways": "#3a3a1a"}
                return f"background-color: {colors_map.get(val, '')}"

            styled_alloc = alloc_df.style.applymap(color_regime, subset=["Regime"])
            st.dataframe(styled_alloc, use_container_width=True, hide_index=True)

            # Stop loss table
            st.markdown("**GARCH-based Stop Losses**")
            stop_rows = []
            for ticker in params["tickers"]:
                sd = stop_data[ticker]
                stop_rows.append({
                    "Stock":      ticker,
                    "Entry":      f"₹{sd['entry_price']:,.2f}",
                    "Stop Loss":  f"₹{sd['stop_price']:,.2f}",
                    "Stop %":     f"{sd['stop_pct']:.2f}%",
                    "Daily σ":    f"{sd['daily_sigma_pct']:.2f}%",
                })
            st.dataframe(pd.DataFrame(stop_rows), use_container_width=True, hide_index=True)

            # Portfolio stop loss
            total_risk = sum(stop_data[t]["risk_per_position"] for t in params["tickers"])
            st.markdown(
                f'<div class="warning-box">'
                f'📌 <b>Portfolio Stop Loss (95% monthly VaR):</b> '
                f'{port_metrics["monthly_var_95"]*100:.2f}% → ₹{capital_used * port_metrics["monthly_var_95"]:,.0f}<br>'
                f'📌 <b>Total ₹ at Risk (individual stops):</b> ₹{total_risk:,.0f}'
                f'</div>',
                unsafe_allow_html=True,
            )

        with pie_col:
            pie_fig = plot_allocation_bar(weights)
            st.pyplot(pie_fig, use_container_width=True)
            plt.close(pie_fig)

            # DCC correlation matrix (if multi-stock)
            if len(params["tickers"]) > 1:
                st.markdown("**DCC Correlation Matrix (current)**")
                corr_df = pd.DataFrame(
                    dcc["corr_matrix"],
                    index=params["tickers"],
                    columns=params["tickers"],
                ).round(3)
                styled_corr = corr_df.style.background_gradient(
                    cmap="RdYlGn", vmin=-1, vmax=1
                ).format("{:.3f}")
                st.dataframe(styled_corr, use_container_width=True)
                st.caption(
                    f"DCC α={dcc['dcc_a']:.4f} (news shock)  |  "
                    f"DCC β={dcc['dcc_b']:.4f} (persistence)"
                )

        # ── DCA Schedule ────────────────────────────────────────────
        if invest_mode == "dca":
            from core.portfolio import generate_dca_schedule
            st.markdown(
                f'<div class="section-header">④ DCA Deployment Schedule '
                f'({dca_months} months, front-loaded)</div>',
                unsafe_allow_html=True,
            )
            dca_df = generate_dca_schedule(weights, capital_used, dca_months)

            dca_display = dca_df.copy()
            dca_display["Deploy (₹)"] = dca_display["Deploy (₹)"].map(lambda x: f"₹{x:,.0f}")
            for t in params["tickers"]:
                if t in dca_display.columns:
                    dca_display[t] = dca_display[t].map(lambda x: f"₹{x:,.0f}")
            st.dataframe(dca_display, use_container_width=True, hide_index=True)

            fig_dca = plot_dca_schedule(dca_df)
            st.pyplot(fig_dca, use_container_width=True)
            plt.close(fig_dca)

            st.markdown(
                '<div class="info-box">'
                '💡 Front-loading applies because current regime signals are freshest.<br>'
                '⚡ Rebalance immediately if HMM detects a regime change mid-schedule.'
                '</div>',
                unsafe_allow_html=True,
            )

        # ── Regime Transition Risk ──────────────────────────────────
        st.markdown(
            '<div class="section-header">'
            + ('⑤' if invest_mode == "dca" else '④')
            + ' Regime Transition Risk</div>',
            unsafe_allow_html=True,
        )

        # Regime summary cards
        regime_cols = st.columns(len(params["tickers"]))
        for i, ticker in enumerate(params["tickers"]):
            r = regimes[ticker]
            current = r["regime"]
            stay_p  = r["transition_probs"].get(current, 0)
            col_map = {"Bull": "#68d391", "Bear": "#fc8181", "Sideways": "#f6e05e"}
            badge_color = col_map.get(current, "#a0aec0")
            with regime_cols[i]:
                st.markdown(
                    f'<div class="metric-card">'
                    f'<div class="metric-label">{ticker}</div>'
                    f'<div class="metric-value" style="color:{badge_color}; font-size:18px">'
                    f'{current}</div>'
                    f'<div class="metric-delta">Stay prob: {stay_p:.1%}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # Transition probability chart
        fig_regime = plot_regime_transitions(regimes)
        st.pyplot(fig_regime, use_container_width=True)
        plt.close(fig_regime)

        # Narrative transition warnings
        for ticker in params["tickers"]:
            r = regimes[ticker]
            current = r["regime"]
            # Find highest prob non-current regime
            other_probs = {k: v for k, v in r["transition_probs"].items() if k != current}
            if other_probs:
                most_likely_shift = max(other_probs, key=other_probs.get)
                shift_prob = other_probs[most_likely_shift]
                if shift_prob > 0.25:
                    risk_color = "#fc8181" if most_likely_shift == "Bear" else "#f6e05e"
                    st.markdown(
                        f'<div class="warning-box">'
                        f'⚠️ <b>{ticker}</b>: {shift_prob:.1%} probability of shifting from '
                        f'<b>{current}</b> → <b style="color:{risk_color}">{most_likely_shift}</b>. '
                        f'Monitor closely and consider reducing position if regime shifts.'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

        st.markdown(
            '<div class="info-box">'
            '⚡ Trigger a full rebalance if any stock\'s HMM regime shifts.<br>'
            '⚡ Re-run DCC-GARCH monthly to update correlations and stop losses.'
            '</div>',
            unsafe_allow_html=True,
        )