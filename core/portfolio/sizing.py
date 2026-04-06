"""
============================================================
PORTFOLIO OPTIMIZER: GARCH + DCC-GARCH + HMM + Black-Litterman MVO
============================================================

Use the GARCH volatility to get the stop loss for each stock. 
For the expected return, take a user input of their target return, 
but also compare it to the predicted return from our model. For the predicted return, 
first use HMM to check which regime we are in. Ask the user if they want to allow shorting, 
if they want to invest fully or invest that amount over a period of let's say 6 months 
and their risk appetite (how much they are willing to lose per month). 
Then use mean-variance optimization to maximize expected return. 
If there are multiple stocks, use DCC-GARCH to get the time-varying correlations 
alongside time-varying volatilites, adjusting stop losses accrodingly. 


Improvements:

Replace pure MVO with Black-Litterman — 
    standard MVO is notorious for being hypersensitive to expected return inputs. 
    Black-Litterman blends market equilibrium returns with your HMM-derived views, 
    making allocations far more stable

CVaR constraint instead of variance — 
    variance penalizes upside equally. CVaR only constrains tail losses, 
    which is what the user actually cares about

Add regime-change rebalancing triggers — 
    don't just rebalance monthly; rebalance immediately when HMM detects a regime shift

Portfolio-level stop loss in addition to individual stops — 
    individual stops can cascade in a correlated downturn

Momentum blend into expected returns — 
    regime mean alone is too noisy; add 1M/3M momentum as a secondary signal
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
    raw = raw[tickers].dropna()
    log_returns = np.log(raw / raw.shift(1)).dropna()
    print(f"    {len(log_returns)} trading days loaded ({log_returns.index[0].date()} → {log_returns.index[-1].date()})")
    return raw, log_returns

def get_market_caps(tickers: list) -> dict:
    """Fetch the market cap for each ticker"""
    market_caps = {}
    financial_data = fetch_financial_data(tickers)

    for ticker in tickers:
        data = financial_data.get(ticker)
        if not data: continue

        # Extract Info metrics with fallback to 0
        info = data['info']
        market_cap = info.get('marketCap', 0) or 0
        market_caps[ticker] = market_cap

    return market_caps


# ============================================================
# SECTION 2: UNIVARIATE GARCH(1,1)
# ============================================================

def fit_garch_single(return_series: pd.Series) -> dict:
    """
    Fit GARCH(1,1) to a single asset.
    Returns forecasted daily sigma and standardized residuals.
    """
    scaled = return_series * 100  # GARCH works better on percentage returns
    model = arch_model(scaled, vol="Garch", p=1, q=1, dist="normal", rescale=False)
    res = model.fit(disp="off", show_warning=False, options={'maxiter': 1000})

    # 1-step ahead forecast
    forecast = res.forecast(horizon=1, reindex=False)
    sigma_next = float(np.sqrt(forecast.variance.iloc[-1, 0])) / 100

    cond_vol = res.conditional_volatility / 100
    std_resid = res.std_resid  # ε_t = r_t / σ_t

    return {
        "model": res,
        "sigma_forecast": sigma_next,         # daily σ for next period
        "cond_vol": cond_vol,
        "std_resid": std_resid,
        "params": res.params,
    }


# ============================================================
# SECTION 3: DCC-GARCH (Dynamic Conditional Correlation)
# ============================================================

def fit_dcc_garch(returns_df: pd.DataFrame) -> dict:
    """
    Two-stage DCC-GARCH:
      Stage 1: Fit univariate GARCH(1,1) per asset → get σ_i(t) and ε_i(t)
      Stage 2: Model time-varying correlation via DCC equations:
                Q_t = (1-a-b)·Q̄ + a·ε_{t-1}ε'_{t-1} + b·Q_{t-1}
                R_t = diag(Q_t)^{-½} · Q_t · diag(Q_t)^{-½}
      Final:   H_t = D_t · R_t · D_t    (D_t = diag of GARCH σ's)
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
    eps = std_resids.values  # shape: (T, n)
    T = len(eps)

    # Q̄ = unconditional covariance of standardized residuals
    Q_bar = np.cov(eps.T)
    if Q_bar.ndim == 0:  # single asset edge case
        Q_bar = np.array([[Q_bar]])

    # --- Stage 2: Optimize DCC parameters (a, b) ---
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
            # Clamp diagonal for numerical stability
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

    # --- Re-run DCC to get final R_T ---
    Q_t = Q_bar.copy()
    for t in range(1, T):
        e_lag = eps[t - 1].reshape(-1, 1)
        Q_t = (1 - a_hat - b_hat) * Q_bar + a_hat * (e_lag @ e_lag.T) + b_hat * Q_t

    d_inv = 1.0 / np.sqrt(np.diag(Q_t))
    R_current = Q_t * np.outer(d_inv, d_inv)
    np.fill_diagonal(R_current, 1.0)

    # --- Build annualized covariance matrix ---
    sigma_vec = np.array([garch_fits[t]["sigma_forecast"] for t in tickers])
    # Daily cov → annualize by *252
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
    Fit a 3-state Gaussian HMM per asset using:
      Features: [log_return, rolling_5d_vol]

    States are labelled post-hoc by mean return:
      Highest mean → Bull | Lowest mean → Bear | Middle → Sideways
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

        # Label states by mean return and volatility
        state_mean_ret = {}
        state_vol = {}
        for s in range(3):
            mask = states_seq == s
            state_mean_ret[s] = ret[mask].mean() if mask.sum() > 0 else 0.0
            state_vol[s] = ret[mask].std() if mask.sum() > 0 else 0.0

        state_score = {}
        for s in range(3):
            # normalize both metrics
            ret_norm = (state_mean_ret[s] - np.mean(list(state_mean_ret.values())))
            vol_norm = (state_vol[s] - np.mean(list(state_vol.values())))
        
            # higher return good, higher vol bad
            state_score[s] = ret_norm - vol_norm

        sorted_states = sorted(state_score.items(), key=lambda x: x[1])

        bear_state = sorted_states[0][0]
        side_state = sorted_states[1][0]
        bull_state = sorted_states[2][0]

        label_map = {bear_state: "Bear", side_state: "Sideways", bull_state: "Bull"}
        current_label = label_map[states_seq[-1]]

        # Transition probabilities from current state
        current_state_id = states_seq[-1]
        trans_probs = hmm.transmat_[current_state_id]
        trans_named = {label_map[i]: round(trans_probs[i], 3) for i in range(n_states)}

        results[ticker] = {
            "regime": current_label,
            "regime_mean_daily": state_mean_ret[states_seq[-1]],
            "state_means": {label_map[s]: state_mean_ret[s] for s in range(n_states)},
            "transition_probs": trans_named,  # probability of staying in / leaving regime
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
      1. HMM regime-conditioned historical mean  (weight: 0.50)
      2. 1M + 3M momentum signal                 (weight: 0.30)
      3. User target return                       (weight: 0.20)

    Also flags when model forecast strongly disagrees with user target.
    """
    trading_days = 252
    exp_returns = {}

    for ticker in returns_df.columns:
        ret_series = returns_df[ticker]

        # Signal 1: Regime-conditioned mean (annualized)
        regime_daily = regimes[ticker]["regime_mean_daily"]
        regime_annual = regime_daily * trading_days
        # if regimes[ticker]["regime"] == "Bear":
        #     regime_annual *= 1.5   # amplify negativity
        # elif regimes[ticker]["regime"] == "Bull":
        #     regime_annual *= 1.2

        # Signal 2: Momentum (1-month and 3-month, equal blend)
        mom_1m = ret_series.tail(21).mean() * trading_days
        mom_3m = ret_series.tail(63).mean() * trading_days
        momentum_annual = 0.5 * mom_1m + 0.5 * mom_3m

        # Signal 3: User target
        if regimes[ticker]["regime"] == "Bear":
            user_weight = 0.0   # or even negative bias
        else:
            user_weight = 0.2

        model_annual = 0.6 * regime_annual + 0.4 * momentum_annual + user_weight * user_target_annual

        # Divergence check: is model wildly different from user target?
        divergence_pct = abs(model_annual - user_target_annual) * 100
        if divergence_pct > 15:
            warning = f"⚠️  Model ({model_annual*100:.1f}%) vs User Target ({user_target_annual*100:.1f}%) diverge by {divergence_pct:.1f}pp"
        else:
            warning = None

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
    views: dict,        # {ticker: expected_annual_return from our model}
    tau: float = 0.5,  # uncertainty in prior (smaller = trust market more)
    risk_aversion: float = 2.5,
) -> np.ndarray:
    """
    Black-Litterman model:
      Prior (π): Implied equilibrium returns from market-cap weights
      Views (Q): Our model's expected returns per asset
      Posterior (μ_BL): Blended estimate

    BL Formula:
      μ_BL = [(τΣ)^{-1} + P'Ω^{-1}P]^{-1} [(τΣ)^{-1}π + P'Ω^{-1}Q]
    """
    n = len(tickers)
    market_caps = get_market_caps(tickers)
    total_mcap = sum(market_caps.values())
    w_mkt = np.array([market_caps[t] / total_mcap for t in tickers])

    # Implied equilibrium returns: π = λ·Σ·w_mkt
    pi = risk_aversion * cov_annual @ w_mkt

    # View matrix P: absolute views (one view per asset → P = I)
    P = np.eye(n)
    Q = np.array([views[t] for t in tickers])

    # Uncertainty of views Ω = diag(τ · P·Σ·P')
    tau_sigma = tau * cov_annual
    omega = np.diag(np.diag(P @ tau_sigma @ P.T)) * 0.1

    # BL posterior
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
    n = len(tickers)
    z_95 = norm.ppf(0.95)
    risk_free_rate = 0.07
    
    # Target annual variance based on monthly risk appetite
    sigma_annual_max = (risk_appetite_monthly / z_95) * np.sqrt(12)
    variance_max = sigma_annual_max ** 2

    def objective(w):
        ret = w @ mu
        vol = np.sqrt(w @ cov_annual @ w)
        excess = ret - 0.07
        return -excess / vol if vol > 0 else 1e6

    def portfolio_variance(w):
        return float(w @ cov_annual @ w)

    constraints = [
        {"type": "eq", "fun": lambda w: np.sum(w) - 1},
        {"type": "ineq", "fun": lambda w: 2.0 - np.sum(np.abs(w))}
    ]

    if allow_short:
        # Bounds: -30% to 150% (allowing leverage/shorts)
        bounds = [(-0.40, 1.20) for _ in range(n)]
    else:
        # Bounds: Long-only, max 60% in one stock
        bounds = [(0.0, 0.60) for _ in range(n)]

    # Dynamic starting points based on n
    starts = [
        np.ones(n) / n,  # Equal weight
        (mu == mu.max()).astype(float), # Concentrated in best performer
    ]

    best_result = None
    for w0 in starts:
        res = minimize(
            objective, w0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"ftol": 1e-10, "maxiter": 1000},
        )
        if res.success:
            if best_result is None or res.fun < best_result.fun:
                best_result = res

    # FALLBACK: If the risk budget is impossible, find the Minimum Variance Portfolio
    if best_result is None:
        res_min_vol = minimize(
            portfolio_variance, np.ones(n)/n,
            method="SLSQP",
            bounds=bounds,
            constraints=[{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
        )
        weights = res_min_vol.x
    else:
        weights = best_result.x

    # Post-process weights
    weights[np.abs(weights) < 0.01] = 0    
    weights /= weights.sum()
    port_ret = float(weights @ mu)
    port_vol = float(np.sqrt(weights @ cov_annual @ weights))

    excess_return = port_ret - risk_free_rate
    
    return {
        "weights": {tickers[i]: weights[i] for i in range(n)},
        "weights_arr": weights,
        "annual_return": port_ret,
        "annual_vol": port_vol,
        "monthly_vol": port_vol / np.sqrt(12),
        "sharpe": excess_return / port_vol if port_vol > 0 else 0,
        "sharpe": port_ret / port_vol if port_vol > 0 else 0,
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
        stop = entry_price × (1 - k × σ_daily)
    k is tightened for larger positions (more capital at risk).
    Portfolio stop loss = capital × monthly_var_95
    """
    stop_data = {}

    for ticker, weight in weights.items():
        price = float(prices[ticker].iloc[-1])
        sigma = sigma_forecasts[ticker]
        allocation = weight * capital
        shares = allocation / price if price > 0 else 0

        # Slightly tighter stop for larger weights
        k_adj = k * (1.0 + 0.3 * weight)
        stop_price = price * (1 - k_adj * sigma)
        stop_pct   = k_adj * sigma * 100
        risk_amt   = allocation * k_adj * sigma  # ₹ at risk per position

        stop_data[ticker] = {
            "entry_price": price,
            "stop_price": stop_price,
            "stop_pct": stop_pct,
            "daily_sigma_pct": sigma * 100,
            "weight_pct": weight * 100,
            "allocation": allocation,
            "shares": shares,
            "risk_per_position": risk_amt,
        }

    return stop_data


# ============================================================
# SECTION 8: DCA SCHEDULE GENERATOR
# ============================================================

def generate_dca_schedule(weights: dict, capital: float, months: int = 6) -> pd.DataFrame:
    """
    Generate monthly DCA schedule with slight front-loading:
    Months are weighted by a decay factor so early months deploy slightly more.
    (Rationale: current regime signal is freshest now)
    """
    # Decay weights: month 1 gets most, last month gets least
    decay = np.array([1.0 / (1 + 0.1 * m) for m in range(months)])
    decay /= decay.sum()  # normalize to sum=1

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
    invest_mode: str = "lump_sum",  # "lump_sum" | "dca"
    dca_months: int = 6,
    stop_loss_k: float = 1.5,
):
    DIVIDER = "=" * 65

    print(f"\n{DIVIDER}")
    print("  PORTFOLIO OPTIMIZER  |  GARCH + DCC + HMM + Black-Litterman")
    print(DIVIDER)

    # ── Step 1: Data ──────────────────────────────────────────
    print("\n[1/7] Fetching market data...")
    prices, returns = fetch_data(tickers)

    market_caps = get_market_caps(tickers)

    # ── Step 2: HMM Regimes ───────────────────────────────────
    print("\n[2/7] Detecting market regimes via HMM...")
    regimes = detect_regimes(returns)
    regime_table = []
    for t in tickers:
        r = regimes[t]
        stay_prob = r["transition_probs"].get(r["regime"], "—")
        regime_table.append([t, r["regime"], f"{stay_prob:.0%}", f"{r['regime_mean_daily']*100:.3f}%"])
    print(tabulate(regime_table, headers=["Stock", "Regime", "Stay Prob", "Regime Daily Mean"], tablefmt="rounded_outline"))

    # ── Step 3: DCC-GARCH ─────────────────────────────────────
    print("\n[3/7] Fitting DCC-GARCH (time-varying correlations + volatilities)...")
    dcc = fit_dcc_garch(returns)
    print(f"    DCC parameters → α (news shock): {dcc['dcc_a']:.4f}  |  β (persistence): {dcc['dcc_b']:.4f}")

    vol_table = []
    for t in tickers:
        sig = dcc["sigma_forecasts"][t]
        sig_annual = sig * np.sqrt(252)
        vol_table.append([t, f"{sig*100:.2f}%", f"{sig_annual*100:.1f}%"])
    print(tabulate(vol_table, headers=["Stock", "Daily σ (GARCH)", "Annual σ"], tablefmt="rounded_outline"))

    print("\n    DCC Correlation Matrix:")
    corr_df = pd.DataFrame(dcc["corr_matrix"], index=tickers, columns=tickers)
    print(tabulate(corr_df.round(3), headers=tickers, tablefmt="rounded_outline", showindex=True))

    # ── Step 4: Expected Returns ─────────────────────────────
    print("\n[4/7] Estimating expected returns (Regime + Momentum + User Target)...")
    exp_returns = estimate_expected_returns(returns, regimes, user_target_annual)

    ret_table = []
    for t in tickers:
        er = exp_returns[t]
        ret_table.append([
            t,
            f"{er['regime_signal']*100:.1f}%",
            f"{er['momentum_signal']*100:.1f}%",
            f"{er['user_target']*100:.1f}%",
            f"{er['annual']*100:.1f}%",
        ])
    print(tabulate(ret_table, headers=["Stock", "Regime Signal", "Momentum", "User Target", "Model Blended"], tablefmt="rounded_outline"))

    for t in tickers:
        w = exp_returns[t]["divergence_warning"]
        if w:
            print(f"    {w}")

    # ── Step 5: Black-Litterman ───────────────────────────────
    print("\n[5/7] Applying Black-Litterman to blend market prior with model views...")
    views = {t: exp_returns[t]["annual"] for t in tickers}
    mu_bl = black_litterman_returns(
        market_caps=market_caps,
        cov_annual=dcc["cov_annual"],
        tickers=tickers,
        views=views,
    )
    bl_table = [[tickers[i], f"{views[tickers[i]]*100:.1f}%", f"{mu_bl[i]*100:.1f}%"] for i in range(len(tickers))]
    print(tabulate(bl_table, headers=["Stock", "Raw Model View", "BL Posterior Return"], tablefmt="rounded_outline"))

    # ── Step 6: MVO ───────────────────────────────────────────
    print("\n[6/7] Running Mean-Variance Optimization (CVaR-constrained)...")
    print(f"    Risk appetite: max {risk_appetite_monthly*100:.1f}% monthly loss (95% confidence)")
    print(f"    Short selling: {'Allowed (max 30% per stock)' if allow_short else 'Not allowed'}")

    mvo = mean_variance_optimize(
        mu=mu_bl,
        cov_annual=dcc["cov_annual"],
        tickers=tickers,
        risk_appetite_monthly=risk_appetite_monthly,
        allow_short=allow_short,
    )

    print(f"\n    ✅ Portfolio Expected Return : {mvo['annual_return']*100:.2f}% p.a.")
    print(f"    ✅ Portfolio Volatility       : {mvo['annual_vol']*100:.2f}% p.a.")
    print(f"    ✅ Sharpe Ratio               : {mvo['sharpe']:.2f}")
    print(f"    ✅ Monthly VaR (95%)          : {mvo['var_95_monthly']*100:.2f}%")

    # ── Step 7: Stop Losses + Final Allocations ───────────────
    print("\n[7/7] Computing allocations and GARCH-based stop losses...")
    stop_data = calculate_stop_losses(
        prices, dcc["sigma_forecasts"], mvo["weights"], capital, stop_loss_k
    )

    # ── Final Output ──────────────────────────────────────────
    print(f"\n{DIVIDER}")
    print("  FINAL ALLOCATION SUMMARY")
    print(DIVIDER)
    print(f"\n  Total Capital      : ₹{capital:>12,.2f}")
    print(f"  Investment Mode    : {'Dollar-Cost Averaging over ' + str(dca_months) + ' months' if invest_mode == 'dca' else 'Lump Sum'}")
    print(f"  User Target Return : {user_target_annual*100:.1f}% p.a.")
    print(f"  Risk Appetite      : {risk_appetite_monthly*100:.1f}% max monthly loss")

    alloc_table = []
    for t in tickers:
        sd = stop_data[t]
        alloc_table.append([
            t,
            f"₹{sd['entry_price']:>8,.2f}",
            f"{sd['weight_pct']:.1f}%",
            f"₹{sd['allocation']:>10,.2f}",
            f"{sd['shares']:.2f}",
            f"₹{sd['risk_per_position']:>8,.2f}",
        ])
    print()
    print(tabulate(alloc_table,
        headers=["Stock", "Entry Price", "Weight", "Allocation", "Shares", "Capital at Risk"],
        tablefmt="rounded_outline"))

    stop_table = []
    for t in tickers:
        sd = stop_data[t]
        stop_table.append([
            t,
            f"₹{sd['entry_price']:>8,.2f}",
            f"₹{sd['stop_price']:>8,.2f}",
            f"{sd['stop_pct']:.2f}%",
            f"{sd['daily_sigma_pct']:.2f}%",
            regimes[t]["regime"],
        ])
    print()
    print(tabulate(stop_table,
        headers=["Stock", "Entry", "Stop Loss", "Stop %", "Daily σ", "Regime"],
        tablefmt="rounded_outline"))

    # Portfolio-level stop loss
    total_risk = sum(sd["risk_per_position"] for sd in stop_data.values())
    portfolio_stop_pct = mvo["var_95_monthly"] * 100
    print(f"\n  📌 Portfolio Stop Loss (monthly VaR 95%) : {portfolio_stop_pct:.2f}%  →  ₹{capital * mvo['var_95_monthly']:,.2f}")
    print(f"  📌 Total ₹ at Risk (individual stops)   : ₹{total_risk:,.2f}")

    # ── DCA Schedule ─────────────────────────────────────────
    if invest_mode == "dca":
        print(f"\n{DIVIDER}")
        print(f"  DCA DEPLOYMENT SCHEDULE  ({dca_months} months, front-loaded)")
        print(DIVIDER)
        dca_df = generate_dca_schedule(mvo["weights"], capital, dca_months)
        print()
        print(tabulate(dca_df, headers=dca_df.columns, tablefmt="rounded_outline", showindex=False, floatfmt=",.2f"))
        print("\n  Note: Front-loading applies because current regime signals are freshest.")
        print("  Rebalance immediately if HMM detects a regime change mid-schedule.")

    # ── Regime Change Warning ─────────────────────────────────
    print(f"\n{DIVIDER}")
    print("  REGIME TRANSITION RISK")
    print(DIVIDER)
    for t in tickers:
        r = regimes[t]
        print(f"\n  {t} — Currently: {r['regime']}")
        for target_regime, prob in r["transition_probs"].items():
            bar = "█" * int(prob * 20)
            print(f"    → {target_regime:<10} {prob:.1%}  {bar}")

    print(f"\n  ⚡ Trigger a full rebalance if any stock's HMM regime shifts.")
    print(f"  ⚡ Re-run DCC-GARCH monthly to update correlations and stop losses.")

    print(f"\n{'='*65}\n")

    return {
        "weights": mvo["weights"],
        "stop_data": stop_data,
        "regimes": regimes,
        "portfolio_metrics": {
            "annual_return": mvo["annual_return"],
            "annual_vol": mvo["annual_vol"],
            "sharpe": mvo["sharpe"],
            "monthly_var_95": mvo["var_95_monthly"],
        },
        "dcc": dcc,
        "bl_returns": {tickers[i]: mu_bl[i] for i in range(len(tickers))},
    }


# ============================================================
# ENTRY POINT — configure and run here
# ============================================================

if __name__ == "__main__":

    # ── User Inputs ────────────────────────────────────────────
    TICKERS = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS"]

    CAPITAL               = 1_000_000   # ₹10 Lakhs
    USER_TARGET_ANNUAL    = 0.18        # 18% target return per year
    RISK_APPETITE_MONTHLY = 0.05        # Willing to lose max 5% per month (95% VaR)
    ALLOW_SHORT           = False       # Set True to allow short positions
    INVEST_MODE           = "dca"       # "lump_sum" or "dca"
    DCA_MONTHS            = 6           # Relevant only if INVEST_MODE = "dca"
    STOP_LOSS_K           = 1.5         # Stop = entry × (1 - k × σ_daily), k=1.5 → ~1.5σ stop


    results = run_optimizer(
        tickers=TICKERS,
        capital=CAPITAL,
        user_target_annual=USER_TARGET_ANNUAL,
        risk_appetite_monthly=RISK_APPETITE_MONTHLY,
        allow_short=ALLOW_SHORT,
        invest_mode=INVEST_MODE,
        dca_months=DCA_MONTHS,
        stop_loss_k=STOP_LOSS_Ks
    )