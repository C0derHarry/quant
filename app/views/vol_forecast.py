"""
pages/vol_forecast.py
─────────────────────────────────────────────────────────────────
Volatility Forecasting Dashboard
Integrates: GARCH model selection + EWMA diagnostics
─────────────────────────────────────────────────────────────────
"""

import warnings
warnings.filterwarnings("ignore")

import sys
import os
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from arch import arch_model
from statsmodels.tsa.stattools import pacf
from scipy.stats import norm

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from core.volatility.ewma import (
    ewma_variance, ewma_volatility, get_optimal_lambda, half_life, decay_table
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
    font-size: 22px;
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
.regime-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 4px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    font-weight: 600;
}
.best-model-box {
    background: linear-gradient(135deg, #1a2035 0%, #0e1117 100%);
    border: 1px solid #4a5568;
    border-left: 3px solid #63b3ed;
    border-radius: 8px;
    padding: 16px 20px;
    margin: 16px 0;
}
.stDataFrame { font-family: 'IBM Plex Mono', monospace; font-size: 12px; }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# CORE FUNCTIONS — GARCH
# ═══════════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False)
def fetch_returns(tickers: list[str], period: str = "10y") -> pd.DataFrame:
    """
    Download prices and compute equal-weight portfolio log-returns.
    Single ticker → returns that ticker's return series.
    Multiple tickers → equal-weight blended return series.
    """
    raw = yf.download(tickers, period=period, auto_adjust=True, progress=False)["Close"]
    if isinstance(raw, pd.Series):
        raw = raw.to_frame(tickers[0])
    raw = raw[tickers].dropna()
    log_ret = np.log(raw / raw.shift(1)).dropna()
    if len(tickers) == 1:
        return log_ret[tickers[0]], raw
    # Equal-weight portfolio returns
    port_ret = log_ret.mean(axis=1)
    port_ret.name = "Portfolio"
    return port_ret, raw


def run_garch_selection(returns: pd.Series) -> tuple[pd.DataFrame, int, int]:
    """
    PACF-guided GARCH model grid search.
    Returns:
        models_df : DataFrame with AIC/BIC for every candidate
        best_p    : selected p
        best_q    : selected q
    """
    pacf_vals, _ = pacf(returns ** 2, nlags=20, alpha=0.05)
    n = len(returns)
    sig_threshold = 1.96 / np.sqrt(n)
    sig_lags = np.where(np.abs(pacf_vals[1:]) > sig_threshold)[0] + 1

    cap = 3
    max_pq = 1
    for lag in sig_lags:
        if lag <= cap:
            max_pq = lag
    max_pq = max(max_pq, 1)

    models: dict[str, dict] = {}

    def _fit(p, q):
        try:
            if p == 0:
                res = arch_model(returns, vol='Garch', q=q).fit(
                    disp='off', options={'maxiter': 1000})
            elif q == 0:
                res = arch_model(returns, vol='Garch', p=p).fit(
                    disp='off', options={'maxiter': 1000})
            else:
                res = arch_model(returns, vol='Garch', p=p, q=q).fit(
                    disp='off', options={'maxiter': 1000})
            if res.convergence_flag == 0:
                return res
        except Exception:
            pass
        return None

    candidate_specs = (
        [(p, q) for p in range(1, max_pq + 1) for q in range(1, max_pq + 1)]
        + [(p, 0) for p in range(1, max_pq + 1)]
        + [(0, q) for q in range(1, max_pq + 1)]
    )

    for p, q in candidate_specs:
        key = f"GARCH({p},{q})"
        res = _fit(p, q)
        if res is not None:
            # Check significance of GARCH params
            pvals = res.pvalues
            garch_pvals = pvals[pvals.index.str.startswith(('alpha', 'beta'))]
            all_sig = (garch_pvals < 0.05).all()
            models[key] = {
                "AIC": round(res.aic, 4),
                "BIC": round(res.bic, 4),
                "All Params Significant": "✅" if all_sig else "❌",
            }

    if not models:
        return pd.DataFrame(), 1, 1

    df = pd.DataFrame(models).T.sort_values("BIC")

    # Pick best by joint AIC+BIC and significance
    best_p, best_q = 1, 1
    best_bic = np.inf
    best_aic = np.inf
    for p, q in candidate_specs:
        key = f"GARCH({p},{q})"
        if key not in models:
            continue
        row = models[key]
        if row["BIC"] < best_bic and row["AIC"] < best_aic:
            best_bic = row["BIC"]
            best_aic = row["AIC"]
            best_p, best_q = p, q

    return df, best_p, best_q


def model_predict(returns: pd.Series, best_p: int, best_q: int,
                  horizon: int) -> pd.DataFrame:
    """Run best GARCH model and return forecast DataFrame."""
    horizon = min(max(horizon, 1), 10)
    if best_p == 0:
        fitted = arch_model(returns, vol='Garch', q=best_q).fit(
            disp='off', options={'maxiter': 1000})
    elif best_q == 0:
        fitted = arch_model(returns, vol='Garch', p=best_p).fit(
            disp='off', options={'maxiter': 1000})
    else:
        fitted = arch_model(returns, vol='Garch', p=best_p, q=best_q).fit(
            disp='off', options={'maxiter': 1000})

    forecast = fitted.forecast(horizon=horizon, reindex=False)
    var_fc = forecast.variance.iloc[0].values

    df = pd.DataFrame({
        "Day": range(1, horizon + 1),
        "Variance": np.round(var_fc, 8),
        "Daily Vol": np.round(np.sqrt(var_fc), 6),
        "Ann. Volatility": np.round(np.sqrt(var_fc) * np.sqrt(252), 4),
    }).set_index("Day")
    return df, fitted



# ═══════════════════════════════════════════════════════════════
# PLOTTING HELPERS
# ═══════════════════════════════════════════════════════════════

def plot_ewma_history(returns: pd.Series, lambda_: float,
                      prices: pd.DataFrame | pd.Series) -> plt.Figure:
    """EWMA vs Rolling Std two-panel chart."""
    ewma_vol = ewma_volatility(returns, lambda_=lambda_)
    roll_vol = returns.rolling(21).std() * np.sqrt(252)
    roll_vol.name = "Rolling Std (21d)"

    if isinstance(prices, pd.DataFrame):
        px = prices.mean(axis=1)
    else:
        px = prices

    fig, (ax_p, ax_v) = plt.subplots(2, 1, figsize=(11, 7),
                                      gridspec_kw={"height_ratios": [1, 2]},
                                      sharex=True)
    fig.patch.set_facecolor("#0e1117")
    for ax in (ax_p, ax_v):
        ax.set_facecolor("#141923")
        ax.spines[:].set_color("#2d3748")
        ax.tick_params(colors="#718096", labelsize=9)

    ax_p.plot(px, color="#63b3ed", linewidth=0.9, label="Price")
    ax_p.set_ylabel("Price", color="#718096", fontsize=9)
    ax_p.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"₹{x:,.0f}"))
    ax_p.legend(fontsize=8, facecolor="#0e1117", labelcolor="white")

    ax_v.plot(ewma_vol, color="#fc8181", linewidth=1.4,
              label=f"EWMA (λ={lambda_:.4f})", zorder=3)
    ax_v.plot(roll_vol, color="#68d391", linewidth=1.2,
              linestyle="--", alpha=0.8, label="Rolling Std (21d)", zorder=2)
    ax_v.fill_between(ewma_vol.index, ewma_vol, roll_vol,
                      where=(ewma_vol > roll_vol), interpolate=True,
                      alpha=0.1, color="#fc8181")
    ax_v.set_ylabel("Ann. Volatility", color="#718096", fontsize=9)
    ax_v.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x*100:.0f}%"))
    ax_v.legend(fontsize=8, facecolor="#0e1117", labelcolor="white")
    ax_v.xaxis.set_major_locator(mdates.YearLocator())
    ax_v.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.autofmt_xdate(rotation=0, ha="center")
    fig.tight_layout()
    return fig


