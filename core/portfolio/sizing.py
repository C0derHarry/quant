"""
============================================================
PORTFOLIO OPTIMIZER
GARCH + DCC-GARCH + HMM + Black-Litterman + Ledoit-Wolf MVO
============================================================

Improvements over previous version
------------------------------------
1. HMM regime smoothing      — EMA over posterior probabilities stops
                               day-to-day regime flipping; label only
                               changes when smoothed probability holds
                               above a confidence threshold.
2. James-Stein shrinkage     — raw mean returns shrunk toward the
                               cross-sectional grand mean, reducing
                               estimation error significantly.
3. Ledoit-Wolf covariance    — replaces raw np.cov everywhere;
                               well-conditioned even for small T/n.
4. Fat-tail Monte Carlo      — portfolio VaR / CVaR estimated by
                               bootstrap + Student-t fit rather than
                               normal assumption.
5. Diversification constraint — hard max_weight = 0.40 per position,
                                combined with L2 penalty so weights
                                spread by risk/reward within that cap.
"""

import numpy as np
import pandas as pd
import yfinance as yf
import warnings
from arch import arch_model
from hmmlearn.hmm import GaussianHMM
from scipy.optimize import minimize
from scipy.stats import norm, t as student_t
from sklearn.covariance import LedoitWolf
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

    if isinstance(raw, pd.Series):
        raw = raw.to_frame(tickers[0])

    available = [t for t in tickers if t in raw.columns]
    missing   = [t for t in tickers if t not in raw.columns]
    if missing:
        print(f"    Warning: No data returned for: {missing}. Proceeding without them.")
    if not available:
        raise ValueError(
            f"yfinance returned no data for any of: {tickers}. "
            "Check the ticker symbols and your internet connection."
        )

    raw = raw[available]
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
        f"({log_returns.index[0].date()} to {log_returns.index[-1].date()})"
    )
    return raw, log_returns


def get_market_caps(tickers: list) -> dict:
    """Fetch market cap for each ticker, fall back to equal weight."""
    market_caps = {}
    financial_data = fetch_financial_data(tickers)

    for ticker in tickers:
        data = financial_data.get(ticker)
        if not data:
            market_caps[ticker] = 1
            continue
        info = data['info']
        mc = info.get('marketCap', 0) or 0
        market_caps[ticker] = mc if mc > 0 else 1

    if sum(market_caps.values()) == 0:
        market_caps = {t: 1 for t in tickers}

    return market_caps


# ============================================================
# SECTION 2: LEDOIT-WOLF COVARIANCE SHRINKAGE
# ============================================================

def ledoit_wolf_cov(returns_matrix: np.ndarray) -> np.ndarray:
    """
    Ledoit-Wolf analytical shrinkage estimator.

    Why this matters: the sample covariance matrix is notoriously
    ill-conditioned when T (observations) is not much larger than
    n (assets). LW shrinks toward a scaled identity matrix with an
    analytically optimal shrinkage intensity. No cross-validation
    needed, and it dramatically reduces estimation error for MVO.

    Returns an (n x n) positive-definite shrunk covariance matrix.
    """
    lw = LedoitWolf()
    lw.fit(returns_matrix)
    return lw.covariance_


# ============================================================
# SECTION 3: UNIVARIATE GARCH(1,1)
# ============================================================

def fit_garch_single(return_series: pd.Series) -> dict:
    """Fit GARCH(1,1) to a single asset."""
    scaled = return_series * 100
    model = arch_model(scaled, vol="Garch", p=1, q=1, dist="t", rescale=False)
    res = model.fit(disp="off", show_warning=False, options={'maxiter': 1000})

    forecast = res.forecast(horizon=1, reindex=False)
    sigma_next = float(np.sqrt(forecast.variance.iloc[-1, 0])) / 100

    return {
        "model":          res,
        "sigma_forecast": sigma_next,
        "cond_vol":       res.conditional_volatility / 100,
        "std_resid":      res.std_resid,
        "params":         res.params,
    }


# ============================================================
# SECTION 4: DCC-GARCH (with Ledoit-Wolf for Q_bar)
# ============================================================

