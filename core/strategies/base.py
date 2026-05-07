"""Strategy base class and shared data types."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal
import pandas as pd


@dataclass
class ParamSpec:
    name:     str
    type:     Literal['int', 'float', 'enum', 'bool']
    default:  Any
    label:    str
    help:     str
    min:      float | None = None
    max:      float | None = None
    choices:  list[str] | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in vars(self).items() if v is not None or k in ('min', 'max')}


@dataclass
class Trade:
    date:          str
    ticker:        str
    side:          str    # 'buy' | 'sell'
    value:         float  # notional ₹
    price:         float
    cost_total:    float
    cost_breakdown: dict[str, float]


@dataclass
class BacktestResult:
    strategy_id:    str
    equity_curve:   list[dict]  # {date, value}
    benchmark_curve: list[dict]  # {date, value}
    drawdown_curve: list[dict]  # {date, dd_pct}
    trade_log:      list[dict]
    kpis:           dict[str, Any]
    params:         dict
    universe:       str
    start_date:     str
    end_date:       str
    brokerage_id:   str
    total_cost:     float
    survivorship_bias_warning: bool = True


class Strategy(ABC):
    id:          str
    label:       str
    description: str
    reference:   str
    BASIC_PARAMS:    list[ParamSpec] = field(default_factory=list)
    ADVANCED_PARAMS: list[ParamSpec] = field(default_factory=list)
    REQUIRES_FUNDAMENTALS: bool = False

    @classmethod
    def catalog_entry(cls) -> dict:
        return {
            "id":                    cls.id,
            "label":                 cls.label,
            "description":           cls.description,
            "reference":             cls.reference,
            "requires_fundamentals": cls.REQUIRES_FUNDAMENTALS,
            "basic_params":          [p.to_dict() for p in cls.BASIC_PARAMS],
            "advanced_params":       [p.to_dict() for p in cls.ADVANCED_PARAMS],
        }

    @abstractmethod
    def generate_signals(
        self,
        prices:       pd.DataFrame,
        fundamentals: dict | None,
        params:       dict,
    ) -> pd.DataFrame:
        """Return weights_df: index=rebalance dates, cols=tickers, values=weight (0-1, sum≤1)."""
        ...