def plot_garch_forecast(forecast_df: pd.DataFrame, fitted_model,
                        returns: pd.Series) -> plt.Figure:
    """Plot historical conditional vol + GARCH forecast ribbon."""
    cond_vol_ann = fitted_model.conditional_volatility / 100 * np.sqrt(252)
    days = forecast_df.index.tolist()
    forecast_ann = forecast_df["Ann. Volatility"].values

    fig, ax = plt.subplots(figsize=(11, 5))
    fig.patch.set_facecolor("#0e1117")
    ax.set_facecolor("#141923")
    ax.spines[:].set_color("#2d3748")
    ax.tick_params(colors="#718096", labelsize=9)

    # Historical conditional vol (last 252 days for clarity)
    hist_tail = cond_vol_ann.iloc[-252:]
    ax.plot(hist_tail.index, hist_tail.values,
            color="#a0aec0", linewidth=0.9, alpha=0.7, label="Historical σ")

    # Forecast as extended x-axis with integer steps
    last_date = returns.index[-1]
    fcast_x = [last_date + pd.Timedelta(days=i) for i in range(1, len(days) + 1)]

    ax.plot([last_date] + fcast_x,
            [hist_tail.iloc[-1]] + list(forecast_ann),
            color="#f6e05e", linewidth=2.0, marker="o", markersize=5,
            zorder=5, label="GARCH Forecast")

    # Confidence ribbon (±1 std proxy)
    ribbon_upper = list(forecast_ann * 1.15)
    ribbon_lower = list(forecast_ann * 0.85)
    ax.fill_between(fcast_x, ribbon_lower, ribbon_upper,
                    color="#f6e05e", alpha=0.12, label="±15% band")

    ax.axvline(last_date, color="#4a5568", linewidth=1, linestyle="--", alpha=0.6)
    ax.set_ylabel("Annualised Volatility", color="#718096", fontsize=9)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x*100:.1f}%"))
    ax.legend(fontsize=8, facecolor="#0e1117", labelcolor="white")
    ax.set_title("GARCH Conditional Volatility + Forecast", color="#e2e8f0",
                 fontsize=11, fontfamily="monospace", pad=10)
    fig.tight_layout()
    return fig


