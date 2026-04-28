import warnings
import numpy as np
import pandas as pd
import yfinance as yf
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from hmmlearn.hmm import GaussianHMM

warnings.filterwarnings("ignore")
router = APIRouter()


def _safe(v):
    if isinstance(v, (np.integer,)):   return int(v)
    if isinstance(v, np.floating):     return None if np.isnan(v) or np.isinf(v) else float(v)
    if isinstance(v, float) and (np.isnan(v) or np.isinf(v)): return 0.0
    if isinstance(v, np.ndarray):      return v.tolist()
    if isinstance(v, pd.DataFrame):    return v.fillna(0).to_dict(orient="records")
    if isinstance(v, dict):            return {k: _safe(vv) for k, vv in v.items()}
    if isinstance(v, list):            return [_safe(i) for i in v]
    return v


# ── Request models ────────────────────────────────────────────────────────────

class BacktestRequest(BaseModel):
    tickers:       list[str]
    weights:       dict[str, float]
    train_months:  int   = 6
    test_months:   int   = 1
    n_windows:     int   = 12
    cost_bps:      int   = 10
    atr_stop_mult: float = 2.0
    use_ml:        bool  = True
    use_regimes:   bool  = True


class SensitivityRequest(BaseModel):
    tickers: list[str]
    weights: dict[str, float]
    period:  str = "2y"


# ── Walk-forward backtest ─────────────────────────────────────────────────────

