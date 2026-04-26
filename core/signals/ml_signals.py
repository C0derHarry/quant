"""
core/signals/ml_signals.py
══════════════════════════════════════════════════════════════════════════════
ML-based directional signal: P(5-day up | features at t)

The core upgrade over rule-based signals:
  "RSI > 70 = sell"  →  "P(down | RSI=72, MACD=neg, ADX=25) = 0.67"
  You get a probability, not just a direction.

Pipeline
────────
1. Base features     — RSI, MACD histogram, MACD signal cross, Bollinger %B,
                       ADX, DI spread, ATR/close, 5/20/60d returns, EWMA/rolling
                       vol ratio (all computable with data ≤ t, no look-ahead)
2. Lag augmentation  — each base feature is shifted by 1, 2, 5 bars so the
                       model sees recent history, not just today's snapshot
3. Target            — sign of forward 5-day return (1 = up, 0 = down)
                       constructed via shift(-5), dropped from feature matrix
4. Chronological split — last 20% of sorted dates as test set, NO shuffling
5. Model             — GradientBoostingClassifier wrapped in
                       CalibratedClassifierCV (isotonic regression) so
                       predict_proba produces true probabilities, not just ranks
6. Evaluation        — log-loss, Brier score, ROC-AUC, accuracy + base rate

Leakage checklist (all boxes ticked)
─────────────────────────────────────
  ✅ All indicators use only past + current data (rolling, ewm with min_periods)
  ✅ EWMA variance update: var[t] = λ·var[t-1] + (1-λ)·r[t]²
     r[t] = close[t]/close[t-1]-1 is observable at t
  ✅ Target = fwd_ret.shift(-5); last 5 rows → NaN → dropped before training
  ✅ Train / test split is purely chronological (iloc, never shuffle)
  ✅ Calibration CV uses 5-fold within the training block only
══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import warnings
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import (
    brier_score_loss,
    classification_report,
    log_loss,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

from core.signals.technical_indicators import ADX, ATR, MACD, RSI, Boll_Bands


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

FORWARD_HORIZON    = 5          # trading days ahead to predict
TEST_FRACTION      = 0.20       # last 20 % of bars held out as test set
LAG_DAYS           = [1, 2, 5]  # lags applied to every base feature
EWMA_LAMBDA        = 0.94       # RiskMetrics daily decay factor
ROLLING_VOL_WINDOW = 252        # denominator window for vol-ratio feature


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — FEATURE ENGINEERING
# ─────────────────────────────────────────────────────────────────────────────

def _ewma_vol(returns: pd.Series, lam: float = EWMA_LAMBDA) -> pd.Series:
    """
    Recursive EWMA annualised daily volatility — no look-ahead.

    Update rule:  var[t] = λ·var[t-1] + (1-λ)·r[t]²

    r[t] = close[t]/close[t-1]-1 is observable at t, so this is safe.
    Seed variance uses the first 21 return values (NaN filled to 0).
    """
    r = returns.fillna(0).values.astype(float)
    n = len(r)
    var = np.empty(n)

    warmup = min(21, n)
    var[0] = np.var(r[:warmup], ddof=0) if warmup > 1 else r[0] ** 2

    alpha = 1.0 - lam
    for t in range(1, n):
        var[t] = lam * var[t - 1] + alpha * r[t] ** 2

    return pd.Series(np.sqrt(var) * np.sqrt(252), index=returns.index, name="ewma_vol_ann")


def build_base_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Construct all base features at time t using only data ≤ t.

    Returns
    ───────
    DataFrame with columns:
      rsi          — 14-period RSI
      macd_hist    — MACD line minus signal line
      macd_cross   — +1 bullish cross, -1 bearish cross, 0 no cross
      pct_b        — Bollinger %B  (position within bands, 0–1 typically)
      adx          — 14-period Average Directional Index (trend strength)
      di_spread    — +DI minus -DI (directional bias)
      atr_ratio    — ATR / Close (normalised intraday volatility)
      ret_5d       — 5-day backward return
      ret_20d      — 20-day backward return
      ret_60d      — 60-day backward return
      vol_ratio    — EWMA annualised vol / 252-day rolling vol
                     > 1 → vol above long-run average (elevated risk)
    """
    df    = df.copy()
    close = df["Close"]
    rets  = close.pct_change()
    feat  = pd.DataFrame(index=df.index)

    # ── RSI ───────────────────────────────────────────────────────────────────
    feat["rsi"] = RSI(df, period=14)["RSI"]

    # ── MACD histogram + cross signal ────────────────────────────────────────
    macd_df          = MACD(df)                                  # ['MACD','Signal']
    feat["macd_hist"]  = macd_df["MACD"] - macd_df["Signal"]
    hist_sign          = np.sign(feat["macd_hist"])
    # diff of sign: +2 on bullish cross, -2 on bearish → clip to ±1
    feat["macd_cross"] = hist_sign.diff().fillna(0).clip(-1, 1).astype(int)

    # ── Bollinger %B = (Close - Lower) / (Upper - Lower) ─────────────────────
    bb_df      = Boll_Bands(df, period=20, num_std_dev=2)        # ['Upper','Lower','Bandwidth']
    band_range = bb_df["Upper Band"] - bb_df["Lower Band"]
    feat["pct_b"] = (close - bb_df["Lower Band"]) / band_range.replace(0.0, np.nan)

    # ── ADX + directional bias ────────────────────────────────────────────────
    adx_df             = ADX(df, period=14)                      # ['ADX','+DI','-DI']
    feat["adx"]        = adx_df["ADX"]
    feat["di_spread"]  = adx_df["+DI"] - adx_df["-DI"]

    # ── ATR / Close — normalised volatility ──────────────────────────────────
    feat["atr_ratio"] = ATR(df, period=14)["ATR"] / close

    # ── Momentum returns (backward, no leakage) ───────────────────────────────
    feat["ret_5d"]  = close.pct_change(5)
    feat["ret_20d"] = close.pct_change(20)
    feat["ret_60d"] = close.pct_change(60)

    # ── Vol regime: EWMA vol / long-run rolling vol ───────────────────────────
    ewma       = _ewma_vol(rets)
    roll_vol   = rets.rolling(ROLLING_VOL_WINDOW).std() * np.sqrt(252)
    feat["vol_ratio"] = ewma / roll_vol.replace(0.0, np.nan)

    return feat


