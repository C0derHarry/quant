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
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.portfolio import run_optimizer, generate_dca_schedule

# ── Styling ───────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
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
    font-size: 11px; color: #718096;
    text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 4px;
}
.metric-value {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 20px; font-weight: 600; color: #e2e8f0;
}
.metric-delta { font-size: 12px; color: #68d391; margin-top: 2px; }

.section-header {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 13px; font-weight: 600; color: #a0aec0;
    text-transform: uppercase; letter-spacing: 0.1em;
    border-bottom: 1px solid #2d3748; padding-bottom: 8px; margin: 24px 0 16px 0;
}
.warning-box {
    background: #2d1f0e; border: 1px solid #dd6b20;
    border-left: 3px solid #ed8936; border-radius: 6px;
    padding: 10px 14px; margin: 6px 0; font-size: 13px; color: #fbd38d;
}
.info-box {
    background: #0e1a2d; border: 1px solid #2b6cb0;
    border-left: 3px solid #63b3ed; border-radius: 6px;
    padding: 10px 14px; margin: 6px 0; font-size: 13px; color: #bee3f8;
}
.regime-pill {
    display: inline-block; padding: 2px 10px; border-radius: 20px;
    font-family: 'IBM Plex Mono', monospace; font-size: 11px; font-weight: 600;
}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

REGIME_COLOR = {"Bull": "#68d391", "Bear": "#fc8181", "Sideways": "#f6e05e"}
REGIME_BG    = {"Bull": "#1a3a2a", "Bear": "#3a1a1a", "Sideways": "#3a3a1a"}


def _regime_pill(label: str) -> str:
    color = REGIME_COLOR.get(label, "#a0aec0")
    bg    = REGIME_BG.get(label, "#2d3748")
    return (
        f'<span class="regime-pill" '
        f'style="color:{color}; background:{bg};">{label}</span>'
    )


def plot_weight_bar(weights: dict) -> plt.Figure:
    tickers = list(weights.keys())
    values  = [v * 100 for v in weights.values()]
    colors  = ["#68d391" if v >= 0 else "#fc8181" for v in values]

    fig, ax = plt.subplots(figsize=(max(5, len(tickers) * 1.4), 3.5))
    fig.patch.set_facecolor("#0e1117")
    ax.set_facecolor("#141923")
    ax.spines[:].set_color("#2d3748")
    ax.tick_params(colors="#718096", labelsize=9)

    bars = ax.bar(tickers, values, color=colors, edgecolor="#0e1117", width=0.5)
    ax.axhline(0, color="#4a5568", linewidth=0.8, linestyle="--")
    ax.axhline(50, color="#f6e05e", linewidth=0.8, linestyle=":", alpha=0.6,
               label="50% cap")
    ax.axhline(-40, color="#fc8181", linewidth=0.8, linestyle=":", alpha=0.6)

    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + (1.5 if val >= 0 else -3),
                f"{val:.1f}%", ha="center", va="bottom",
                color="#e2e8f0", fontsize=9, fontfamily="monospace")

    ax.set_ylabel("Weight (%)", color="#718096", fontsize=9)
    ax.legend(fontsize=8, facecolor="#0e1117", labelcolor="white")
    ax.set_title("Portfolio Weights", color="#e2e8f0",
                 fontfamily="monospace", pad=8)
    fig.tight_layout()
    return fig


def plot_dca_schedule(dca_df: pd.DataFrame) -> plt.Figure:
    months  = dca_df["Month"].tolist()
    tickers = [c for c in dca_df.columns if c not in ["Month", "Deploy (₹)"]]
    colors  = plt.cm.Set2(np.linspace(0, 1, max(len(tickers), 1)))
    x       = np.arange(len(months))

    fig, ax = plt.subplots(figsize=(max(7, len(months) * 1.2), 4))
    fig.patch.set_facecolor("#0e1117")
    ax.set_facecolor("#141923")
    ax.spines[:].set_color("#2d3748")
    ax.tick_params(colors="#718096", labelsize=9)

    bottom = np.zeros(len(months))
    for i, ticker in enumerate(tickers):
        vals = dca_df[ticker].values
        ax.bar(x, vals, 0.6, bottom=bottom, color=colors[i],
               label=ticker, edgecolor="#0e1117", linewidth=0.5)
        bottom += vals

    ax.set_xticks(x)
    ax.set_xticklabels(months, color="#718096", fontsize=9)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"₹{v/1e5:.1f}L"))
    ax.set_ylabel("Deploy (₹)", color="#718096", fontsize=9)
    ax.legend(fontsize=8, facecolor="#0e1117", labelcolor="white")
    ax.set_title("Monthly Deployment", color="#e2e8f0",
                 fontfamily="monospace", pad=8)
    fig.tight_layout()
    return fig


# ═══════════════════════════════════════════════════════════════
# MAIN PAGE
# ═══════════════════════════════════════════════════════════════

