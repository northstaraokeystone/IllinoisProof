"""
IllinoisProof Detection Modules

Core fraud detection methodologies:
- benford: Benford's Law first/second digit analysis
- entropy: Shannon entropy + compression ratio
- cascade: Cross-tier cascade detection
- network: PAC-to-legislation network analysis
- identity: Identity theft pattern detection
"""

from . import benford
from . import entropy
from . import cascade
from . import network
from . import identity

__all__ = ["benford", "entropy", "cascade", "network", "identity"]
