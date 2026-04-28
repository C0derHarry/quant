"""
Walk-forward validation.
Fits the ML model and computes Risk Parity weights on each train window,
then backtests on the next out-of-sample test window.
Only the out-of-sample equity curve is stitched together.
"""

import os
import warnings
import numpy as np
import pandas as pd
import yfinance as yf
from dateutil.relativedelta import relativedelta
from datetime import date

warnings.filterwarnings("ignore")


def _load_or_fit_model(ticker: str, train_df: pd.DataFrame):
    """Use daily cache or fit fresh MLSignalModel on the given train slice."""
    import joblib
    from core.signals.ml_signals import MLSignalModel

    cache_dir = os.path.join(os.path.dirname(__file__), "..", "signal_cache")
    os.makedirs(cache_dir, exist_ok=True)
    tag  = ticker.replace(".", "_").replace("^", "")
    path = os.path.join(cache_dir, f"{tag}_{date.today().isoformat()}_wf.joblib")

    if os.path.exists(path):
        try:
            return joblib.load(path)
        except Exception:
            pass

    model = MLSignalModel()
    model.fit(train_df, verbose=False)
    try:
        joblib.dump(model, path)
    except Exception:
        pass
    return model


def _rp_weights(returns_df: pd.DataFrame, tickers: list[str]) -> dict[str, float]:
    from core.portfolio.optimization import risk_parity
    try:
        result = risk_parity(tickers, period="3y")
        return result["weights"]
    except Exception:
        n = len(tickers)
        return {t: 1 / n for t in tickers}


