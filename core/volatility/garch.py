import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf
import numpy as np
from statsmodels.tsa.stattools import pacf
from statsmodels.graphics.tsaplots import plot_pacf
from arch import arch_model
import warnings

warnings.filterwarnings("ignore")


# from core.data import fetch_ohlcv_data

data = yf.download("RELIANCE.NS", period = '10y', interval='1d')
returns = data['Close'].pct_change().dropna()
returns = returns.squeeze()

best_specs = 0, 0

def model_predict(returns, horizon: int) -> pd.DataFrame:
    
    # Cap horizon at 7
    horizon = min(horizon, 7)
    if horizon < 1:
        raise ValueError("Horizon must be at least 1 day.")

    best_p, best_q = best_specs

    # ── Refit best model and forecast ──────────────────────────────────────
    if best_p == 0:
        best_model = arch_model(returns, vol='Garch', q=best_q).fit(
            disp='off', options={'maxiter': 1000}
        )
    elif best_q == 0:
        best_model = arch_model(returns, vol='Garch', p=best_p).fit(
            disp='off', options={'maxiter': 1000}
        )
    else: 
        best_model = arch_model(returns, vol='Garch', p=best_p, q=best_q).fit(
            disp='off', options={'maxiter': 1000}
        )

    forecast = best_model.forecast(horizon=horizon, reindex=False)

    # forecast.variance is a DataFrame of shape (1, horizon)
    variance_forecast = forecast.variance.iloc[0]  

    forecast_df = pd.DataFrame({
        'day': range(1, horizon + 1),
        'variance': variance_forecast.values,
        'volatility': np.sqrt(variance_forecast.values),          # daily vol
        'annualised_volatility': np.sqrt(variance_forecast.values) * np.sqrt(252)
    }).set_index('day')

    print(f"\nVolatility Forecast for next {horizon} day(s):")
    print(forecast_df.to_string())

    return forecast_df

