from typing import Optional


def score_band(value: float, bands: list[tuple[float, float]]) -> float:
    """
    Piecewise linear scoring between breakpoints.
    bands: sorted list of (threshold, score) pairs.
    Clamps to the first/last score for values outside the range.
    """
    if not bands:
        return 50.0
    if value <= bands[0][0]:
        return float(bands[0][1])
    if value >= bands[-1][0]:
        return float(bands[-1][1])
    for i in range(len(bands) - 1):
        lo_v, lo_s = bands[i]
        hi_v, hi_s = bands[i + 1]
        if lo_v <= value <= hi_v:
            t = (value - lo_v) / (hi_v - lo_v)
            return lo_s + t * (hi_s - lo_s)
    return float(bands[-1][1])


def to_letter(score: Optional[float]) -> str:
    """Convert 0–100 score to A–F letter grade."""
    if score is None:
        return "N/A"
    if score >= 80:
        return "A"
    if score >= 65:
        return "B"
    if score >= 50:
        return "C"
    if score >= 35:
        return "D"
    return "F"


# ── India-tuned scoring bands ─────────────────────────────────────────────────

# Annual volatility as percentage — lower is better
# Indian large-caps typically run 14–22%; Nifty ~16–18%
VOL_BANDS = [
    (0.0,  92),
    (10.0, 80),
    (15.0, 68),
    (20.0, 52),
    (25.0, 36),
    (32.0, 18),
    (45.0,  5),
]

# Maximum drawdown as positive percentage — lower is better
MDD_BANDS = [
    (0.0,  95),
    (5.0,  82),
    (10.0, 68),
    (20.0, 50),
    (30.0, 32),
    (40.0, 18),
    (60.0,  5),
]

# Sharpe ratio (rf = 7%) — higher is better
# Indian market Sharpe historically ~0.3–0.8; good stock > 1.0
SHARPE_BANDS = [
    (-2.0,  0),
    (-0.5,  8),
    (0.0,  22),
    (0.3,  36),
    (0.7,  52),
    (1.0,  68),
    (1.5,  82),
    (2.0,  94),
    (3.0, 100),
]

# Sortino ratio — higher is better (usually 20–50% above Sharpe)
SORTINO_BANDS = [
    (-2.0,  0),
    (-0.5,  8),
    (0.0,  22),
    (0.5,  38),
    (1.0,  52),
    (1.5,  66),
    (2.0,  80),
    (3.0,  92),
    (4.0, 100),
]

# Beta — lower market sensitivity is better for risk grading
BETA_BANDS = [
    (0.0,  88),
    (0.5,  92),
    (0.8,  82),
    (1.0,  70),
    (1.2,  52),
    (1.5,  32),
    (2.0,  15),
    (3.0,   5),
]

# Technical bull_ratio (0–1) — higher is better
TECH_BULL_BANDS = [
    (0.00,  5),
    (0.25, 22),
    (0.40, 40),
    (0.50, 50),
    (0.60, 60),
    (0.70, 72),
    (0.80, 85),
    (1.00, 98),
]

# ── M2 additions ──────────────────────────────────────────────────────────────

# Trailing P/E — lower is cheaper; negative PE (losses) → missing before calling
PE_BANDS = [
    (0.0,  92),
    (10.0, 82),
    (15.0, 70),
    (20.0, 57),
    (25.0, 42),
    (35.0, 25),
    (50.0,  8),
]

# Price-to-Book — lower is cheaper for value
PB_BANDS = [
    (0.0,  92),
    (1.0,  82),
    (2.0,  70),
    (3.0,  55),
    (4.0,  40),
    (6.0,  22),
    (10.0,  8),
]

# EV/Sales — lower is cheaper; sector-agnostic proxy
EV_SALES_BANDS = [
    (0.0,  92),
    (0.5,  82),
    (1.0,  70),
    (2.0,  55),
    (3.0,  40),
    (5.0,  22),
    (8.0,   8),
]

# Earnings Yield (EBIT/EV) — higher is cheaper (Magic Formula)
# India context: >10% EY is attractive; <3% EY is expensive
EY_BANDS = [
    (-0.50,  5),
    ( 0.00, 15),
    ( 0.02, 28),
    ( 0.05, 48),
    ( 0.08, 65),
    ( 0.12, 82),
    ( 0.15, 92),
    ( 0.20, 98),
]

# Return on Capital (Magic Formula EBIT/Invested Capital) — higher is better
ROC_BANDS = [
    (-0.50,  5),
    ( 0.00, 12),
    ( 0.05, 25),
    ( 0.10, 42),
    ( 0.15, 58),
    ( 0.20, 72),
    ( 0.30, 85),
    ( 0.40, 95),
]

# Return on Equity — higher is better; India blue-chips ~12–20%
ROE_BANDS = [
    (-0.50,  5),
    ( 0.00, 12),
    ( 0.08, 28),
    ( 0.12, 45),
    ( 0.15, 60),
    ( 0.20, 75),
    ( 0.25, 88),
    ( 0.35, 98),
]

# Debt/Equity ratio (decimal, not %) — lower leverage is better
# yfinance debtToEquity is in %; divide by 100 before calling
DE_BANDS = [
    (0.0,  92),
    (0.2,  82),
    (0.5,  68),
    (1.0,  50),
    (1.5,  32),
    (2.0,  18),
    (3.0,   5),
]

