"""RGHOSTCHAIN access: READ-ONLY, loopback-only, allowlisted.

The adapter understands the ledger but never writes to it. The submit
daemon (rghostchain_submitd.py, 127.0.0.1:8741, stdlib only) owns the
chain; the adapter may only read it through four GET endpoints. Every
write endpoint is refused, by name, in :func:`check_chain_call` — there
is no code path in this package that POSTs to the chain.

Allowed (GET only):
  /health          block counts + validity, real and DRY chains
  /rtrackr/assets  game-asset feed
  /market/view     DRY market lane (read-only)
  /market/verify   DRY market lane (read-only)

Refused (never called, in any method):
  POST /rghostchain/submit   append a block
  POST /rtrackr/register     register a rid/block
  POST /rtrackr/ingest       rebuild the feed
  POST /market/submit        DRY market submit

DRY by default: the daemon writes nft_mint blocks to the DRY-SUBMIT
chain unless started with --real (Rizal) AND given a verified RSIGN
seal (owner_rid == asset.rid) AND mode live. Since 2026-11-18 (pt62u),
LIVE mints additionally need a minter proof from ThundR's or GIZMO's
own registered key in the sha-pinned registry, else 403; the block
records minter / minter_device / minted_by.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from .protocol import Refused

DAEMON_PORT = 8741
DAEMON_TIMEOUT = 2.0

# RTRACKR schemas (rtrackr-digest.md).
GAME_ASSETS_SCHEMA = "rzl.rtrackr.game-assets.v1"
MINTER_REQUEST_SCHEMA = "rzl.rmint.minter-request.v1"
MINTERS = ("thundr", "gizmo")

# GET endpoints the adapter is allowed to call on the daemon.
CHAIN_READ_PATHS = frozenset({
    "/health",
    "/rtrackr/assets",
    "/market/view",
    "/market/verify",
})

# Write endpoints the adapter must NEVER call. Refused by name, in any
# method, even with GO: the adapter never submits, registers, ingests,
# or mints. Humans and the daemon own the chain.
CHAIN_REFUSED_WRITES = frozenset({
    "/rghostchain/submit",
    "/rtrackr/register",
    "/rtrackr/ingest",
    "/market/submit",
})

# Block types from the RGHOSTCHAIN digest (rghostchain_submitd.py).
BLOCK_TYPES = (
    "genesis",
    "cryptobot_mint",
    "nft_mint",
    "transfer",
    "note",
    "convert",
    "index",
)


def check_chain_call(method: str, path: str) -> None:
    """Enforce the read-only rule. Raises Refused for anything disallowed.

    Only GET of an allowlisted read path passes. A refused write path is
    refused by name; anything else is refused as not allowlisted.
    """
    clean = (path or "").split("?", 1)[0]
    if method != "GET":
        raise Refused(
            "Chain write refused: the adapter never calls %s %s. It is "
            "read-only against RGHOSTCHAIN (GET /health, /rtrackr/assets, "
            "/market/view, /market/verify only)."
            % (method, clean),
            rule="chain read-only",
        )
    if clean in CHAIN_REFUSED_WRITES:
        raise Refused(
            "Chain write refused: %s is a write endpoint the adapter must "
            "never call. Humans and the daemon own the chain." % clean,
            rule="chain read-only",
        )
    if clean not in CHAIN_READ_PATHS:
        raise Refused(
            "Chain path refused: %s is not on the adapter's read allowlist "
            "(GET /health, /rtrackr/assets, /market/view, /market/verify)."
            % clean,
            rule="chain read-only",
        )


def chain_get(path: str, port: int = DAEMON_PORT,
              timeout: float = DAEMON_TIMEOUT):
    """Loopback GET against the daemon. Returns (status, decoded-or-None).

    Returns (0, None) when the daemon does not answer. Raises Refused
    for any path outside the read allowlist — before any request is made.
    """
    check_chain_call("GET", path)
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:%d%s" % (port, path), timeout=timeout
        ) as resp:
            raw = resp.read()
            try:
                return resp.status, json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                return resp.status, raw.decode("utf-8", "replace")[:2000]
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except Exception:
        return 0, None


def daemon_health(port: int = DAEMON_PORT) -> dict:
    """Report the submit daemon's health from GET /health (read-only).

    Follows the daemon's own /health payload (rghostchain_submitd.py):
    real_flag, real/dry block counts + validity, verifier presence, and
    the trust-registry pin state — the pin state is the minter-gate
    signal, since the ThundR/GIZMO-only LIVE minter gate checks proofs
    against the sha-pinned registry. Tips (latest block hashes) are NOT
    in /health and are reported as unknown rather than invented.
    """
    out = {
        "port": port,
        "up": False,
        "mode": "unknown",
        "real": None,
        "dry": None,
        "verifier_present": None,
        "minter_gate": {"status": "unknown", "registry_pin_valid": None},
        "tips": None,
        "tips_note": ("/health carries block counts and validity, not tip "
                      "hashes; tips are unknown to the adapter."),
    }
    status, body = chain_get("/health", port=port)
    if status != 200 or not isinstance(body, dict):
        out["detail"] = ("unreachable" if status == 0
                         else "HTTP %d" % status)
        return out
    out["up"] = True
    out["service"] = body.get("service")
    real_flag = body.get("real_flag") is True
    out["mode"] = ("live-capable (started with --real; LIVE still needs a "
                   "verified RSIGN seal + minter proof per submit)"
                   if real_flag else
                   "dry-only (DRY-SUBMIT chain; LIVE needs --real)")
    out["real_flag"] = real_flag
    out["real"] = {"blocks": body.get("real_blocks"),
                   "valid": body.get("real_valid")}
    out["dry"] = {"blocks": body.get("dry_blocks"),
                  "valid": body.get("dry_valid")}
    out["verifier_present"] = body.get("verifier_present")
    pin_valid = body.get("trust_registry_pin_valid")
    out["minter_gate"] = {
        "status": ("operational (ThundR/GIZMO-only LIVE minter gate; "
                   "sha-pinned registry loads)" if pin_valid is True else
                   "registry unavailable (pinned registry does not load; "
                   "LIVE minting cannot verify minters)" if pin_valid is False
                   else "unknown"),
        "registry_pin_valid": pin_valid,
        "registry_path_present": body.get("trust_registry_path_present"),
    }
    return out


# -- RTRACKR: the adapter's read surface for chain state ---------------
# RTRACKR is the public tracker / read layer for RGHOSTCHAIN: the chain
# stays local, RTRACKR publishes a scrubbed public view (registry rows,
# Я token, Orca pool, holders, wallets). The adapter reads it the way
# the feed readers do (rtrackr-feed.js, rtrackr_feed.gd): live API
# (GET /rtrackr/assets on the daemon) → derived game-assets JSON →
# cached copy. Every report names the source that served it and its
# timestamp: the baked snapshot (2026-11-10) goes stale, the game feed
# (2026-11-18) is newer, and a snapshot value is never a live balance.


def is_live_asset(asset: dict) -> bool:
    """Live = on_chain true AND a signature present.

    The feed's own rule (rtrackr-digest.md): ``is_live(asset)`` is
    on_chain true and a non-empty sig; the JS readers also accept
    status "live" as a shortcut. "Registered" is not live: ThundR's
    wallet-RID row (ЯID-0014-KREH) is registered, on_chain false, no
    block hash — report it as such, never as minted.
    """
    if not isinstance(asset, dict) or asset.get("on_chain") is not True:
        return False
    sig = asset.get("sig") or asset.get("signature")
    if isinstance(sig, str) and sig.strip():
        return True
    return asset.get("status") == "live"


def _summarise_feed(data: dict, source: str) -> dict:
    """Summarise a game-assets feed payload (any source)."""
    assets = data.get("assets") or []
    summaries = []
    for asset in assets:
        block = asset.get("block") or {}
        summaries.append({
            "rid": asset.get("rid"),
            "kind": asset.get("kind"),
            "status": asset.get("status"),
            "on_chain": asset.get("on_chain"),
            "block_height": block.get("height"),
            "block_hash": asset.get("block_hash"),
            "is_live": is_live_asset(asset),
        })
    return {
        "source": source,
        "generated": data.get("generated"),
        "schema": data.get("schema"),
        "schema_ok": data.get("schema") == GAME_ASSETS_SCHEMA,
        "live": data.get("live"),
        "dry": data.get("dry"),
        "chain_valid": data.get("chain_valid"),
        "history_height": data.get("history_height"),
        "assets": summaries,
        "note": ("Source + timestamp are part of the data: a baked or "
                 "cached value is never a live balance."),
    }


def _read_feed_file(path) -> dict | None:
    """Read a game-assets JSON file. None when missing/unreadable/wrong shape."""
    if path is None:
        return None
    target = Path(path)
    if target.is_symlink() or not target.is_file():
        return None
    try:
        data = json.loads(target.read_bytes().decode("utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def rtrackr_feed(port: int = DAEMON_PORT, derived_path=None,
                 cache_path=None) -> dict:
    """Read RTRACKR chain state in the feed reader's own order.

    1. Live API: GET /rtrackr/assets on the daemon (loopback :8741).
    2. Derived game-assets JSON file (when a path is given).
    3. Cached copy (when a path is given).
    4. Nothing: source None, detail says why.

    Always reports which source served the data and its generated
    timestamp. Read-only: this never calls the submit/register/ingest
    POSTs.
    """
    status, body = chain_get("/rtrackr/assets", port=port)
    if status == 200 and isinstance(body, dict):
        return _summarise_feed(body, "live:127.0.0.1:%d" % port)
    derived = _read_feed_file(derived_path)
    if derived is not None:
        return _summarise_feed(derived, "derived:%s" % derived_path)
    cached = _read_feed_file(cache_path)
    if cached is not None:
        return _summarise_feed(cached, "cache:%s" % cache_path)
    return {
        "source": None,
        "generated": None,
        "schema": None,
        "schema_ok": False,
        "live": None,
        "dry": None,
        "chain_valid": None,
        "history_height": None,
        "assets": [],
        "detail": ("no RTRACKR source answered (daemon :%d %s; no derived "
                   "or cached feed given or readable)"
                   % (port, "unreachable" if status == 0
                      else "HTTP %d" % status)),
    }


# -- Queues: DRY events only, minter requests for ThundR/GIZMO ---------
# The feed's queue() throws on mode live, and the game build never sends
# "live" from its queue. The adapter follows the same rule: it queues
# DRY events only, in the feed's shape (submit then register, register
# only after the mint block is confirmed). A live mint is never a direct
# submit — it is a minter request (rzl.rmint.minter-request.v1) queued
# for ThundR or GIZMO only, who add their own minter proof. The adapter
# writes these queues to its own state dir and never POSTs them: the
# chain stays read-only from here.


def _queue_home(home_dir=None) -> Path:
    if home_dir is not None:
        return Path(home_dir)
    env = os.environ.get("THUNDR_ADAPTER_HOME")
    if env:
        return Path(env)
    return Path.home() / ".config" / "thundr-adapter"


def _append_queue(home_dir, filename: str, record: dict) -> dict:
    home = _queue_home(home_dir)
    home.mkdir(parents=True, exist_ok=True)
    path = home / filename
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"queued": True, "path": str(path), "record": record}


def queue_dry_event(event: dict, home_dir=None) -> dict:
    """Queue a DRY event, in the feed's shape. Refuses mode live.

    Mirrors the feed readers: ``queue()`` throws on live. A live event
    is never queued here — a live mint goes through
    :func:`queue_minter_request` instead.
    """
    if not isinstance(event, dict):
        raise Refused("DRY queue refused: event must be an object",
                      rule="queue dry-only")
    mode = event.get("mode", "dry")
    if mode != "dry":
        raise Refused(
            "DRY queue refused: mode %r is not dry. The adapter queues "
            "DRY events only; a live mint is a minter request for "
            "ThundR/GIZMO, never a queued live event." % (mode,),
            rule="queue dry-only",
        )
    record = dict(event, mode="dry")
    return _append_queue(home_dir, "dry-queue.jsonl", record)


def queue_minter_request(request: dict, home_dir=None) -> dict:
    """Queue a live-mint request for ThundR or GIZMO only.

    The record follows rzl.rmint.minter-request.v1. The minter adds its
    own minter proof; the adapter holds no key and never submits. The
    request is queued locally for ThundR/GIZMO to pick up — it is NOT
    posted to /rmint/minter/request by the adapter (the chain stays
    read-only from here).
    """
    if not isinstance(request, dict):
        raise Refused("Minter request refused: request must be an object",
                      rule="minter-request thundr/gizmo only")
    minter = request.get("minter")
    if minter not in MINTERS:
        raise Refused(
            "Minter request refused: minter must be thundr or gizmo, not "
            "%r. A live mint is a request for ThundR/GIZMO only."
            % (minter,),
            rule="minter-request thundr/gizmo only",
        )
    record = dict(request, schema=MINTER_REQUEST_SCHEMA,
                  status="queued for ThundR/GIZMO")
    out = _append_queue(home_dir, "rmint-minter-requests.jsonl", record)
    out["status"] = "queued for ThundR/GIZMO"
    return out
