"""Updates: check versions/build stamps, apply only with an explicit GO.

No network is involved: "update available" here means the canonical
registry on this machine is newer (different content stamp) than the
bundled snapshot, or the recorded build stamp no longer matches the
registry. ``check()`` only reads. ``apply()`` requires ``go=True`` and
raises :class:`~thundr_adapter.protocol.Refused` otherwise; with GO it
performs exactly one safe, reversible update — refreshing the bundled
snapshot from the canonical registry — after verifying the schema.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from .analyze import (RZL_AWAITING_SIGNING, RZL_GAPS, build_stamp_check,
                      registry_diff)
from .protocol import Refused
from .registry import BUNDLED_SNAPSHOT, SCHEMA, content_stamp


def open_items() -> dict:
    """Known open items from the RZL index parts catalog.

    Report only — the adapter never auto-fixes these. Closing them is
    build work (completing/signing RGENERATR, giving RMIND a runner),
    not an adapter update. RbotLoadR-missing is NOT listed: gap #0
    closed as a draft on 2026-11-19 (RbotLoadR 0.0.1, verified) and now
    awaits owner signing instead.
    """
    return {
        "source": "RZL index scan 2026-11-04 (grounding/rzl-index-digest.md)",
        "items": list(RZL_GAPS),
        "awaiting_signing": list(RZL_AWAITING_SIGNING),
        "note": ("Known open items from the parts catalog. Report only — "
                 "the adapter never auto-fixes them."),
    }


def check(canonical_path=None, build_path=None) -> dict:
    """Compare canonical registry vs bundled snapshot vs build stamp.

    Returns versions, stamps, the registry diff summary, and whether an
    update is available. Read-only.
    """
    from .registry import Registry, resolve_registry_path

    bundled = json.loads(BUNDLED_SNAPSHOT.read_text(encoding="utf-8"))
    try:
        live_path = resolve_registry_path(canonical_path)
        live = json.loads(Path(live_path).read_text(encoding="utf-8"))
        live_source = str(live_path)
    except (OSError, ValueError) as exc:
        return {
            "update_available": False,
            "live_source": None,
            "bundled_version": bundled.get("version"),
            "bundled_stamp": content_stamp(bundled),
            "open_items": open_items(),
            "error": "canonical registry unreadable: %s" % exc,
        }
    diff = registry_diff(live, bundled)
    out = {
        "live_source": live_source,
        "live_version": live.get("version"),
        "live_stamp": diff["live_stamp"],
        "bundled_version": bundled.get("version"),
        "bundled_stamp": diff["bundled_stamp"],
        "in_sync": diff["in_sync"],
        "added": diff["added"],
        "removed": diff["removed"],
        "changed_ids": sorted(diff["changed"].keys()),
        "update_available": not diff["in_sync"],
        "open_items": open_items(),
    }
    if build_path is not None:
        out["build_stamp"] = build_stamp_check(build_path, live)
    if live_source == str(BUNDLED_SNAPSHOT):
        out["note"] = ("No canonical registry on this machine; live source "
                       "is the bundled snapshot itself, so no update is "
                       "available.")
        out["update_available"] = False
    return out


def apply(go: bool = False, canonical_path=None, expected_stamp=None) -> dict:
    """Refresh the bundled snapshot from the canonical registry.

    Requires explicit ``go=True``. Verifies the canonical file is a
    ``thundr.core.commands.v1`` registry before copying, writes via a
    temporary file + atomic replace, and re-stamps the snapshot metadata.
    When ``expected_stamp`` is given (the live_stamp from
    ``adapter.update.check``), the refresh is content-bound: it refuses
    when the canonical registry changed since the check, so an approval
    can never land on different content than was reviewed. This is the
    only update v0.1 performs; app/model updates need a human-run
    verified installer.
    """
    if not go:
        raise Refused(
            "Update apply refused: no explicit GO. Run adapter.update.check "
            "first and have Rizal approve the exact update.",
            rule="update.apply requires go=True",
        )
    from .registry import resolve_registry_path

    canonical = Path(resolve_registry_path(canonical_path))
    if canonical.resolve() == BUNDLED_SNAPSHOT.resolve():
        return {"applied": False,
                "reason": "canonical source is the bundled snapshot itself; nothing to refresh"}
    try:
        data = json.loads(canonical.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Refused("Update refused: canonical registry unreadable: %s" % exc) from exc
    if data.get("schema") != SCHEMA:
        raise Refused("Update refused: canonical file is not a %s registry" % SCHEMA)
    if expected_stamp is not None and content_stamp(data) != expected_stamp:
        raise Refused(
            "Update refused: the canonical registry changed since the "
            "check (content stamp mismatch). Re-run adapter.update.check "
            "and approve the new content.",
            rule="update.apply content-bound",
        )
    tmp = BUNDLED_SNAPSHOT.with_suffix(".json.tmp-tpa")
    try:
        shutil.copyfile(canonical, tmp)
        os.replace(tmp, BUNDLED_SNAPSHOT)
    finally:
        if tmp.exists():
            tmp.unlink()
    stamp = content_stamp(data)
    meta_path = BUNDLED_SNAPSHOT.parent / "snapshot.json"
    meta = {
        "source": str(canonical),
        "refreshed_by": "adapter.update.apply (GO)",
        "content_sha256": stamp,
        "commands": len(data.get("commands", [])),
        "version": data.get("version"),
    }
    meta_tmp = meta_path.with_suffix(".json.tmp-tpa")
    try:
        meta_tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
        os.replace(meta_tmp, meta_path)
    finally:
        if meta_tmp.exists():
            meta_tmp.unlink()
    return {"applied": True, "source": str(canonical),
            "commands": len(data.get("commands", [])),
            "content_sha256": stamp,
            "note": "Bundled snapshot refreshed. Re-run diagnostics to verify."}
