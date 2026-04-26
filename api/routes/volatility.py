from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import yfinance as yf
import numpy as np
import pandas as pd
from scipy.stats import norm
from core.volatility.ewma import (
    ewma_variance, ewma_volatility, get_optimal_lambda, half_life, decay_table,
    rolling_volatility,
)
from core.volatility.garch import run_garch, model_predict

router = APIRouter()


class VolRequest(BaseModel):
    tickers: list[str]
    period:  str = "10y"


class ForecastRequest(BaseModel):
    tickers: list[str]
    period:  str  = "10y"
    best_p:  int  = 1
    best_q:  int  = 1
    horizon: int  = 5


def _normalize(ticker: str) -> str:
    if ticker.endswith((".NS", ".BO")):
        return ticker
    return ticker + ".NS"

def _fetch_returns(tickers: list[str], period: str):
    yf_tickers = [_normalize(t) for t in tickers]
    raw = yf.download(yf_tickers, period=period, auto_adjust=True, progress=False)["Close"]
    if isinstance(raw, pd.Series):
        raw = raw.to_frame(yf_tickers[0])
    raw.columns = [c.replace(".NS", "").replace(".BO", "") for c in raw.columns]
    raw = raw.dropna(how="all").ffill(limit=5).dropna()
    if raw.empty:
        raise ValueError(f"No price data returned for {tickers} over period '{period}'")
    log_ret = np.log(raw / raw.shift(1)).dropna()
    bare = tickers[0].replace(".NS", "").replace(".BO", "")
    if len(tickers) == 1:
        return log_ret[bare], raw
    port_ret = log_ret.mean(axis=1)
    port_ret.name = "Portfolio"
    return port_ret, raw


@router.post("/analyze")
def analyze(req: VolRequest):
    try:
        returns, prices = _fetch_returns(req.tickers, req.period)
        opt_lambda      = get_optimal_lambda(returns)

        ewma_vol_s  = ewma_volatility(returns, lambda_=opt_lambda)
        ewma_var_s  = ewma_variance(returns, lambda_=opt_lambda)
        roll_vol_s  = rolling_volatility(returns, window=21)
        z95         = norm.ppf(0.95)

        # GARCH grid search
        models_df, best_p, best_q, best_aic, best_bic = _garch_grid(returns)

        # Historical EWMA + rolling (last 504 days for chart performance)
        tail    = min(504, len(ewma_vol_s))
        vol_history = []
        for i in range(tail):
            idx = len(ewma_vol_s) - tail + i
            vol_history.append({
                "date":       ewma_vol_s.index[idx].strftime("%Y-%m-%d"),
                "ewma_vol":   round(float(ewma_vol_s.iloc[idx]) * 100, 4),
                "rolling_vol":round(float(roll_vol_s.iloc[idx]) * 100, 4)
                               if idx < len(roll_vol_s) and not np.isnan(roll_vol_s.iloc[idx]) else None,
            })

        return {
            "opt_lambda":  round(opt_lambda, 6),
            "half_life":   round(half_life(opt_lambda), 1),
            "current_vol": round(float(ewma_vol_s.iloc[-1]) * 100, 4),
            "peak_vol":    round(float(ewma_vol_s.max()) * 100, 4),
            "peak_date":   ewma_vol_s.idxmax().strftime("%Y-%m-%d"),
            "mean_vol":    round(float(ewma_vol_s.mean()) * 100, 4),
            "var_1d_1m":   round(1_000_000 * z95 * float(np.sqrt(ewma_var_s.iloc[-1])), 0),
            "vol_history": vol_history,
            "decay_table": decay_table().reset_index().to_dict(orient="records"),
            "garch_models": models_df,
            "best_p":      best_p,
            "best_q":      best_q,
            "best_aic":    best_aic,
            "best_bic":    best_bic,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/forecast")
def forecast(req: ForecastRequest):
    try:
        returns, _ = _fetch_returns(req.tickers, req.period)
        fc_df      = model_predict(returns, req.best_p, req.best_q, req.horizon)
        z95        = norm.ppf(0.95)

        rows = []
        for day, row in fc_df.iterrows():
            rows.append({
                "day":          int(day),
                "variance":     float(row["variance"]),
                "daily_vol":    round(float(row["volatility"]) * 100, 4),
                "ann_vol":      round(float(row["annualised_volatility"]) * 100, 4),
                "var_1d_1m":    round(1_000_000 * z95 * float(row["volatility"]), 0),
            })

        # Fetch conditional vol history for chart
        from arch import arch_model as arch
        if req.best_p == 0:
            fitted = arch(returns, vol='Garch', q=req.best_q).fit(disp='off')
        elif req.best_q == 0:
            fitted = arch(returns, vol='Garch', p=req.best_p).fit(disp='off')
        else:
            fitted = arch(returns, vol='Garch', p=req.best_p, q=req.best_q).fit(disp='off')

        cond_vol = fitted.conditional_volatility * np.sqrt(252)
        tail_cv  = min(252, len(cond_vol))
        hist_vol = []
        for i in range(tail_cv):
            idx = len(cond_vol) - tail_cv + i
            hist_vol.append({
                "date": cond_vol.index[idx].strftime("%Y-%m-%d"),
                "vol":  round(float(cond_vol.iloc[idx]) * 100, 4),
            })

        return {"forecast": rows, "hist_vol": hist_vol}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _garch_grid(returns: pd.Series):
    from statsmodels.tsa.stattools import pacf
    from arch import arch_model as arch

    pacf_vals, _ = pacf(returns ** 2, nlags=20, alpha=0.05)
    sig_threshold = 1.96 / np.sqrt(len(returns))
    sig_lags = np.where(np.abs(pacf_vals[1:]) > sig_threshold)[0] + 1

    upper = 3
    for lag in sig_lags:
        if 1 <= lag <= 3:
            upper = lag

    candidate_specs = (
        [(p, q) for p in range(1, upper+1) for q in range(1, upper+1)]
        + [(p, 0) for p in range(1, upper+1)]
        + [(0, q) for q in range(1, upper+1)]
    )

    models_out = []
    best_bic, best_aic, best_spec = np.inf, np.inf, (1, 1)

    for p, q in candidate_specs:
        try:
            if p == 0:
                res = arch(returns, vol='Garch', q=q).fit(disp='off', options={'maxiter': 1000})
            elif q == 0:
                res = arch(returns, vol='Garch', p=p).fit(disp='off', options={'maxiter': 1000})
            else:
                res = arch(returns, vol='Garch', p=p, q=q).fit(disp='off', options={'maxiter': 1000})
            if res.convergence_flag != 0:
                continue
            pv      = res.pvalues
            garch_p = pv[pv.index.str.startswith(('alpha', 'beta'))]
            all_sig = bool((garch_p < 0.05).all())
            models_out.append({
                "model":     f"GARCH({p},{q})",
                "aic":       round(float(res.aic), 4),
                "bic":       round(float(res.bic), 4),
                "all_significant": all_sig,
            })
            if res.bic < best_bic and res.aic < best_aic:
                best_bic, best_aic, best_spec = res.bic, res.aic, (p, q)
        except Exception:
            continue

    models_out.sort(key=lambda x: x["bic"])
    return models_out, best_spec[0], best_spec[1], round(best_aic, 2), round(best_bic, 2)
