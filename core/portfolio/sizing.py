"""
============================================================
PORTFOLIO OPTIMIZER: GARCH + DCC-GARCH + HMM + Black-Litterman MVO
============================================================
"""

import numpy as np
import pandas as pd
import yfinance as yf
import warnings
from arch import arch_model
from hmmlearn.hmm import GaussianHMM
from scipy.optimize import minimize
from scipy.stats import norm
from tabulate import tabulate
from core.data import fetch_financial_data


warnings.filterwarnings("ignore")
np.random.seed(42)


# ============================================================
# SECTION 1: DATA FETCHING
# ============================================================

def fetch_data(tickers: list, period: str = "5y") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fetch adjusted closing prices and compute log returns."""
    print(f"    Downloading {len(tickers)} stocks over {period}...")
    raw = yf.download(tickers, period=period, auto_adjust=True, progress=False)["Close"]

    # Single-ticker download returns a Series — promote to DataFrame
    if isinstance(raw, pd.Series):
        raw = raw.to_frame(tickers[0])

    # Keep only tickers that actually came back
    available = [t for t in tickers if t in raw.columns]
    missing   = [t for t in tickers if t not in raw.columns]
    if missing:
        print(f"    ⚠️  No data returned for: {missing}. Proceeding without them.")
    if not available:
        raise ValueError(
            f"yfinance returned no data for any of: {tickers}. "
            "Check the ticker symbols and your internet connection."
        )

    raw = raw[available]

    # Drop rows where ALL columns are NaN, then forward-fill short gaps (≤5 days)
    raw = raw.dropna(how="all").ffill(limit=5).dropna()

    if raw.empty:
        raise ValueError(
            f"Price data for {available} is empty after cleaning. "
            "Try a shorter period or check the ticker symbols."
        )

    log_returns = np.log(raw / raw.shift(1)).dropna()

    if log_returns.empty:
        raise ValueError(
            f"Could not compute returns for {available} — "
            "price series may be too short."
        )

    print(
        f"    {len(log_returns)} trading days loaded "
        f"({log_returns.index[0].date()} → {log_returns.index[-1].date()})"
    )
    return raw, log_returns


def get_market_caps(tickers: list) -> dict:
    """Fetch the market cap for each ticker."""
    market_caps = {}
    financial_data = fetch_financial_data(tickers)

    for ticker in tickers:
        data = financial_data.get(ticker)
        if not data:
            continue
        info = data['info']
        market_cap = info.get('marketCap', 0) or 0
        # Fallback: use equal weight proxy if market cap is unavailable
        market_caps[ticker] = market_cap if market_cap > 0 else 1

    # If all came back zero, return equal weights
    if sum(market_caps.values()) == 0:
        market_caps = {t: 1 for t in tickers}

    return market_caps


# ============================================================
# SECTION 2: UNIVARIATE GARCH(1,1)
# ============================================================

def fit_garch_single(return_series: pd.Series) -> dict:
    """
    Fit GARCH(1,1) to a single asset.
    Returns forecasted daily sigma and standardized residuals.
    """
    scaled = return_series * 100
    model = arch_model(scaled, vol="Garch", p=1, q=1, dist="t", rescale=False)
    res = model.fit(disp="off", show_warning=False, options={'maxiter': 1000})

    forecast = res.forecast(horizon=1, reindex=False)
    sigma_next = float(np.sqrt(forecast.variance.iloc[-1, 0])) / 100

    cond_vol = res.conditional_volatility / 100
    std_resid = res.std_resid

    return {
        "model": res,
        "sigma_forecast": sigma_next,
        "cond_vol": cond_vol,
        "std_resid": std_resid,
        "params": res.params,
    }


# ============================================================
# SECTION 3: DCC-GARCH
# ============================================================

def fit_dcc_garch(returns_df: pd.DataFrame) -> dict:
    """
    Two-stage DCC-GARCH:
      Stage 1 – univariate GARCH(1,1) per asset
      Stage 2 – DCC correlation dynamics
      Final   – annualised covariance H_t = D_t · R_t · D_t
    """
    tickers = returns_df.columns.tolist()
    n = len(tickers)

    # --- Stage 1: Univariate GARCH ---
    garch_fits = {}
    std_resids = pd.DataFrame(index=returns_df.index)

    for ticker in tickers:
        fit = fit_garch_single(returns_df[ticker])
        garch_fits[ticker] = fit
        std_resids[ticker] = fit["std_resid"]

    std_resids = std_resids.dropna()
    eps = std_resids.values
    T = len(eps)

    Q_bar = np.cov(eps.T)
    if Q_bar.ndim == 0:
        Q_bar = np.array([[float(Q_bar)]])

    # --- Stage 2: Optimize DCC parameters ---
    def dcc_neg_loglik(params):
        a, b = params
        if a <= 0 or b <= 0 or a + b >= 0.9999:
            return 1e10
        Q_t = Q_bar.copy()
        ll = 0.0
        for t in range(1, T):
            e_lag = eps[t - 1].reshape(-1, 1)
            Q_t = (1 - a - b) * Q_bar + a * (e_lag @ e_lag.T) + b * Q_t
            d_inv = 1.0 / np.sqrt(np.diag(Q_t))
            R_t = Q_t * np.outer(d_inv, d_inv)
            np.fill_diagonal(R_t, 1.0)
            try:
                sign, logdet = np.linalg.slogdet(R_t)
                if sign <= 0:
                    return 1e10
                R_inv = np.linalg.inv(R_t)
                e_t = eps[t]
                ll += -0.5 * (logdet + e_t @ R_inv @ e_t - e_t @ e_t)
            except np.linalg.LinAlgError:
                return 1e10
        return -ll

    opt = minimize(
        dcc_neg_loglik,
        x0=[0.05, 0.90],
        bounds=[(1e-6, 0.49), (1e-6, 0.98)],
        method="L-BFGS-B",
        options={"ftol": 1e-10, "maxiter": 500},
    )
    a_hat, b_hat = opt.x

    # Re-run DCC to get final R_T
    Q_t = Q_bar.copy()
    for t in range(1, T):
        e_lag = eps[t - 1].reshape(-1, 1)
        Q_t = (1 - a_hat - b_hat) * Q_bar + a_hat * (e_lag @ e_lag.T) + b_hat * Q_t

    d_inv = 1.0 / np.sqrt(np.diag(Q_t))
    R_current = Q_t * np.outer(d_inv, d_inv)
    np.fill_diagonal(R_current, 1.0)

    sigma_vec = np.array([garch_fits[t]["sigma_forecast"] for t in tickers])
    cov_daily = np.outer(sigma_vec, sigma_vec) * R_current
    cov_annual = cov_daily * 252

    return {
        "garch_fits": garch_fits,
        "cov_annual": cov_annual,
        "cov_daily": cov_daily,
        "corr_matrix": R_current,
        "sigma_forecasts": {t: garch_fits[t]["sigma_forecast"] for t in tickers},
        "dcc_a": a_hat,
        "dcc_b": b_hat,
        "Q_bar": Q_bar,
    }


# ============================================================
# SECTION 4: HMM REGIME DETECTION
# ============================================================

def detect_regimes(returns_df: pd.DataFrame, n_states: int = 3) -> dict:
    """
    Fit a 3-state Gaussian HMM per asset.
    States labelled post-hoc: Bull / Sideways / Bear.
    """
    results = {}

    for ticker in returns_df.columns:
        ret = returns_df[ticker].values
        roll_vol = (
            returns_df[ticker].rolling(5).std().bfill().values
        )
        features = np.column_stack([ret, roll_vol])

        hmm = GaussianHMM(
            n_components=n_states,
            covariance_type="diag",
            n_iter=2000,
            tol=1e-5,
            random_state=42,
        )
        hmm.fit(features)
        states_seq = hmm.predict(features)

        state_mean_ret = {}
        state_vol = {}
        for s in range(3):
            mask = states_seq == s
            state_mean_ret[s] = ret[mask].mean() if mask.sum() > 0 else 0.0
            state_vol[s] = ret[mask].std() if mask.sum() > 0 else 0.0

        state_score = {}
        for s in range(3):
            ret_norm = state_mean_ret[s] - np.mean(list(state_mean_ret.values()))
            vol_norm = state_vol[s] - np.mean(list(state_vol.values()))
            state_score[s] = ret_norm - vol_norm

        sorted_states = sorted(state_score.items(), key=lambda x: x[1])
        bear_state = sorted_states[0][0]
        side_state = sorted_states[1][0]
        bull_state = sorted_states[2][0]

        label_map = {bear_state: "Bear", side_state: "Sideways", bull_state: "Bull"}
        current_label = label_map[states_seq[-1]]

        current_state_id = states_seq[-1]
        trans_probs = hmm.transmat_[current_state_id]
        trans_named = {label_map[i]: round(trans_probs[i], 3) for i in range(n_states)}

        results[ticker] = {
            "regime": current_label,
            "regime_mean_daily": state_mean_ret[states_seq[-1]],
            "state_means": {label_map[s]: state_mean_ret[s] for s in range(n_states)},
            "transition_probs": trans_named,
            "history": [label_map[s] for s in states_seq],
        }

    return results


# ============================================================
# SECTION 5: EXPECTED RETURN ESTIMATION
# ============================================================

def estimate_expected_returns(
    returns_df: pd.DataFrame,
    regimes: dict,
    user_target_annual: float,
) -> dict:
    """
    Blend three signals into expected annual return per asset:
      1. HMM regime-conditioned historical mean  (weight: 0.60)
      2. 1M + 3M momentum signal                 (weight: 0.40 or 0.20)
      3. User target return                       (weight: 0.20, suppressed in Bear)
    """
    trading_days = 252
    exp_returns = {}

    for ticker in returns_df.columns:
        ret_series = returns_df[ticker]

        regime_daily = regimes[ticker]["regime_mean_daily"]
        regime_annual = regime_daily * trading_days

        mom_1m = ret_series.tail(21).mean() * trading_days
        mom_3m = ret_series.tail(63).mean() * trading_days
        momentum_annual = 0.5 * mom_1m + 0.5 * mom_3m

        if regimes[ticker]["regime"] == "Bear":
            user_weight = 0.0
        else:
            user_weight = 0.2

        model_annual = 0.6 * regime_annual + 0.4 * momentum_annual + user_weight * user_target_annual

        divergence_pct = abs(model_annual - user_target_annual) * 100
        warning = (
            f"⚠️  Model ({model_annual*100:.1f}%) vs User Target ({user_target_annual*100:.1f}%)"
            f" diverge by {divergence_pct:.1f}pp"
            if divergence_pct > 15 else None
        )

        exp_returns[ticker] = {
            "annual": model_annual,
            "daily": model_annual / trading_days,
            "regime_signal": regime_annual,
            "momentum_signal": momentum_annual,
            "user_target": user_target_annual,
            "divergence_warning": warning,
        }

    return exp_returns


# ============================================================
# SECTION 6: BLACK-LITTERMAN + MVO
# ============================================================

def black_litterman_returns(
    market_caps: dict,
    cov_annual: np.ndarray,
    tickers: list,
    views: dict,
    tau: float = 0.5,
    risk_aversion: float = 2.5,
) -> np.ndarray:
    """
    Black-Litterman posterior:
      Prior  (π): implied equilibrium returns from market-cap weights
      Views  (Q): model's expected returns per asset
      Result (μ_BL): blended estimate
    """
    n = len(tickers)
    total_mcap = sum(market_caps.values())
    w_mkt = np.array([market_caps[t] / total_mcap for t in tickers])

    pi = risk_aversion * cov_annual @ w_mkt

    P = np.eye(n)
    Q = np.array([views[t] for t in tickers])

    tau_sigma = tau * cov_annual
    omega = np.diag(np.diag(P @ tau_sigma @ P.T)) * 0.1

    tau_sigma_inv = np.linalg.inv(tau_sigma)
    omega_inv = np.linalg.inv(omega)

    M_inv = tau_sigma_inv + P.T @ omega_inv @ P
    M = np.linalg.inv(M_inv)
    mu_bl = M @ (tau_sigma_inv @ pi + P.T @ omega_inv @ Q)

    return mu_bl


def mean_variance_optimize(
    mu: np.ndarray,
    cov_annual: np.ndarray,
    tickers: list,
    risk_appetite_monthly: float,
    allow_short: bool = False,
) -> dict:
    """
    Maximise regularised Sharpe ratio.

    Design philosophy
    -----------------
    • No hard per-stock weight cap — allocation is driven purely by each
      asset's risk/reward contribution.  A stock with 2× better Sharpe
      naturally receives ~2× the weight.
    • L2 regularisation (λ·‖w‖²) replaces hard caps.  It penalises
      concentration smoothly, so weights spread proportionally rather
      than hitting a wall at an arbitrary ceiling.
    • No gross-exposure constraint — that was the direct cause of
      cancelling pairs (e.g. +50% Reliance / -40% HDFC just to satisfy
      Σ|w| ≤ 2 while meeting the equality constraint).
    • For long/short mode the only short-side constraint is a cap on
      *total* short exposure (≤ 40% of portfolio), so individual short
      positions are still sized by risk/reward, not by a per-stock limit.

    Constraints
    -----------
    Long-only : Σw = 1,  w_i ≥ 0
    Long/short: Σw = 1,  w_i ≥ −1  (soft total-short cap via constraint)
                         Σ min(w_i, 0) ≥ −MAX_TOTAL_SHORT
    """
    n              = len(tickers)
    z_95           = norm.ppf(0.95)
    risk_free_rate = 0.07
    eq_w           = np.ones(n) / n

    # ── Regularisation strength ──────────────────────────────────────────
    # λ = 0.10 means the penalty equals ~10% of the Sharpe signal.
    # Increase to spread weights more evenly; decrease to let the best
    # stock dominate more aggressively.
    LAMBDA = 0.10

    # ── Short-side parameters (only used when allow_short=True) ──────────
    MAX_TOTAL_SHORT = 0.40   # max 40% of portfolio in short positions in total
    MAX_SHORT_SINGLE = -0.35 # no single position shorter than -35%
    MAX_LONG_SINGLE  =  0.90 # single stock can go up to 90% if it earns it

    if allow_short:
        bounds = [(MAX_SHORT_SINGLE, MAX_LONG_SINGLE) for _ in range(n)]
    else:
        bounds = [(0.0, 1.0) for _ in range(n)]   # fully open upward — L2 handles concentration

    # ── Objective: −Sharpe + λ·‖w‖² ─────────────────────────────────────
    def objective(w):
        ret    = w @ mu
        vol    = np.sqrt(w @ cov_annual @ w)
        sharpe = (ret - risk_free_rate) / vol if vol > 1e-9 else -1e6
        penalty = LAMBDA * np.dot(w, w)
        return -sharpe + penalty

    # ── Constraints ──────────────────────────────────────────────────────
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]

    if allow_short:
        # Total short exposure must not exceed MAX_TOTAL_SHORT
        # Σ min(w_i, 0) ≥ −MAX_TOTAL_SHORT  ↔  Σ min(w_i,0) + MAX_TOTAL_SHORT ≥ 0
        constraints.append({
            "type": "ineq",
            "fun":  lambda w: MAX_TOTAL_SHORT + np.sum(np.minimum(w, 0.0))
        })

    # ── Starting points ──────────────────────────────────────────────────
    rank = np.argsort(mu)   # rank[0] = worst BL return, rank[-1] = best

    # 1. Equal weight
    starts = [eq_w.copy()]

    # 2. Risk-parity (inverse-vol weights) — good baseline
    try:
        inv_vol = 1.0 / np.sqrt(np.diag(cov_annual))
        starts.append(inv_vol / inv_vol.sum())
    except Exception:
        pass

    # 3. Return-proportional: weight ∝ max(μ_i, 0)  (long-only friendly)
    mu_pos = np.maximum(mu, 0.0)
    if mu_pos.sum() > 1e-9:
        starts.append(mu_pos / mu_pos.sum())

    # 4. Sharpe-proportional: weight ∝ μ_i / σ_i  (individual asset Sharpe)
    try:
        ind_sharpe = (mu - risk_free_rate) / np.sqrt(np.diag(cov_annual))
        ind_sharpe_pos = np.maximum(ind_sharpe, 0.0)
        if ind_sharpe_pos.sum() > 1e-9:
            starts.append(ind_sharpe_pos / ind_sharpe_pos.sum())
    except Exception:
        pass

    if allow_short and n >= 2:
        # 5. 130/30 style: tilt best up, worst down proportionally
        w_tilt = eq_w.copy()
        tilt   = min(0.25, MAX_TOTAL_SHORT / max(n // 2, 1))
        n_long  = max(n // 2, 1)
        n_short = n - n_long
        for i, idx in enumerate(rank[:n_short]):
            w_tilt[idx] -= tilt / max(n_short, 1)
        for i, idx in enumerate(rank[n_short:]):
            w_tilt[idx] += tilt / max(n_long, 1)
        starts.append(w_tilt)

        # 6. Short only the single worst asset; long everything else
        s = min(0.20, MAX_TOTAL_SHORT)
        w_s = np.full(n, (1.0 + s) / (n - 1))
        w_s[rank[0]] = -s
        starts.append(w_s)

    # ── Optimise from each start, keep the best ──────────────────────────
    best_result = None
    for w0 in starts:
        w0 = np.array(w0, dtype=float)
        w0 = np.clip(w0, [b[0] for b in bounds], [b[1] for b in bounds])
        s  = w0.sum()
        w0 = w0 / s if abs(s) > 1e-9 else eq_w
        res = minimize(
            objective, w0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"ftol": 1e-10, "maxiter": 2000},
        )
        if res.success and (best_result is None or res.fun < best_result.fun):
            best_result = res

    # Fallback: minimum-variance portfolio
    if best_result is None:
        res_mv = minimize(
            lambda w: w @ cov_annual @ w,
            eq_w,
            method="SLSQP",
            bounds=bounds,
            constraints=[{"type": "eq", "fun": lambda w: np.sum(w) - 1}],
        )
        weights = res_mv.x if res_mv.success else eq_w
    else:
        weights = best_result.x

    # ── Post-process ─────────────────────────────────────────────────────
    # Strip genuine numerical noise only — keep any position that is
    # intentionally small but meaningful (threshold: 0.2%)
    noise_floor = 2e-3
    weights[np.abs(weights) < noise_floor] = 0.0

    total = weights.sum()
    weights = weights / total if abs(total) > 1e-9 else eq_w

    port_ret = float(weights @ mu)
    port_vol = float(np.sqrt(weights @ cov_annual @ weights))
    excess_return = port_ret - risk_free_rate

    return {
        "weights":        {tickers[i]: float(weights[i]) for i in range(n)},
        "weights_arr":    weights,
        "annual_return":  port_ret,
        "annual_vol":     port_vol,
        "monthly_vol":    port_vol / np.sqrt(12),
        "sharpe":         excess_return / port_vol if port_vol > 1e-9 else 0.0,
        "var_95_monthly": (port_vol / np.sqrt(12)) * z_95,
    }


# ============================================================
# SECTION 7: STOP LOSS CALCULATION
# ============================================================

def calculate_stop_losses(
    prices: pd.DataFrame,
    sigma_forecasts: dict,
    weights: dict,
    capital: float,
    k: float = 1.5,
) -> dict:
    """
    Individual stop loss:
      Long  position: stop = entry × (1 - k_adj × σ_daily)   [price falls]
      Short position: stop = entry × (1 + k_adj × σ_daily)   [price rises]
    k is tightened slightly for larger absolute positions.
    """
    stop_data = {}

    for ticker, weight in weights.items():
        price      = float(prices[ticker].iloc[-1])
        sigma      = sigma_forecasts[ticker]
        allocation = weight * capital          # negative for shorts
        is_short   = weight < 0
        shares     = allocation / price if price > 0 else 0   # negative for shorts

        k_adj = k * (1.0 + 0.3 * abs(weight))

        if is_short:
            # Cover (buy back) if price rises above stop
            stop_price = price * (1 + k_adj * sigma)
        else:
            # Sell if price falls below stop
            stop_price = price * (1 - k_adj * sigma)

        stop_pct = k_adj * sigma * 100
        risk_amt = abs(allocation) * k_adj * sigma

        stop_data[ticker] = {
            "entry_price":       price,
            "stop_price":        stop_price,
            "stop_pct":          stop_pct,      # always positive magnitude
            "daily_sigma_pct":   sigma * 100,
            "weight_pct":        weight * 100,
            "allocation":        allocation,
            "shares":            shares,
            "is_short":          is_short,
            "risk_per_position": risk_amt,
        }

    return stop_data


# ============================================================
# SECTION 8: DCA SCHEDULE GENERATOR
# ============================================================

def generate_dca_schedule(weights: dict, capital: float, months: int = 6) -> pd.DataFrame:
    """
    Monthly DCA with front-loading (current regime signal is freshest now).
    """
    decay = np.array([1.0 / (1 + 0.1 * m) for m in range(months)])
    decay /= decay.sum()

    rows = []
    for month_idx, month_fraction in enumerate(decay, start=1):
        monthly_capital = capital * month_fraction
        row = {"Month": f"Month {month_idx}", "Deploy (₹)": round(monthly_capital, 2)}
        for ticker, w in weights.items():
            row[ticker] = round(w * monthly_capital, 2)
        rows.append(row)

    return pd.DataFrame(rows)


# ============================================================
# SECTION 9: MAIN PIPELINE
# ============================================================

def run_optimizer(
    tickers: list,
    capital: float,
    user_target_annual: float,
    risk_appetite_monthly: float,
    allow_short: bool = False,
    invest_mode: str = "lump_sum",
    dca_months: int = 6,
    stop_loss_k: float = 1.5,
):
    DIVIDER = "=" * 65

    print(f"\n{DIVIDER}")
    print("  PORTFOLIO OPTIMIZER  |  GARCH + DCC + HMM + Black-Litterman")
    print(DIVIDER)

    # Step 1: Data
    print("\n[1/7] Fetching market data...")
    prices, returns = fetch_data(tickers)

    # Reconcile: fetch_data may have dropped tickers with no data
    tickers = returns.columns.tolist()

    market_caps = get_market_caps(tickers)

    # Step 2: HMM Regimes
    print("\n[2/7] Detecting market regimes via HMM...")
    regimes = detect_regimes(returns)
    regime_table = []
    for t in tickers:
        r = regimes[t]
        stay_prob = r["transition_probs"].get(r["regime"], 0)
        regime_table.append([t, r["regime"], f"{stay_prob:.0%}", f"{r['regime_mean_daily']*100:.3f}%"])
    print(tabulate(regime_table, headers=["Stock", "Regime", "Stay Prob", "Regime Daily Mean"], tablefmt="rounded_outline"))

    # Step 3: DCC-GARCH
    print("\n[3/7] Fitting DCC-GARCH...")
    dcc = fit_dcc_garch(returns)
    print(f"    DCC α: {dcc['dcc_a']:.4f}  |  DCC β: {dcc['dcc_b']:.4f}")

    # Step 4: Expected Returns
    print("\n[4/7] Estimating expected returns...")
    exp_returns = estimate_expected_returns(returns, regimes, user_target_annual)
    for t in tickers:
        w = exp_returns[t]["divergence_warning"]
        if w:
            print(f"    {w}")

    # Step 5: Black-Litterman
    print("\n[5/7] Applying Black-Litterman...")
    views = {t: exp_returns[t]["annual"] for t in tickers}
    mu_bl = black_litterman_returns(
        market_caps=market_caps,
        cov_annual=dcc["cov_annual"],
        tickers=tickers,
        views=views,
    )

    # Step 6: MVO
    print("\n[6/7] Running Mean-Variance Optimization (max 50% per stock)...")
    mvo = mean_variance_optimize(
        mu=mu_bl,
        cov_annual=dcc["cov_annual"],
        tickers=tickers,
        risk_appetite_monthly=risk_appetite_monthly,
        allow_short=allow_short,
    )

    # Step 7: Stop Losses
    print("\n[7/7] Computing stop losses...")
    stop_data = calculate_stop_losses(
        prices, dcc["sigma_forecasts"], mvo["weights"], capital, stop_loss_k
    )

    # DCA Schedule
    dca_df = None
    if invest_mode == "dca":
        dca_df = generate_dca_schedule(mvo["weights"], capital, dca_months)

    print(f"\n{'='*65}\n")

    return {
        "weights":           mvo["weights"],
        "stop_data":         stop_data,
        "regimes":           regimes,
        "dca_df":            dca_df,
        "portfolio_metrics": {
            "annual_return":  mvo["annual_return"],
            "annual_vol":     mvo["annual_vol"],
            "sharpe":         mvo["sharpe"],
            "monthly_var_95": mvo["var_95_monthly"],
        },
        "dcc":        dcc,
        "bl_returns": {tickers[i]: mu_bl[i] for i in range(len(tickers))},
        "exp_returns": exp_returns,
    }


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    TICKERS               = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS"]
    CAPITAL               = 1_000_000
    USER_TARGET_ANNUAL    = 0.18
    RISK_APPETITE_MONTHLY = 0.05
    ALLOW_SHORT           = False
    INVEST_MODE           = "dca"
    DCA_MONTHS            = 6
    STOP_LOSS_K           = 1.5

    results = run_optimizer(
        tickers=TICKERS,
        capital=CAPITAL,
        user_target_annual=USER_TARGET_ANNUAL,
        risk_appetite_monthly=RISK_APPETITE_MONTHLY,
        allow_short=ALLOW_SHORT,
        invest_mode=INVEST_MODE,
        dca_months=DCA_MONTHS,
        stop_loss_k=STOP_LOSS_K,
    )