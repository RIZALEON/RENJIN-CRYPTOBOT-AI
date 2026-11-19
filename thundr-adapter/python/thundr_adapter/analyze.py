"""Analysis: read-only file inspection, registry diffs, host parity checks.

Everything here reads and compares; nothing writes. File paths handed to
these functions must already be sandboxed by the caller (the server
applies ``safe_path`` before dispatch); the helpers below refuse
symlinks that escape the tree they are asked about.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from .registry import content_stamp

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def file_info(path: str | os.PathLike) -> dict:
    """Hash + structure of one file. Refuses symlinks (reports, never follows)."""
    target = Path(path)
    info = {"path": str(target), "exists": target.exists(),
            "is_symlink": target.is_symlink()}
    if not target.exists() or target.is_symlink() or not target.is_file():
        return info
    digest = hashlib.sha256()
    size = 0
    lines = 0
    try:
        with open(target, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                digest.update(chunk)
                size += len(chunk)
                lines += chunk.count(b"\n")
    except OSError as exc:
        info["error"] = str(exc)
        return info
    info["bytes"] = size
    info["sha256"] = digest.hexdigest()
    info["lines"] = lines
    return info


def registry_diff(live: dict, bundled: dict) -> dict:
    """Diff two registries by command id (live vs bundled snapshot).

    Compares the normalised JSON of each command, so a diff entry means
    real content changed, not key order. Added/removed/changed ids are
    reported; the full command bodies are included for changed ids only.
    """
    live_cmds = {c.get("id"): c for c in live.get("commands", [])}
    bundled_cmds = {c.get("id"): c for c in bundled.get("commands", [])}
    added = sorted(set(live_cmds) - set(bundled_cmds))
    removed = sorted(set(bundled_cmds) - set(live_cmds))
    changed = {}
    for cid in sorted(set(live_cmds) & set(bundled_cmds)):
        left = json.dumps(live_cmds[cid], ensure_ascii=False, sort_keys=True)
        right = json.dumps(bundled_cmds[cid], ensure_ascii=False, sort_keys=True)
        if left != right:
            changed[cid] = {"live": live_cmds[cid], "bundled": bundled_cmds[cid]}
    return {
        "live_version": live.get("version"),
        "bundled_version": bundled.get("version"),
        "live_stamp": content_stamp(live),
        "bundled_stamp": content_stamp(bundled),
        "live_count": len(live_cmds),
        "bundled_count": len(bundled_cmds),
        "added": added,
        "removed": removed,
        "changed": changed,
        "in_sync": not added and not removed and not changed,
    }


def host_check(hosts_path: str | os.PathLike,
               root: str | os.PathLike | None = None) -> dict:
    """Parity check from hosts.json: does every wired host's page/file exist?

    ``hosts.json`` (schema ``thundr.core.hosts.v2``) lists web float/scout
    hosts, the native helper, the Godot game and the Python command centre,
    each with a ``state`` (``wired`` / ``staged`` / ...). This check reads
    that map and verifies each listed path exists under ``root`` (default:
    the ``root`` field in hosts.json, ``~/R/ЯLAB/RCRYPTOFORGE``). Missing
    paths are reported, never created. ``@staging`` paths resolve against
    the ``staging`` field.
    """
    hosts_file = Path(hosts_path)
    outcome = {"hosts_file": str(hosts_file), "exists": hosts_file.exists(),
               "hosts": [], "wired": 0, "missing": 0}
    if not hosts_file.is_file():
        return outcome
    try:
        data = json.loads(hosts_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        outcome["error"] = "unreadable hosts.json: %s" % exc
        return outcome
    base = Path(root) if root is not None else Path(
        os.path.expanduser(data.get("root", "")))
    staging = Path(os.path.expanduser(data.get("staging", "")))

    def resolve(value: str) -> Path:
        if value.startswith("@staging/"):
            return staging / value[len("@staging/"):]
        if value.startswith("~/"):
            return Path(os.path.expanduser(value))
        return base / value

    entries = []
    for section in ("web", "native", "godot", "python", "installed"):
        for host in data.get(section, []):
            entries.append((section, host))
    for section, host in entries:
        rel = host.get("page") or host.get("file") or host.get("game") or ""
        target = resolve(rel) if rel else None
        present = bool(target and target.exists())
        state = str(host.get("state", ""))
        entry = {"section": section, "id": host.get("id"),
                 "state": state, "path": rel,
                 "resolved": str(target) if target else None,
                 "present": present}
        outcome["hosts"].append(entry)
        if state == "wired" and present:
            outcome["wired"] += 1
        elif state == "wired" and not present:
            outcome["missing"] += 1
    outcome["root"] = str(base)
    outcome["staging"] = str(staging)
    return outcome


def build_stamp_check(build_path: str | os.PathLike,
                      registry_data: dict) -> dict:
    """Compare a thundr-build.json stamp against a registry's live stamp.

    Follows the gen-thundr-core rule: the build number only bumps when the
    content sha256 changes. Reports whether the stamp matches the registry
    as it stands now (a mismatch means the registry changed since the last
    codegen run).
    """
    build_file = Path(build_path)
    outcome = {"build_file": str(build_file), "exists": build_file.exists(),
               "match": False}
    if not build_file.is_file():
        return outcome
    try:
        stamp = json.loads(build_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        outcome["error"] = "unreadable thundr-build.json: %s" % exc
        return outcome
    live = content_stamp(registry_data)
    outcome["build"] = stamp.get("build")
    outcome["stamped"] = stamp.get("stamped")
    outcome["recorded_sha256"] = stamp.get("content_sha256")
    outcome["live_sha256"] = live
    outcome["recorded_commands"] = stamp.get("commands")
    outcome["live_commands"] = len(registry_data.get("commands", []))
    outcome["match"] = stamp.get("content_sha256") == live
    return outcome


# -- .rzl parts catalog (RZL index) -----------------------------------
# The parts catalog for the THUNDR × RENJIN build, from the RZL index
# scan (RZL_INDEX.pdf, 81 pp, scan date 2026-11-04; digest in
# grounding/rzl-index-digest.md; 1,388 .rzl files across ~/R + iCloud).
# The digest is grounding; the full 4,286-line index text stays in the
# grounding folder and is NOT copied into the adapter tree.
# One entry postdates the scan: RbotLoadR 0.0.1 (UNSIGNED DRAFT) was
# supplied 2026-11-19 and closes index gap #0 as a draft — verified
# below against its manifest (sha256 + size + byte-identical .html).
RZL_INDEX = {
    "source": "RZL_INDEX.pdf (81 pp, scan date 2026-11-04)",
    "total_rzl_files": 1388,
    "components": [
        {"name": "RbotLoadR", "pieces": 1, "unique": 1, "size_mb": 0.01,
         "not_pure": 0, "status": "0.0.1 UNSIGNED DRAFT, verified",
         "version": "0.0.1",
         "sha256": ("d1ea6a6a5435ab90ecb2f623f2e4670f602753eb00e3d237c8b1612"
                    "c97c84aed"),
         "size_bytes": 7160,
         "note": ("MISSING in the index scan; 0.0.1 UNSIGNED DRAFT supplied "
                  "2026-11-19 (grounding/rbotloadr-0.0.1/). Single-file "
                  "HTML+JS pure .rzl loader (one HTML file with a .rzl "
                  "extension, NOT a ZIP), derived from RCOMMAND/HARDSHELL/"
                  "opener. Opens rzl.v1 eggs by picker/drag-drop, verifies "
                  "every manifest component (sha256 + size), mounts the "
                  "egg's index.html with read-only window.RZL_VFS; also "
                  "reads ENJIN-ASSEMBLY (rzl.enjin.assembly.v1) pins. No "
                  "network, no signing, no chain append. Manifest schema "
                  "rzl.rghostchain.enjin_egg.payload.v1, draft, "
                  "NOT_APPENDED, role loader. Verified 2026-11-19: sha256 "
                  "matches the manifest, size 7160 B, .rzl and .html "
                  "byte-identical. Awaits owner signing (RGHOSTKEY; "
                  "biometric optional, never required).")},
        {"name": "RVM", "pieces": 155, "unique": 13, "size_mb": 272.49,
         "not_pure": 23, "status": "COMPLETE as runtime",
         "note": ("RVM 0.1.0–0.1.4 + RVM-LINUX 0.1.1–0.1.2 (+android). "
                  "RVM-LINUX-0.1.0 not pure (raw .bin kernel/disk images; "
                  "0.1.1+ wrap them as .bin.js).")},
        {"name": "RGENERATR", "pieces": 27, "unique": 2, "size_mb": 13.09,
         "not_pure": 0, "status": "PARTIAL",
         "note": ("Only RGENERATOR 2.1.9 (egg5 rkey0, egg6 passkey), "
                  "both UNSIGNED. Adapter spec v1 + assets snapshot "
                  "supplied 2026-11-19 (grounding/rgeneratr/): RGENERATR "
                  "is the asset adapter — one writer "
                  "(rgen_asset_adapter.py reads the local RGHOSTCHAIN "
                  "jsonl + RTRACKR registry, never writes the chain) "
                  "producing out/assets.json (schema "
                  "rzl.rgeneratr.assets.v1) + .sha256 sidecar; readers "
                  "(TerraformЯ game wallet, ЯBOT wallet, rizal.pw "
                  "RWALLET, RTRACKR) never edit it. Assets stay PREVIEW "
                  "until a verified nft_mint block exists AND the seal "
                  "has a signature. Snapshot 2026-10-30: one asset "
                  "(rid-asset-0001-genesis), still PREVIEW awaiting "
                  "signed seal.")},
        {"name": "RBATIBABOX", "pieces": 137, "unique": 52, "size_mb": 985.37,
         "not_pure": 0, "status": "PRESENT",
         "note": ("BATIBABOX core/EMBED/LOG/SKILLS + bbx-lex pieces; some "
                  "members matched via manifest (e.g. notes-reader eggs) "
                  "— review.")},
        {"name": "RMIND", "pieces": 7, "unique": 7, "size_mb": 73.18,
         "not_pure": 0, "status": "PRESENT as memory docs only",
         "note": ("MACHINE-MIND, MACHINE-MIND-LIVE, DRAGON-SKULL-MIND, "
                  "machine-mind-2.1.4-android (rzl.doc.v1). No runner of "
                  "its own.")},
        {"name": "ЯSEED", "pieces": 255, "unique": 42, "size_mb": 69.15,
         "not_pure": 0, "status": "COMPLETE",
         "note": ("Only pure-.rzl model: RSEED 0.0.1–0.1.10 + "
                  "yaseed-0.1.9-android; tokenizer + ternary weights "
                  "(seed) + generate/train + manifest. Toy scale. "
                  "Pure-.rzl ancestor of RENJIN.")},
        {"name": "OTHER pure .RZL", "pieces": 777, "unique": 423,
         "size_mb": 3883.18, "not_pure": 7,
         "status": "skills, docs, eggs, logs",
         "note": ("Includes SCRIBE-UNIFIED-MASTER-20261104.RZL, "
                  "YAMANUAL-MERGED rev5/rev6, BOTABLETA notes. Not-pure "
                  "entries include ЯENJIN test embeds (BP-RZL-0027/0032/…"
                  ") — ENJIN test embeds exist but are not pure.")},
    ],
}

# Gaps the true build must still close (from the index digest).
# RbotLoadR-missing is NOT here: gap #0 closed as a draft on 2026-11-19
# (RbotLoadR 0.0.1 UNSIGNED DRAFT, verified — see RZL_AWAITING_SIGNING).
RZL_GAPS = (
    "RGENERATR is PARTIAL and UNSIGNED: only RGENERATOR 2.1.9.",
    "RMIND has no runner: memory docs only.",
    "RVM-LINUX-0.1.0 is not pure (raw .bin kernel/disk images).",
)

# Drafts that are verified but await owner signing (RGHOSTKEY; biometric optional, never required).
RZL_AWAITING_SIGNING = (
    "RbotLoadR 0.0.1 — UNSIGNED DRAFT, verified (sha256 d1ea6a6a…; "
    "NOT_APPENDED); owner signs with RGHOSTKEY later (biometric optional, never required).",
)


def component_check() -> dict:
    """Component presence against the RZL index parts catalog.

    Reports each component's status from the index scan and flags the
    gaps the true build must close. This is a catalog report, not a live
    filesystem scan: the adapter holds no .rzl inventory of its own, the
    digest carries no per-component paths, and the index (scan date
    2026-11-04) is the newest parts record — with the RbotLoadR 0.0.1
    draft (supplied 2026-11-19) applied on top. A live re-scan needs the
    Mac tree and the full index text in grounding/rzl-index.txt.
    """
    return {
        "index_source": RZL_INDEX["source"],
        "scan_date": "2026-11-04",
        "total_rzl_files": RZL_INDEX["total_rzl_files"],
        "components": [dict(c) for c in RZL_INDEX["components"]],
        "gaps": list(RZL_GAPS),
        "awaiting_signing": list(RZL_AWAITING_SIGNING),
        "note": ("Catalog report from the RZL index scan, not a live "
                 "filesystem scan. The full 4,286-line index text stays "
                 "in grounding/; this table is the digest."),
    }


# -- RGENERATR asset feed ---------------------------------------------
# Shape from RGENERATR-ADAPTER-SPEC-20261030.md (format v1, owner ThundR):
# one writer (rgen_asset_adapter.py) produces out/assets.json +
# out/assets.json.sha256 from the local RGHOSTCHAIN jsonl + RTRACKR
# registry and never writes the chain; every reader (TerraformЯ game
# wallet, ЯBOT wallet, rizal.pw RWALLET, RTRACKR) never edits the feed.
# "One place, one writer." Assets stay PREVIEW until a verified
# nft_mint block exists for the rid AND the seal has a signature; seals
# are written on the phone by RSIGN on Rizal's command (ES256/P-256, never a
# private key) and moved phone→Neo over USB via devicectl.
RGENERATR_ASSETS_SCHEMA = "rzl.rgeneratr.assets.v1"


def _sidecar_sha256(sidecar: Path) -> str | None:
    """Read a .sha256 sidecar: bare hex, or '<hex>  <filename>'."""
    try:
        text = sidecar.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    tokens = text.split()
    if not tokens:
        return None
    return tokens[0] if _SHA256_HEX.match(tokens[0]) else None


def rgeneratr_assets(feed_path: str | os.PathLike) -> dict:
    """Read-only report of an RGENERATR asset feed (out/assets.json).

    Knows the feed shape from the spec: schema
    ``rzl.rgeneratr.assets.v1``, owners[]/assets[], per-asset status /
    seal_hash / seal_sig_present / block / chain_verify /
    rtracker_status. Evaluates the live gate per asset — live ONLY when
    a verified nft_mint block exists for the rid AND the seal has a
    signature — and flags any feed whose status disagrees with the gate.
    Verifies the .sha256 sidecar when present.

    The adapter is a READER of this feed, like the wallets: it never
    writes assets.json, never signs, never mints. One place, one writer
    (rgen_asset_adapter.py).
    """
    feed = Path(feed_path)
    out = {"feed": str(feed), "exists": feed.exists(),
           "is_symlink": feed.is_symlink(), "schema_ok": False,
           "sidecar": {"present": False}, "owners": 0, "assets": [],
           "live": 0, "preview": 0}
    if not feed.exists() or feed.is_symlink() or not feed.is_file():
        return out
    try:
        raw = feed.read_bytes()
        data = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as exc:
        out["error"] = "unreadable assets.json: %s" % exc
        return out
    if not isinstance(data, dict):
        out["error"] = "assets.json is not a JSON object"
        return out
    out["schema"] = data.get("schema")
    out["schema_ok"] = data.get("schema") == RGENERATR_ASSETS_SCHEMA
    out["generated"] = data.get("generated")
    out["sources"] = data.get("sources")
    sidecar = Path(str(feed) + ".sha256")
    if sidecar.is_file() and not sidecar.is_symlink():
        expected = _sidecar_sha256(sidecar)
        actual = hashlib.sha256(raw).hexdigest()
        out["sidecar"] = {
            "present": True,
            "readable": expected is not None,
            "match": expected == actual if expected is not None else False,
        }
    owners = data.get("owners") or []
    out["owners"] = len(owners)
    for owner in owners:
        for asset in owner.get("assets") or []:
            verify = asset.get("chain_verify") or {}
            minted = (verify.get("ok") is True
                      and isinstance(verify.get("nft_mint_blocks_for_rid"), int)
                      and verify["nft_mint_blocks_for_rid"] >= 1)
            sealed = asset.get("seal_sig_present") is True
            gate_ok = minted and sealed
            status = str(asset.get("status", ""))
            entry = {
                "asset_id": asset.get("asset_id"),
                "label": asset.get("label"),
                "owner_handle": asset.get("owner_handle"),
                "rid": asset.get("rid"),
                "status": status,
                "seal_hash": asset.get("seal_hash"),
                "seal_sig_present": asset.get("seal_sig_present"),
                "block": asset.get("block"),
                "chain_verify": {
                    "ok": verify.get("ok"),
                    "blocks": verify.get("blocks"),
                    "nft_mint_blocks_for_rid": verify.get(
                        "nft_mint_blocks_for_rid"),
                    "errors": verify.get("errors"),
                },
                "rtracker_status": asset.get("rtracker_status"),
                "rtracker_asset_hash": asset.get("rtracker_asset_hash"),
                "wallet": asset.get("wallet"),
                "live_gate": {
                    "nft_mint_verified": minted,
                    "seal_signed": sealed,
                    "eligible": gate_ok,
                },
            }
            if status == "live":
                out["live"] += 1
                entry["gate_consistent"] = gate_ok
                if not gate_ok:
                    entry["flag"] = (
                        "INCONSISTENT: feed says live but the live gate "
                        "fails (nft_mint_verified=%s, seal_signed=%s)"
                        % (minted, sealed))
            elif status.startswith("preview"):
                out["preview"] += 1
                entry["gate_consistent"] = not gate_ok
                if gate_ok:
                    entry["flag"] = ("gate satisfied but feed still preview "
                                     "(writer has not flipped it yet)")
                else:
                    reasons = []
                    if not minted:
                        reasons.append(
                            "no verified nft_mint block for this rid")
                    if not sealed:
                        reasons.append("seal has no signature")
                    entry["preview_reason"] = "; ".join(reasons)
            else:
                entry["gate_consistent"] = False
                entry["flag"] = "unknown status value: %r" % status
            out["assets"].append(entry)
    return out


# -- Wallet snapshot (ЯWALET watch-only) -------------------------------
# The wallet is WATCH-ONLY for the adapter: it reads roster / snapshot /
# pool state only and never signs, sends, swaps, mints, or moves
# anything. Snapshot shape: rzl.rpotlatch.rtrackr.snapshot.v2 (public
# snapshot: entries, holders, wallets, token, pool). Every file is
# verified against its SHA256SUMS manifest pin when one is given — the
# manifest pattern from rbox.web.rwalet.SHA256SUMS (pin every web asset,
# verify on load). A mismatch is reported, never silently trusted. Note
# the pins point at the -2 variants: rtrackr-snapshot-2.json and
# rtrackr-button-2.js match their pins; the base snapshot/button files
# are older revisions and do NOT match (rtrackr-digest.md §1).
RTRACKR_SNAPSHOT_SCHEMA = "rzl.rpotlatch.rtrackr.snapshot.v2"


def _parse_sums_manifest(manifest_path: Path) -> dict:
    """Parse a SHA256SUMS manifest into {basename: (sha256, entry)}."""
    pins = {}
    try:
        text = manifest_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return pins
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        digest, name = parts[0], parts[-1]
        if not _SHA256_HEX.match(digest):
            continue
        pins[Path(name).name] = (digest, name)
    return pins


def _name_candidates(filename: str) -> list:
    """Filenames to try against manifest pins: the name itself, minus a
    trailing ``.bin`` (Rizal's uploads carry ``.bin``), and minus a
    ``-2``/``-3`` revision suffix (the manifest pins the shipped name,
    which is the -2 variant for the snapshot and button)."""
    names = [filename]
    if filename.endswith(".bin"):
        names.append(filename[:-4])
    for base in list(names):
        stripped = re.sub(r"-\d+(\.[^.]+)$", r"\1", base)
        if stripped != base:
            names.append(stripped)
    return names


def verify_manifest_pin(file_path: str | os.PathLike,
                        manifest_path: str | os.PathLike) -> dict:
    """Check one file against its SHA256SUMS manifest pin.

    Matches by basename, tolerating a trailing ``.bin`` on the local
    copy (Rizal's uploads carry ``.bin``) and a ``-2``/``-3`` revision
    suffix (the manifest pins the shipped name). Returns the pin, the
    actual hash, and whether they match. A missing pin is reported as
    ``pin_found: False`` — never treated as verified.
    """
    target = Path(file_path)
    manifest = Path(manifest_path)
    out = {"file": str(target), "manifest": str(manifest),
           "exists": target.exists(), "pin_found": False,
           "expected": None, "actual": None, "match": False,
           "manifest_entry": None}
    if not target.exists() or target.is_symlink() or not target.is_file():
        return out
    out["actual"] = file_info(target).get("sha256")
    pins = _parse_sums_manifest(manifest)
    for name in _name_candidates(target.name):
        if name in pins:
            out["expected"], out["manifest_entry"] = pins[name]
            out["pin_found"] = True
            break
    out["match"] = (out["pin_found"] and out["expected"] == out["actual"])
    return out


def wallet_snapshot(snapshot_path: str | os.PathLike,
                    manifest_path: str | os.PathLike | None = None) -> dict:
    """Read-only report of a wallet/roster snapshot (watch-only).

    Reads a public rtrackr snapshot (schema
    ``rzl.rpotlatch.rtrackr.snapshot.v2``): counts of entries/holders/
    wallets, the token summary, and the pool summary. When a SHA256SUMS
    manifest is given, the snapshot is verified against its pin and the
    outcome (verified / mismatch / no pin) is part of the report.
    Nothing here signs, sends, swaps, or moves anything.
    """
    snap = Path(snapshot_path)
    out = {"snapshot": str(snap), "exists": snap.exists(),
           "is_symlink": snap.is_symlink(), "schema_ok": False,
           "verification": {"checked": False,
                            "reason": "no manifest given"}}
    if not snap.exists() or snap.is_symlink() or not snap.is_file():
        return out
    try:
        data = json.loads(snap.read_bytes().decode("utf-8"))
    except (OSError, ValueError) as exc:
        out["error"] = "unreadable snapshot: %s" % exc
        return out
    if not isinstance(data, dict):
        out["error"] = "snapshot is not a JSON object"
        return out
    out["schema"] = data.get("schema")
    out["schema_ok"] = data.get("schema") == RTRACKR_SNAPSHOT_SCHEMA
    out["generated"] = data.get("generated")
    out["generated_label"] = data.get("generated_label")
    out["entries"] = len(data.get("entries") or [])
    out["holders"] = len(data.get("holders") or [])
    out["wallets"] = len(data.get("wallets") or [])
    # Live vs registered: entries mix two presentations of the same rows,
    # so count RIDs, not rows (rtrackr-digest.md §3). A row is LIVE only
    # with a sealed block behind it; "registered" with no block hash is
    # NOT live. Standing example: ThundR's wallet-RID row
    # (ЯID-0014-KREH) is registered but unsealed in both the snapshot
    # and the game feed, while the ThundR cryptobot row (block 2) IS
    # live. Report it as such, never as minted.
    entries = data.get("entries") or []
    rids = sorted({e.get("rid") for e in entries if e.get("rid")})
    live_rows = [e for e in entries
                 if e.get("mode") == "live" or e.get("status") == "live"]
    unsealed = [{"rid": e.get("rid"), "name": e.get("name"),
                 "kind": e.get("kind")}
                for e in entries
                if e.get("status") == "registered"
                and not e.get("block_hash")]
    out["distinct_rids"] = len(rids)
    out["rids"] = rids
    out["live_rows"] = len(live_rows)
    out["registered_unsealed"] = unsealed
    token = data.get("token") or {}
    out["token"] = {k: token.get(k) for k in
                    ("name", "symbol", "chain", "mint", "decimals",
                     "supply_ui", "token_program")}
    pool = data.get("pool") or {}
    out["pool"] = {k: pool.get(k) for k in
                   ("dex", "pool_type", "pair", "address",
                    "liquidity_usd", "price_usd", "price_sol")}
    out["sources"] = data.get("sources")
    if manifest_path is not None:
        check = verify_manifest_pin(snap, manifest_path)
        out["verification"] = {
            "checked": True,
            "pin_found": check["pin_found"],
            "match": check["match"],
            "expected": check["expected"],
            "actual": check["actual"],
            "manifest_entry": check["manifest_entry"],
            "verdict": ("verified" if check["match"] else
                        "MISMATCH: file does not match its manifest pin"
                        if check["pin_found"] else
                        "no pin for this file in the manifest"),
        }
    return out
