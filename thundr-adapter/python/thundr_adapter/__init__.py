"""ThundR Plugin Adapter (TPA) v0.1 — reference implementation.

Lets any bot or AI (including Muse) communicate with ThundR, run
diagnostics, analysis, debugging, repair proposals, update checks, and
visual integrations — offline-first, loopback-only, GO-gated for anything
that mutates state.

Grounding: the canonical THUNDR-CORE registry (thundr-commands.json), the
MCR command centre (controlroom.py), thundr_chat.py, the A2 Swift core,
the Linux Python port, and the RENJIN-CRYPTOBOT-AI backroom rules. See
ADAPTER.md in the repository root for the full spec and the trace table.
"""

from .protocol import ADAPTER_VERSION as __version__
from .protocol import VERSION as PROTOCOL_VERSION

__all__ = ["__version__", "PROTOCOL_VERSION"]