def run_pos_sizing():

    for key in ["sizing_results", "sizing_params"]:
        if key not in st.session_state:
            st.session_state[key] = None

    # ── Header ────────────────────────────────────────────────
    st.title("⚖️ Position Sizing")
    st.markdown(
        "<p style='color:#718096; font-size:14px; margin-top:-10px;'>"
        "GARCH · DCC-GARCH · HMM Regime Detection · Black-Litterman MVO"
        "</p>",
        unsafe_allow_html=True,
    )

    # ── Section 1: Inputs ─────────────────────────────────────
    st.markdown('<div class="section-header">① Configure</div>', unsafe_allow_html=True)

    r1c1, r1c2 = st.columns([3, 1])
    with r1c1:
        ticker_input = st.text_input(
            "Tickers (comma-separated)",
            value="RELIANCE.NS, TCS.NS, HDFCBANK.NS",
            placeholder="e.g. RELIANCE.NS, TCS.NS",
        )
    with r1c2:
        invest_mode = st.radio(
            "Mode", ["lump_sum", "dca"],
            format_func=lambda x: "Lump Sum" if x == "lump_sum" else "DCA",
        )

    tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]

    r2c1, r2c2, r2c3, r2c4 = st.columns(4)
    with r2c1:
        capital = st.number_input(
            "Capital (₹)", min_value=10_000, max_value=100_000_000,
            value=1_000_000, step=10_000, format="%d",
        )
    with r2c2:
        user_target_annual = st.slider(
            "Target return (% p.a.)", 5, 50, 18
        ) / 100.0
    with r2c3:
        risk_appetite_monthly = st.slider(
            "Max monthly loss (%)", 1, 20, 5
        ) / 100.0
    with r2c4:
        allow_short = st.toggle("Allow short selling", value=False)
        dca_months = None
        if invest_mode == "dca":
            dca_months = st.slider("DCA months", 2, 12, 6)

    # Mode note
    if len(tickers) == 1:
        st.markdown(
            '<div class="info-box">Single-stock mode — univariate GARCH(1,1).</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="info-box">Multi-stock mode ({len(tickers)} assets) — '
            f'DCC-GARCH models time-varying correlations. '
            f'Max 50% per stock enforced.</div>',
            unsafe_allow_html=True,
        )

    run_btn = st.button("🚀 Run Optimizer", type="primary", disabled=not bool(tickers))

    # ── Run pipeline ──────────────────────────────────────────
    if run_btn and tickers:
        with st.spinner("Running: GARCH → DCC → HMM → Black-Litterman → MVO… (~30s)"):
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
                    "allow_short": allow_short,
                }
            except Exception as e:
                st.error(f"Optimizer error: {e}")
                st.exception(e)
                st.stop()

    # ── Results ───────────────────────────────────────────────
    if st.session_state["sizing_results"] is None:
        return

    results      = st.session_state["sizing_results"]
    params       = st.session_state["sizing_params"]
    weights      = results["weights"]
    stop_data    = results["stop_data"]
    regimes      = results["regimes"]
    port_metrics = results["portfolio_metrics"]
    capital_used = params["capital"]
    invest_mode  = params["invest_mode"]

    # ── ② Portfolio Metrics ───────────────────────────────────
    st.markdown('<div class="section-header">② Portfolio Metrics</div>', unsafe_allow_html=True)

    pm1, pm2, pm3, pm4, pm5 = st.columns(5)
    t_df  = port_metrics.get("t_df", 5.0)
    cards = [
        (pm1, "Expected Return",      f"{port_metrics['annual_return']*100:.2f}%",  "p.a."),
        (pm2, "Volatility",           f"{port_metrics['annual_vol']*100:.2f}%",     "p.a."),
        (pm3, "Sharpe Ratio",         f"{port_metrics['sharpe']:.2f}",              "rf = 7%"),
        (pm4, "MC VaR (95%, 1mo)",    f"{abs(port_metrics['mc_var'])*100:.2f}%",
         f"t-dist df={t_df:.1f}"),
        (pm5, "MC CVaR (95%, 1mo)",   f"{abs(port_metrics['mc_cvar'])*100:.2f}%",
         f"Rs{capital_used * abs(port_metrics['mc_cvar']):,.0f}"),
    ]
    for col, label, value, delta in cards:
        with col:
            st.markdown(
                f'<div class="metric-card">'
                f'<div class="metric-label">{label}</div>'
                f'<div class="metric-value">{value}</div>'
                f'<div class="metric-delta">{delta}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── ③ Combined Allocation + Stop Loss Table ───────────────
    st.markdown(
        '<div class="section-header">③ Allocation & Stop Losses</div>',
        unsafe_allow_html=True,
    )

    table_col, chart_col = st.columns([3, 2])

    with table_col:
        rows = []
        for ticker in params["tickers"]:
            sd = stop_data[ticker]
            regime = regimes[ticker]["regime"]
            bl_ret = results["bl_returns"][ticker]
            is_short = sd.get("is_short", False)
            direction = "SHORT" if is_short else "LONG"
            stop_label = "Cover ▲" if is_short else "Stop ▼"
            rows.append({
                "Stock":        ticker,
                "Dir":          direction,
                "Regime":       regime,
                "BL Return":    f"{bl_ret*100:.1f}%",
                "Weight":       f"{sd['weight_pct']:.1f}%",
                "Alloc (₹)":   f"₹{sd['allocation']:,.0f}",
                "Shares":       f"{sd['shares']:.3f}",
                "Entry (₹)":   f"₹{sd['entry_price']:,.2f}",
                f"{stop_label}":f"₹{sd['stop_price']:,.2f}",
                "Stop %":       f"{sd['stop_pct']:.2f}%",
                "Daily σ":      f"{sd['daily_sigma_pct']:.2f}%",
                "At Risk (₹)":  f"₹{sd['risk_per_position']:,.0f}",
            })

        df_alloc = pd.DataFrame(rows)

        def colour_cells(row):
            styles = [""] * len(row)
            idx = df_alloc.columns.tolist()

            # Direction column: red bg for short, green for long
            if "Dir" in idx:
                di = idx.index("Dir")
                if row["Dir"] == "SHORT":
                    styles[di] = "background-color:#3a1a1a; color:#fc8181; font-weight:700;"
                else:
                    styles[di] = "background-color:#1a3a2a; color:#68d391; font-weight:700;"

            # Regime column
            if "Regime" in idx:
                ri = idx.index("Regime")
                bg    = REGIME_BG.get(row["Regime"], "")
                color = REGIME_COLOR.get(row["Regime"], "white")
                styles[ri] = f"background-color:{bg}; color:{color}; font-weight:600;"

            return styles

        styled = df_alloc.style.apply(colour_cells, axis=1)
        st.dataframe(styled, width='stretch', hide_index=True)

        # Portfolio-level risk summary
        total_risk = sum(stop_data[t]["risk_per_position"] for t in params["tickers"])
        st.markdown(
            f'<div class="warning-box">'
            f'📌 <b>Portfolio Stop (95% monthly VaR):</b> '
            f'{port_metrics["monthly_var_95"]*100:.2f}% '
            f'→ ₹{capital_used * port_metrics["monthly_var_95"]:,.0f} &nbsp;|&nbsp; '
            f'<b>Total ₹ at Risk:</b> ₹{total_risk:,.0f}'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Regime shift warnings (only if probability > 25%)
        for ticker in params["tickers"]:
            r = regimes[ticker]
            current = r["regime"]
            other = {k: v for k, v in r["transition_probs"].items() if k != current}
            if other:
                top_shift = max(other, key=other.get)
                if other[top_shift] > 0.25:
                    risk_col = REGIME_COLOR.get(top_shift, "#a0aec0")
                    st.markdown(
                        f'<div class="warning-box">'
                        f'⚠️ <b>{ticker}</b>: {other[top_shift]:.0%} chance of '
                        f'{current} → <span style="color:{risk_col}">{top_shift}</span>. '
                        f'Monitor closely.'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

    with chart_col:
        fig_w = plot_weight_bar(weights)
        st.pyplot(fig_w, width='stretch')
        plt.close(fig_w)

        # Compact regime summary with smoothed probabilities
        st.markdown("**Current Regimes**")
        regime_cols = st.columns(len(params["tickers"]))
        for i, ticker in enumerate(params["tickers"]):
            r        = regimes[ticker]
            current  = r["regime"]
            stay_p   = r["transition_probs"].get(current, 0)
            smooth_p = r.get("regime_probs", {}).get(current, stay_p)
            with regime_cols[i]:
                prob_lines = "<br>".join(
                    f'<span style="color:{REGIME_COLOR.get(k, "#a0aec0")};font-size:10px;">'
                    f'{k}: {v:.0%}</span>'
                    for k, v in r.get("regime_probs", {}).items()
                )
                st.markdown(
                    f'<div class="metric-card" style="padding:10px 14px;">'
                    f'<div class="metric-label">{ticker}</div>'
                    f'<div style="margin:4px 0;">{_regime_pill(current)}</div>'
                    f'<div style="margin-top:4px;">{prob_lines}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ── ④ DCA Schedule (only in DCA mode) ─────────────────────
    if invest_mode == "dca" and results.get("dca_df") is not None:
        dca_df = results["dca_df"]
        st.markdown(
            f'<div class="section-header">'
            f'④ DCA Schedule — {params["dca_months"]} months, front-loaded'
            f'</div>',
            unsafe_allow_html=True,
        )

        dca_col, dca_chart_col = st.columns([2, 3])

        with dca_col:
            dca_display = dca_df.copy()
            dca_display["Deploy (₹)"] = dca_display["Deploy (Rs)"].map(lambda x: f"₹{x:,.0f}")
            for t in params["tickers"]:
                if t in dca_display.columns:
                    dca_display[t] = dca_display[t].map(lambda x: f"₹{x:,.0f}")
            st.dataframe(dca_display, width='stretch', hide_index=True)

        with dca_chart_col:
            fig_dca = plot_dca_schedule(dca_df)
            st.pyplot(fig_dca, width='stretch')
            plt.close(fig_dca)

        st.markdown(
            '<div class="info-box">'
            '💡 Front-loading applies because current regime signals are freshest. '
            'Trigger a full rebalance if HMM detects a regime shift mid-schedule.'
            '</div>',
            unsafe_allow_html=True,
        )