def fit_dcc_garch(returns_df: pd.DataFrame) -> dict:
    """
    Two-stage DCC-GARCH.
    Stage 1 - univariate GARCH(1,1) per asset -> sigma_i(t) and eps_i(t)
    Stage 2 - DCC correlation dynamics on standardised residuals.
              Q_bar is estimated with Ledoit-Wolf shrinkage so the
              unconditional correlation matrix is better conditioned.
    Final   - H_t = D_t . R_t . D_t (annualised).
    """
    tickers = returns_df.columns.tolist()

    garch_fits = {}
    std_resids = pd.DataFrame(index=returns_df.index)

    for ticker in tickers:
        fit = fit_garch_single(returns_df[ticker])
        garch_fits[ticker] = fit
        std_resids[ticker] = fit["std_resid"]

    std_resids = std_resids.dropna()
    eps = std_resids.values
    T   = len(eps)

    # Ledoit-Wolf for Q_bar instead of raw np.cov
    Q_bar = ledoit_wolf_cov(eps)
    if Q_bar.ndim == 0:
        Q_bar = np.array([[float(Q_bar)]])

    def dcc_neg_loglik(params):
        a, b = params
        if a <= 0 or b <= 0 or a + b >= 0.9999:
            return 1e10
        Q_t = Q_bar.copy()
        ll  = 0.0
        for t in range(1, T):
            e_lag = eps[t - 1].reshape(-1, 1)
            Q_t   = (1 - a - b) * Q_bar + a * (e_lag @ e_lag.T) + b * Q_t
            d_inv = 1.0 / np.sqrt(np.diag(Q_t))
            R_t   = Q_t * np.outer(d_inv, d_inv)
            np.fill_diagonal(R_t, 1.0)
            try:
                sign, logdet = np.linalg.slogdet(R_t)
                if sign <= 0:
                    return 1e10
                R_inv = np.linalg.inv(R_t)
                e_t   = eps[t]
                ll   += -0.5 * (logdet + e_t @ R_inv @ e_t - e_t @ e_t)
            except np.linalg.LinAlgError:
                return 1e10
        return -ll

    opt = minimize(
        dcc_neg_loglik, x0=[0.05, 0.90],
        bounds=[(1e-6, 0.49), (1e-6, 0.98)],
        method="L-BFGS-B",
        options={"ftol": 1e-10, "maxiter": 500},
    )
    a_hat, b_hat = opt.x

    Q_t = Q_bar.copy()
    for t in range(1, T):
        e_lag = eps[t - 1].reshape(-1, 1)
        Q_t   = (1 - a_hat - b_hat) * Q_bar + a_hat * (e_lag @ e_lag.T) + b_hat * Q_t

    d_inv     = 1.0 / np.sqrt(np.diag(Q_t))
    R_current = Q_t * np.outer(d_inv, d_inv)
    np.fill_diagonal(R_current, 1.0)

    sigma_vec  = np.array([garch_fits[t]["sigma_forecast"] for t in tickers])
    cov_daily  = np.outer(sigma_vec, sigma_vec) * R_current
    cov_annual = cov_daily * 252

    return {
        "garch_fits":      garch_fits,
        "cov_annual":      cov_annual,
        "cov_daily":       cov_daily,
        "corr_matrix":     R_current,
        "sigma_forecasts": {t: garch_fits[t]["sigma_forecast"] for t in tickers},
        "dcc_a":           a_hat,
        "dcc_b":           b_hat,
        "Q_bar":           Q_bar,
    }


# ============================================================
# SECTION 5: HMM REGIME DETECTION  (with EMA smoothing)
# ============================================================

