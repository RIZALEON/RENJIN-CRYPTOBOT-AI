"""ThundR Plugin Adapter (TPA) — protocol envelope, method table, errors.

Protocol version ``tpa.v1``. Every adapter call, local or over the loopback
HTTP server, returns the same envelope shape, modelled on the LocalBrain
``call(tool:text:done:)`` bridge result (``{ok, via, reply}``) from
RIZALEON/RTHUNDR ``src/LocalBrain.swift`` (branch
``feature/native-diagnostics``):

    {"ok": true,  "via": "<route>", "data": {...}}        # data calls
    {"ok": true,  "via": "<route>", "reply": "<text>"}    # chat calls
    {"ok": false, "via": "<route>", "error": "<reason>"}  # failures
    {"ok": false, "via": "<route>", "refused": true,
     "reply": "<refuse reply>"}                           # GO/refuse refusals
    {"ok": false, "via": "<route>", "go_gated": true,
     "error": "go-gated", "reply": "<handoff>"}           # wallet/signing
                                                          # verbs: not forbidden,
                                                          # need Rizal's explicit
                                                          # GO for that exact action

``via`` always names the route that answered, so a caller can tell a live
brain reply from a registry fallback from an offline note. Nothing here ever
fakes a live brain reply: when no brain is reachable, ``via`` says so.
"""

from __future__ import annotations

VERSION = "tpa.v1"
ADAPTER_VERSION = "0.1.1"
ADAPTER_NAME = "ThundR Plugin Adapter"

# The twelve tpa.v1 methods. Names are stable; new methods arrive as
# tpa.v2, never by silently changing these.
METHODS = (
    "adapter.hello",
    "adapter.commands.list",
    "adapter.commands.get",
    "adapter.chat",
    "adapter.diagnostics",
    "adapter.analyze",
    "adapter.debug",
    "adapter.repair.propose",
    "adapter.repair.apply",
    "adapter.update.check",
    "adapter.update.apply",
    "adapter.visual",
)

# Methods that only read. Everything else is gated or plan-only.
READ_ONLY_METHODS = frozenset(
    {
        "adapter.hello",
        "adapter.commands.list",
        "adapter.commands.get",
        "adapter.chat",
        "adapter.diagnostics",
        "adapter.analyze",
        "adapter.debug",
        "adapter.repair.propose",
        "adapter.update.check",
        "adapter.visual",
    }
)

# Methods that mutate state and therefore require an explicit GO.
GO_GATED_METHODS = frozenset(
    {
        "adapter.repair.apply",
        "adapter.update.apply",
    }
)

# Operations the adapter NEVER performs — not even with GO. Like ThundR,
# the adapter routes approval requests (request/queue only); signing,
# sealing, enrolling, and minting happen only on the pinned device, by
# the human, through RGHOSTKEY (one interface, same method names
# everywhere; per-device pinned keys; nothing shared). And the wallet is
# WATCH-ONLY for the adapter: it never sends, swaps, or transfers
# anything — it reads roster / snapshot / pool state only. There is no
# tpa.v1 method for any of these, and repair.apply refuses a step whose
# action names one of them.
NEVER_OPERATIONS = frozenset({"sign", "seal", "enroll", "mint",
                              "send", "swap", "transfer"})


class Refused(Exception):
    """Raised when an action is refused: GO-only, or a refuse-rule match.

    Carries the human-readable refusal in ``reply`` so callers can surface
    it verbatim instead of inventing their own wording.
    """

    def __init__(self, reply: str, rule: str | None = None):
        super().__init__(reply)
        self.reply = reply
        self.rule = rule


class ProtocolError(ValueError):
    """Malformed request: unknown method, wrong shapes, bad parameters."""


def ok(via: str, data=None, reply: str | None = None) -> dict:
    """Build a success envelope. ``data`` for structured calls, ``reply`` for chat."""
    out = {"ok": True, "via": via}
    if data is not None:
        out["data"] = data
    if reply is not None:
        out["reply"] = reply
    return out


def fail(error: str, via: str | None = None, refused: bool = False,
         reply: str | None = None) -> dict:
    """Build a failure envelope. ``refused=True`` marks a GO/refuse refusal."""
    out = {"ok": False, "error": error}
    if via is not None:
        out["via"] = via
    if refused:
        out["refused"] = True
    if reply is not None:
        out["reply"] = reply
    return out


def refused_reply(reply: str, via: str, rule: str | None = None) -> dict:
    """Build a refusal envelope from a registry refuse reply."""
    out = {"ok": False, "via": via, "refused": True, "reply": reply,
           "error": "refused"}
    if rule is not None:
        out["rule"] = rule
    return out


def go_gated_reply(reply: str, via: str, verb: str | None = None) -> dict:
    """Build a GO-gated envelope for wallet/signing verbs.

    Distinct from ``refused``: the action is not forbidden, it needs
    Rizal's explicit GO for that exact action — his command is
    sufficient authorization for the live /rmint/request flow; no
    biometric step is required. Nothing was run.
    """
    out = {"ok": False, "via": via, "go_gated": True,
           "error": "go-gated", "reply": reply}
    if verb is not None:
        out["verb"] = verb
    return out


def validate_request(obj) -> tuple[str, dict]:
    """Validate a decoded JSON request body. Returns (method, params).

    Accepts ``{"method": "...", "params": {...}}``. ``params`` defaults to
    ``{}`` when absent. Raises :class:`ProtocolError` on anything else.
    """
    if not isinstance(obj, dict):
        raise ProtocolError("request must be a JSON object")
    method = obj.get("method")
    if not isinstance(method, str) or method not in METHODS:
        raise ProtocolError("unknown method: %r" % (method,))
    params = obj.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ProtocolError("params must be a JSON object")
    return method, params


def hello_data() -> dict:
    """Payload for adapter.hello: identity, versions, methods, safety stance."""
    return {
        "adapter": ADAPTER_NAME,
        "adapter_version": ADAPTER_VERSION,
        "protocol": VERSION,
        "methods": list(METHODS),
        "read_only": sorted(READ_ONLY_METHODS),
        "go_gated": sorted(GO_GATED_METHODS),
        "never": sorted(NEVER_OPERATIONS),
        "transport": "loopback-only (127.0.0.1)",
        "offline": True,
    }
