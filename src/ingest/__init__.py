"""
IllinoisProof Ingest Modules

Data ingestion from 47 public data sources across three tiers:
- Tier 1 (Dolton): comptroller, cook_county, foia
- Tier 2 (IDES): ides
- Tier 3 (Madigan): pacer, sunshine
"""

from . import comptroller
from . import cook_county
from . import pacer
from . import sunshine
from . import ides
from . import foia

__all__ = ["comptroller", "cook_county", "pacer", "sunshine", "ides", "foia"]