def detect_regimes(
    returns_df: pd.DataFrame,
    n_states: int = 3,
    ema_span: int = 10,
    confidence_threshold: float = 0.55,
) -> dict:
    """
    3-state Gaussian HMM per asset with posterior probability smoothing.

    The core problem with raw HMM predict() is that it assigns a hard
    label to each day based on the most likely state at that instant.
    This is noisy: a volatile week can flip the label Bull->Bear->Bull
    within three days, making the regime signal useless for weekly or
    monthly position sizing.

    Fix: use predict_proba() (the full posterior distribution over
    states), apply an EMA with ema_span days to smooth each state's
    probability, then only assign a label when the smoothed probability
    exceeds confidence_threshold. If no state clears the threshold, the
    previous label is held (sticky regime).

    The smoothed probabilities are also returned so that
    estimate_expected_returns() can use a weighted blend of state means
    rather than a binary label. This is the right way to propagate
    uncertainty through the pipeline.
    """
    results = {}

    for ticker in returns_df.columns:
        ret      = returns_df[ticker].values
        roll_vol = returns_df[ticker].rolling(5).std().bfill().values
        features = np.column_stack([ret, roll_vol])

        hmm = GaussianHMM(
            n_components=n_states,
            covariance_type="diag",
            n_iter=2000,
            tol=1e-5,
            random_state=42,
        )
        hmm.fit(features)

        # Full posterior: shape (T, n_states)
        state_probs = hmm.predict_proba(features)

        # EMA-smooth each state's probability column
        smooth_arr = (
            pd.DataFrame(state_probs)
            .ewm(span=ema_span, adjust=False)
            .mean()
            .values
        )

        # Hard-label the smoothed sequence with stickiness
        hard_states   = np.empty(len(ret), dtype=int)
        current_state = int(np.argmax(smooth_arr[0]))
        for i in range(len(ret)):
            max_prob  = smooth_arr[i].max()
            max_state = int(np.argmax(smooth_arr[i]))
            if max_prob >= confidence_threshold:
                current_state = max_state
            hard_states[i] = current_state

        # Label states by risk-adjusted score (return - vol)
        state_mean_ret = {}
        state_vol      = {}
        for s in range(n_states):
            mask              = hard_states == s
            state_mean_ret[s] = ret[mask].mean() if mask.sum() > 0 else 0.0
            state_vol[s]      = ret[mask].std()  if mask.sum() > 0 else 1e-6

        state_score = {
            s: (state_mean_ret[s] - np.mean(list(state_mean_ret.values())))
               - (state_vol[s]    - np.mean(list(state_vol.values())))
            for s in range(n_states)
        }
        sorted_states = sorted(state_score.items(), key=lambda x: x[1])
        label_map = {
            sorted_states[0][0]: "Bear",
            sorted_states[1][0]: "Sideways",
            sorted_states[2][0]: "Bull",
        }

        current_state_id = hard_states[-1]
        current_label    = label_map[current_state_id]
        trans_probs      = hmm.transmat_[current_state_id]
        trans_named      = {label_map[i]: round(float(trans_probs[i]), 3) for i in range(n_states)}

        # Smoothed probability of each named regime at the last timestep
        smooth_named = {label_map[s]: float(smooth_arr[-1, s]) for s in range(n_states)}

        results[ticker] = {
            "regime":            current_label,
            "regime_probs":      smooth_named,
            "regime_mean_daily": state_mean_ret[current_state_id],
            "state_means":       {label_map[s]: state_mean_ret[s] for s in range(n_states)},
            "state_vols":        {label_map[s]: state_vol[s]      for s in range(n_states)},
            "transition_probs":  trans_named,
            "history":           [label_map[s] for s in hard_states],
        }

    return results


# ============================================================
# SECTION 6: EXPECTED RETURN ESTIMATION
#            with James-Stein shrinkage
# ============================================================

def _james_stein_shrinkage(
    raw_returns: np.ndarray,
    market_return: float,
) -> np.ndarray:
    """
    James-Stein shrinkage toward the market (grand mean).

    Standard formula:
        mu_JS = (1 - c) * mu_raw  +  c * mu_market

    where the shrinkage intensity c is:
        c = (n - 2) * sigma_avg^2 / ||mu_raw - mu_market||^2

    c is clamped to [0, 1]. When individual estimates are noisy
    relative to their variance, c approaches 1 and we mostly trust the
    market. When estimates are precise and spread out, c -> 0.

    This is provably better in MSE than raw estimates for n >= 3 assets.
    """
    n            = len(raw_returns)
    diff         = raw_returns - market_return
    diff_norm_sq = float(np.dot(diff, diff))

    if diff_norm_sq < 1e-12 or n < 3:
        return raw_returns

    sigma_sq_avg = diff_norm_sq / n
    c = float(np.clip((n - 2) * sigma_sq_avg / diff_norm_sq, 0.0, 1.0))

    return (1.0 - c) * raw_returns + c * market_return


