"""Repairs: propose plans, never execute without an explicit GO.

Modelled on ``NativeMaintenance`` (RIZALEON/RTHUNDR ``src/LocalBrain.swift``):
a proposal is NOT authorization or execution. ``propose()`` returns a plan
and touches nothing. ``apply()`` requires ``go=True`` and raises
:class:`~thundr_adapter.protocol.Refused` otherwise — and even with GO it
only executes steps whose action is on the explicit ``SAFE_ACTIONS``
allowlist. In v0.1 that allowlist holds no mutating action at all: real
repairs need a human-run, separately verified installer, exactly as the
native adapter requires. The human-approval path is:

    1. Call ``adapter.repair.propose`` (or ``thundr-adapter repair-propose``)
       and read the plan. The server stores the plan and returns a
       plan_id + nonce (approve-by-reference, mirroring RGHOSTKEY
       vc27/vc31: the approver sends id + nonce, never the payload).
    2. Rizal reviews the plan and gives an explicit GO for the exact steps.
    3. ``adapter.repair.apply`` loads the STORED plan by id + nonce and
       applies it. A human runs any refused step through a verified
       installer / the owning tool (e.g. ``build-mac.sh`` for the Mac
       app, ``thundr heal`` for float drift). The adapter never performs
       the install itself.
    4. Re-run ``adapter.diagnostics`` to verify the repair landed.

HARD RULE (RGHOSTKEY): the adapter never signs, seals, enrolls, or
mints — not even with GO. A plan step naming one of those actions is
refused outright. Signing happens only on the pinned device, by the
human, through RGHOSTKEY.
"""

from __future__ import annotations

import hmac
import secrets

from .protocol import NEVER_OPERATIONS, Refused

# Actions apply() is allowed to execute with GO. v0.1 intentionally holds
# no mutating action: the adapter proposes; humans (or verified installers)
# perform. Add an action here only with a design review + a test proving
# it is reversible and scoped.
SAFE_ACTIONS = frozenset({"noop"})

NOT_EXECUTED = "REPAIR PROPOSAL — NOT EXECUTED."


class PlanStore:
    """In-memory store for repair plans: approve-by-reference.

    Mirrors RGHOSTKEY vc27/vc31 approve: the approver sends only a plan
    id + nonce, and this store loads and checks the stored plan itself —
    the requester never sends the payload, so a tampered plan cannot be
    smuggled into apply(). Plans live only for the process lifetime
    (like the server's per-start token); there is no held unlock
    context, no timer, and no auto-approve — a stored plan is a
    proposal, not an authorization.
    """

    def __init__(self):
        self._plans: dict[str, dict] = {}

    def store(self, plan: dict) -> tuple[str, str]:
        """Store a plan. Returns (plan_id, nonce) for the approver."""
        plan_id = "tpa-plan-" + secrets.token_urlsafe(12)
        nonce = secrets.token_urlsafe(16)
        self._plans[plan_id] = {"plan": plan, "nonce": nonce}
        return plan_id, nonce

    def load(self, plan_id: str, nonce: str) -> dict:
        """Load a stored plan by id + nonce. Raises Refused on mismatch."""
        entry = self._plans.get(plan_id or "")
        if entry is None:
            raise Refused(
                "Unknown repair plan id: %r. Propose a plan first; "
                "approvals reference a stored plan, never a payload."
                % (plan_id,),
                rule="repair.apply approve-by-reference",
            )
        if not hmac.compare_digest(entry["nonce"], nonce or ""):
            raise Refused(
                "Repair plan nonce mismatch for %r. The approval must "
                "carry the nonce returned with the proposal." % (plan_id,),
                rule="repair.apply approve-by-reference",
            )
        return entry["plan"]

    def __len__(self):
        return len(self._plans)


def _step(step_id: str, action: str, target: str, detail: str,
          risk: str = "low", requires: str = "human approval + verified installer") -> dict:
    return {
        "id": step_id,
        "action": action,
        "target": target,
        "detail": detail,
        "risk": risk,
        "requires": requires,
        "executed": False,
    }