# ML calibrated P(5-day up) — higher is better for momentum
ML_PUP_BANDS = [
    (0.00,  5),
    (0.35, 20),
    (0.42, 38),
    (0.50, 50),
    (0.58, 65),
    (0.65, 80),
    (0.70, 92),
    (0.80, 98),
]

# EWMA current daily volatility as % — lower is better (real-time risk)
# 0.5% daily ≈ 7.9% ann.; 1.0% daily ≈ 15.9% ann.; 1.6% daily ≈ 25.4% ann.
EWMA_DAILY_VOL_BANDS = [
    (0.0,  92),
    (0.5,  82),
    (0.8,  68),
    (1.0,  55),
    (1.3,  38),
    (1.6,  22),
    (2.0,   8),
]

# ── M3 additions ──────────────────────────────────────────────────────────────

# EV/EBITDA — lower is cheaper; non-financial only
# India context: <8x cheap, 10-15x fair, >20x expensive
EV_EBITDA_BANDS = [
    ( 0.0, 95),
    ( 5.0, 88),
    ( 8.0, 75),
    (12.0, 58),
    (16.0, 40),
    (20.0, 22),
    (30.0,  8),
]

# Graham Number margin of safety (fraction) — higher is better
# MoS = (Graham Number / Price) − 1; positive = undervalued by Graham's estimate
GRAHAM_MOS_BANDS = [
    (-1.00,  5),
    (-0.50, 10),
    (-0.30, 18),
    (-0.15, 30),
    ( 0.00, 40),
    ( 0.15, 55),
    ( 0.30, 72),
    ( 0.50, 88),
    ( 0.80, 98),
]

# PEG ratio (P/E ÷ earnings growth %) — lower is better; ≤1 is the classic threshold
PEG_BANDS = [
    (0.0, 95),
    (0.5, 85),
    (0.8, 75),
    (1.0, 62),
    (1.5, 45),
    (2.0, 28),
    (3.0, 12),
    (5.0,  5),
]

# Return on Capital Employed (EBIT / Capital Employed) — higher is better
ROCE_BANDS = [
    (-0.30,  5),
    ( 0.00, 12),
    ( 0.08, 28),
    ( 0.12, 45),
    ( 0.16, 62),
    ( 0.22, 78),
    ( 0.30, 92),
    ( 0.40, 98),
]

# Gross Margin (Gross Profit / Revenue) — higher is better; non-financial only
GROSS_MARGIN_BANDS = [
    (-0.30,  5),
    ( 0.00, 12),
    ( 0.10, 28),
    ( 0.20, 45),
    ( 0.35, 62),
    ( 0.50, 78),
    ( 0.65, 92),
    ( 0.80, 98),
]

# Piotroski F-Score (0–9, scaled) — higher = stronger financial health
PIOTROSKI_BANDS = [
    (0, 5),
    (2, 18),
    (4, 38),
    (5, 52),
    (6, 68),
    (7, 82),
    (8, 92),
    (9, 98),
]

# Revenue CAGR (multi-year) — higher is better
REV_CAGR_BANDS = [
    (-0.30,  5),
    (-0.10, 15),
    ( 0.00, 25),
    ( 0.05, 40),
    ( 0.10, 58),
    ( 0.15, 72),
    ( 0.20, 85),
    ( 0.30, 95),
]

# 52-week price return (fraction) — higher = stronger medium-term momentum
RETURN_52WK_BANDS = [
    (-0.60,  5),
    (-0.30, 15),
    (-0.15, 28),
    ( 0.00, 40),
    ( 0.10, 52),
    ( 0.20, 65),
    ( 0.35, 80),
    ( 0.60, 95),
]

# ── M4 additions ──────────────────────────────────────────────────────────────

# ROIC = NOPAT / Invested Capital; WACC ≈ 12% for India → >12% = value creation
ROIC_BANDS = [
    (-0.20,  5),
    ( 0.00, 10),
    ( 0.08, 28),
    ( 0.12, 50),   # WACC threshold — above this is value creation
    ( 0.15, 62),
    ( 0.20, 75),
    ( 0.25, 88),
    ( 0.35, 98),
]

# Altman Z''-Score (emerging market variant) — higher = safer
# >2.6 = Safe zone; 1.1–2.6 = Grey zone; <1.1 = Distress zone
ALTMAN_BANDS = [
    (-2.0,  5),
    ( 0.0, 12),
    ( 1.1, 30),
    ( 1.8, 48),
    ( 2.6, 72),
    ( 3.5, 88),
    ( 5.0, 98),
]

# Beneish M-Score — lower is safer (less likely manipulation)
# M < -1.78 = unlikely manipulator; M > -1.78 = flag
BENEISH_BANDS = [
    (-3.5, 98),
    (-2.5, 85),
    (-2.0, 72),
    (-1.78, 55),   # Beneish (1999) threshold
    (-1.50, 38),
    (-1.00, 20),
    ( 0.00,  8),
    ( 1.00,  2),
]

# Dual Momentum signals (0 = neither, 1 = one, 2 = both abs+rel positive)
DUAL_MOMENTUM_BANDS = [
    (0.0, 20),
    (1.0, 60),
    (2.0, 95),
]

# Kelly Criterion fraction — higher = greater historical edge
# Negative Kelly = unfavourable historical distribution
KELLY_BANDS = [
    (-0.50,  5),
    ( 0.00, 20),
    ( 0.05, 35),
    ( 0.10, 52),
    ( 0.15, 65),
    ( 0.20, 78),
    ( 0.30, 90),
    ( 0.50, 98),
]