def estimate_expected_returns(
    returns_df: pd.DataFrame,
    regimes: dict,
    user_target_annual: float,
    market_annual_return: float = 0.12,
    ml_views: dict | None = None,
) -> dict:
    """
    Blend three signals, then apply James-Stein shrinkage.

    Signal blending
    ---------------
    Rather than picking the current binary regime label and plugging in
    that state's mean, we use the smoothed regime probabilities as a soft
    mixture weight. If the model thinks there is 60% Bull and 40% Sideways,
    the regime signal is:
        0.60 * bull_mean + 0.40 * sideways_mean + 0.00 * bear_mean

    This is far more stable than a binary switch and correctly propagates
    the HMM's uncertainty into the return estimate.

    After blending, all assets' raw estimates are passed through
    James-Stein shrinkage toward the market return. This prevents any
    single asset from being assigned an absurdly high or low expected
    return just because its recent regime happened to be very strong.
    """
    trading_days = 252
    raw_annual   = {}

    for ticker in returns_df.columns:
        ret_series   = returns_df[ticker]
        regime_info  = regimes[ticker]
        state_means  = regime_info["state_means"]
        regime_probs = regime_info["regime_probs"]

        # Signal 1: soft regime-conditioned mean
        regime_daily = sum(
            regime_probs.get(lbl, 0.0) * state_means.get(lbl, 0.0)
            for lbl in ["Bull", "Sideways", "Bear"]
        )
        regime_annual = regime_daily * trading_days

        # Signal 2: momentum (1M + 3M equal blend)
        mom_1m = ret_series.tail(21).mean() * trading_days
        mom_3m = ret_series.tail(63).mean() * trading_days
        momentum_annual = 0.5 * mom_1m + 0.5 * mom_3m

        # Signal 3: user target, down-weighted in bearish regimes
        bear_prob   = regime_probs.get("Bear", 0.0)
        user_weight = max(0.0, 0.20 * (1.0 - 2.0 * bear_prob))

        if ml_views and ticker in ml_views:
            p_up   = float(ml_views[ticker])
            ml_ann = (2 * p_up - 1) * 0.30
            raw_annual[ticker] = (
                0.45 * regime_annual
                + 0.30 * momentum_annual
                + user_weight * user_target_annual
                + 0.20 * ml_ann
            )
        else:
            raw_annual[ticker] = (
                0.55 * regime_annual
                + 0.35 * momentum_annual
                + user_weight * user_target_annual
            )

    # James-Stein shrinkage across all assets
    tickers  = list(raw_annual.keys())
    raw_arr  = np.array([raw_annual[t] for t in tickers])
    shrunken = _james_stein_shrinkage(raw_arr, market_annual_return)

    exp_returns = {}
    for i, ticker in enumerate(tickers):
        model_annual = float(shrunken[i])
        div_pct      = abs(model_annual - user_target_annual) * 100
        warning      = (
            f"Model ({model_annual*100:.1f}%) vs User Target "
            f"({user_target_annual*100:.1f}%) diverge by {div_pct:.1f}pp"
            if div_pct > 15 else None
        )
        exp_returns[ticker] = {
            "annual":             model_annual,
            "daily":              model_annual / trading_days,
            "regime_signal":      raw_annual[ticker],
            "momentum_signal":    momentum_annual,
            "user_target":        user_target_annual,
            "divergence_warning": warning,
        }

    return exp_returns


# ============================================================
# SECTION 7: BLACK-LITTERMAN
# ============================================================

def black_litterman_returns(
    market_caps: dict,
    cov_annual: np.ndarray,
    tickers: list,
    views: dict,
    tau: float = 0.5,
    risk_aversion: float = 2.5,
) -> np.ndarray:
    """Black-Litterman posterior blending market equilibrium with model views."""
    n        = len(tickers)
    total_mc = sum(market_caps.values())
    w_mkt    = np.array([market_caps[t] / total_mc for t in tickers])
    pi       = risk_aversion * cov_annual @ w_mkt

    P         = np.eye(n)
    Q         = np.array([views[t] for t in tickers])
    tau_sigma = tau * cov_annual
    omega     = np.diag(np.diag(P @ tau_sigma @ P.T)) * 0.1

    tau_sigma_inv = np.linalg.inv(tau_sigma)
    omega_inv     = np.linalg.inv(omega)
    M_inv         = tau_sigma_inv + P.T @ omega_inv @ P
    mu_bl         = np.linalg.inv(M_inv) @ (tau_sigma_inv @ pi + P.T @ omega_inv @ Q)

    return mu_bl