def walk_forward(
    tickers:       list[str],
    train_months:  int   = 6,
    test_months:   int   = 1,
    n_windows:     int   = 12,
    cost_bps:      int   = 10,
    atr_stop_mult: float = 2.0,
    use_ml:        bool  = True,
    use_regimes:   bool  = True,
) -> dict:
    from core.backtesting.engine import run_backtest
    from core.portfolio.sizing import detect_regimes

    # Download enough history for all windows
    total_months = train_months + test_months * n_windows + 3
    period_str   = f"{min(total_months // 12 + 2, 5)}y"
    raw = yf.download(tickers, period=period_str, auto_adjust=True, progress=False)["Close"]
    if isinstance(raw, pd.Series):
        raw = raw.to_frame(tickers[0])
    raw = raw.dropna(how="all").ffill(limit=5).dropna()
    if raw.empty:
        raise ValueError("No price data for walk-forward validation.")

    log_rets = np.log(raw / raw.shift(1)).dropna()
    today    = pd.Timestamp.now().normalize()

    all_equity:  list[dict] = []
    all_bench:   list[dict] = []
    window_metrics = []

    for i in range(n_windows):
        # Window dates (working backwards from today)
        test_end   = today - relativedelta(months=(n_windows - 1 - i) * test_months)
        test_start = test_end - relativedelta(months=test_months)
        train_end  = test_start
        train_start = train_end - relativedelta(months=train_months)

        train_mask = (log_rets.index >= train_start) & (log_rets.index < train_end)
        test_mask  = (log_rets.index >= test_start)  & (log_rets.index < test_end)

        train_rets = log_rets[train_mask]
        test_rets  = log_rets[test_mask]

        if len(train_rets) < 20 or len(test_rets) < 5:
            continue

        # Weights from risk parity on training data
        weights = {t: 1 / len(tickers) for t in tickers}
        try:
            from sklearn.covariance import LedoitWolf
            lw  = LedoitWolf()
            lw.fit(train_rets.values)
            cov = lw.covariance_ * 252
            mu  = train_rets.mean().values * 252
            n   = len(tickers)

            from scipy.optimize import minimize

            def _rc(w):
                pv = np.sqrt(w @ cov @ w)
                return w * (cov @ w) / (pv + 1e-9)

            def _obj(w):
                rc = _rc(w)
                d  = rc[:, None] - rc[None, :]
                return float(np.sum(d ** 2))

            res = minimize(_obj, np.ones(n) / n, method="SLSQP",
                           bounds=[(0.001, 1.0)] * n,
                           constraints=[{"type": "eq", "fun": lambda w: np.sum(w) - 1}],
                           options={"ftol": 1e-14, "maxiter": 1000})
            w = res.x / res.x.sum()
            weights = {tickers[j]: float(w[j]) for j in range(n)}
        except Exception:
            pass

        # ML signals on test window
        ml_signals_df = None
        if use_ml:
            ml_signals_df = {}
            for t in tickers:
                try:
                    train_ohlcv = yf.download(t, period=period_str, auto_adjust=True, progress=False)
                    if isinstance(train_ohlcv.columns, pd.MultiIndex):
                        train_ohlcv.columns = train_ohlcv.columns.get_level_values(0)
                    slice_train = train_ohlcv[train_ohlcv.index < train_end]
                    if len(slice_train) < 60:
                        continue
                    model    = _load_or_fit_model(t, slice_train)
                    slice_test = train_ohlcv[(train_ohlcv.index >= test_start) & (train_ohlcv.index < test_end)]
                    if slice_test.empty:
                        continue
                    p_ups = []
                    for _, row in slice_test.iterrows():
                        try:
                            sig = model.latest_signal(train_ohlcv[train_ohlcv.index <= row.name])
                            p_ups.append((row.name, sig["p_up"]))
                        except Exception:
                            pass
                    if p_ups:
                        ml_signals_df[t] = pd.Series(dict(p_ups))
                except Exception:
                    pass
            if ml_signals_df:
                ml_signals_df = pd.DataFrame(ml_signals_df)
            else:
                ml_signals_df = None

        # HMM regimes from training data applied to test
        regime_series = None
        if use_regimes:
            try:
                regime_result = detect_regimes(train_rets)
                # Use last regime label as constant for the test window
                last_regimes  = {t: v["regime"] for t, v in regime_result.items()}
                # Apply uniformly for the test window
                test_idx      = log_rets[test_mask].index
                dominant      = max(set(last_regimes.values()), key=list(last_regimes.values()).count)
                regime_series = pd.Series(dominant, index=test_idx)
            except Exception:
                pass

        # Run backtest on test window only
        try:
            result = run_backtest(
                tickers       = tickers,
                weights       = weights,
                period        = period_str,
                cost_bps      = cost_bps,
                atr_stop_mult = atr_stop_mult,
                ml_signals_df = ml_signals_df,
                regime_series = regime_series,
            )
            # Filter equity curve to test window only
            test_start_str = test_start.strftime("%Y-%m-%d")
            test_end_str   = test_end.strftime("%Y-%m-%d")
            window_curve   = [
                p for p in result["equity_curve"]
                if test_start_str <= p["date"] < test_end_str
            ]
            if window_curve:
                # Re-normalise so each window starts at 100
                base = window_curve[0]["value"]
                bbase = window_curve[0]["benchmark"]
                for p in window_curve:
                    p["value"]     = round(p["value"] / base * 100, 2)
                    p["benchmark"] = round(p["benchmark"] / bbase * 100, 2)
                all_equity.extend(window_curve)

            wm = result["metrics"]
            window_metrics.append({
                "window":      i + 1,
                "train_start": train_start.strftime("%Y-%m-%d"),
                "train_end":   train_end.strftime("%Y-%m-%d"),
                "test_start":  test_start.strftime("%Y-%m-%d"),
                "test_end":    test_end.strftime("%Y-%m-%d"),
                "sharpe":      wm["sharpe"],
                "return":      wm["total_return"],
                "max_drawdown": wm["max_drawdown"],
            })
        except Exception as e:
            print(f"Walk-forward window {i+1} failed: {e}")
            continue

    if not all_equity:
        raise ValueError("No walk-forward windows completed successfully.")

    # Stitch equity curve: chain each window starting from previous end value
    stitched   = []
    carry      = 100.0
    bench_carry = 100.0
    prev_val   = None
    for p in all_equity:
        if prev_val is None:
            carry      = 100.0
            bench_carry = 100.0
        else:
            carry       = carry * (p["value"] / 100.0)
            bench_carry = bench_carry * (p["benchmark"] / 100.0)
        stitched.append({
            "date":      p["date"],
            "value":     round(carry, 2),
            "benchmark": round(bench_carry, 2),
        })
        prev_val = p["value"]

    # Aggregate metrics
    sharpes       = [w["sharpe"] for w in window_metrics]
    returns       = [w["return"] for w in window_metrics]
    drawdowns     = [w["max_drawdown"] for w in window_metrics]
    avg_sharpe    = round(float(np.mean(sharpes)), 3) if sharpes else 0.0
    total_ret_oos = round(float(stitched[-1]["value"] / 100 - 1) * 100, 2) if stitched else 0.0
    max_dd_oos    = round(float(min(drawdowns)), 2) if drawdowns else 0.0
    bench_oos     = round(float(stitched[-1]["benchmark"] / 100 - 1) * 100, 2) if stitched else 0.0

    # Degradation: linear slope of Sharpe over windows (negative = getting worse)
    degrad_slope = 0.0
    if len(sharpes) >= 3:
        x = np.arange(len(sharpes), dtype=float)
        degrad_slope = round(float(np.polyfit(x, sharpes, 1)[0]), 4)

    return {
        "equity_curve":     stitched,
        "window_metrics":   window_metrics,
        "aggregate": {
            "sharpe":        avg_sharpe,
            "annual_return": total_ret_oos,
            "max_drawdown":  max_dd_oos,
            "calmar":        round(total_ret_oos / abs(max_dd_oos), 3) if max_dd_oos != 0 else 0.0,
            "alpha":         round(total_ret_oos - bench_oos, 2),
        },
        "degradation_slope": degrad_slope,
    }
