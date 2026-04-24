"""
EWMA Volatility Model
=========================================================
Implements:
  1. ewma_variance()       — recursive EWMA with configurable λ
  2. ewma_volatility()     — annualised σ = σ_daily × √252
  3. get_optimal_lambda()  — MLE-optimal decay factor
  4. half_life()           — shock decay half-life
  5. decay_table()         — λ sensitivity summary
  6. Plot helpers          — EWMA vs rolling, lambda sweep
"""

import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy.optimize import minimize_scalar
from scipy.stats import norm
import warnings

warnings.filterwarnings("ignore")


def ewma_variance(returns: pd.Series, lambda_: float = 0.94) -> pd.Series:
    """
    Recursive EWMA variance estimator (RiskMetrics-style).
    σ²ₜ = λ·σ²ₜ₋₁ + (1−λ)·r²ₜ
    """
    if not (0 < lambda_ < 1):
        raise ValueError(f"lambda_ must be in (0, 1), got {lambda_}")
    r = returns.values.astype(float)
    n = len(r)
    var = np.empty(n)
    warmup = min(21, n)
    var[0] = np.var(r[:warmup], ddof=1)
    alpha = 1.0 - lambda_
    for t in range(1, n):
        var[t] = lambda_ * var[t - 1] + alpha * r[t] ** 2
    return pd.Series(var, index=returns.index, name=f"ewma_var_λ{lambda_}")


def ewma_volatility(returns: pd.Series, lambda_: float = 0.94,
                    annualise: bool = True) -> pd.Series:
    """Annualised EWMA volatility. σ_annual = σ_daily × √252"""
    var = ewma_variance(returns, lambda_)
    vol = np.sqrt(var)
    if annualise:
        vol *= np.sqrt(252)
        vol.name = f"EWMA Vol (λ={lambda_}, ann.)"
    else:
        vol.name = f"EWMA Vol (λ={lambda_}, daily)"
    return vol


def rolling_volatility(returns: pd.Series, window: int = 21,
                       annualise: bool = True) -> pd.Series:
    """Simple rolling standard deviation. σ_annual = σ_daily × √252"""
    vol = returns.rolling(window).std()
    if annualise:
        vol *= np.sqrt(252)
        vol.name = f"Rolling Std (w={window}, ann.)"
    else:
        vol.name = f"Rolling Std (w={window}, daily)"
    return vol


def get_optimal_lambda(returns: pd.Series, bounds: tuple = (0.85, 0.99)) -> float:
    """MLE-optimal decay factor via negative log-likelihood minimisation."""
    def nll(lam):
        T = len(returns)
        variances = np.zeros(T)
        variances[0] = np.var(returns.values)
        for t in range(1, T):
            variances[t] = lam * variances[t - 1] + (1 - lam) * (returns.iloc[t - 1] ** 2)
        return 0.5 * np.sum(
            np.log(variances + 1e-10) + (returns.values ** 2) / (variances + 1e-10)
        )

    res = minimize_scalar(nll, bounds=bounds, method="bounded")
    return float(res.x)


def half_life(lambda_: float) -> float:
    """Days for a volatility shock to decay to half its initial weight."""
    return np.log(0.5) / np.log(lambda_)


def decay_table(lambdas=None) -> pd.DataFrame:
    """Summary table: λ, half-life, effective window (95% weight)."""
    if lambdas is None:
        lambdas = np.round(np.arange(0.90, 1.00, 0.01), 2).tolist()
    rows = []
    for lam in lambdas:
        hl  = half_life(lam)
        eff = np.log(0.05) / np.log(lam)
        rows.append({
            "λ": lam,
            "Half-life (days)": round(hl, 1),
            "95%-weight window (days)": round(eff, 0),
        })
    return pd.DataFrame(rows).set_index("λ")


# ─────────────────────────────────────────────
# Plotting helpers
# ─────────────────────────────────────────────

