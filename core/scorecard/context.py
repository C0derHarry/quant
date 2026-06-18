from dataclasses import dataclass, field
from typing import Optional
import pandas as pd


@dataclass
class ScoreContext:
    """
    Carries all pre-fetched data into build_scorecard. The route is responsible
    for fetching; this class is pure data — no yfinance / FastAPI imports.
    """
    ticker: str
    ohlcv: pd.DataFrame              # Daily OHLCV for the target ticker; must have 'Close' column
    benchmark_ohlcv: pd.DataFrame    # Daily OHLCV for Nifty 50 (^NSEI); must have 'Close' column
    is_financial: bool = False       # True for banks/NBFCs — skips inapplicable models

    # Pre-computed by the route (so engine stays decoupled from API layer)
    tech_summary: Optional[dict] = None  # {'bull_ratio', 'bullish', 'bearish', 'neutral', 'total', 'verdict'}

    # M2+ fundamentals (None = not yet fetched → pillar returns N/A)
    financials: Optional[pd.DataFrame] = None
    balance_sheet: Optional[pd.DataFrame] = None
    cash_flow: Optional[pd.DataFrame] = None
    info: Optional[dict] = None

    # M2+ ML signal (pre-computed by route to keep engine pure)
    ml_p_up: Optional[float] = None  # calibrated P(5-day up) from GBM; None = not available

    # M4+ factor models
    peers: Optional[dict] = None     # {ticker: {'info': dict, ...}}
