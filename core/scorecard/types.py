from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ModelResult:
    key: str
    label: str
    raw_value: Optional[float]
    display: str
    sub_score: Optional[float]    # 0–100; None = not computed
    status: str                   # 'ok' | 'partial' | 'missing'
    tier: str                     # 'free' | 'premium'
    note: Optional[str]

    def to_dict(self) -> dict:
        return {
            "key":        self.key,
            "label":      self.label,
            "raw_value":  self.raw_value,
            "display":    self.display,
            "sub_score":  round(self.sub_score, 1) if self.sub_score is not None else None,
            "status":     self.status,
            "tier":       self.tier,
            "note":       self.note,
        }


@dataclass
class PillarResult:
    key: str
    label: str
    score: Optional[float]        # 0–100 weighted mean of ok/partial models; None if no data
    grade: str                    # 'A'–'F' | 'N/A'
    verdict: str
    models: list[ModelResult] = field(default_factory=list)
    coverage: float = 0.0         # fraction of models that are ok or partial

    def to_dict(self) -> dict:
        return {
            "key":      self.key,
            "label":    self.label,
            "score":    round(self.score, 1) if self.score is not None else None,
            "grade":    self.grade,
            "verdict":  self.verdict,
            "coverage": round(self.coverage, 2),
            "models":   [m.to_dict() for m in self.models],
        }


@dataclass
class Scorecard:
    ticker: str
    as_of: str
    is_financial: bool
    data_warning: Optional[str]
    pillars: list[PillarResult] = field(default_factory=list)
    overall_score: Optional[float] = None
    overall_grade: str = "N/A"

    def to_dict(self) -> dict:
        return {
            "ticker":        self.ticker,
            "as_of":         self.as_of,
            "is_financial":  self.is_financial,
            "data_warning":  self.data_warning,
            "overall": {
                "score": round(self.overall_score, 1) if self.overall_score is not None else None,
                "grade": self.overall_grade,
            },
            "pillars": [p.to_dict() for p in self.pillars],
        }
