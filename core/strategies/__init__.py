"""Strategy catalog registry."""
from .cross_sectional_mom import CrossSectionalMomentum
from .ivy_gtaa import IvyGTAA

CATALOG: dict[str, type] = {
    CrossSectionalMomentum.id: CrossSectionalMomentum,
    IvyGTAA.id:               IvyGTAA,
}

__all__ = ["CATALOG", "CrossSectionalMomentum", "IvyGTAA"]
