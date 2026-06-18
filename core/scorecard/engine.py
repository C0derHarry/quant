"""
Scorecard engine (pure Python — no FastAPI, no yfinance).
M1: Risk + Momentum pillars graded from KPIs and technical composite.
M2: All 4 pillars graded — Value/Quality from fundamentals, Momentum adds
    ML P(up), Risk adds EWMA current vol (both require ctx population by route).
"""
import datetime as dt
import numpy as np
import pandas as pd

from core.stats.kpi import CAGR, volatility, Sharpe, Sortino, max_dd, jensens_alpha
from core.scorecard.types import ModelResult, PillarResult, Scorecard
from core.scorecard.context import ScoreContext
from core.scorecard.normalize import (
    score_band, to_letter,
    VOL_BANDS, MDD_BANDS, SHARPE_BANDS, SORTINO_BANDS, BETA_BANDS, TECH_BULL_BANDS,
    PE_BANDS, PB_BANDS, EV_SALES_BANDS, EY_BANDS, ROC_BANDS,
    ROE_BANDS, DE_BANDS, ML_PUP_BANDS, EWMA_DAILY_VOL_BANDS,
    EV_EBITDA_BANDS, GRAHAM_MOS_BANDS, PEG_BANDS,
    ROCE_BANDS, GROSS_MARGIN_BANDS, PIOTROSKI_BANDS, REV_CAGR_BANDS, RETURN_52WK_BANDS,
    ROIC_BANDS, ALTMAN_BANDS, BENEISH_BANDS, DUAL_MOMENTUM_BANDS, KELLY_BANDS,
)
from core.scorecard.pillars import (
    RISK_WEIGHTS, MOMENTUM_WEIGHTS, VALUE_WEIGHTS, QUALITY_WEIGHTS,
    VERDICTS, PILLAR_ORDER, PILLAR_LABELS,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe(fn, *args, **kwargs):
    """Call fn; return None on any exception."""
    try:
        v = fn(*args, **kwargs)
        if v is None or (isinstance(v, float) and not np.isfinite(v)):
            return None
        return v
    except Exception:
        return None


def _missing(key: str, label: str, tier: str, note: str) -> ModelResult:
    return ModelResult(key=key, label=label, raw_value=None, display="—",
                       sub_score=None, status="missing", tier=tier, note=note)


def _aggregate_pillar(key: str, models: list[ModelResult],
                      weights: dict[str, float]) -> PillarResult:
    """Weighted mean of ok/partial sub-scores. Returns N/A pillar if no data."""
    label = PILLAR_LABELS[key]
    usable = [m for m in models if m.sub_score is not None and m.status in ("ok", "partial")]
    total = len(models)
    if not usable:
        grade = "N/A"
        verdict = VERDICTS.get((key, "N/A"), "Insufficient data for this pillar.")
        return PillarResult(key=key, label=label, score=None, grade=grade,
                            verdict=verdict, models=models, coverage=0.0)
    weighted_sum = sum(m.sub_score * weights.get(m.key, 1.0) for m in usable)
    weight_total = sum(weights.get(m.key, 1.0) for m in usable)
    score = weighted_sum / weight_total
    grade = to_letter(score)
    verdict = VERDICTS.get((key, grade), "")
    coverage = len(usable) / max(total, 1)
    return PillarResult(key=key, label=label, score=score, grade=grade,
                        verdict=verdict, models=models, coverage=coverage)


def _na_pillar(key: str) -> PillarResult:
    label = PILLAR_LABELS[key]
    verdict = VERDICTS.get((key, "N/A"), "Not yet available.")
    return PillarResult(key=key, label=label, score=None, grade="N/A",
                        verdict=verdict, models=[], coverage=0.0)


# ── Risk pillar model functions (M1) ─────────────────────────────────────────

def _model_annual_vol(ctx: ScoreContext) -> ModelResult:
    vol = _safe(volatility, ctx.ohlcv, 252)
    if vol is None or vol <= 0:
        return _missing("annual_vol", "Annual Volatility", "free",
                        "Could not compute volatility from price history.")
    pct = vol * 100
    sub = score_band(pct, VOL_BANDS)
    return ModelResult(
        key="annual_vol", label="Annual Volatility",
        raw_value=round(pct, 2), display=f"{pct:.1f}%",
        sub_score=sub, status="ok", tier="free",
        note=f"Annualised daily return standard deviation over {len(ctx.ohlcv)} trading days.",
    )


def _model_max_drawdown(ctx: ScoreContext) -> ModelResult:
    mdd = _safe(max_dd, ctx.ohlcv)
    if mdd is None or mdd < 0:
        return _missing("max_drawdown", "Max Drawdown", "free",
                        "Could not compute drawdown from price history.")
    pct = mdd * 100
    sub = score_band(pct, MDD_BANDS)
    return ModelResult(
        key="max_drawdown", label="Max Drawdown",
        raw_value=round(pct, 2), display=f"-{pct:.1f}%",
        sub_score=sub, status="ok", tier="free",
        note="Peak-to-trough decline in the observed period.",
    )


def _model_sharpe(ctx: ScoreContext) -> ModelResult:
    sr = _safe(Sharpe, ctx.ohlcv, 252)
    if sr is None:
        return _missing("sharpe", "Sharpe Ratio", "free",
                        "Could not compute Sharpe ratio.")
    sub = score_band(sr, SHARPE_BANDS)
    return ModelResult(
        key="sharpe", label="Sharpe Ratio",
        raw_value=round(sr, 3), display=f"{sr:.2f}",
        sub_score=sub, status="ok", tier="free",
        note="Return per unit of total volatility, above the 7% risk-free rate.",
    )


def _model_sortino(ctx: ScoreContext) -> ModelResult:
    sr = _safe(Sortino, ctx.ohlcv, 252)
    if sr is None:
        return _missing("sortino", "Sortino Ratio", "free",
                        "Could not compute Sortino ratio.")
    sub = score_band(sr, SORTINO_BANDS)
    return ModelResult(
        key="sortino", label="Sortino Ratio",
        raw_value=round(sr, 3), display=f"{sr:.2f}",
        sub_score=sub, status="ok", tier="free",
        note="Return per unit of downside volatility only (does not penalise upside).",
    )


def _model_beta(ctx: ScoreContext) -> ModelResult:
    try:
        port_close = ctx.ohlcv["Close"].dropna()
        bench_close = ctx.benchmark_ohlcv["Close"].dropna()
        port_rets  = port_close.pct_change().dropna()
        bench_rets = bench_close.pct_change().dropna()
        aligned = pd.concat([port_rets, bench_rets], axis=1, join="inner").dropna()
        if len(aligned) < 60:
            raise ValueError("too few aligned bars")
        p = aligned.iloc[:, 0]
        b = aligned.iloc[:, 1]
        years = len(aligned) / 252.0
        beta, *_ = jensens_alpha(p, b, years)
        if not np.isfinite(beta):
            raise ValueError("non-finite beta")
        sub = score_band(beta, BETA_BANDS)
        return ModelResult(
            key="beta", label="Market Beta",
            raw_value=round(beta, 3), display=f"{beta:.2f}",
            sub_score=sub, status="ok", tier="free",
            note="Sensitivity to Nifty 50 moves. β<1 = less market risk; β>1 = amplified market risk.",
        )
    except Exception:
        return _missing("beta", "Market Beta", "free",
                        "Could not align ticker and Nifty returns for beta calculation.")


# ── Momentum pillar model functions (M1) ─────────────────────────────────────

def _model_tech_composite(ctx: ScoreContext) -> ModelResult:
    ts = ctx.tech_summary
    if not ts or ts.get("total", 0) == 0:
        return _missing("tech_composite", "Technical Composite", "free",
                        "Insufficient price data for technical indicators.")
    bull_ratio = ts.get("bull_ratio", 0.0)
    sub = score_band(bull_ratio, TECH_BULL_BANDS)
    bull = ts.get("bullish", 0)
    bear = ts.get("bearish", 0)
    neut = ts.get("neutral", 0)
    verdict_raw = ts.get("verdict", "NEUTRAL")
    return ModelResult(
        key="tech_composite", label="Technical Composite",
        raw_value=round(bull_ratio * 100, 1),
        display=f"{bull}↑ {bear}↓ {neut}→ ({verdict_raw})",
        sub_score=sub, status="ok", tier="free",
        note=f"{bull} bullish, {bear} bearish, {neut} neutral out of {ts['total']} indicators.",
    )


# ── Value pillar model functions (M2) ────────────────────────────────────────

def _safe_info_float(info: dict, key: str) -> float | None:
    """Pull a float from yfinance info dict; return None if missing/nan/inf."""
    val = info.get(key)
    if val is None:
        return None
    try:
        v = float(val)
        return v if np.isfinite(v) else None
    except Exception:
        return None


def _model_pe(ctx: ScoreContext) -> ModelResult:
    if ctx.info is None:
        return _missing("pe", "Trailing P/E", "free", "No fundamental data available.")
    pe = _safe_info_float(ctx.info, "trailingPE")
    if pe is None or pe <= 0:
        return _missing("pe", "Trailing P/E", "free",
                        "P/E not available or negative (company may be loss-making).")
    sub = score_band(pe, PE_BANDS)
    return ModelResult(
        key="pe", label="Trailing P/E",
        raw_value=round(pe, 2), display=f"{pe:.1f}x",
        sub_score=sub, status="ok", tier="free",
        note="Price / trailing 12-month EPS. Lower multiples suggest cheaper entry on earnings.",
    )


def _model_pb(ctx: ScoreContext) -> ModelResult:
    if ctx.info is None:
        return _missing("pb", "Price / Book", "free", "No fundamental data available.")
    pb = _safe_info_float(ctx.info, "priceToBook")
    if pb is None or pb <= 0:
        return _missing("pb", "Price / Book", "free",
                        "P/B not available or negative (negative book value).")
    sub = score_band(pb, PB_BANDS)
    return ModelResult(
        key="pb", label="Price / Book",
        raw_value=round(pb, 2), display=f"{pb:.2f}x",
        sub_score=sub, status="ok", tier="free",
        note="Market cap / book value of equity. Below 1x may indicate assets priced cheaply.",
    )


def _model_ev_sales(ctx: ScoreContext) -> ModelResult:
    if ctx.info is None:
        return _missing("ev_sales", "EV / Sales", "free", "No fundamental data available.")
    evs = _safe_info_float(ctx.info, "enterpriseToRevenue")
    if evs is None or evs < 0:
        return _missing("ev_sales", "EV / Sales", "free", "EV/Sales not available.")
    sub = score_band(evs, EV_SALES_BANDS)
    return ModelResult(
        key="ev_sales", label="EV / Sales",
        raw_value=round(evs, 2), display=f"{evs:.2f}x",
        sub_score=sub, status="ok", tier="free",
        note="Enterprise value relative to revenue — useful across industries.",
    )


def _model_earnings_yield(ctx: ScoreContext) -> ModelResult:
    """Magic Formula Earnings Yield = EBIT / Enterprise Value."""
    try:
        if ctx.info is None or ctx.financials is None or ctx.balance_sheet is None:
            raise ValueError("no financial data")
        info = ctx.info
        fin  = ctx.financials
        total_cash = float(info.get("totalCash") or 0)
        total_debt = float(info.get("totalDebt") or 0)
        market_cap = float(info.get("marketCap") or 0)
        if market_cap <= 0:
            raise ValueError("market cap unavailable")
        # EBIT with bank/holding-co fallback (same pattern as value.py)
        if "EBIT" in fin.index:
            ebit = float(fin.loc["EBIT"].iloc[0])
        elif "Pretax Income" in fin.index:
            ebit = float(fin.loc["Pretax Income"].iloc[0])
        else:
            raise ValueError("no EBIT or Pretax Income")
        if pd.isna(ebit):
            raise ValueError("EBIT is NaN")
        ev = market_cap + total_debt - total_cash
        if ev <= 0:
            raise ValueError("non-positive EV")
        ey = ebit / ev
        sub = score_band(ey, EY_BANDS)
        return ModelResult(
            key="earnings_yield", label="Earnings Yield",
            raw_value=round(ey, 4), display=f"{ey*100:.1f}%",
            sub_score=sub, status="ok", tier="free",
            note="EBIT / Enterprise Value (Magic Formula). Higher yield = cheaper on operating earnings.",
        )
    except Exception:
        return _missing("earnings_yield", "Earnings Yield", "free",
                        "Could not compute earnings yield from available financial data.")


def _model_roc(ctx: ScoreContext) -> ModelResult:
    """Magic Formula Return on Capital = EBIT / Invested Capital."""
    try:
        if ctx.info is None or ctx.financials is None or ctx.balance_sheet is None:
            raise ValueError("no financial data")
        fin = ctx.financials
        bs  = ctx.balance_sheet
        # EBIT
        if "EBIT" in fin.index:
            ebit = float(fin.loc["EBIT"].iloc[0])
        elif "Pretax Income" in fin.index:
            ebit = float(fin.loc["Pretax Income"].iloc[0])
        else:
            raise ValueError("no EBIT")
        if pd.isna(ebit):
            raise ValueError("EBIT NaN")
        # Invested capital — identical fallback chain as value.py
        if "Current Assets" in bs.index and "Current Liabilities" in bs.index:
            net_ppe     = float(bs.loc["Net PPE"].iloc[0]) if "Net PPE" in bs.index else 0.0
            work_cap    = float(bs.loc["Current Assets"].iloc[0]) - float(bs.loc["Current Liabilities"].iloc[0])
            inv_cap     = (net_ppe or 0.0) + work_cap
        elif "Invested Capital" in bs.index:
            inv_cap = float(bs.loc["Invested Capital"].iloc[0])
        elif "Common Stock Equity" in bs.index:
            inv_cap = float(bs.loc["Common Stock Equity"].iloc[0])
        elif "Stockholders Equity" in bs.index:
            inv_cap = float(bs.loc["Stockholders Equity"].iloc[0])
        else:
            raise ValueError("cannot determine invested capital")
        if pd.isna(inv_cap) or inv_cap == 0:
            raise ValueError("invested capital zero/NaN")
        roc = ebit / inv_cap
        sub = score_band(roc, ROC_BANDS)
        return ModelResult(
            key="roc", label="Return on Capital",
            raw_value=round(roc, 4), display=f"{roc*100:.1f}%",
            sub_score=sub, status="ok", tier="free",
            note="EBIT / Invested Capital (Magic Formula). Measures how efficiently capital is deployed.",
        )
    except Exception:
        return _missing("roc", "Return on Capital", "free",
                        "Could not compute ROC from available financial data.")


# ── Quality pillar model functions (M2) ──────────────────────────────────────

def _model_roe(ctx: ScoreContext) -> ModelResult:
    try:
        if ctx.info is None:
            raise ValueError("no info")
        roe = _safe_info_float(ctx.info, "returnOnEquity")
        if roe is None and ctx.financials is not None and ctx.balance_sheet is not None:
            fin = ctx.financials
            bs  = ctx.balance_sheet
            ni_row = "Net Income" if "Net Income" in fin.index else None
            eq_row = ("Common Stock Equity" if "Common Stock Equity" in bs.index
                      else "Stockholders Equity" if "Stockholders Equity" in bs.index
                      else None)
            if ni_row and eq_row:
                ni = float(fin.loc[ni_row].iloc[0])
                eq = float(bs.loc[eq_row].iloc[0])
                if not pd.isna(ni) and not pd.isna(eq) and eq != 0:
                    roe = ni / eq
        if roe is None:
            raise ValueError("ROE unavailable")
        sub = score_band(roe, ROE_BANDS)
        return ModelResult(
            key="roe", label="Return on Equity",
            raw_value=round(roe, 4), display=f"{roe*100:.1f}%",
            sub_score=sub, status="ok", tier="free",
            note="Net Income / Shareholders Equity. Higher ROE indicates efficient use of equity.",
        )
    except Exception:
        return _missing("roe", "Return on Equity", "free",
                        "Could not compute ROE from available data.")


def _model_de_ratio(ctx: ScoreContext) -> ModelResult:
    try:
        if ctx.info is None:
            raise ValueError("no info")
        de_raw = _safe_info_float(ctx.info, "debtToEquity")
        if de_raw is None:
            raise ValueError("debtToEquity not in info")
        # yfinance returns debtToEquity as a percentage (e.g. 45 = 0.45 ratio)
        de = de_raw / 100.0
        if de < 0:
            raise ValueError("negative D/E (unusual balance sheet)")
        sub = score_band(de, DE_BANDS)
        return ModelResult(
            key="de_ratio", label="Debt / Equity",
            raw_value=round(de, 3), display=f"{de:.2f}x",
            sub_score=sub, status="ok", tier="free",
            note="Total Debt / Shareholders Equity. Lower ratio = less financial leverage.",
        )
    except Exception:
        return _missing("de_ratio", "Debt / Equity", "free",
                        "Could not retrieve leverage data.")


# ── Shared DataFrame helper (M3+) ────────────────────────────────────────────

def _df_float(df, row: str, col: int = 0) -> float | None:
    """Safe float extraction from yfinance-style df (rows=metrics, cols=dates newest-first)."""
    if df is None or row not in df.index or df.shape[1] <= col:
        return None
    try:
        v = float(df.loc[row].iloc[col])
        return v if np.isfinite(v) else None
    except Exception:
        return None


def _ebit(fin) -> float | None:
    """EBIT with bank/holding-co fallback to Pretax Income."""
    for row in ("EBIT", "Pretax Income"):
        v = _df_float(fin, row)
        if v is not None:
            return v
    return None


# ── Value pillar model functions (M3) ────────────────────────────────────────

def _model_ev_ebitda(ctx: ScoreContext) -> ModelResult:
    if ctx.is_financial:
        return _missing("ev_ebitda", "EV / EBITDA", "free",
                        "EV/EBITDA is not meaningful for financial sector companies.")
    if ctx.info is None:
        return _missing("ev_ebitda", "EV / EBITDA", "free", "No fundamental data available.")
    evx = _safe_info_float(ctx.info, "enterpriseToEbitda")
    if evx is None or evx <= 0:
        return _missing("ev_ebitda", "EV / EBITDA", "free", "EV/EBITDA not available.")
    sub = score_band(evx, EV_EBITDA_BANDS)
    return ModelResult(
        key="ev_ebitda", label="EV / EBITDA",
        raw_value=round(evx, 2), display=f"{evx:.1f}x",
        sub_score=sub, status="ok", tier="free",
        note="Enterprise value / EBITDA. Removes capital structure and tax rate differences.",
    )


def _model_graham(ctx: ScoreContext) -> ModelResult:
    """Graham Number = √(22.5 × EPS × BVPS); score = margin of safety vs current price."""
    try:
        if ctx.info is None:
            raise ValueError("no info")
        eps  = _safe_info_float(ctx.info, "trailingEps")
        bvps = _safe_info_float(ctx.info, "bookValue")
        price = (_safe_info_float(ctx.info, "currentPrice")
                 or _safe_info_float(ctx.info, "regularMarketPrice")
                 or float(ctx.ohlcv["Close"].iloc[-1]))
        if eps is None or eps <= 0:
            raise ValueError("non-positive EPS — Graham Number undefined")
        if bvps is None or bvps <= 0:
            raise ValueError("non-positive book value")
        if not price or price <= 0:
            raise ValueError("invalid price")
        graham_num = (22.5 * eps * bvps) ** 0.5
        mos = (graham_num / price) - 1.0      # positive = undervalued
        sub = score_band(mos, GRAHAM_MOS_BANDS)
        return ModelResult(
            key="graham", label="Graham Number",
            raw_value=round(mos, 4),
            display=f"₹{graham_num:.0f} ({mos*100:+.1f}% MoS)",
            sub_score=sub, status="ok", tier="free",
            note=f"Graham Number = √(22.5 × EPS × BVPS). Positive margin of safety indicates model-estimated undervaluation.",
        )
    except Exception:
        return _missing("graham", "Graham Number", "free",
                        "Requires positive EPS and positive book value per share.")


def _model_peg(ctx: ScoreContext) -> ModelResult:
    """PEG = trailing P/E ÷ earnings growth (%). Computed from financial statements, not info."""
    try:
        if ctx.info is None or ctx.financials is None:
            raise ValueError("no data")
        pe = _safe_info_float(ctx.info, "trailingPE")
        if pe is None or pe <= 0:
            raise ValueError("invalid PE")
        fin = ctx.financials
        ni_curr = _df_float(fin, "Net Income", 0)
        ni_prev = _df_float(fin, "Net Income", 1)
        if ni_curr is None or ni_prev is None:
            raise ValueError("insufficient earnings history")
        if ni_prev <= 0:
            return ModelResult(
                key="peg", label="PEG Ratio",
                raw_value=None, display="—",
                sub_score=20, status="partial", tier="free",
                note="Negative prior-year earnings make PEG undefined; growth trajectory penalised.",
            )
        eps_growth = (ni_curr / ni_prev) - 1.0
        if eps_growth <= 0:
            return ModelResult(
                key="peg", label="PEG Ratio",
                raw_value=None, display=f"neg ({eps_growth*100:.1f}% growth)",
                sub_score=20, status="partial", tier="free",
                note=f"Negative earnings growth ({eps_growth*100:.1f}% YoY) makes PEG undefined; penalised.",
            )
        peg = pe / (eps_growth * 100.0)
        sub = score_band(peg, PEG_BANDS)
        return ModelResult(
            key="peg", label="PEG Ratio",
            raw_value=round(peg, 2), display=f"{peg:.2f}x",
            sub_score=sub, status="ok", tier="free",
            note=f"P/E {pe:.1f}x ÷ YoY earnings growth {eps_growth*100:.1f}%. Below 1x = growth not fully priced in.",
        )
    except Exception:
        return _missing("peg", "PEG Ratio", "free",
                        "Requires valid P/E and at least two years of earnings history.")


# ── Quality pillar model functions (M3) ──────────────────────────────────────

def _model_roce(ctx: ScoreContext) -> ModelResult:
    """ROCE = EBIT / (Total Assets − Current Liabilities)."""
    try:
        if ctx.financials is None or ctx.balance_sheet is None:
            raise ValueError("no financial data")
        fin = ctx.financials
        bs  = ctx.balance_sheet
        ebit_val = _ebit(fin)
        if ebit_val is None:
            raise ValueError("EBIT unavailable")
        ta = _df_float(bs, "Total Assets")
        cl = _df_float(bs, "Current Liabilities") or 0.0
        if ta is None or ta <= 0:
            raise ValueError("Total Assets unavailable")
        ce = ta - cl
        if ce <= 0:
            raise ValueError("non-positive capital employed")
        roce = ebit_val / ce
        sub = score_band(roce, ROCE_BANDS)
        return ModelResult(
            key="roce", label="Return on Capital Employed",
            raw_value=round(roce, 4), display=f"{roce*100:.1f}%",
            sub_score=sub, status="ok", tier="free",
            note="EBIT / (Total Assets − Current Liabilities). Measures operating efficiency across the full capital base.",
        )
    except Exception:
        return _missing("roce", "Return on Capital Employed", "free",
                        "Could not compute ROCE from available data.")


def _model_gross_margin(ctx: ScoreContext) -> ModelResult:
    if ctx.is_financial:
        return _missing("gross_margin", "Gross Margin", "free",
                        "Gross Margin is not meaningful for financial sector companies.")
    try:
        if ctx.financials is None:
            raise ValueError("no financials")
        fin = ctx.financials
        gp  = _df_float(fin, "Gross Profit")
        rev = (_df_float(fin, "Total Revenue") or _df_float(fin, "Operating Revenue"))
        if gp is None or rev is None or rev == 0:
            raise ValueError("cannot compute gross margin")
        gm = gp / rev
        sub = score_band(gm, GROSS_MARGIN_BANDS)
        return ModelResult(
            key="gross_margin", label="Gross Margin",
            raw_value=round(gm, 4), display=f"{gm*100:.1f}%",
            sub_score=sub, status="ok", tier="free",
            note="Gross Profit / Revenue. Indicates pricing power and production cost efficiency.",
        )
    except Exception:
        return _missing("gross_margin", "Gross Margin", "free",
                        "Could not compute gross margin from available data.")


def _model_piotroski(ctx: ScoreContext) -> ModelResult:
    """Piotroski F-Score: 9 binary financial health signals; scaled to /9 if data is partial."""
    if ctx.is_financial:
        return _missing("piotroski", "Piotroski F-Score", "free",
                        "Piotroski score is not applicable to financial sector companies.")
    try:
        if ctx.financials is None or ctx.balance_sheet is None:
            raise ValueError("no financial data")
        fin = ctx.financials
        bs  = ctx.balance_sheet
        cf  = ctx.cash_flow
        if fin.shape[1] < 2 or bs.shape[1] < 2:
            raise ValueError("need 2 years of statements for YoY signals")

        checked = 0
        score   = 0

        def signal(cond):
            nonlocal checked, score
            if cond is None:
                return
            checked += 1
            if cond:
                score += 1

        # ── Profitability ─────────────────────────────────────────────────────
        ni   = _df_float(fin, "Net Income", 0)
        ni1  = _df_float(fin, "Net Income", 1)
        ta   = _df_float(bs, "Total Assets", 0)
        ta1  = _df_float(bs, "Total Assets", 1)
        ocf  = _df_float(cf, "Operating Cash Flow", 0) if cf is not None else None

        roa  = (ni  / ta)  if (ni  is not None and ta  and ta  > 0) else None
        roa1 = (ni1 / ta1) if (ni1 is not None and ta1 and ta1 > 0) else None

        signal(roa  > 0 if roa  is not None else None)                              # F1: ROA > 0
        signal(ocf  > 0 if ocf  is not None else None)                              # F2: OCF > 0
        signal((roa - roa1) > 0 if (roa is not None and roa1 is not None) else None) # F3: ΔROA
        signal(                                                                       # F4: accruals
            (ocf / ta) > roa
            if (ocf is not None and ta and ta > 0 and roa is not None)
            else None
        )

        # ── Leverage / Liquidity ─────────────────────────────────────────────
        ltd  = _df_float(bs, "Long Term Debt", 0) or 0.0
        ltd1 = _df_float(bs, "Long Term Debt", 1) or 0.0
        ca   = _df_float(bs, "Current Assets", 0)
        cl   = _df_float(bs, "Current Liabilities", 0)
        ca1  = _df_float(bs, "Current Assets", 1)
        cl1  = _df_float(bs, "Current Liabilities", 1)
        shr  = _df_float(bs, "Ordinary Shares Number", 0) or _df_float(bs, "Share Issued", 0)
        shr1 = _df_float(bs, "Ordinary Shares Number", 1) or _df_float(bs, "Share Issued", 1)

        lev  = (ltd  / ta)  if (ta  and ta  > 0) else None
        lev1 = (ltd1 / ta1) if (ta1 and ta1 > 0) else None
        cur  = (ca  / cl)   if (ca  is not None and cl  and cl  > 0) else None
        cur1 = (ca1 / cl1)  if (ca1 is not None and cl1 and cl1 > 0) else None

        signal((lev  <= lev1)  if (lev  is not None and lev1  is not None) else None)  # F5: Δleverage
        signal((cur  >= cur1)  if (cur  is not None and cur1  is not None) else None)  # F6: Δliquidity
        signal((shr  <= shr1)  if (shr  is not None and shr1  is not None) else None)  # F7: no dilution

        # ── Operating efficiency ─────────────────────────────────────────────
        gp   = _df_float(fin, "Gross Profit", 0)
        gp1  = _df_float(fin, "Gross Profit", 1)
        rev  = _df_float(fin, "Total Revenue", 0) or _df_float(fin, "Operating Revenue", 0)
        rev1 = _df_float(fin, "Total Revenue", 1) or _df_float(fin, "Operating Revenue", 1)

        gm   = (gp  / rev)  if (gp  is not None and rev  and rev  > 0) else None
        gm1  = (gp1 / rev1) if (gp1 is not None and rev1 and rev1 > 0) else None
        at   = (rev  / ta)  if (rev  is not None and ta  and ta  > 0) else None
        at1  = (rev1 / ta1) if (rev1 is not None and ta1 and ta1 > 0) else None

        signal((gm >= gm1) if (gm is not None and gm1 is not None) else None)    # F8: Δgross margin
        signal((at >= at1) if (at is not None and at1 is not None) else None)    # F9: Δasset turnover

        if checked < 4:
            raise ValueError("too few signals evaluable")

        scaled = round(score * 9 / checked) if checked < 9 else score
        sub    = score_band(scaled, PIOTROSKI_BANDS)
        status = "ok" if checked == 9 else "partial"
        return ModelResult(
            key="piotroski", label="Piotroski F-Score",
            raw_value=scaled, display=f"{score}/{checked} → {scaled}/9",
            sub_score=sub, status=status, tier="free",
            note=f"{score} of {checked} financial health signals positive (scaled to /9). Higher = stronger balance sheet.",
        )
    except Exception:
        return _missing("piotroski", "Piotroski F-Score", "free",
                        "Could not compute Piotroski score from available data.")


def _model_revenue_cagr(ctx: ScoreContext) -> ModelResult:
    """Multi-year revenue compound annual growth rate from income statement."""
    try:
        if ctx.financials is None:
            raise ValueError("no financials")
        fin     = ctx.financials
        rev_row = "Total Revenue" if "Total Revenue" in fin.index else "Operating Revenue"
        if rev_row not in fin.index:
            raise ValueError("no revenue row")
        rev_series = fin.loc[rev_row].dropna()
        if len(rev_series) < 2:
            raise ValueError("need at least 2 years of revenue")
        vals      = [float(v) for v in rev_series.values]  # newest → oldest
        rev_new   = vals[0]
        rev_old   = vals[-1]
        n_years   = len(vals) - 1
        if rev_old <= 0 or rev_new <= 0:
            raise ValueError("non-positive revenue")
        cagr = (rev_new / rev_old) ** (1.0 / n_years) - 1.0
        sub  = score_band(cagr, REV_CAGR_BANDS)
        return ModelResult(
            key="revenue_cagr", label="Revenue CAGR",
            raw_value=round(cagr, 4), display=f"{cagr*100:.1f}% p.a.",
            sub_score=sub, status="ok", tier="free",
            note=f"{n_years}-year revenue compound annual growth rate.",
        )
    except Exception:
        return _missing("revenue_cagr", "Revenue CAGR", "free",
                        "Could not compute revenue CAGR from available data.")


# ── Momentum addition (M3 free) ───────────────────────────────────────────────

def _model_return_52wk(ctx: ScoreContext) -> ModelResult:
    """52-week price return from OHLCV (uses up to 252 trading days)."""
    try:
        close = ctx.ohlcv["Close"].dropna()
        if len(close) < 30:
            raise ValueError("insufficient price history")
        n        = min(len(close) - 1, 252)
        ret      = float(close.iloc[-1]) / float(close.iloc[-1 - n]) - 1.0
        sub      = score_band(ret, RETURN_52WK_BANDS)
        status   = "ok" if n >= 200 else "partial"
        note_days = f"{n}-trading-day"
        return ModelResult(
            key="return_52wk", label="52-Week Return",
            raw_value=round(ret, 4), display=f"{ret*100:+.1f}%",
            sub_score=sub, status=status, tier="free",
            note=f"{note_days} price return. Captures medium-term price momentum.",
        )
    except Exception:
        return _missing("return_52wk", "52-Week Return", "free",
                        "Could not compute 52-week return from price history.")


# ── Value pillar model functions (M4 — premium) ──────────────────────────────

_WACC    = 0.12   # India context: ~7% RF + 5% ERP ≈ 12%
_TERM_G  = 0.04   # India long-run terminal growth (GDP + inflation proxy)
_COE     = 0.12   # Cost of equity (simplified CAPM with β≈1)
_TAX_DEF = 0.25   # Default corporate tax rate (India flat rate)


def _shares_and_price(info: dict, ohlcv: pd.DataFrame):
    """Return (shares, price); raises if either is invalid."""
    shares = (_safe_info_float(info, "sharesOutstanding")
              or _safe_info_float(info, "impliedSharesOutstanding"))
    price  = (_safe_info_float(info, "currentPrice")
              or _safe_info_float(info, "regularMarketPrice")
              or float(ohlcv["Close"].iloc[-1]))
    if not shares or shares <= 0:
        raise ValueError("shares outstanding unavailable")
    if not price or price <= 0:
        raise ValueError("current price unavailable")
    return shares, price


def _tax_rate(info: dict) -> float:
    t = _safe_info_float(info, "effectiveTaxRate")
    if t and 0.05 < t < 0.55:
        return t
    return _TAX_DEF


def _model_dcf(ctx: ScoreContext, *, include_premium: bool) -> ModelResult:
    """5-year DCF with terminal value. FCF = OCF − |CapEx|. WACC=12%, TV g=4%."""
    if not include_premium:
        return _missing("dcf", "DCF Intrinsic Value", "premium",
                        "5-year discounted cash flow model — available on Premium plan.")
    try:
        if ctx.cash_flow is None or ctx.info is None:
            raise ValueError("no financial data")
        cf  = ctx.cash_flow
        shares, price = _shares_and_price(ctx.info, ctx.ohlcv)

        # FCF series — use "Free Cash Flow" directly if present, else OCF − |CapEx|
        if "Free Cash Flow" in cf.index:
            fcf_series = cf.loc["Free Cash Flow"].dropna()
        else:
            ocf_s   = cf.loc["Operating Cash Flow"].dropna() if "Operating Cash Flow" in cf.index else None
            capex_s = cf.loc["Capital Expenditure"].dropna()  if "Capital Expenditure" in cf.index else None
            if ocf_s is None or capex_s is None:
                raise ValueError("no FCF data")
            n = min(len(ocf_s), len(capex_s))
            fcf_vals = [float(ocf_s.iloc[i]) - abs(float(capex_s.iloc[i]))
                        for i in range(n)]
            fcf_series = pd.Series(fcf_vals)

        fcf_vals = [float(v) for v in fcf_series.values[:5] if np.isfinite(v)]
        if not fcf_vals or fcf_vals[0] <= 0:
            raise ValueError("negative or zero base FCF")

        base_fcf = fcf_vals[0]
        # Historical FCF growth; cap to [-5%, 25%]
        if len(fcf_vals) >= 2 and fcf_vals[-1] > 0:
            g_hist = (fcf_vals[0] / fcf_vals[-1]) ** (1.0 / (len(fcf_vals) - 1)) - 1.0
            growth = max(min(g_hist, 0.25), -0.05)
        else:
            growth = 0.10

        pv_fcf = 0.0
        fcf_t  = base_fcf
        for t in range(1, 6):
            fcf_t  *= (1 + growth)
            pv_fcf += fcf_t / (1 + _WACC) ** t

        tv     = fcf_t * (1 + _TERM_G) / (_WACC - _TERM_G)
        pv_tv  = tv / (1 + _WACC) ** 5

        cash   = _safe_info_float(ctx.info, "totalCash") or 0
        debt   = _safe_info_float(ctx.info, "totalDebt") or 0
        equity_val = pv_fcf + pv_tv + cash - debt
        intrinsic  = equity_val / shares
        mos        = intrinsic / price - 1.0

        sub = score_band(mos, GRAHAM_MOS_BANDS)
        return ModelResult(
            key="dcf", label="DCF Intrinsic Value",
            raw_value=round(mos, 4),
            display=f"₹{intrinsic:.0f} ({mos*100:+.1f}% MoS)",
            sub_score=sub, status="ok", tier="premium",
            note=f"5-yr DCF: WACC={_WACC*100:.0f}%, FCF growth={growth*100:.1f}%, TV g={_TERM_G*100:.0f}%. Model-estimated fair value; assumptions may be wrong.",
        )
    except Exception:
        return _missing("dcf", "DCF Intrinsic Value", "premium",
                        "DCF requires positive FCF history — available on Premium plan.")


def _model_epv(ctx: ScoreContext, *, include_premium: bool) -> ModelResult:
    """Earnings Power Value = Normalised EBIT(1-t) / WACC. No growth assumed."""
    if not include_premium:
        return _missing("epv", "Earnings Power Value", "premium",
                        "EPV intrinsic value (no-growth scenario) — available on Premium plan.")
    try:
        if ctx.financials is None or ctx.info is None:
            raise ValueError("no financial data")
        fin = ctx.financials
        shares, price = _shares_and_price(ctx.info, ctx.ohlcv)

        # Normalise EBIT over up to 3 years
        ebit_vals = [_ebit_at(fin, c) for c in range(min(3, fin.shape[1]))]
        ebit_vals = [v for v in ebit_vals if v is not None]
        if not ebit_vals:
            raise ValueError("EBIT unavailable")
        norm_ebit = sum(ebit_vals) / len(ebit_vals)

        nopat     = norm_ebit * (1 - _tax_rate(ctx.info))
        epv_firm  = nopat / _WACC
        cash      = _safe_info_float(ctx.info, "totalCash") or 0
        debt      = _safe_info_float(ctx.info, "totalDebt") or 0
        epv_ps    = (epv_firm + cash - debt) / shares
        mos       = epv_ps / price - 1.0

        sub    = score_band(mos, GRAHAM_MOS_BANDS)
        status = "ok" if len(ebit_vals) >= 2 else "partial"
        return ModelResult(
            key="epv", label="Earnings Power Value",
            raw_value=round(mos, 4),
            display=f"₹{epv_ps:.0f} ({mos*100:+.1f}% MoS)",
            sub_score=sub, status=status, tier="premium",
            note=f"EPV = Normalised EBIT(1-t) / WACC ({_WACC*100:.0f}%). No growth assumed — floor valuation. Model-estimated; assumptions may be wrong.",
        )
    except Exception:
        return _missing("epv", "Earnings Power Value", "premium",
                        "EPV requires EBIT history — available on Premium plan.")


def _ebit_at(fin, col: int) -> float | None:
    for row in ("EBIT", "Pretax Income"):
        v = _df_float(fin, row, col)
        if v is not None:
            return v
    return None


def _model_ri(ctx: ScoreContext, *, include_premium: bool) -> ModelResult:
    """Residual Income model: Value = Book Value + RI / (CoE − g)."""
    if not include_premium:
        return _missing("ri_model", "Residual Income Model", "premium",
                        "RI intrinsic value (book value + excess returns) — available on Premium plan.")
    try:
        if ctx.financials is None or ctx.balance_sheet is None or ctx.info is None:
            raise ValueError("no financial data")
        fin = ctx.financials
        bs  = ctx.balance_sheet
        shares, price = _shares_and_price(ctx.info, ctx.ohlcv)

        ni  = _df_float(fin, "Net Income")
        bv  = (_df_float(bs, "Common Stock Equity")
               or _df_float(bs, "Stockholders Equity"))
        if ni is None or bv is None or bv <= 0:
            raise ValueError("need net income and positive book value")

        ri            = ni - (_COE * bv)
        intrinsic_eq  = bv + ri / (_COE - _TERM_G)
        intrinsic_ps  = intrinsic_eq / shares
        mos           = intrinsic_ps / price - 1.0

        sub = score_band(mos, GRAHAM_MOS_BANDS)
        return ModelResult(
            key="ri_model", label="Residual Income Model",
            raw_value=round(mos, 4),
            display=f"₹{intrinsic_ps:.0f} ({mos*100:+.1f}% MoS)",
            sub_score=sub, status="ok", tier="premium",
            note=f"BV + RI/(CoE−g): CoE={_COE*100:.0f}%, g={_TERM_G*100:.0f}%. Model-estimated fair value; assumptions may be wrong.",
        )
    except Exception:
        return _missing("ri_model", "Residual Income Model", "premium",
                        "RI model requires earnings + book value — available on Premium plan.")


# ── Quality pillar model functions (M4 — premium) ────────────────────────────

def _model_roic(ctx: ScoreContext, *, include_premium: bool) -> ModelResult:
    """ROIC = NOPAT / Invested Capital. Positive ROIC−WACC spread = value creation."""
    if not include_premium:
        return _missing("roic", "Return on Invested Capital", "premium",
                        "ROIC vs WACC value-creation spread — available on Premium plan.")
    try:
        if ctx.financials is None or ctx.balance_sheet is None or ctx.info is None:
            raise ValueError("no financial data")
        fin = ctx.financials
        bs  = ctx.balance_sheet

        ebit_val = _ebit(fin)
        if ebit_val is None:
            raise ValueError("EBIT unavailable")

        nopat   = ebit_val * (1 - _tax_rate(ctx.info))
        ta      = _df_float(bs, "Total Assets")
        cl      = _df_float(bs, "Current Liabilities") or 0.0
        cash    = _safe_info_float(ctx.info, "totalCash") or 0.0
        if ta is None or ta <= 0:
            raise ValueError("Total Assets unavailable")

        # Invested Capital = Total Assets − Non-interest-bearing CL − Excess cash
        inv_cap = ta - cl - cash * 0.5   # keep half cash as operational
        if inv_cap <= 0:
            raise ValueError("non-positive invested capital")

        roic   = nopat / inv_cap
        spread = roic - _WACC
        sub    = score_band(roic, ROIC_BANDS)
        spread_str = f"{spread*100:+.1f}%"
        return ModelResult(
            key="roic", label="Return on Invested Capital",
            raw_value=round(roic, 4), display=f"{roic*100:.1f}%",
            sub_score=sub, status="ok", tier="premium",
            note=f"NOPAT / Invested Capital. ROIC−WACC spread: {spread_str} ({'value creation' if spread > 0 else 'value destruction'}).",
        )
    except Exception:
        return _missing("roic", "Return on Invested Capital", "premium",
                        "ROIC requires EBIT + balance sheet — available on Premium plan.")


def _model_altman(ctx: ScoreContext, *, include_premium: bool) -> ModelResult:
    """Altman Z''-Score (emerging market variant). X1–X4 from balance sheet + EBIT."""
    if not include_premium:
        return _missing("altman_z", "Altman Z-Score", "premium",
                        "Financial distress indicator (Altman Z'') — available on Premium plan.")
    if ctx.is_financial:
        return _missing("altman_z", "Altman Z-Score", "premium",
                        "Altman Z-Score is not applicable to financial sector companies.")
    try:
        if ctx.financials is None or ctx.balance_sheet is None or ctx.info is None:
            raise ValueError("no financial data")
        fin = ctx.financials
        bs  = ctx.balance_sheet

        ta = _df_float(bs, "Total Assets")
        if ta is None or ta <= 0:
            raise ValueError("Total Assets unavailable")

        # X1 = Working Capital / Total Assets
        wc = (_df_float(bs, "Working Capital")
              or _compute_wc(bs))
        x1 = wc / ta if wc is not None else None

        # X2 = Retained Earnings / Total Assets
        re = _df_float(bs, "Retained Earnings")
        x2 = re / ta if re is not None else None

        # X3 = EBIT / Total Assets
        ebit_val = _ebit(fin)
        x3 = ebit_val / ta if ebit_val is not None else None

        # X4 = Book Value of Equity / Total Liabilities
        bve = _df_float(bs, "Common Stock Equity") or _df_float(bs, "Stockholders Equity")
        tl  = (_df_float(bs, "Total Liabilities Net Minority Interest")
               or (ta - bve if bve else None))
        x4 = bve / tl if (bve is not None and tl and tl > 0) else None

        # Z'' = 6.56×X1 + 3.26×X2 + 6.72×X3 + 1.05×X4
        z = 0.0
        available = []
        if x1 is not None: z += 6.56 * x1; available.append("X1")
        if x2 is not None: z += 3.26 * x2; available.append("X2")
        if x3 is not None: z += 6.72 * x3; available.append("X3")
        if x4 is not None: z += 1.05 * x4; available.append("X4")

        if len(available) < 2:
            raise ValueError("insufficient Altman variables")

        # Conservative adjustment if X2 missing (expected median RE/TA ≈ 0.10)
        status = "ok"
        if x2 is None:
            z += 3.26 * 0.10
            status = "partial"

        sub  = score_band(z, ALTMAN_BANDS)
        zone = "Safe" if z > 2.6 else "Grey" if z > 1.1 else "Distress"
        return ModelResult(
            key="altman_z", label="Altman Z-Score",
            raw_value=round(z, 2), display=f"{z:.2f} ({zone})",
            sub_score=sub, status=status, tier="premium",
            note=f"Altman Z'' ({', '.join(available)}). >2.6 Safe; 1.1–2.6 Grey; <1.1 Distress zone.",
        )
    except Exception:
        return _missing("altman_z", "Altman Z-Score", "premium",
                        "Altman Z-Score requires balance sheet data — available on Premium plan.")


def _compute_wc(bs) -> float | None:
    ca = _df_float(bs, "Current Assets")
    cl = _df_float(bs, "Current Liabilities")
    return (ca - cl) if (ca is not None and cl is not None) else None


def _model_beneish(ctx: ScoreContext, *, include_premium: bool) -> ModelResult:
    """Beneish M-Score: 8-ratio earnings manipulation indicator. M > −1.78 = flag."""
    if not include_premium:
        return _missing("beneish", "Beneish M-Score", "premium",
                        "Earnings manipulation indicator — available on Premium plan.")
    if ctx.is_financial:
        return _missing("beneish", "Beneish M-Score", "premium",
                        "Beneish M-Score is not applicable to financial sector companies.")
    try:
        if (ctx.financials is None or ctx.balance_sheet is None
                or ctx.cash_flow is None or ctx.info is None):
            raise ValueError("no financial data")
        fin = ctx.financials
        bs  = ctx.balance_sheet
        cf  = ctx.cash_flow
        if fin.shape[1] < 2 or bs.shape[1] < 2:
            raise ValueError("need 2 years of statements")

        # Pull all needed variables (t = col 0 = current; t-1 = col 1)
        rev  = _df_float(fin, "Total Revenue", 0) or _df_float(fin, "Operating Revenue", 0)
        rev1 = _df_float(fin, "Total Revenue", 1) or _df_float(fin, "Operating Revenue", 1)
        ar   = _df_float(bs, "Accounts Receivable", 0)
        ar1  = _df_float(bs, "Accounts Receivable", 1)
        gp   = _df_float(fin, "Gross Profit", 0)
        gp1  = _df_float(fin, "Gross Profit", 1)
        ta   = _df_float(bs, "Total Assets", 0)
        ta1  = _df_float(bs, "Total Assets", 1)
        ca   = _df_float(bs, "Current Assets", 0)
        ca1  = _df_float(bs, "Current Assets", 1)
        ppe  = _df_float(bs, "Net PPE", 0)
        ppe1 = _df_float(bs, "Net PPE", 1)
        depr = (_df_float(cf, "Depreciation", 0)
                or _df_float(cf, "Depreciation And Amortization", 0))
        depr1= (_df_float(cf, "Depreciation", 1)
                or _df_float(cf, "Depreciation And Amortization", 1))
        sga  = _df_float(fin, "Selling General And Administration", 0)
        sga1 = _df_float(fin, "Selling General And Administration", 1)
        ltd  = (_df_float(bs, "Long Term Debt", 0) or 0)
        ltd1 = (_df_float(bs, "Long Term Debt", 1) or 0)
        cl   = (_df_float(bs, "Current Liabilities", 0) or 0)
        cl1  = (_df_float(bs, "Current Liabilities", 1) or 0)
        ni   = _df_float(fin, "Net Income", 0)
        ocf  = _df_float(cf, "Operating Cash Flow", 0)

        m = -4.84   # intercept (full model)
        n_terms = 0

        # 1. DSRI: receivables growing faster than sales → flag
        if ar and ar1 and rev and rev1 and rev > 0 and rev1 > 0:
            m += 0.92 * ((ar / rev) / (ar1 / rev1)); n_terms += 1

        # 2. GMI: declining gross margin → flag
        if gp and gp1 and rev and rev1 and rev > 0 and rev1 > 0 and (gp / rev) > 0:
            m += 0.528 * ((gp1 / rev1) / (gp / rev)); n_terms += 1

        # 3. AQI: asset quality deteriorating → flag
        if ca and ca1 and ppe and ppe1 and ta and ta1 and ta > 0 and ta1 > 0:
            q0 = 1 - (ca + ppe) / ta
            q1 = 1 - (ca1 + ppe1) / ta1
            if q1 != 0:
                m += 0.404 * (q0 / q1); n_terms += 1

        # 4. SGI: rapid sales growth → higher manipulation risk
        if rev and rev1 and rev1 > 0:
            m += 0.892 * (rev / rev1); n_terms += 1

        # 5. DEPI: decreasing depreciation rate → flag
        if depr and depr1 and ppe and ppe1 and (depr + ppe) > 0 and (depr1 + ppe1) > 0:
            m += 0.115 * ((depr1 / (depr1 + ppe1)) / (depr / (depr + ppe))); n_terms += 1

        # 6. SGAI: rising SGA relative to sales → flag (coefficient is negative = benign)
        if sga and sga1 and rev and rev1 and rev > 0 and rev1 > 0:
            m += -0.172 * ((sga / rev) / (sga1 / rev1)); n_terms += 1

        # 7. LVGI: rising leverage → flag (coefficient is negative = benign)
        if ta and ta1 and ta > 0 and ta1 > 0:
            lev  = (ltd + cl)  / ta
            lev1 = (ltd1 + cl1) / ta1
            if lev1 > 0:
                m += -0.327 * (lev / lev1); n_terms += 1

        # 8. TATA: high accruals vs OCF → flag
        if ni is not None and ocf is not None and ta and ta > 0:
            m += 4.679 * ((ni - ocf) / ta); n_terms += 1

        if n_terms < 3:
            raise ValueError("too few Beneish variables")

        # Rescale intercept if some terms missing
        if n_terms < 8:
            m = m * (n_terms / 8)

        status = "ok" if n_terms >= 6 else "partial"
        sub    = score_band(m, BENEISH_BANDS)
        flag   = "Flag" if m > -1.78 else "Clean"
        return ModelResult(
            key="beneish", label="Beneish M-Score",
            raw_value=round(m, 3), display=f"{m:.2f} ({flag})",
            sub_score=sub, status=status, tier="premium",
            note=f"Beneish M-Score ({n_terms}/8 ratios). M > −1.78 = possible manipulation; M < −1.78 = no signal.",
        )
    except Exception:
        return _missing("beneish", "Beneish M-Score", "premium",
                        "Beneish M-Score requires 2 years of statements — available on Premium plan.")


# ── Momentum pillar model functions (M4 — premium) ───────────────────────────

def _model_dual_momentum(ctx: ScoreContext, *, include_premium: bool) -> ModelResult:
    """Dual Momentum: absolute (vs RF) + relative (vs Nifty). 0–2 signals."""
    if not include_premium:
        return _missing("dual_momentum", "Dual Momentum", "premium",
                        "Absolute + relative momentum signal — available on Premium plan.")
    try:
        close = ctx.ohlcv["Close"].dropna()
        if len(close) < 60:
            raise ValueError("insufficient price history")

        n   = min(len(close) - 1, 252)
        ret = float(close.iloc[-1]) / float(close.iloc[-1 - n]) - 1.0

        RF_ANNUAL  = 0.07
        rf_period  = RF_ANNUAL * (n / 252)
        abs_signal = ret > rf_period

        rel_signal = False
        if not ctx.benchmark_ohlcv.empty and len(ctx.benchmark_ohlcv) > n:
            bench = ctx.benchmark_ohlcv["Close"].dropna()
            if len(bench) > n:
                ret_bench  = float(bench.iloc[-1]) / float(bench.iloc[-1 - n]) - 1.0
                rel_signal = ret > ret_bench

        signals = int(abs_signal) + int(rel_signal)
        sub     = score_band(float(signals), DUAL_MOMENTUM_BANDS)
        period  = f"{n // 21}M" if n >= 21 else f"{n}D"
        a_lbl, r_lbl = ("✓" if abs_signal else "✗"), ("✓" if rel_signal else "✗")

        return ModelResult(
            key="dual_momentum", label="Dual Momentum",
            raw_value=float(signals), display=f"{signals}/2 (abs {a_lbl}, rel {r_lbl})",
            sub_score=sub, status="ok", tier="premium",
            note=f"{period} return {ret*100:+.1f}%. Absolute vs {RF_ANNUAL*100:.0f}% RF: {a_lbl}. Relative vs Nifty: {r_lbl}.",
        )
    except Exception:
        return _missing("dual_momentum", "Dual Momentum", "premium",
                        "Dual Momentum requires price history — available on Premium plan.")


def _model_kelly(ctx: ScoreContext, *, include_premium: bool) -> ModelResult:
    """Kelly Criterion: optimal position fraction from daily win/loss statistics."""
    if not include_premium:
        return _missing("kelly", "Kelly Criterion", "premium",
                        "Optimal position sizing from historical return distribution — Premium plan.")
    try:
        rets = ctx.ohlcv["Close"].pct_change().dropna()
        if len(rets) < 60:
            raise ValueError("insufficient history")
        wins   = rets[rets > 0]
        losses = rets[rets < 0]
        if len(wins) == 0 or len(losses) == 0:
            raise ValueError("degenerate return series")
        p     = len(wins) / len(rets)
        avg_w = float(wins.mean())
        avg_l = float(losses.abs().mean())
        if avg_w <= 0 or avg_l <= 0:
            raise ValueError("degenerate win/loss")
        b     = avg_w / avg_l                    # odds: gain per unit loss
        kelly = (b * p - (1 - p)) / b            # Kelly fraction
        sub   = score_band(kelly, KELLY_BANDS)
        return ModelResult(
            key="kelly", label="Kelly Criterion",
            raw_value=round(kelly, 4), display=f"{kelly*100:.1f}% edge",
            sub_score=sub, status="ok", tier="premium",
            note=f"Win rate {p:.0%}, avg gain {avg_w*100:.2f}%, avg loss {avg_l*100:.2f}%. Full Kelly position size: {max(kelly*100,0):.1f}%.",
        )
    except Exception:
        return _missing("kelly", "Kelly Criterion", "premium",
                        "Kelly Criterion requires price history — available on Premium plan.")


# ── Momentum addition (M2 premium) ────────────────────────────────────────────

def _model_ml_pup(ctx: ScoreContext, *, include_premium: bool) -> ModelResult:
    if not include_premium:
        return _missing("ml_pup", "ML Probability Signal", "premium",
                        "Gradient-boosting P(5-day up) — available on Premium plan.")
    if ctx.ml_p_up is None:
        return _missing("ml_pup", "ML Probability Signal", "premium",
                        "ML signal could not be computed for this ticker.")
    p = ctx.ml_p_up
    sub = score_band(p, ML_PUP_BANDS)
    regime = "Bullish" if p >= 0.65 else "Bearish" if p <= 0.40 else "Neutral"
    return ModelResult(
        key="ml_pup", label="ML Probability Signal",
        raw_value=round(p, 4), display=f"P(up) {p:.0%}",
        sub_score=sub, status="ok", tier="premium",
        note=f"Gradient-boosting calibrated probability of 5-day positive return ({regime} signal).",
    )


# ── Risk addition (M2 premium) ────────────────────────────────────────────────

def _model_ewma_var(ctx: ScoreContext, *, include_premium: bool) -> ModelResult:
    if not include_premium:
        return _missing("ewma_var", "EWMA Current Volatility", "premium",
                        "Real-time EWMA volatility — available on Premium plan.")
    try:
        from scipy.stats import norm as _norm
        from core.volatility.ewma import ewma_variance, get_optimal_lambda

        ret = ctx.ohlcv["Close"].pct_change().dropna()
        if len(ret) < 30:
            raise ValueError("too few observations for EWMA")
        opt_lambda = _safe(get_optimal_lambda, ret) or 0.94
        ewma_var_s = ewma_variance(ret, lambda_=opt_lambda)
        cur_var    = float(ewma_var_s.iloc[-1])
        if not np.isfinite(cur_var) or cur_var <= 0:
            raise ValueError("EWMA variance non-finite")
        daily_vol_pct = (cur_var ** 0.5) * 100
        var_1m = 1_000_000 * _norm.ppf(0.95) * (cur_var ** 0.5)
        sub = score_band(daily_vol_pct, EWMA_DAILY_VOL_BANDS)
        return ModelResult(
            key="ewma_var", label="EWMA Current Volatility",
            raw_value=round(daily_vol_pct, 3),
            display=f"{daily_vol_pct:.2f}% daily",
            sub_score=sub, status="ok", tier="premium",
            note=f"EWMA daily σ (λ={opt_lambda:.2f}). 1-day 95% VaR on ₹10 L position ≈ ₹{var_1m:,.0f}.",
        )
    except Exception:
        return _missing("ewma_var", "EWMA Current Volatility", "premium",
                        "Could not compute EWMA volatility.")


# ── Main entry point ──────────────────────────────────────────────────────────

def build_scorecard(ctx: ScoreContext, *, include_premium: bool = True) -> Scorecard:
    """Build a 4-pillar Scorecard. M4: 8 premium models (DCF, EPV, RI, ROIC, Altman, Beneish, Dual Mom, Kelly)."""
    data_warning: str | None = None

    # Safety check — if OHLCV is too short, flag and return all N/A
    if ctx.ohlcv is None or len(ctx.ohlcv) < 30:
        data_warning = "Insufficient price history — scorecard could not be computed."
        pillars = [_na_pillar(k) for k in PILLAR_ORDER]
        return Scorecard(
            ticker=ctx.ticker,
            as_of=dt.date.today().isoformat(),
            is_financial=ctx.is_financial,
            data_warning=data_warning,
            pillars=pillars,
            overall_score=None,
            overall_grade="N/A",
        )

    # ── Value pillar ──────────────────────────────────────────────────────────
    value_models = [
        _model_earnings_yield(ctx),
        _model_roc(ctx),
        _model_pe(ctx),
        _model_pb(ctx),
        _model_ev_sales(ctx),
        _model_ev_ebitda(ctx),                               # M3
        _model_graham(ctx),                                  # M3
        _model_peg(ctx),                                     # M3
        _model_dcf(ctx, include_premium=include_premium),    # M4 premium
        _model_epv(ctx, include_premium=include_premium),    # M4 premium
        _model_ri(ctx,  include_premium=include_premium),    # M4 premium
    ]
    value_pillar = _aggregate_pillar("value", value_models, VALUE_WEIGHTS)

    # ── Quality pillar ────────────────────────────────────────────────────────
    quality_models = [
        _model_roe(ctx),
        _model_de_ratio(ctx),
        _model_roce(ctx),                                          # M3
        _model_gross_margin(ctx),                                  # M3
        _model_piotroski(ctx),                                     # M3
        _model_revenue_cagr(ctx),                                  # M3
        _model_roic(ctx,    include_premium=include_premium),      # M4 premium
        _model_altman(ctx,  include_premium=include_premium),      # M4 premium
        _model_beneish(ctx, include_premium=include_premium),      # M4 premium
    ]
    quality_pillar = _aggregate_pillar("quality", quality_models, QUALITY_WEIGHTS)

    # ── Momentum pillar ───────────────────────────────────────────────────────
    momentum_models = [
        _model_tech_composite(ctx),
        _model_return_52wk(ctx),                                         # M3
        _model_ml_pup(ctx,          include_premium=include_premium),    # M2 premium
        _model_dual_momentum(ctx,   include_premium=include_premium),    # M4 premium
        _model_kelly(ctx,           include_premium=include_premium),    # M4 premium
    ]
    momentum_pillar = _aggregate_pillar("momentum", momentum_models, MOMENTUM_WEIGHTS)

    # ── Risk pillar ───────────────────────────────────────────────────────────
    risk_models = [
        _model_annual_vol(ctx),
        _model_max_drawdown(ctx),
        _model_sharpe(ctx),
        _model_sortino(ctx),
        _model_beta(ctx),
        _model_ewma_var(ctx, include_premium=include_premium),
    ]
    risk_pillar = _aggregate_pillar("risk", risk_models, RISK_WEIGHTS)

    pillars = [value_pillar, quality_pillar, momentum_pillar, risk_pillar]

    # ── Overall score (mean of graded pillars only) ───────────────────────────
    graded = [p for p in pillars if p.score is not None]
    overall_score = sum(p.score for p in graded) / len(graded) if graded else None
    overall_grade = to_letter(overall_score)

    return Scorecard(
        ticker=ctx.ticker,
        as_of=dt.date.today().isoformat(),
        is_financial=ctx.is_financial,
        data_warning=data_warning,
        pillars=pillars,
        overall_score=overall_score,
        overall_grade=overall_grade,
    )
