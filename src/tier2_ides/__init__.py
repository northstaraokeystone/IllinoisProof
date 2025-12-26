"""
IllinoisProof Tier 2: IDES Pandemic Fraud Detection

Detection focus: Identity theft patterns via cross-match gap exploitation

Key metrics:
- Total overpayments: $5.24B
- Recovered: $511.7M (10%)
- Non-recoverable (identity theft): $2.8B
- Cross-match suspension: 18 months (Mar 2020 - Sept 2021)
"""

from . import crossmatch
from . import recovery
from . import waiver

__all__ = ["crossmatch", "recovery", "waiver"]
