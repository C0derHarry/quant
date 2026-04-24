import pandas as pd
import yfinance as yf
import numpy as np
from statsmodels.tsa.stattools import pacf
from arch import arch_model
import warnings

warnings.filterwarnings("ignore")


def model_predict(returns: pd.Series, best_p: int, best_q: int,
                  horizon: int) -> pd.DataFrame:
    """Fit GARCH(best_p, best_q) and forecast volatility for `horizon` days."""
    horizon = min(max(horizon, 1), 7)

    if best_p == 0:
        fitted = arch_model(returns, vol='Garch', q=best_q).fit(
            disp='off', options={'maxiter': 1000})
    elif best_q == 0:
        fitted = arch_model(returns, vol='Garch', p=best_p).fit(
            disp='off', options={'maxiter': 1000})
    else:
        fitted = arch_model(returns, vol='Garch', p=best_p, q=best_q).fit(
            disp='off', options={'maxiter': 1000})

    forecast          = fitted.forecast(horizon=horizon, reindex=False)
    variance_forecast = forecast.variance.iloc[0]

    forecast_df = pd.DataFrame({
        'day':                  range(1, horizon + 1),
        'variance':             variance_forecast.values,
        'volatility':           np.sqrt(variance_forecast.values),
        'annualised_volatility': np.sqrt(variance_forecast.values) * np.sqrt(252),
    }).set_index('day')

    print(f"\nVolatility Forecast for next {horizon} day(s):")
    print(forecast_df.to_string())
    return forecast_df


def run_garch(returns: pd.Series) -> tuple[int, int]:
    """
    PACF-guided GARCH model grid search.
    Returns (best_p, best_q) selected by lowest joint AIC + BIC.
    """
    pacf_values, _ = pacf(returns ** 2, nlags=20, alpha=0.05)
    n = len(returns)
    significance_threshold = 1.96 / np.sqrt(n)
    significant_lags = np.where(np.abs(pacf_values[1:]) > significance_threshold)[0] + 1

    print(f"Significance Threshold: +/- {significance_threshold:.4f}")

    upper = 3  # fallback max order
    for lag in significant_lags:
        if 1 <= lag <= 3:
            upper = lag

    print(f"Setting upper bounds for alpha and beta as {upper}")

    candidate_specs = (
        [(p, q) for p in range(1, upper + 1) for q in range(1, upper + 1)]
        + [(p, 0) for p in range(1, upper + 1)]
        + [(0, q) for q in range(1, upper + 1)]
    )

    models: dict[str, dict] = {}

    for p, q in candidate_specs:
        try:
            if p == 0:
                result = arch_model(returns, vol='Garch', q=q).fit(
                    disp='off', options={'maxiter': 1000})
            elif q == 0:
                result = arch_model(returns, vol='Garch', p=p).fit(
                    disp='off', options={'maxiter': 1000})
            else:
                result = arch_model(returns, vol='Garch', p=p, q=q).fit(
                    disp='off', options={'maxiter': 1000})

            if result.convergence_flag != 0:
                continue

            pvals      = result.pvalues
            garch_pvals = pvals[pvals.index.str.startswith(('alpha', 'beta'))]
            all_sig    = (garch_pvals < 0.05).all()

            key = f"GARCH({p},{q})"
            models[key] = {'AIC': result.aic, 'BIC': result.bic}
            status = "✅" if all_sig else "❌"
            print(f"  {key}: AIC={result.aic:.2f}  BIC={result.bic:.2f}  {status}")
        except Exception:
            continue

    if models:
        print(pd.DataFrame(models).T.sort_values('BIC'))

    best_bic  = np.inf
    best_aic  = np.inf
    best_spec = (1, 1)

    for p, q in candidate_specs:
        key = f"GARCH({p},{q})"
        if key not in models:
            continue
        row = models[key]
        if row['BIC'] < best_bic and row['AIC'] < best_aic:
            best_bic  = row['BIC']
            best_aic  = row['AIC']
            best_spec = (p, q)

    best_p, best_q = best_spec
    print(f"Best model: GARCH({best_p},{best_q}) | BIC: {best_bic:.4f} | AIC: {best_aic:.4f}")
    return best_p, best_q


if __name__ == "__main__":
    data    = yf.download("RELIANCE.NS", period='10y', interval='1d', progress=False)
    returns = data['Close'].pct_change().dropna().squeeze()
    best_p, best_q = run_garch(returns)
    model_predict(returns, best_p, best_q, horizon=3)