def add_lag_features(feat: pd.DataFrame, lags: list[int] = LAG_DAYS) -> pd.DataFrame:
    """
    Append t-lag versions of every base feature.

    Shift by +lag means we look at the value from lag bars ago — always
    in the past, never the future.  The model therefore sees the current
    state AND how it evolved over recent history.

    Example: rsi_lag1 at t = rsi at t-1
    """
    base_cols = feat.columns.tolist()
    parts     = [feat]
    for lag in lags:
        shifted              = feat[base_cols].shift(lag)
        shifted.columns      = [f"{c}_lag{lag}" for c in base_cols]
        parts.append(shifted)
    return pd.concat(parts, axis=1)


def build_target(df: pd.DataFrame, horizon: int = FORWARD_HORIZON) -> pd.Series:
    """
    Binary classification target: 1 if close[t + horizon] > close[t].

    Construction is leakage-free because:
      (a) this column is ONLY used as y — never as a feature
      (b) rows where the target is NaN (last `horizon` bars) are
          dropped in prepare_dataset() before any model sees them
    """
    fwd_ret = df["Close"].pct_change(horizon).shift(-horizon)
    return (fwd_ret > 0).astype(float).rename("target")


def prepare_dataset(
    df: pd.DataFrame,
    lags: list[int] = LAG_DAYS,
    horizon: int    = FORWARD_HORIZON,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Full feature-build pipeline: raw OHLCV → (X, y) with no NaN rows.

    Rows are dropped where any indicator hasn't warmed up yet (early bars)
    or where the forward target is unknown (last `horizon` bars).
    Index order is preserved — no shuffling.
    """
    feat   = build_base_features(df)
    feat   = add_lag_features(feat, lags)
    target = build_target(df, horizon)

    combined = pd.concat([feat, target], axis=1).dropna()
    X = combined.drop(columns=["target"])
    y = combined["target"].astype(int)
    return X, y


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — CHRONOLOGICAL TRAIN / TEST SPLIT
# ─────────────────────────────────────────────────────────────────────────────

def chrono_split(
    X: pd.DataFrame,
    y: pd.Series,
    test_frac: float = TEST_FRACTION,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """
    Strict chronological split.

    Train = first (1 - test_frac) bars  [earliest dates]
    Test  = last  test_frac bars        [most recent dates]

    Never shuffle.  Never use any random state here.
    """
    n     = len(X)
    split = int(n * (1.0 - test_frac))
    return (
        X.iloc[:split],
        X.iloc[split:],
        y.iloc[:split],
        y.iloc[split:],
    )


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — MODEL CONSTRUCTION
# ─────────────────────────────────────────────────────────────────────────────

def build_model(
    n_estimators:  int   = 400,
    max_depth:     int   = 4,
    learning_rate: float = 0.04,
    subsample:     float = 0.80,
    calibration:   str   = "isotonic",
) -> Pipeline:
    """
    Build a calibrated Gradient Boosting classifier.

    Why calibration?
    ────────────────
    Raw GBM probabilities are well *ranked* (high AUC) but poorly
    *calibrated* — they cluster near 0 and 1 rather than reflecting
    true likelihoods.  CalibratedClassifierCV fits an isotonic regression
    (or Platt sigmoid) on cross-validation folds of the training set to
    map raw scores → reliable probabilities.

    After calibration, P(up) = 0.67 genuinely means that across all bars
    where the model outputs ~0.67, roughly 67 % resulted in a 5-day gain.

    Hyper-parameter notes
    ─────────────────────
    max_depth=4         — shallow trees reduce overfitting on noisy returns
    subsample=0.80      — stochastic boosting, improves generalisation
    min_samples_leaf=20 — at least 20 bars per leaf prevents tiny splits
    StandardScaler      — no-op for trees but enables future model swaps
                          (e.g., drop-in logistic regression comparison)
    """
    base_gbm = GradientBoostingClassifier(
        n_estimators     = n_estimators,
        max_depth        = max_depth,
        learning_rate    = learning_rate,
        subsample        = subsample,
        min_samples_leaf = 20,
        max_features     = "sqrt",    # further variance reduction
        random_state     = 42,
    )
    calibrated = CalibratedClassifierCV(
        estimator = base_gbm,
        method    = calibration,      # "isotonic" or "sigmoid"
        cv        = 5,                # 5-fold CV within the training block
    )
    return Pipeline([
        ("scaler", StandardScaler()),
        ("clf",    calibrated),
    ])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 — EVALUATION
# ─────────────────────────────────────────────────────────────────────────────

def evaluate(
    model:   Pipeline,
    X_test:  pd.DataFrame,
    y_test:  pd.Series,
    verbose: bool = True,
) -> dict:
    """
    Compute and (optionally) print a full evaluation summary.

    Metrics
    ───────
    log_loss  — probabilistic loss; random classifier ≈ ln(2) ≈ 0.693
    brier     — MSE of proba; random classifier ≈ 0.25
    roc_auc   — ranking quality; 0.5 = random, 1.0 = perfect
    accuracy  — directional accuracy at 0.5 threshold
    pos_rate  — base rate (fraction of up-days in test set)

    A model is useful when:
      log_loss  < ln(2)   (beats random)
      brier     < 0.25    (beats random)
      roc_auc   > 0.55    (some discrimination)
    """
    proba = model.predict_proba(X_test)[:, 1]
    preds = (proba >= 0.5).astype(int)

    metrics = {
        "log_loss":  round(log_loss(y_test, proba),         4),
        "brier":     round(brier_score_loss(y_test, proba), 4),
        "roc_auc":   round(roc_auc_score(y_test, proba),    4),
        "accuracy":  round((preds == y_test).mean(),        4),
        "n_test":    int(len(y_test)),
        "pos_rate":  round(float(y_test.mean()),            4),
    }

    if verbose:
        div = "=" * 55
        print(f"\n{div}")
        print("  ML SIGNAL MODEL — TEST-SET EVALUATION")
        print(div)
        print(f"  Test bars          : {metrics['n_test']}")
        print(f"  Base rate (% up)   : {metrics['pos_rate']:.2%}")
        print(f"  Accuracy (≥0.50)   : {metrics['accuracy']:.2%}")
        print(f"  ROC-AUC            : {metrics['roc_auc']:.4f}  "
              f"(random = 0.50)")
        print(f"  Log-Loss           : {metrics['log_loss']:.4f}  "
              f"(random ≈ {np.log(2):.4f})")
        print(f"  Brier Score        : {metrics['brier']:.4f}  "
              f"(random ≈ 0.2500)")
        print(div)
        print(classification_report(
            y_test, preds,
            target_names=["Down (0)", "Up (1)"],
        ))

    return metrics


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5 — MLSignalModel: THE PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

class MLSignalModel:
    """
    End-to-end ML directional signal model.

    Quick-start
    ───────────
    model   = MLSignalModel()
    metrics = model.fit(df)                    # df: OHLCV DataFrame
    proba   = model.predict_proba(df)          # pd.Series of P(5d-up)
    signals = model.signal(df, long_threshold=0.60, short_threshold=0.40)
    fi      = model.feature_importance(top_n=15)

    signal() returns a DataFrame with columns:
      p_up    — calibrated P(5-day up move) ∈ [0, 1]
      signal  — +1 (Long) | 0 (Flat) | -1 (Short)
      regime  — "Long" | "Flat" | "Short"

    Thresholds
    ──────────
    long_threshold  = 0.60 → enter long when model is at least 60 % confident
    short_threshold = 0.40 → enter short when confidence in up-move < 40 %
    The 0.40–0.60 band is the "uncertain / flat" zone.

    Interpretation example
    ──────────────────────
    p_up = 0.72, signal = +1
      "Given RSI=54, MACD turning positive, ADX=32, vol_ratio=1.2,
       this setup has historically produced a 5-day gain 72 % of the time."
    """

    def __init__(
        self,
        forward_horizon: int   = FORWARD_HORIZON,
        test_frac:       float = TEST_FRACTION,
        lags:            list  = None,
        n_estimators:    int   = 400,
        max_depth:       int   = 4,
        learning_rate:   float = 0.04,
        subsample:       float = 0.80,
        calibration:     str   = "isotonic",
    ):
        self.forward_horizon = forward_horizon
        self.test_frac       = test_frac
        self.lags            = lags if lags is not None else LAG_DAYS
        self.n_estimators    = n_estimators
        self.max_depth       = max_depth
        self.learning_rate   = learning_rate
        self.subsample       = subsample
        self.calibration     = calibration

        self._model:        Optional[Pipeline] = None
        self._feature_cols: list[str]          = []
        self._train_end:    Optional[pd.Timestamp] = None
        self._metrics:      dict               = {}

    # ── fit ──────────────────────────────────────────────────────────────────
    def fit(self, df: pd.DataFrame, verbose: bool = True) -> dict:
        """
        Build features → chronological split → train → evaluate.

        Parameters
        ──────────
        df      : OHLCV DataFrame (must have Open, High, Low, Close, Volume)
        verbose : print progress and evaluation summary

        Returns
        ───────
        dict with test-set metrics: log_loss, brier, roc_auc, accuracy, …
        """
        X, y = prepare_dataset(df, lags=self.lags, horizon=self.forward_horizon)

        X_tr, X_te, y_tr, y_te = chrono_split(X, y, self.test_frac)

        self._feature_cols = X.columns.tolist()
        self._train_end    = X_tr.index[-1]

        if verbose:
            print(f"\nFeature matrix  : {X.shape[0]} bars × {X.shape[1]} features")
            print(f"Train window    : {X_tr.index[0].date()} → {X_tr.index[-1].date()} "
                  f"({len(X_tr)} bars)")
            print(f"Test window     : {X_te.index[0].date()} → {X_te.index[-1].date()} "
                  f"({len(X_te)} bars)")
            print(f"Training model  : GBM({self.n_estimators} trees, "
                  f"depth={self.max_depth}) + isotonic calibration …")

        self._model = build_model(
            n_estimators  = self.n_estimators,
            max_depth     = self.max_depth,
            learning_rate = self.learning_rate,
            subsample     = self.subsample,
            calibration   = self.calibration,
        )
        self._model.fit(X_tr, y_tr)

        self._test_proba = self._model.predict_proba(X_te)[:, 1]
        self._y_test     = y_te

        self._metrics = evaluate(self._model, X_te, y_te, verbose=verbose)
        return self._metrics

    # ── predict_proba ─────────────────────────────────────────────────────────
    def predict_proba(self, df: pd.DataFrame) -> pd.Series:
        """
        Return P(5-day up) for each bar where all features are available.

        Rows with insufficient indicator history (NaN features) are silently
        dropped; the returned Series index aligns with those clean rows.

        The model never sees the target column — predict_proba operates
        purely on features.
        """
        self._check_fitted()

        feat = build_base_features(df)
        feat = add_lag_features(feat, self.lags)
        feat = feat.dropna()
        # Enforce the exact column order the model was trained on
        feat = feat[self._feature_cols]

        proba = self._model.predict_proba(feat)[:, 1]
        return pd.Series(proba, index=feat.index, name="p_up")

    # ── signal ────────────────────────────────────────────────────────────────
    def signal(
        self,
        df:              pd.DataFrame,
        long_threshold:  float = 0.60,
        short_threshold: float = 0.40,
    ) -> pd.DataFrame:
        """
        Convert calibrated probabilities to a three-way directional signal.

        Signal rules
        ────────────
          p_up ≥ long_threshold   → +1  Long
          p_up ≤ short_threshold  → -1  Short
          otherwise               →  0  Flat  (uncertainty band)

        Parameters
        ──────────
        long_threshold  : minimum P(up) to go long  (default 0.60)
        short_threshold : maximum P(up) to go short (default 0.40)

        Returns
        ───────
        DataFrame[p_up, signal, regime]
        """
        p = self.predict_proba(df)

        sig = pd.Series(0, index=p.index, dtype=int, name="signal")
        sig[p >= long_threshold]  =  1
        sig[p <= short_threshold] = -1

        regime = sig.map({1: "Long", 0: "Flat", -1: "Short"}).rename("regime")

        return pd.DataFrame({"p_up": p, "signal": sig, "regime": regime})

    # ── feature_importance ────────────────────────────────────────────────────
    def feature_importance(self, top_n: int = 20) -> pd.Series:
        """
        Mean impurity-decrease feature importance, averaged across the
        calibration CV folds.

        Returns a Series sorted descending — highest-impact features first.
        """
        self._check_fitted()

        clf_step = self._model.named_steps["clf"]
        ccs      = clf_step.calibrated_classifiers_      # list of CV fold models

        importances = np.zeros(len(self._feature_cols))
        for cc in ccs:
            # sklearn >= 1.2: attribute is `.estimator`; older: `.base_estimator`
            gbm = getattr(cc, "estimator", getattr(cc, "base_estimator", None))
            if gbm is not None:
                importances += gbm.feature_importances_
        importances /= max(len(ccs), 1)

        fi = pd.Series(importances, index=self._feature_cols, name="importance")
        return fi.sort_values(ascending=False).head(top_n)

    # ── signal_at_latest_bar ──────────────────────────────────────────────────
    def latest_signal(self, df: pd.DataFrame) -> dict:
        """
        Return a human-readable summary of the signal at the most recent bar.

        Useful for live use: model.latest_signal(df) prints the current
        probability and recommended position.
        """
        self._check_fitted()
        sig_df = self.signal(df)
        last   = sig_df.iloc[-1]
        date   = sig_df.index[-1]

        return {
            "date":   date,
            "p_up":   round(float(last["p_up"]), 4),
            "signal": int(last["signal"]),
            "regime": last["regime"],
        }

    # ── properties ───────────────────────────────────────────────────────────
    @property
    def metrics(self) -> dict:
        """Test-set evaluation metrics from the last fit() call."""
        return self._metrics

    @property
    def feature_cols(self) -> list[str]:
        """Ordered list of feature names the model was trained on."""
        return self._feature_cols.copy()

    @property
    def train_end(self) -> Optional[pd.Timestamp]:
        """Last date in the training set (test begins the next bar)."""
        return self._train_end

    # ── internal ─────────────────────────────────────────────────────────────
    def _check_fitted(self) -> None:
        if self._model is None:
            raise RuntimeError(
                "Model is not fitted. Call .fit(df) with an OHLCV DataFrame first."
            )


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6 — CONVENIENCE FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def run_ml_signal(
    df:              pd.DataFrame,
    long_threshold:  float = 0.60,
    short_threshold: float = 0.40,
    verbose:         bool  = True,
) -> tuple[MLSignalModel, pd.DataFrame]:
    """
    One-shot: fit a model and return the fitted model + signal DataFrame.

    Parameters
    ──────────
    df              : OHLCV DataFrame (Close + High + Low required)
    long_threshold  : P(up) threshold to generate a +1 long signal
    short_threshold : P(up) threshold below which a -1 short signal fires
    verbose         : print training progress and evaluation summary

    Returns
    ───────
    (model, signals_df)
      model       : fitted MLSignalModel (reuse for .predict_proba on new data)
      signals_df  : DataFrame[p_up, signal, regime] aligned to df.index
    """
    model = MLSignalModel()
    model.fit(df, verbose=verbose)
    signals = model.signal(df, long_threshold, short_threshold)

    if verbose:
        print("\n── Feature Importance (top 12) ──────────────────────────")
        fi = model.feature_importance(top_n=12)
        for feat, imp in fi.items():
            bar = "█" * int(imp * 400)
            print(f"  {feat:<30} {imp:.4f}  {bar}")

        last = model.latest_signal(df)
        regime_color = {"Long": "↑", "Short": "↓", "Flat": "→"}
        print(f"\n── Latest Signal ────────────────────────────────────────")
        print(f"  Date     : {last['date'].date()}")
        print(f"  P(up)    : {last['p_up']:.2%}")
        print(f"  Signal   : {last['signal']:+d}  "
              f"{regime_color.get(last['regime'], '')} {last['regime']}")

        # Distribution of signals over test period
        test_start  = model.train_end
        test_signals = signals[signals.index > test_start]
        counts = test_signals["regime"].value_counts()
        total  = len(test_signals)
        print(f"\n── Signal distribution (test period) ───────────────────")
        for reg in ["Long", "Flat", "Short"]:
            n   = counts.get(reg, 0)
            pct = n / total * 100 if total > 0 else 0
            bar = "█" * int(pct / 2)
            print(f"  {reg:<6} {n:>4}  ({pct:4.1f}%)  {bar}")

    return model, signals