def plot_lambda_sensitivity(returns: pd.Series) -> plt.Figure:
    lambdas = np.round(np.arange(0.90, 1.00, 0.01), 2).tolist()
    cmap = plt.cm.RdYlGn
    colours = [cmap(i / (len(lambdas) - 1)) for i in range(len(lambdas))]

    fig, ax = plt.subplots(figsize=(11, 4))
    fig.patch.set_facecolor("#0e1117")
    ax.set_facecolor("#141923")
    ax.spines[:].set_color("#2d3748")
    ax.tick_params(colors="#718096", labelsize=9)

    for lam, col in zip(lambdas, colours):
        vol = ewma_volatility(returns, lambda_=lam)
        ax.plot(vol, color=col, linewidth=0.9, alpha=0.85, label=f"λ={lam:.2f}")

    ax.set_ylabel("Ann. Volatility", color="#718096", fontsize=9)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x*100:.0f}%"))
    ax.legend(title="λ", title_fontsize=8, fontsize=7,
              loc="upper right", ncol=2, facecolor="#0e1117", labelcolor="white")
    ax.set_title("EWMA Lambda Sensitivity", color="#e2e8f0",
                 fontsize=11, fontfamily="monospace", pad=10)
    fig.tight_layout()
    return fig


def show_vol_forecast():

    # ═══════════════════════════════════════════════════════════════
    # SESSION STATE KEYS
    # ═══════════════════════════════════════════════════════════════

    for key in ["garch_ran", "returns", "prices_raw", "models_df",
                "best_p", "best_q", "opt_lambda", "tickers_used",
                "forecast_df", "fitted_model"]:
        if key not in st.session_state:
            st.session_state[key] = None

    if "garch_ran" not in st.session_state or st.session_state["garch_ran"] is None:
        st.session_state["garch_ran"] = False
    if "forecast_ran" not in st.session_state:
        st.session_state["forecast_ran"] = False


    # ═══════════════════════════════════════════════════════════════
    # UI — HEADER
    # ═══════════════════════════════════════════════════════════════

    st.title("📈 Volatility Forecasting")
    st.markdown(
        "<p style='color:#718096; font-size:14px; margin-top:-10px;'>"
        "GARCH model selection · EWMA diagnostics · Forward volatility forecasting"
        "</p>",
        unsafe_allow_html=True,
    )

    # ═══════════════════════════════════════════════════════════════
    # SECTION 1 — STOCK SELECTION
    # ═══════════════════════════════════════════════════════════════

    st.markdown('<div class="section-header">① Stock Selection</div>', unsafe_allow_html=True)

    col_left, col_right = st.columns([2, 1])
    with col_left:
        ticker_input = st.text_input(
            "Enter ticker(s) — comma-separated for multiple",
            value="RELIANCE.NS",
            placeholder="e.g. RELIANCE.NS, TCS.NS, HDFCBANK.NS",
            help=(
                "For multiple stocks, equal-weight portfolio returns are used. "
                "Use NSE tickers (e.g. RELIANCE.NS) or US tickers (e.g. AAPL)."
            ),
        )
    with col_right:
        period = st.selectbox(
            "Data period", options=["5y", "7y", "10y", "3y"], index=2
        )

    tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]

    if len(tickers) > 1:
        st.info(
            f"📊 **Portfolio mode** — {len(tickers)} stocks with **equal exposure** "
            f"({100/len(tickers):.1f}% each). GARCH is fitted on the blended return series.",
            icon="ℹ️",
        )

    run_analysis = st.button("🔍 Run GARCH Model Selection", type="primary",
                            disabled=not bool(tickers))

    # ═══════════════════════════════════════════════════════════════
    # SECTION 2 — GARCH ANALYSIS
    # ═══════════════════════════════════════════════════════════════

    if run_analysis and tickers:
        with st.spinner("Fetching data & fitting GARCH grid…"):
            try:
                returns, prices_raw = fetch_returns(tickers, period=period)
                models_df, best_p, best_q = run_garch_selection(returns)
                opt_lambda = get_optimal_lambda(returns)

                st.session_state.update({
                    "garch_ran": True,
                    "returns": returns,
                    "prices_raw": prices_raw,
                    "models_df": models_df,
                    "best_p": best_p,
                    "best_q": best_q,
                    "opt_lambda": opt_lambda,
                    "tickers_used": tickers,
                    "forecast_ran": False,
                    "forecast_df": None,
                    "fitted_model": None,
                })
            except Exception as e:
                st.error(f"Error fetching data or fitting model: {e}")
                st.stop()

    if st.session_state["garch_ran"]:
        returns = st.session_state["returns"]
        prices_raw = st.session_state["prices_raw"]
        models_df = st.session_state["models_df"]
        best_p = st.session_state["best_p"]
        best_q = st.session_state["best_q"]
        opt_lambda = st.session_state["opt_lambda"]

        # ── EWMA quick stats ────────────────────────────────────────
        st.markdown('<div class="section-header">② EWMA Diagnostics</div>',
                    unsafe_allow_html=True)

        ewma_vol_series = ewma_volatility(returns, lambda_=opt_lambda)
        roll_vol_series = returns.rolling(21).std() * np.sqrt(252)
        ewma_var_series = ewma_variance(returns, lambda_=opt_lambda)

        confidence_level = 0.95
        z_score = norm.ppf(confidence_level)
        var_series = z_score * np.sqrt(ewma_var_series)  # as % of position

        m1, m2, m3, m4, m5 = st.columns(5)
        with m1:
            st.markdown(f"""
            <div class="metric-card">
            <div class="metric-label">Optimal λ (MLE)</div>
            <div class="metric-value">{opt_lambda:.4f}</div>
            <div class="metric-delta">Half-life: {half_life(opt_lambda):.1f}d</div>
            </div>""", unsafe_allow_html=True)
        with m2:
            st.markdown(f"""
            <div class="metric-card">
            <div class="metric-label">Current Ann. Vol (EWMA)</div>
            <div class="metric-value">{ewma_vol_series.iloc[-1]*100:.2f}%</div>
            <div class="metric-delta">{ewma_vol_series.index[-1].date()}</div>
            </div>""", unsafe_allow_html=True)
        with m3:
            st.markdown(f"""
            <div class="metric-card">
            <div class="metric-label">Peak EWMA Vol</div>
            <div class="metric-value">{ewma_vol_series.max()*100:.2f}%</div>
            <div class="metric-delta">{ewma_vol_series.idxmax().date()}</div>
            </div>""", unsafe_allow_html=True)
        with m4:
            st.markdown(f"""
            <div class="metric-card">
            <div class="metric-label">Mean EWMA Vol</div>
            <div class="metric-value">{ewma_vol_series.mean()*100:.2f}%</div>
            <div class="metric-delta">10-yr average</div>
            </div>""", unsafe_allow_html=True)
        with m5:
            st.markdown(f"""
            <div class="metric-card">
            <div class="metric-label">1-Day VaR (95%, ₹1M)</div>
            <div class="metric-value">₹{1_000_000 * z_score * np.sqrt(ewma_var_series.iloc[-1]):,.0f}</div>
            <div class="metric-delta">per ₹10L invested</div>
            </div>""", unsafe_allow_html=True)

        tab_ewma_hist, tab_lambda_sens, tab_decay = st.tabs(
            ["EWMA vs Rolling Std", "Lambda Sensitivity", "Decay Table"]
        )
        with tab_ewma_hist:
            fig_ewma = plot_ewma_history(returns, opt_lambda, prices_raw)
            st.pyplot(fig_ewma, use_container_width=True)
            plt.close(fig_ewma)

        with tab_lambda_sens:
            fig_lam = plot_lambda_sensitivity(returns)
            st.pyplot(fig_lam, use_container_width=True)
            plt.close(fig_lam)

        with tab_decay:
            dt = decay_table()
            # highlight the optimal lambda row
            opt_lam_rounded = round(opt_lambda, 2)
            def highlight_optimal(row):
                if abs(row.name - opt_lam_rounded) < 0.005:
                    return ['background-color: #2a3a4a'] * len(row)
                return [''] * len(row)
            st.dataframe(
                dt.style.apply(highlight_optimal, axis=1).format(
                    {"Half-life (days)": "{:.1f}", "95%-weight window (days)": "{:.0f}"}
                ),
                use_container_width=True,
            )
            st.caption(f"Row highlighted in blue ≈ your optimal λ ({opt_lambda:.4f})")

        # ── GARCH model comparison ──────────────────────────────────
        st.markdown('<div class="section-header">③ GARCH Model Comparison</div>',
                    unsafe_allow_html=True)

        if not models_df.empty:
            def highlight_best(row):
                if row.name == f"GARCH({best_p},{best_q})":
                    return ['background-color: #1a3a2a; color: #68d391'] * len(row)
                return [''] * len(row)

            styled_df = (
                models_df.style
                .apply(highlight_best, axis=1)
                .format({"AIC": "{:.4f}", "BIC": "{:.4f}"})
                .background_gradient(subset=["BIC"], cmap="RdYlGn_r")
            )
            st.dataframe(styled_df, use_container_width=True)
        else:
            st.warning("No GARCH models converged. Try a different ticker or period.")

        # ── Best model highlight box ────────────────────────────────
        best_row = models_df.loc[f"GARCH({best_p},{best_q})"] if not models_df.empty else None
        if best_row is not None:
            st.markdown(
                f"""<div class="best-model-box">
                <span style="font-family:'IBM Plex Mono',monospace; font-size:12px; color:#718096;">
                SELECTED MODEL</span><br>
                <span style="font-family:'IBM Plex Mono',monospace; font-size:22px;
                            font-weight:600; color:#63b3ed;">
                GARCH({best_p},{best_q})</span>
                &nbsp;&nbsp;
                <span style="font-family:'IBM Plex Mono',monospace; font-size:13px; color:#a0aec0;">
                AIC: {best_row['AIC']:.4f} &nbsp;|&nbsp; BIC: {best_row['BIC']:.4f}
                </span>
                </div>""",
                unsafe_allow_html=True,
            )

        # ── Forecast section ────────────────────────────────────────
        st.markdown('<div class="section-header">④ Volatility Forecast</div>',
                    unsafe_allow_html=True)

        fc_col1, fc_col2 = st.columns([1, 3])
        with fc_col1:
            horizon = st.slider(
                "Forecast horizon (days)", min_value=1, max_value=10, value=5, step=1
            )
            run_forecast_btn = st.button(
                f"▶ Run Forecast ({horizon}d)",
                type="primary",
                disabled=models_df.empty,
            )

        if run_forecast_btn:
            with st.spinner(f"Refitting GARCH({best_p},{best_q}) and forecasting…"):
                forecast_df, fitted_model = model_predict(returns, best_p, best_q, horizon)
                st.session_state["forecast_df"] = forecast_df
                st.session_state["fitted_model"] = fitted_model
                st.session_state["forecast_ran"] = True

        if st.session_state["forecast_ran"] and st.session_state["forecast_df"] is not None:
            forecast_df = st.session_state["forecast_df"]
            fitted_model = st.session_state["fitted_model"]

            # Forecast table
            fc_display = forecast_df.copy()
            fc_display["Daily Vol"] = fc_display["Daily Vol"].map(lambda x: f"{x*100:.4f}%")
            fc_display["Ann. Volatility"] = fc_display["Ann. Volatility"].map(
                lambda x: f"{x*100:.2f}%"
            )
            fc_display["Variance"] = fc_display["Variance"].map(lambda x: f"{x:.2e}")
            st.dataframe(fc_display, use_container_width=True)

            # Forecast plot
            fig_fc = plot_garch_forecast(forecast_df, fitted_model, returns)
            st.pyplot(fig_fc, use_container_width=True)
            plt.close(fig_fc)

            # Quick VaR from GARCH forecast
            st.markdown("**Implied 95% 1-Day VaR from GARCH forecast (₹1M position)**")
            # # var_cols = st.columns(len(forecast_df))
            # # for i, (day, row) in enumerate(forecast_df.iterrows()):
            # #     var_inr = 1_000_000 * z_score * row["Daily Vol"]
            # #     with var_cols[i]:
            # #         st.metric(f"Day {day}", f"₹{var_inr:,.0f}", delta=None)
            # for day, row in forecast_df.iterrows():
            #     var_inr = 1_000_000 * z_score * row["Daily Vol"]
            #     # Each call to st.metric creates a new row automatically
            #     st.metric(label=f"Forecast Day {day}", value=f"₹{var_inr:,.0f}")
            if st.session_state["forecast_ran"] and st.session_state["forecast_df"] is not None:
                forecast_df = st.session_state["forecast_df"]
                
                # 1. Create a clean copy for the VaR table
                # We use .reset_index() to turn the 'Day' index into a visible column
                var_display_df = forecast_df.copy().reset_index()
                
                # 2. Calculate the VaR column
                # z_score is defined earlier in your script (norm.ppf(0.95))
                var_display_df["1-Day VaR (₹1M)"] = 1_000_000 * z_score * var_display_df["Daily Vol"]
                
                # 3. Filter to ONLY show 'Day' and 'VaR'
                var_display_df = var_display_df[["Day", "1-Day VaR (₹1M)"]]
                
                # 4. Format for display
                var_display_df["1-Day VaR (₹1M)"] = var_display_df["1-Day VaR (₹1M)"].map(lambda x: f"₹{x:,.0f}")
                
                # 5. Render to UI
                st.markdown("### 🛡️ Risk Forecast (VaR)")
                st.dataframe(
                    var_display_df, 
                    use_container_width=False, 
                    hide_index=True # Hides the default pandas row numbers
                )