def run_garch(returns):

    pacf_values, conf_int = pacf(returns**2, nlags=20, alpha=0.05)

    n = len(returns)
    significance_threshold = 1.96 / np.sqrt(n)

    print(f"Significance Threshold: +/- {significance_threshold:.4f}")

    # Find indices where PACF is outside the threshold (excluding lag 0)
    significant_lags = np.where(np.abs(pacf_values[1:]) > significance_threshold)[0] + 1

    threshold = 3
    current_lag = 0
    best_p, best_q = 3, 3  # fallback

    for lag in significant_lags:
        if lag > current_lag and lag <= threshold:
            best_p = lag
            best_q = lag
    
    print(f"Setting upper bounds for alpha and beta as {best_q}, {best_p}")

    models = {}
    for p in range(1, best_q+1):
        for q in range(1, best_p+1):
            result = arch_model(returns, vol='Garch', p=p, q=q).fit(disp='off', options={'maxiter': 1000})
            params = result.params              # Coefficients
            pvalues = result.pvalues            # P-values
            tvalues = result.tvalues            # t-statistics
            std_err = result.std_err            # Standard errors
            conf_int = result.conf_int()        # 95% Confidence intervals (DataFrame)

            # Combine into one clean DataFrame
            summary_df = pd.DataFrame({
                'coef': params,
                'std_err': std_err,
                't_stat': tvalues,
                'p_value': pvalues,
                'ci_lower': conf_int['lower'],
                'ci_upper': conf_int['upper']
            })
            garch_terms = summary_df[
                summary_df.index.str.startswith('alpha') |
                summary_df.index.str.startswith('beta')
            ]

            all_significant = (garch_terms['p_value'] < 0.05).all()

            if result.convergence_flag == 0:
                print("Optimization Successful")
            else:
                print(f"Optimization Failed with flag: {result.convergence_flag}")

            if all_significant:
                print("✅ All GARCH parameters are significant.")
            else:
                insignificant = garch_terms[garch_terms['p_value'] >= 0.05]
                print("❌ Insignificant parameters found:")
                print(insignificant[['coef', 'p_value']])
            models[f'GARCH({p},{q})'] = {'AIC': result.aic, 'BIC': result.bic}

    for p in range(1, best_p+1):
        result = arch_model(returns, vol='Garch', p=p).fit(disp='off', options={'maxiter': 1000})
        params = result.params              # Coefficients
        pvalues = result.pvalues            # P-values
        tvalues = result.tvalues            # t-statistics
        std_err = result.std_err            # Standard errors
        conf_int = result.conf_int()        # 95% Confidence intervals (DataFrame)

        # Combine into one clean DataFrame
        summary_df = pd.DataFrame({
            'coef': params,
            'std_err': std_err,
            't_stat': tvalues,
            'p_value': pvalues,
            'ci_lower': conf_int['lower'],
            'ci_upper': conf_int['upper']
        })
        garch_terms = summary_df[
            summary_df.index.str.startswith('alpha') |
            summary_df.index.str.startswith('beta')
        ]

        all_significant = (garch_terms['p_value'] < 0.05).all()

        if result.convergence_flag == 0:
            print("Optimization Successful")
        else:
            print(f"Optimization Failed with flag: {result.convergence_flag}")

        if all_significant:
            print("✅ All GARCH parameters are significant.")
        else:
            insignificant = garch_terms[garch_terms['p_value'] >= 0.05]
            print("❌ Insignificant parameters found:")
            print(insignificant[['coef', 'p_value']])
        models[f'GARCH({p},0)'] = {'AIC': result.aic, 'BIC': result.bic}


    for q in range(1, best_q+1):
        result = arch_model(returns, vol='Garch', q=q).fit(disp='off', options={'maxiter': 1000})
        params = result.params              # Coefficients
        pvalues = result.pvalues            # P-values
        tvalues = result.tvalues            # t-statistics
        std_err = result.std_err            # Standard errors
        conf_int = result.conf_int()        # 95% Confidence intervals (DataFrame)

        # Combine into one clean DataFrame
        summary_df = pd.DataFrame({
            'coef': params,
            'std_err': std_err,
            't_stat': tvalues,
            'p_value': pvalues,
            'ci_lower': conf_int['lower'],
            'ci_upper': conf_int['upper']
        })
        garch_terms = summary_df[
            summary_df.index.str.startswith('alpha') |
            summary_df.index.str.startswith('beta')
        ]

        all_significant = (garch_terms['p_value'] < 0.05).all()

        if result.convergence_flag == 0:
            print("Optimization Successful")
        else:
            print(f"Optimization Failed with flag: {result.convergence_flag}")

        if all_significant:
            print("✅ All GARCH parameters are significant.")
        else:
            insignificant = garch_terms[garch_terms['p_value'] >= 0.05]
            print("❌ Insignificant parameters found:")
            print(insignificant[['coef', 'p_value']])
        models[f'GARCH(0,{q})'] = {'AIC': result.aic, 'BIC': result.bic}

    print(pd.DataFrame(models).T.sort_values('BIC'))

    # ──  Grid search for best (p, q) by BIC ─────────────────────────────────
    best_bic = np.inf
    best_aic = np.inf
    best_spec = (1, 1)  # sensible fallback

    candidate_specs = (
        [(p, q) for p in range(1, best_p + 1) for q in range(1, best_q + 1)]  # GARCH(p,q)
        + [(p, 0) for p in range(1, best_q + 1)]                               # pure GARCH
        + [(0, q) for q in range(1, best_p + 1)]                               # pure ARCH
    )

    for p, q in candidate_specs:
        try:
            if not p:
                res = arch_model(returns, vol='Garch', p=p).fit(
                    disp='off', options={'maxiter': 1000}
                )
            if not q: 
                res = arch_model(returns, vol='Garch', q=q).fit(
                    disp='off', options={'maxiter': 1000}
                )
            else: 
                res = arch_model(returns, vol='Garch', p=p, q=q).fit(
                    disp='off', options={'maxiter': 1000}
                )
            if res.convergence_flag == 0 and res.bic < best_bic and res.aic < best_aic:
                best_bic = res.bic
                best_aic = res.aic
                best_spec = (p, q)
        except Exception:
            continue

    best_p, best_q = best_spec
    print(f"Best model selected: GARCH({best_p},{best_q}) | BIC: {best_bic:.4f} | AIC: {best_aic:.4f}")

run_garch(returns)
model_predict(returns, horizon=3)