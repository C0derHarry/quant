"""
Pillar configuration: weights and verdict templates.
All thresholds / scoring bands live in normalize.py.
"""

# ── Pillar weights (model_key -> weight within its pillar) ────────────────────
# Weights renormalize over available (ok/partial) models at runtime.

RISK_WEIGHTS: dict[str, float] = {
    "annual_vol":   1.2,  # most intuitive risk metric for retail
    "max_drawdown": 1.5,  # worst-case loss — highest weight
    "sharpe":       1.5,  # reward per unit risk
    "sortino":      1.0,  # downside-only risk
    "beta":         0.8,  # market sensitivity
    "ewma_var":     1.0,  # M2: real-time EWMA volatility (premium)
}

MOMENTUM_WEIGHTS: dict[str, float] = {
    "tech_composite":  1.0,   # M1: technical indicator composite
    "ml_pup":          1.2,   # M2: calibrated ML P(5-day up) (premium)
    "return_52wk":     1.0,   # M3: 52-week price momentum (free)
    "dual_momentum":   1.1,   # M4: absolute + relative momentum (premium)
    "kelly":           0.8,   # M4: Kelly Criterion edge signal (premium)
}

VALUE_WEIGHTS: dict[str, float] = {
    "earnings_yield": 1.2,   # M2: Magic Formula EY (EBIT/EV)
    "roc":            1.0,   # M2: Magic Formula ROC (EBIT/Invested Capital)
    "pe":             1.0,   # M2: trailing P/E from info
    "pb":             0.8,   # M2: price-to-book
    "ev_sales":       0.7,   # M2: EV/Sales
    "ev_ebitda":      0.9,   # M3: EV/EBITDA (non-financial only)
    "graham":         1.0,   # M3: Graham Number margin of safety
    "peg":            0.8,   # M3: PEG ratio
    "dcf":            1.5,   # M4: DCF intrinsic value — highest weight (premium)
    "epv":            1.0,   # M4: Earnings Power Value, no-growth (premium)
    "ri_model":       0.8,   # M4: Residual Income model (premium)
}

QUALITY_WEIGHTS: dict[str, float] = {
    "roe":          1.2,   # M2: Return on Equity
    "de_ratio":     0.8,   # M2: Debt/Equity leverage
    "roce":         0.9,   # M3: Return on Capital Employed
    "gross_margin": 0.7,   # M3: Gross Margin (non-financial only)
    "piotroski":    1.2,   # M3: Piotroski F-Score (non-financial only)
    "revenue_cagr": 0.7,   # M3: multi-year revenue growth
    "roic":         1.0,   # M4: Return on Invested Capital (premium)
    "altman_z":     1.2,   # M4: Altman Z-Score financial distress (premium)
    "beneish":      0.8,   # M4: Beneish M-Score earnings quality (premium)
}


# ── Verdict templates (pillar, grade) -> one-line retail-friendly string ──────
# Wording reviewed against spec §4: no buy/sell/target/guaranteed/recommended.

VERDICTS: dict[tuple[str, str], str] = {
    # Risk
    ("risk", "A"):   "Historically stable returns with controlled drawdowns.",
    ("risk", "B"):   "Moderate risk profile; drawdowns and volatility within acceptable ranges.",
    ("risk", "C"):   "Mixed risk signals — volatility and drawdown are worth monitoring.",
    ("risk", "D"):   "Elevated historical volatility and drawdown relative to benchmarks.",
    ("risk", "F"):   "High volatility and significant historical drawdowns; risk metrics suggest elevated uncertainty.",
    ("risk", "N/A"): "Insufficient price history to grade this pillar.",
    # Momentum
    ("momentum", "A"):   "Technical indicators broadly aligned; strong historical momentum signal.",
    ("momentum", "B"):   "Most technical indicators showing positive momentum.",
    ("momentum", "C"):   "Mixed technical signals — no clear directional momentum.",
    ("momentum", "D"):   "Most technical indicators showing negative momentum.",
    ("momentum", "F"):   "Technical indicators broadly negative; sustained downward momentum pattern.",
    ("momentum", "N/A"): "Insufficient data to compute technical indicators.",
    # Value (M3+)
    ("value", "A"):   "Appears attractively valued across multiple model estimates relative to peers.",
    ("value", "B"):   "Trades at a modest discount on several model estimates.",
    ("value", "C"):   "Fairly valued on most model estimates relative to peers.",
    ("value", "D"):   "Appears moderately expensive on most model estimates.",
    ("value", "F"):   "Appears richly valued across most model estimates; limited model-estimated margin of safety.",
    ("value", "N/A"): "Fundamental data not yet available for this pillar.",
    # Quality (M3+)
    ("quality", "A"):   "Strong model-estimated profitability and balance-sheet health.",
    ("quality", "B"):   "Good profitability metrics with a sound balance sheet.",
    ("quality", "C"):   "Average quality metrics — some strengths, some areas to monitor.",
    ("quality", "D"):   "Weak profitability or elevated balance-sheet risk on model estimates.",
    ("quality", "F"):   "Poor model-estimated quality; weak profitability and/or high financial risk.",
    ("quality", "N/A"): "Fundamental data not yet available for this pillar.",
}

PILLAR_ORDER = ["value", "quality", "momentum", "risk"]
PILLAR_LABELS = {
    "value":    "Value",
    "quality":  "Quality",
    "momentum": "Momentum",
    "risk":     "Risk",
}
