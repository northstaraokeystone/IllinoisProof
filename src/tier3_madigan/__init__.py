"""
IllinoisProof Tier 3: Madigan/ComEd Institutional Detection

Detection focus: Network entropy - PAC contributions correlating with legislation

Key entities:
- Friends of Michael J Madigan #665: $6.1M cash
- ComEd (via executives): contributor
- No-work recipients: Olivo, Nice, Acevedo ($4K-5K/month)
- SB 1652: Energy Infrastructure Modernization Act (bribery proven)
"""

from . import pac_network
from . import legislation
from . import nowork

__all__ = ["pac_network", "legislation", "nowork"]