def plot_ewma_vs_rolling(
    prices: pd.Series,
    lambda_: float = 0.94,
    window: int = 21,
    save_path: str = "ewma_vs_rolling.png",
) -> None:
    log_ret  = np.log(prices / prices.shift(1)).dropna()
    ewma_vol = ewma_volatility(log_ret, lambda_=lambda_)
    roll_vol = rolling_volatility(log_ret, window=window)

    fig, (ax_price, ax_vol) = plt.subplots(
        2, 1, figsize=(14, 9),
        gridspec_kw={"height_ratios": [1, 2]},
        sharex=True,
    )
    fig.suptitle(
        f"EWMA vs Rolling Volatility (λ={lambda_}, rolling window={window}d)",
        fontsize=14, fontweight="bold", y=0.98,
    )

    ax_price.plot(prices, color="#1f77b4", linewidth=1.0, label="Price (₹)")
    ax_price.set_ylabel("Price (₹)", fontsize=10)
    ax_price.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"₹{x:,.0f}"))
    ax_price.grid(True, alpha=0.3)
    ax_price.legend(fontsize=9)

    ax_vol.plot(ewma_vol, color="#d62728", linewidth=1.3,
                label=f"EWMA (λ={lambda_})", zorder=3)
    ax_vol.plot(roll_vol, color="#2ca02c", linewidth=1.3, linestyle="--", alpha=0.85,
                label=f"Rolling Std ({window}d)", zorder=2)
    ax_vol.fill_between(
        ewma_vol.index, ewma_vol, roll_vol,
        where=(ewma_vol > roll_vol), interpolate=True,
        alpha=0.12, color="#d62728", label="EWMA > Rolling",
    )
    ax_vol.set_ylabel("Annualised Volatility", fontsize=10)
    ax_vol.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x*100:.0f}%"))
    ax_vol.grid(True, alpha=0.3)
    ax_vol.legend(fontsize=9, loc="upper right")
    ax_vol.xaxis.set_major_locator(mdates.YearLocator())
    ax_vol.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax_vol.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=[4, 7, 10]))
    fig.autofmt_xdate(rotation=0, ha="center")

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    print(f"[✓] Saved: {save_path}")
    plt.close()


def plot_lambda_sensitivity(
    prices: pd.Series,
    lambdas=None,
    save_path: str = "lambda_sensitivity.png",
) -> None:
    if lambdas is None:
        lambdas = [0.90, 0.91, 0.92, 0.93, 0.94, 0.95, 0.96, 0.97, 0.98, 0.99]

    log_ret = np.log(prices / prices.shift(1)).dropna()
    cmap    = plt.cm.RdYlBu_r
    colours = [cmap(i / (len(lambdas) - 1)) for i in range(len(lambdas))]

    fig, axes = plt.subplots(2, 1, figsize=(14, 10), sharex=True,
                             gridspec_kw={"height_ratios": [1, 2.5]})
    fig.suptitle("EWMA Volatility — Lambda Sensitivity Sweep",
                 fontsize=14, fontweight="bold")

    axes[0].plot(prices, color="#555555", linewidth=0.9)
    axes[0].set_ylabel("Price (₹)", fontsize=10)
    axes[0].yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"₹{x:,.0f}"))
    axes[0].grid(True, alpha=0.3)

    for lam, col in zip(lambdas, colours):
        lw  = 1.0 + 0.4 * (lam - 0.90) / 0.09
        vol = ewma_volatility(log_ret, lambda_=lam)
        axes[1].plot(vol, color=col, linewidth=lw, label=f"λ = {lam:.2f}")

    axes[1].set_ylabel("Annualised Volatility", fontsize=10)
    axes[1].yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x*100:.0f}%"))
    axes[1].grid(True, alpha=0.3)
    axes[1].legend(title="Decay factor (λ)", title_fontsize=9,
                   fontsize=8.5, loc="upper right", ncol=2)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    print(f"[✓] Saved: {save_path}")
    plt.close()


# ─────────────────────────────────────────────
# Standalone runner
# ─────────────────────────────────────────────

def run_ewma(ticker_list: list) -> None:
    ticker = ticker_list[0] if ticker_list else "RELIANCE.NS"
    data   = yf.download(ticker, period="10y", interval="1d", progress=False)
    prices = data["Close"].squeeze()

    returns = prices.pct_change().dropna()
    log_ret = np.log(prices / prices.shift(1)).dropna()

    best_lambda = get_optimal_lambda(returns)
    print(f"Optimal Lambda: {best_lambda:.6f}")
    print(f"Half-life     : {half_life(best_lambda):.1f} days")

    ewma_vol = ewma_volatility(log_ret, lambda_=best_lambda)
    roll_vol = rolling_volatility(log_ret, window=21)

    z_score  = norm.ppf(0.95)
    ewma_var = ewma_variance(returns, lambda_=best_lambda)
    var_1d   = 1_000_000 * z_score * np.sqrt(ewma_var.iloc[-1])
    print(f"Current 1-Day VaR (95%, ₹1M): ₹{var_1d:,.2f}")

    print(f"\nDate range  : {prices.index[0].date()} → {prices.index[-1].date()}")
    print(f"Trading days: {len(prices):,}")
    print(f"\n── EWMA Vol (ann.) ──")
    print(f"  Mean : {ewma_vol.mean()*100:.2f}%")
    print(f"  Max  : {ewma_vol.max()*100:.2f}%  on {ewma_vol.idxmax().date()}")
    print(f"  Min  : {ewma_vol.min()*100:.2f}%  on {ewma_vol.idxmin().date()}")

    print(f"\n── Decay table ──")
    print(decay_table().to_string())

    plot_ewma_vs_rolling(prices, best_lambda)
    plot_lambda_sensitivity(prices)
    print("\n[✓] All done.")


if __name__ == "__main__":
    run_ewma(["RELIANCE.NS"])
