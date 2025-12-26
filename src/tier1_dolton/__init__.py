"""
IllinoisProof Tier 1: Dolton/Local Government Detection

Detection focus: Cascade from expense anomalies → deficit → vendor concentration

Red flags documented:
- $779K credit card expenditures missing receipts
- Police overtime: 332 hours in 336-hour pay period
- O.A.K.K. Construction: $200K+ before bribery guilty plea
- $33,027 Amazon purchase (single transaction)
"""

from . import credit_card
from . import vendor
from . import overtime

__all__ = ["credit_card", "vendor", "overtime"]
