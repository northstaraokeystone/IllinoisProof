"""
IllinoisProof Output Modules

Dual output formats:
- citizen: Tweet-ready, dashboard-friendly summaries
- fbi: NIST IR 8387 chain-of-custody, prosecution-ready
- auditor: Illinois Auditor General format compatibility
"""

from . import citizen
from . import fbi
from . import auditor

__all__ = ["citizen", "fbi", "auditor"]
