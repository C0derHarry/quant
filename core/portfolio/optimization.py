"""
Efficient Frontier, Risk Parity, and Min Variance portfolio construction.
All three are standalone — they don't run the full DCC-GARCH/BL pipeline in sizing.py.
Ledoit-Wolf covariance is used throughout for robustness on small samples.
"""

import numpy as np
import pandas as pd
import warnings
import yfinance as yf
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf

warnings.filterwarnings("ignore")
RF_ANNUAL = 0.065  # Indian risk-free rate ~6.5%


def _fetch_returns(tickers: list[str], period: str = "3y") -> pd.DataFrame:
    raw = yf.download(tickers, period=period, auto_adjust=True, progress=False)["Close"]
    if isinstance(raw, pd.Series):
        raw = raw.to_frame(tickers[0])
    raw = raw.dropna(how="all").ffill(limit=5).dropna()
    return np.log(raw / raw.shift(1)).dropna()


def _lw_cov(returns_df: pd.DataFrame) -> np.ndarray:
    lw = LedoitWolf()
    lw.fit(returns_df.values)
    return lw.covariance_


def _portfolio_stats(w: np.ndarray, mu: np.ndarray, cov: np.ndarray) -> tuple[float, float, float]:
    ret = float(w @ mu)
    vol = float(np.sqrt(w @ cov @ w))
    sharpe = (ret - RF_ANNUAL) / vol if vol > 1e-9 else 0.0
    return ret, vol, sharpe


# ── Efficient Frontier ────────────────────────────────────────────────────────

def efficient_frontier(tickers: list[str], period: str = "3y", n_portfolios: int = 50) -> dict:
    returns_df = _fetch_returns(tickers, period)
    mu_daily   = returns_df.mean().values
    mu         = mu_daily * 252
    cov_daily  = _lw_cov(returns_df)
    cov        = cov_daily * 252
    n          = len(tickers)

    bounds  = [(0.0, 1.0)] * n
    eq_cons = {"type": "eq", "fun": lambda w: np.sum(w) - 1}

    def neg_sharpe(w):
        r, v, _ = _portfolio_stats(w, mu, cov)
        return -(r - RF_ANNUAL) / (v + 1e-9)

    def portfolio_vol(w):
        return float(np.sqrt(w @ cov @ w))

    # Min-variance portfolio
    res_mv = minimize(portfolio_vol, np.ones(n) / n, method="SLSQP",
                      bounds=bounds, constraints=[eq_cons],
                      options={"ftol": 1e-12, "maxiter": 1000})
    w_mv   = res_mv.x
    r_mv, v_mv, s_mv = _portfolio_stats(w_mv, mu, cov)

    # Max-Sharpe portfolio
    res_ms = minimize(neg_sharpe, np.ones(n) / n, method="SLSQP",
                      bounds=bounds, constraints=[eq_cons],
                      options={"ftol": 1e-12, "maxiter": 1000})
    w_ms   = res_ms.x
    r_ms, v_ms, s_ms = _portfolio_stats(w_ms, mu, cov)

    # Frontier sweep
    r_min = r_mv
    r_max = float(np.max(mu)) * 0.98  # stay reachable
    targets = np.linspace(r_min, r_max, n_portfolios)

    frontier = []
    for target in targets:
        cons = [eq_cons, {"type": "ineq", "fun": lambda w, t=target: w @ mu - t}]
        res  = minimize(portfolio_vol, w_mv, method="SLSQP",
                        bounds=bounds, constraints=cons,
                        options={"ftol": 1e-12, "maxiter": 1000})
        if res.success:
            w = res.x
            r, v, s = _portfolio_stats(w, mu, cov)
            frontier.append({
                "ret":     round(r * 100, 3),
                "vol":     round(v * 100, 3),
                "sharpe":  round(s, 3),
                "weights": {tickers[i]: round(float(w[i]), 4) for i in range(n)},
            })

    def fmt_point(w, r, v, s):
        return {
            "ret":     round(r * 100, 3),
            "vol":     round(v * 100, 3),
            "sharpe":  round(s, 3),
            "weights": {tickers[i]: round(float(w[i]), 4) for i in range(n)},
        }

    return {
        "frontier":   frontier,
        "max_sharpe": fmt_point(w_ms, r_ms, v_ms, s_ms),
        "min_var":    fmt_point(w_mv, r_mv, v_mv, s_mv),
    }


# ── Risk Parity ───────────────────────────────────────────────────────────────

def risk_parity(tickers: list[str], period: str = "3y") -> dict:
    returns_df = _fetch_returns(tickers, period)
    mu         = returns_df.mean().values * 252
    cov_daily  = _lw_cov(returns_df)
    cov        = cov_daily * 252
    n          = len(tickers)

    def risk_contributions(w):
        port_vol = np.sqrt(w @ cov @ w)
        mrc      = cov @ w                   # marginal risk contribution
        rc       = w * mrc / (port_vol + 1e-9)
        return rc

    def objective(w):
        rc = risk_contributions(w)
        diffs = rc[:, None] - rc[None, :]
        return float(np.sum(diffs ** 2))

    bounds  = [(0.001, 1.0)] * n
    eq_cons = {"type": "eq", "fun": lambda w: np.sum(w) - 1}
    w0      = np.ones(n) / n

    res = minimize(objective, w0, method="SLSQP",
                   bounds=bounds, constraints=[eq_cons],
                   options={"ftol": 1e-14, "maxiter": 2000})
    w   = res.x / res.x.sum()

    r, v, s = _portfolio_stats(w, mu, cov)
    rc      = risk_contributions(w)
    # Normalise so contributions sum to 1 (percentage of total portfolio risk)
    rc_pct  = rc / (rc.sum() + 1e-9)

    return {
        "weights":            {tickers[i]: round(float(w[i]), 4) for i in range(n)},
        "risk_contributions": {tickers[i]: round(float(rc_pct[i]), 4) for i in range(n)},
        "metrics": {
            "annual_return": round(r * 100, 2),
            "annual_vol":    round(v * 100, 2),
            "sharpe":        round(s, 3),
        },
    }


# ── Min Variance ──────────────────────────────────────────────────────────────

def min_variance(tickers: list[str], period: str = "3y") -> dict:
    returns_df = _fetch_returns(tickers, period)
    mu         = returns_df.mean().values * 252
    cov_daily  = _lw_cov(returns_df)
    cov        = cov_daily * 252
    n          = len(tickers)

    bounds  = [(0.0, 1.0)] * n
    eq_cons = {"type": "eq", "fun": lambda w: np.sum(w) - 1}

    res = minimize(lambda w: float(w @ cov @ w), np.ones(n) / n,
                   method="SLSQP", bounds=bounds, constraints=[eq_cons],
                   options={"ftol": 1e-12, "maxiter": 1000})
    w   = res.x
    r, v, s = _portfolio_stats(w, mu, cov)

    return {
        "weights": {tickers[i]: round(float(w[i]), 4) for i in range(n)},
        "metrics": {
            "annual_return": round(r * 100, 2),
            "annual_vol":    round(v * 100, 2),
            "sharpe":        round(s, 3),
        },
    }