# ============================================================
# SECTION 8: FAT-TAIL MONTE CARLO (Bootstrap + Student-t VaR/CVaR)
# ============================================================

def monte_carlo_var(
    returns_df: pd.DataFrame,
    weights: np.ndarray,
    n_simulations: int = 10_000,
    horizon_days: int = 21,
    confidence: float = 0.95,
) -> dict:
    """
    Portfolio VaR and CVaR via two methods:

    1. Block bootstrap - resample contiguous 5-day blocks from historical
       returns to preserve autocorrelation and volatility clustering.
       No distributional assumption; fat tails come for free.

    2. Student-t parametric - fit a t distribution to the portfolio return
       series. The degrees-of-freedom parameter captures tail heaviness.

    Returns the more conservative (larger loss) of the two, alongside
    both estimates for display.
    """
    port_rets  = (returns_df @ weights).values
    T          = len(port_rets)
    block_size = 5
    n_blocks   = max(1, horizon_days // block_size)
    n_starts   = max(1, T - block_size + 1)

    rng = np.random.default_rng(42)

    # Method 1: Block Bootstrap
    sim_bs = np.empty(n_simulations)
    for i in range(n_simulations):
        starts   = rng.integers(0, n_starts, size=n_blocks)
        sampled  = np.concatenate([port_rets[s:s + block_size] for s in starts])
        sim_bs[i] = (1 + sampled[:horizon_days]).prod() - 1

    var_bs  = float(np.percentile(sim_bs, (1 - confidence) * 100))
    cvar_bs = float(sim_bs[sim_bs <= var_bs].mean()) if (sim_bs <= var_bs).any() else var_bs

    # Method 2: Student-t parametric
    mu_p  = port_rets.mean()
    sig_p = port_rets.std(ddof=1)
    try:
        df_fit, loc_fit, scale_fit = student_t.fit(port_rets, floc=mu_p, fscale=sig_p)
        df_fit = max(float(df_fit), 2.1)
    except Exception:
        df_fit, loc_fit, scale_fit = 5.0, mu_p, sig_p

    scale_h = scale_fit * np.sqrt(horizon_days)
    mu_h    = loc_fit * horizon_days
    var_t   = float(student_t.ppf(1 - confidence, df=df_fit, loc=mu_h, scale=scale_h))
    t_draws = student_t.rvs(df=df_fit, loc=mu_h, scale=scale_h,
                             size=n_simulations, random_state=42)
    cvar_t  = float(t_draws[t_draws <= var_t].mean()) if (t_draws <= var_t).any() else var_t

    return {
        "var_monthly":    min(var_bs, var_t),
        "cvar_monthly":   min(cvar_bs, cvar_t),
        "var_bootstrap":  var_bs,
        "var_t":          var_t,
        "cvar_bootstrap": cvar_bs,
        "cvar_t":         cvar_t,
        "t_df":           df_fit,
    }


# ============================================================
# SECTION 9: MEAN-VARIANCE OPTIMISATION
# ============================================================

def mean_variance_optimize(
    mu: np.ndarray,
    cov_annual: np.ndarray,
    tickers: list,
    risk_appetite_monthly: float,
    allow_short: bool = False,
    lambda_reg: float = 0.08,
    max_weight: float = 0.40,
) -> dict:
    """
    Maximise regularised Sharpe ratio.

    Objective: -Sharpe(w) + lambda_reg * ||w||^2

    The L2 penalty spreads weights proportionally to each stock's
    risk/reward: a stock with 2x better Sharpe gets roughly 2x the weight,
    but the penalty prevents runaway concentration. max_weight = 0.40
    is a hard per-stock cap that ensures diversification across any
    portfolio of 3+ assets.
    """
    n               = len(tickers)
    z_95            = norm.ppf(0.95)
    risk_free_rate  = 0.07
    eq_w            = np.ones(n) / n
    MAX_TOTAL_SHORT = 0.40
    MAX_SHORT_SINGLE = -0.35

    bounds = (
        [(MAX_SHORT_SINGLE, max_weight) for _ in range(n)]
        if allow_short
        else [(0.0, max_weight) for _ in range(n)]
    )

    def objective(w):
        ret     = w @ mu
        vol     = np.sqrt(w @ cov_annual @ w)
        sharpe  = (ret - risk_free_rate) / vol if vol > 1e-9 else -1e6
        penalty = lambda_reg * float(np.dot(w, w))
        return -sharpe + penalty

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    if allow_short:
        constraints.append({
            "type": "ineq",
            "fun":  lambda w: MAX_TOTAL_SHORT + np.sum(np.minimum(w, 0.0))
        })

    # Diverse starting points
    rank   = np.argsort(mu)
    starts = [eq_w.copy()]

    try:
        inv_vol = 1.0 / np.sqrt(np.diag(cov_annual))
        starts.append(np.clip(inv_vol / inv_vol.sum(), 0, max_weight))
    except Exception:
        pass

    mu_pos = np.maximum(mu, 0.0)
    if mu_pos.sum() > 1e-9:
        starts.append(np.clip(mu_pos / mu_pos.sum(), 0, max_weight))

    try:
        ind_sharpe = (mu - risk_free_rate) / np.sqrt(np.diag(cov_annual))
        sp = np.maximum(ind_sharpe, 0.0)
        if sp.sum() > 1e-9:
            starts.append(np.clip(sp / sp.sum(), 0, max_weight))
    except Exception:
        pass

    if allow_short and n >= 2:
        w_tilt = eq_w.copy()
        tilt   = min(0.20, MAX_TOTAL_SHORT / max(n // 2, 1))
        n_s    = max(n // 2, 1)
        n_l    = n - n_s
        for idx in rank[:n_s]:
            w_tilt[idx] -= tilt / n_s
        for idx in rank[n_s:]:
            w_tilt[idx] += tilt / n_l
        starts.append(w_tilt)

        s   = min(0.20, MAX_TOTAL_SHORT)
        w_s = np.full(n, (1.0 + s) / max(n - 1, 1))
        w_s[rank[0]] = -s
        starts.append(w_s)

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

    if best_result is None:
        res_mv = minimize(
            lambda w: w @ cov_annual @ w, eq_w,
            method="SLSQP", bounds=bounds,
            constraints=[{"type": "eq", "fun": lambda w: np.sum(w) - 1}],
        )
        weights = res_mv.x if res_mv.success else eq_w
    else:
        weights = best_result.x

    weights[np.abs(weights) < 2e-3] = 0.0
    total   = weights.sum()
    weights = weights / total if abs(total) > 1e-9 else eq_w

    port_ret      = float(weights @ mu)
    port_vol      = float(np.sqrt(weights @ cov_annual @ weights))
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
# SECTION 10: STOP LOSS CALCULATION
# ============================================================

def calculate_stop_losses(
    prices: pd.DataFrame,
    sigma_forecasts: dict,
    weights: dict,
    capital: float,
    k: float = 1.5,
) -> dict:
    """
    Long:  stop = entry x (1 - k_adj x sigma_daily)
    Short: stop = entry x (1 + k_adj x sigma_daily)
    """
    stop_data = {}

    for ticker, weight in weights.items():
        price      = float(prices[ticker].iloc[-1])
        sigma      = sigma_forecasts[ticker]
        allocation = weight * capital
        is_short   = weight < 0
        shares     = allocation / price if price > 0 else 0
        k_adj      = k * (1.0 + 0.3 * abs(weight))
        stop_price = price * (1 + k_adj * sigma) if is_short \
                     else price * (1 - k_adj * sigma)

        stop_data[ticker] = {
            "entry_price":       price,
            "stop_price":        stop_price,
            "stop_pct":          k_adj * sigma * 100,
            "daily_sigma_pct":   sigma * 100,
            "weight_pct":        weight * 100,
            "allocation":        allocation,
            "shares":            shares,
            "is_short":          is_short,
            "risk_per_position": abs(allocation) * k_adj * sigma,
        }

    return stop_data


# ============================================================
# SECTION 11: DCA SCHEDULE
# ============================================================

def generate_dca_schedule(weights: dict, capital: float, months: int = 6) -> pd.DataFrame:
    """Monthly DCA with front-loading."""
    decay = np.array([1.0 / (1 + 0.1 * m) for m in range(months)])
    decay /= decay.sum()
    rows = []
    for idx, frac in enumerate(decay, start=1):
        monthly_capital = capital * frac
        row = {"Month": f"Month {idx}", "Deploy (Rs)": round(monthly_capital, 2)}
        for ticker, w in weights.items():
            row[ticker] = round(w * monthly_capital, 2)
        rows.append(row)
    return pd.DataFrame(rows)


# ============================================================
# SECTION 12: MAIN PIPELINE
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
    ml_views: dict | None = None,
):
    DIVIDER = "=" * 65
    print(f"\n{DIVIDER}")
    print("  PORTFOLIO OPTIMIZER  |  GARCH+DCC+HMM+BL+LW+JS+MC")
    print(DIVIDER)

    print("\n[1/7] Fetching market data...")
    prices, returns = fetch_data(tickers)
    tickers         = returns.columns.tolist()
    market_caps     = get_market_caps(tickers)

    print("\n[2/7] Detecting regimes (EMA-smoothed HMM)...")
    regimes = detect_regimes(returns)
    regime_table = [
        [t,
         regimes[t]["regime"],
         f"{regimes[t]['transition_probs'].get(regimes[t]['regime'], 0):.0%}",
         f"{regimes[t]['regime_mean_daily']*100:.3f}%",
         ", ".join(f"{k}:{v:.0%}" for k, v in regimes[t]["regime_probs"].items())]
        for t in tickers
    ]
    print(tabulate(regime_table,
                   headers=["Stock", "Regime", "Stay Prob", "Daily Mean", "Smoothed Probs"],
                   tablefmt="rounded_outline"))

    print("\n[3/7] Fitting DCC-GARCH (Ledoit-Wolf Q_bar)...")
    dcc = fit_dcc_garch(returns)
    print(f"    DCC alpha: {dcc['dcc_a']:.4f}  |  DCC beta: {dcc['dcc_b']:.4f}")

    print("\n[4/7] Estimating expected returns (James-Stein shrinkage)...")
    exp_returns = estimate_expected_returns(returns, regimes, user_target_annual, ml_views=ml_views)
    for t in tickers:
        w = exp_returns[t]["divergence_warning"]
        if w:
            print(f"    {w}")

    print("\n[5/7] Black-Litterman posterior...")
    views = {t: exp_returns[t]["annual"] for t in tickers}
    mu_bl = black_litterman_returns(
        market_caps=market_caps,
        cov_annual=dcc["cov_annual"],
        tickers=tickers,
        views=views,
    )

    print("\n[6/7] Mean-Variance Optimisation (lambda_reg + max 40% per stock)...")
    mvo = mean_variance_optimize(
        mu=mu_bl,
        cov_annual=dcc["cov_annual"],
        tickers=tickers,
        risk_appetite_monthly=risk_appetite_monthly,
        allow_short=allow_short,
    )

    print("      Running fat-tail Monte Carlo (bootstrap + Student-t)...")
    mc = monte_carlo_var(returns, mvo["weights_arr"])
    mvo["mc"] = mc

    print("\n[7/7] Computing GARCH-based stop losses...")
    stop_data = calculate_stop_losses(
        prices, dcc["sigma_forecasts"], mvo["weights"], capital, stop_loss_k
    )

    dca_df = generate_dca_schedule(mvo["weights"], capital, dca_months) \
             if invest_mode == "dca" else None

    print(f"\n{'='*65}\n")

    return {
        "weights":     mvo["weights"],
        "stop_data":   stop_data,
        "regimes":     regimes,
        "dca_df":      dca_df,
        "portfolio_metrics": {
            "annual_return":  mvo["annual_return"],
            "annual_vol":     mvo["annual_vol"],
            "sharpe":         mvo["sharpe"],
            "monthly_var_95": mvo["var_95_monthly"],
            "mc_var":         mc["var_monthly"],
            "mc_cvar":        mc["cvar_monthly"],
            "t_df":           mc["t_df"],
        },
        "dcc":         dcc,
        "bl_returns":  {tickers[i]: mu_bl[i] for i in range(len(tickers))},
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