@router.post("/run")
def run_backtest_endpoint(req: BacktestRequest):
    try:
        from core.backtesting.walk_forward import walk_forward
        tickers = [t if t.startswith("^") or "." in t else f"{t}.NS" for t in req.tickers]
        weights = {
            (k if k.startswith("^") or "." in k else f"{k}.NS"): v
            for k, v in req.weights.items()
        }
        result = walk_forward(
            tickers       = tickers,
            train_months  = req.train_months,
            test_months   = req.test_months,
            n_windows     = req.n_windows,
            cost_bps      = req.cost_bps,
            atr_stop_mult = req.atr_stop_mult,
            use_ml        = req.use_ml,
            use_regimes   = req.use_regimes,
        )
        return _safe(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Sensitivity grid ──────────────────────────────────────────────────────────

@router.post("/sensitivity")
def sensitivity_endpoint(req: SensitivityRequest):
    try:
        from core.backtesting.sensitivity import sensitivity_grid
        tickers = [t if t.startswith("^") or "." in t else f"{t}.NS" for t in req.tickers]
        weights = {
            (k if k.startswith("^") or "." in k else f"{k}.NS"): v
            for k, v in req.weights.items()
        }
        result = sensitivity_grid(tickers, weights, period=req.period)
        return _safe(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Regime detection ──────────────────────────────────────────────────────────

def _min_duration(labels: list, min_days: int = 5) -> list:
    """Merge any stint shorter than min_days into the preceding state."""
    n = len(labels)
    changed = True
    while changed:
        changed = False
        i = 0
        while i < n:
            j = i
            while j < n and labels[j] == labels[i]:
                j += 1
            if (j - i) < min_days:
                repl = labels[i - 1] if i > 0 else (labels[j] if j < n else labels[i])
                for k in range(i, j):
                    labels[k] = repl
                changed = True
                break
            i = j
    return labels


def _run_hmm(returns: np.ndarray, n_states: int = 3, ema_span: int = 10):
    """Run GaussianHMM with Viterbi decoding. Returns (labels, probs, transmat, state_means)."""
    ret_s    = pd.Series(returns)
    roll_vol = ret_s.rolling(5).std().bfill().values
    roll_5d  = ret_s.rolling(5).mean().bfill().values   # short-term trend
    roll_20d = ret_s.rolling(20).mean().bfill().values  # medium-term trend
    features = np.column_stack([returns, roll_vol, roll_5d, roll_20d])

    # Sticky init: bias toward persistent regimes so EM learns slow-transitioning states
    transmat_init = np.full((n_states, n_states), (1.0 - 0.97) / (n_states - 1))
    np.fill_diagonal(transmat_init, 0.97)

    model = GaussianHMM(n_components=n_states, covariance_type="diag",
                        n_iter=2000, tol=1e-5, random_state=42,
                        params="stmc", init_params="smc")  # keep our transmat init
    model.transmat_ = transmat_init
    model.fit(features)

    # Viterbi hard labels + enforce minimum 5-day stints
    hard_raw = list(model.predict(features))
    hard     = np.array(_min_duration(hard_raw, min_days=5))

    # EMA-smoothed posteriors — used only for the probability display columns
    state_probs = model.predict_proba(features)
    smooth = pd.DataFrame(state_probs).ewm(span=ema_span, adjust=False).mean().values

    # Compute per-state statistics
    state_ret = {}
    state_vol = {}
    for s in range(n_states):
        m = hard == s
        state_ret[s] = returns[m].mean() if m.sum() > 0 else 0.0
        state_vol[s] = returns[m].std()  if m.sum() > 0 else 1e-6

    # Sort by total cumulative log return per state.
    # Captures both per-day return AND duration, so the sustained uptrend always
    # outscores short volatile bursts, and ghost states (0 days, sum=0) fall to Bear.
    sorted_s = sorted(range(n_states), key=lambda s: float(returns[hard == s].sum()))
    label_map = {sorted_s[0]: "Bear", sorted_s[1]: "Sideways", sorted_s[2]: "Bull"}
    labels    = [label_map[s] for s in hard]

    # Reorder transition matrix to Bull / Bear / Sideways order
    idx_order = [sorted_s[2], sorted_s[0], sorted_s[1]]   # Bull, Bear, Sideways
    trans     = model.transmat_[np.ix_(idx_order, idx_order)]

    # Per-state probabilities aligned to Bull / Bear / Sideways columns
    prob_bull     = smooth[:, sorted_s[2]]
    prob_bear     = smooth[:, sorted_s[0]]
    prob_sideways = smooth[:, sorted_s[1]]

    state_means_named = {
        "Bull":     float(state_ret[sorted_s[2]]),
        "Bear":     float(state_ret[sorted_s[0]]),
        "Sideways": float(state_ret[sorted_s[1]]),
    }
    return labels, prob_bull, prob_bear, prob_sideways, trans, state_means_named


@router.get("/regimes")
def regimes_endpoint(tickers: str, period: str = "2y"):
    try:
        ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
        ticker_list = [t if t.startswith("^") or "." in t else f"{t}.NS" for t in ticker_list]

        raw = yf.download(ticker_list, period=period, auto_adjust=True, progress=False)["Close"]
        if isinstance(raw, pd.Series):
            raw = raw.to_frame(ticker_list[0])
        raw      = raw.dropna(how="all").ffill(limit=5).dropna()
        log_rets = np.log(raw / raw.shift(1)).dropna()

        if log_rets.empty or len(log_rets) < 30:
            raise ValueError("Insufficient data for regime detection.")

        response = {}

        for ticker in ticker_list:
            if ticker not in log_rets.columns:
                continue

            ret_vals = log_rets[ticker].values
            labels, pb, pbr, ps, trans, state_means = _run_hmm(ret_vals)

            prices = raw[ticker].reindex(log_rets.index)
            series = []
            for j, (idx, price) in enumerate(prices.items()):
                series.append({
                    "date":          idx.strftime("%Y-%m-%d"),
                    "price":         round(float(price), 2),
                    "regime":        labels[j],
                    "prob_bull":     round(float(pb[j]), 4),
                    "prob_bear":     round(float(pbr[j]), 4),
                    "prob_sideways": round(float(ps[j]), 4),
                })

            # Per-regime stats + average consecutive run length
            df_reg = pd.DataFrame({"regime": labels, "ret": ret_vals},
                                  index=log_rets.index)
            state_stats = []
            for label in ["Bull", "Bear", "Sideways"]:
                subset = df_reg[df_reg["regime"] == label]["ret"]
                # Consecutive run lengths
                run_id  = (df_reg["regime"] != df_reg["regime"].shift()).cumsum()
                groups  = df_reg.groupby(run_id)["regime"].first()
                lengths = df_reg.groupby(run_id).size()
                label_lengths = lengths[groups == label]
                avg_dur = round(float(label_lengths.mean()), 1) if not label_lengths.empty else 0.0
                state_stats.append({
                    "regime":            label,
                    "mean_return":       round(float(subset.mean() * 100), 4) if not subset.empty else 0.0,
                    "vol":               round(float(subset.std() * np.sqrt(252) * 100), 2) if not subset.empty else 0.0,
                    "avg_duration_days": avg_dur,
                })

            response[ticker] = {
                "series":            series,
                "state_stats":       state_stats,
                "transition_matrix": [[round(float(v), 4) for v in row] for row in trans],
            }

        return _safe(response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