def propose(findings: dict | None = None) -> dict:
    """Build a repair plan from diagnostics/analyze findings. Never executes.

    ``findings`` is a diagnostics report (see ``diagnostics.run``) and/or
    an analyze report. Each finding maps to a plan step with a named
    action, target, and the approval it needs. Unknown findings produce a
    single "investigate" step — never a guessed repair.
    """
    findings = findings or {}
    steps: list[dict] = []
    n = 0

    def add(action, target, detail, risk="low"):
        nonlocal n
        n += 1
        steps.append(_step("R%02d" % n, action, target, detail, risk=risk))

    models = (findings.get("models") or {}) if isinstance(findings, dict) else {}
    if models and not models.get("exists"):
        add("reinstall-model", str(models.get("dir")),
            "Model directory is missing. A reviewed replacement artifact "
            "with verified provenance is required; install it through a "
            "supported installer after explicit human approval.",
            risk="high")
    identity = (models or {}).get("identity") or {}
    for spec in identity.get("specs", []):
        if not spec.get("ok"):
            add("replace-model", str(spec.get("file")),
                "Model identity check failed: %s. Replace with the reviewed "
                "artifact matching MODEL-IDENTITY.json (exact bytes + "
                "SHA-256) via a supported installer after human approval."
                % spec.get("reason"), risk="high")
    for name in (models or {}).get("skipped_symlinks", []):
        add("remove-symlink", name,
            "Symlinked model file skipped by inventory. A human should "
            "inspect it and replace it with a regular file if it is meant "
            "to be a model.", risk="medium")

    for service in (findings.get("services") or []):
        if not service.get("up") and service.get("port") in (8329, 8741):
            add("restart-service", "%s (:%s)" % (service.get("service"), service.get("port")),
                "Expected loopback service is not answering. Restart it "
                "through its own launcher (MCR: controlroom serve; gate: "
                "the ThundR gate launcher) after human approval.",
                risk="medium")

    drift = (findings.get("registry_diff") or {})
    if drift and not drift.get("in_sync", True):
        add("refresh-snapshot", "bundled thundr-commands.json",
            "Live registry differs from the bundled snapshot "
            "(added %d, removed %d, changed %d). Refresh the snapshot via "
            "adapter.update.apply with GO, or re-run gen-thundr-core.py."
            % (len(drift.get("added", [])), len(drift.get("removed", [])),
               len(drift.get("changed", {}))), risk="low")

    if not steps:
        steps.append(_step(
            "R00", "investigate", "findings",
            "No actionable finding was supplied. Run adapter.diagnostics "
            "and adapter.analyze first, then propose again from that report.",
            risk="low", requires="none"))
    return {
        "title": NOT_EXECUTED,
        "steps": steps,
        "step_count": len(steps),
        "executed": False,
        "approval_path": (
            "A proposal is not an installed repair. Rizal reviews this plan, "
            "gives an explicit GO for the exact steps, and a human performs "
            "the repair through a verified installer. Re-run diagnostics "
            "afterwards to verify."
        ),
    }


def apply(plan: dict, go: bool = False) -> dict:
    """Apply a repair plan. Requires explicit ``go=True``.

    Raises :class:`Refused` without GO. With GO, executes only steps whose
    action is on the ``SAFE_ACTIONS`` allowlist (v0.1: none mutating) and
    refuses every other step individually, returning a per-step report.
    Nothing outside the allowlist is ever executed by this function.
    """
    if not go:
        raise Refused(
            "Repair apply refused: no explicit GO. A repair proposal is not "
            "authorization. Rizal must approve the exact plan first.",
            rule="repair.apply requires go=True",
        )
    steps = plan.get("steps", []) if isinstance(plan, dict) else []
    report = {"applied": [], "refused": [], "executed_anything": False}
    for step in steps:
        action = step.get("action", "?")
        if action in NEVER_OPERATIONS:
            # HARD RULE: never performed by the adapter, not even with GO.
            report["refused"].append({
                "id": step.get("id"),
                "action": action,
                "reason": ("action %r is never performed by the adapter: "
                           "signing, sealing, enrolling, and minting happen "
                           "only on the pinned device, by the human, "
                           "through RGHOSTKEY" % action),
            })
        elif action in SAFE_ACTIONS:
            report["applied"].append({
                "id": step.get("id"), "action": action,
                "detail": "no-op executed (v0.1 allowlist holds no mutating action)",
            })
        else:
            report["refused"].append({
                "id": step.get("id"),
                "action": action,
                "reason": ("action %r is not on the v0.1 apply allowlist; "
                           "a human must perform it through a verified "
                           "installer" % action),
            })
    report["executed_anything"] = bool(report["applied"])
    report["note"] = (
        "v0.1 applies nothing mutating. Refused steps need a human-run "
        "installer; re-run diagnostics to verify afterwards."
    )
    return report
