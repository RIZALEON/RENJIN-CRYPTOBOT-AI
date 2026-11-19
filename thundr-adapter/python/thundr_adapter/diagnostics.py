"""Diagnostics: read-only health checks for ThundR engines and models.

Grounded in two patterns from the project:

* ``NativeMaintenance.diagnostics`` (RIZALEON/RTHUNDR
  ``src/LocalBrain.swift``, ``feature/native-diagnostics``): offline,
  read-only GGUF inventory — count regular ``.gguf`` files, never follow
  symbolic links, report availability only, never claim inference works.
* ``ModelSelect`` (A2 Swift core, ``src/ModelSelect.swift``): exact
  identity — a model is the file with the exact byte count and SHA-256
  named in ``MODEL-IDENTITY.json``; missing, symlinked, wrong-size or
  wrong-hash files are refused.

Nothing here starts, stops, installs, or modifies anything. A service is
only reported "up" when it answers; anything else is "unreachable", never
assumed live.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path

from .chain import DAEMON_PORT, daemon_health, rtrackr_feed

# Loopback services ThundR is known to use (from the project analysis and
# the registry's models.backup_local_llm). Port 8742 is the adapter itself.
# The 4983 entry is confirmed live by Rizal's screenshot of the running
# RTHUNDR float (2026-11-19): header "SANDISK GRANITE 4.2 3B · 127.0.0.1:4983".
KNOWN_SERVICES = (
    # (port, service, health_path or None)
    (8329, "MCR command centre", "/v1/status"),
    (8741, "RGHOSTCHAIN submit daemon / ThundR gate", "/health"),
    (8080, "backup local LLM", "/v1/models"),
    (8796, "Linux web shell", None),
    (4983, "Granite 4.2 3B relay (macOS, SANDISK)", "/health"),
    (4979, "Granite 4.0 1B relay (Linux)", None),
    (8777, "Granite 4.2 3B relay (Linux)", None),
)

GRANITE_RELAY_PORT = 4983
GRANITE_HEALTH_TIMEOUT = 1.2  # seconds; mirrors the Linux brain's granite_health
ENGINE_CHOICE_FILENAME = "engine-choice.json"

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tcp_up(port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def _http_get(port: int, path: str, timeout: float = 1.0):
    """Best-effort loopback GET. Returns (status, decoded-or-text) or (0, None)."""
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:%d%s" % (port, path), timeout=timeout
        ) as resp:
            raw = resp.read()
            try:
                return resp.status, json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                return resp.status, raw.decode("utf-8", "replace")[:500]
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except Exception:
        return 0, None


def service_status(services=KNOWN_SERVICES) -> list:
    """Probe each known loopback service. Never claims a service is live
    unless it answers."""
    out = []
    for port, name, health_path in services:
        entry = {"port": port, "service": name, "up": False, "detail": "unreachable"}
        if _tcp_up(port):
            entry["up"] = True
            entry["detail"] = "tcp connect ok"
            if health_path:
                code, body = _http_get(port, health_path)
                if code:
                    entry["detail"] = "http %d" % code
                    if isinstance(body, dict):
                        entry["health"] = {
                            k: body[k] for k in ("service", "version", "data", "ok")
                            if k in body
                        }
                else:
                    entry["detail"] = "tcp connect ok; http health check failed"
        out.append(entry)
    return out


def granite_health(port: int = GRANITE_RELAY_PORT,
                   timeout: float = GRANITE_HEALTH_TIMEOUT) -> dict:
    """Probe the Granite 4.2 3B relay ``/health`` (Linux brain.py pattern).

    The macOS float header reads "SANDISK GRANITE 4.2 3B · 127.0.0.1:4983"
    (screenshot 2026-11-19). Returns ``{"up": bool, "detail": str}``;
    "UP" only on HTTP 200, anything else is unreachable or an HTTP code.
    """
    code, _body = _http_get(port, "/health", timeout=timeout)
    if code == 200:
        return {"up": True, "detail": "UP"}
    return {"up": False,
            "detail": "unreachable" if code == 0 else "HTTP %d" % code}


def engine_choice_path(config_dir=None) -> Path:
    """Where the adapter-local engine preference lives.

    Same state dir as the server token (``$THUNDR_ADAPTER_HOME`` or
    ``~/.config/thundr-adapter``). This is the ADAPTER's preference, not
    the live app's: the macOS float keeps its own engine choice, set by
    typing ``use qwen`` / ``use granite`` in the R:> shell.
    """
    if config_dir is not None:
        base = Path(config_dir)
    else:
        env = os.environ.get("THUNDR_ADAPTER_HOME")
        base = Path(env) if env else Path.home() / ".config" / "thundr-adapter"
    return base / ENGINE_CHOICE_FILENAME


def load_engine_preference(config_dir=None) -> str:
    """Adapter-local engine preference ("qwen" default).

    Mirrors the Linux brain's ``_load_choice``: only "qwen" and "granite"
    are valid; anything else (missing file, bad JSON, unknown value)
    falls back to "qwen".
    """
    try:
        value = json.loads(
            engine_choice_path(config_dir).read_text(encoding="utf-8"))["engine"]
        return value if value in ("qwen", "granite") else "qwen"
    except Exception:
        return "qwen"


def save_engine_preference(engine: str, config_dir=None) -> dict:
    """Persist the adapter-local engine preference.

    Mirrors the Linux brain's ``_save_choice``: atomic write via a temp
    file + ``os.replace``. Raises ValueError for anything but
    "qwen"/"granite". This writes only the adapter's own state file; it
    never touches the live app's engine choice.
    """
    if engine not in ("qwen", "granite"):
        raise ValueError("engine must be qwen or granite")
    path = engine_choice_path(config_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp-tpa")
    payload = {"engine": engine,
               "updated": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    try:
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()
    return {"engine": engine, "path": str(path),
            "updated": payload["updated"]}


def engine_status(model_dir=None, config_dir=None) -> dict:
    """Both engines, the way the float status bar shows them.

    Mirrors the Linux brain's ``status-live``: the active engine is
    Granite when the preference is Granite and the relay is up, else
    Qwen. Qwen 1.7B is the in-process llama.cpp fallback on macOS (the
    float status bar reads "Qwen 1.7B · UP, idle, q:0"), so its liveness
    cannot be probed from the adapter — the adapter reports Qwen model
    file presence from the GGUF inventory instead and says so plainly.
    """
    granite = granite_health()
    qwen = {
        "up": None,
        "model_present": None,
        "detail": ("in-process (llama.cpp); liveness is reported by the app "
                   "status bar, not probeable from the adapter"),
    }
    if model_dir is not None:
        inv = gguf_inventory(model_dir)
        qwen_files = [f for f in inv.get("files", [])
                      if "qwen" in f["file"].lower()]
        qwen["model_present"] = bool(qwen_files)
        qwen["model_files"] = [f["file"] for f in qwen_files]
        qwen["detail"] = ("Qwen model file present in %s" % inv.get("dir")
                          if qwen_files else
                          "no Qwen .gguf in %s" % inv.get("dir"))
    preferred = load_engine_preference(config_dir=config_dir)
    active = "granite" if (preferred == "granite" and granite["up"]) else "qwen"
    return {
        "granite": dict(granite, model="Granite 4.2 3B",
                        relay="http://127.0.0.1:%d" % GRANITE_RELAY_PORT),
        "qwen": dict(qwen, model="Qwen 1.7B"),
        "preferred": preferred,
        "active": active,
        "headline": ("Granite :4983" if active == "granite"
                     else "Qwen 1.7B (in-process)"),
    }


def gguf_inventory(model_dir: str | os.PathLike) -> dict:
    """Read-only GGUF inventory of one directory (NativeMaintenance shape).

    Counts regular ``.gguf`` files only. Symlinked files are skipped and
    listed separately; a symlinked directory itself yields an empty
    inventory (never follow a link out of the package). Every file gets
    its exact byte count and SHA-256. Nothing is opened for execution.
    """
    root = Path(model_dir)
    result = {
        "dir": str(root),
        "exists": root.exists(),
        "dir_is_symlink": root.is_symlink(),
        "count": 0,
        "bytes": 0,
        "files": [],
        "skipped_symlinks": [],
        "identity": None,
    }
    if not root.exists() or root.is_symlink():
        return result
    try:
        entries = sorted(root.iterdir(), key=lambda p: p.name)
    except OSError as exc:
        result["error"] = str(exc)
        return result
    for entry in entries:
        if entry.suffix.lower() != ".gguf":
            continue
        if entry.is_symlink():
            result["skipped_symlinks"].append(entry.name)
            continue
        if not entry.is_file():
            continue
        size = entry.stat().st_size
        result["files"].append({
            "file": entry.name,
            "bytes": size,
            "sha256": _sha256_file(entry),
        })
        result["count"] += 1
        result["bytes"] += size
    identity_file = root / "MODEL-IDENTITY.json"
    if identity_file.is_file() and not identity_file.is_symlink():
        result["identity"] = verify_identity(root, result["files"])
    return result


def verify_identity(model_dir: str | os.PathLike, files: list | None = None) -> dict:
    """Verify a model dir against its MODEL-IDENTITY.json (ModelSelect shape).

    Each spec names a file with exact bytes + SHA-256. A spec fails when
    the file is missing, symlinked, the wrong size, or the wrong hash.
    Returns per-spec verdicts; never loads or executes a model.
    """
    root = Path(model_dir)
    outcome = {"present": False, "specs": [], "all_ok": False}
    try:
        identity = json.loads((root / "MODEL-IDENTITY.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        outcome["error"] = "unreadable MODEL-IDENTITY.json: %s" % exc
        return outcome
    outcome["present"] = True
    known = {f["file"]: f for f in (files if files is not None
                                    else gguf_inventory(root)["files"])}
    specs = []
    if isinstance(identity.get("primary"), dict):
        specs.append(("primary", identity["primary"]))
    if isinstance(identity.get("fallback"), dict):
        specs.append(("fallback", identity["fallback"]))
    all_ok = True
    for role, spec in specs:
        verdict = {"role": role, "file": spec.get("file"), "ok": False}
        name = spec.get("file", "")
        expected_bytes = spec.get("bytes")
        expected_sha = spec.get("sha256", "")
        if (not isinstance(name, str) or "/" in name or "\\" in name
                or name.startswith(".") or name in ("", "..")):
            verdict["reason"] = "unsafe model file name"
        elif not isinstance(expected_bytes, int) or expected_bytes <= 0:
            verdict["reason"] = "identity must carry exact bytes"
        elif not _SHA256_HEX.match(str(expected_sha)):
            verdict["reason"] = "identity must carry a sha256 hex digest"
        elif name not in known:
            verdict["reason"] = "model missing or skipped (symlink?)"
        elif known[name]["bytes"] != expected_bytes:
            verdict["reason"] = "size mismatch (%d != %d)" % (
                known[name]["bytes"], expected_bytes)
        elif known[name]["sha256"] != expected_sha:
            verdict["reason"] = "sha256 mismatch"
        else:
            verdict["ok"] = True
            verdict["reason"] = "exact identity verified"
        if not verdict["ok"]:
            all_ok = False
        outcome["specs"].append(verdict)
    outcome["all_ok"] = all_ok and bool(specs)
    return outcome


def knowledge_stats(knowledge_dir: str | os.PathLike) -> dict:
    """Count knowledge scrolls (.md files) under a directory, read-only."""
    root = Path(knowledge_dir)
    result = {"dir": str(root), "exists": root.exists(), "files": 0,
              "bytes": 0, "lines": 0}
    if not root.exists():
        return result
    for path in sorted(root.rglob("*.md")):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        result["files"] += 1
        result["bytes"] += len(data)
        result["lines"] += data.count(b"\n")
    return result


def rghostkey_status() -> dict:
    """RGHOSTKEY status: the polykey interface, as the adapter can see it.

    RGHOSTKEY is an in-app interface (Swift WK handler ``rghostkey``,
    Java JS interface ``RGhostkeyNative``, ``window.RGHOSTKEY``) — there
    is no loopback endpoint the adapter can call, and the MCR exposes no
    key status either. So this report is honest about reachability and
    states the known interface, backends, pinned slots, and the
    adapter's stance instead of probing something that is not there.
    When the interface becomes reachable (a future status surface on the
    app), this function is where the live read belongs.

    Facts from RGHOSTKEY-PARITY-0.1.4.md and the supplied sources
    (grounding/rghostkey/): one interface, same method names everywhere;
    parity means the same methods, NOT shared secrets — every hard
    device keeps its own pinned key and nothing is created, exported,
    copied, or synced. Pins are public pubkey_sha256 values, shown here
    in the truncated form the parity record prints.
    """
    return {
        "reachable": False,
        "reason": ("in-app interface (WK handler / JS interface / "
                   "window.RGHOSTKEY); no loopback endpoint for the "
                   "adapter to call, and the MCR exposes no key status"),
        "interface": ["status", "methods", "unlock", "sign", "approve",
                      "logout", "session start", "revoke",
                      "cast receive/dismiss", "offline nonce", "lockout"],
        "parity": "same methods, not shared secrets",
        "backends": {
            "Secure Enclave": "tag info.rizal.rsign.se.p256 (iPhone 17e)",
            "macOS login keychain": ("non-extractable key "
                                     "info.rizal.rsign.mac.p256.v2, ACL "
                                     "userPresence (Neo)"),
            "AndroidKeyStore": "alias rsign.rghostkey.ec (moto)",
        },
        "pinned_slots": [
            {"device": "neo-rdragon", "pubkey_sha256": "5752020b…8782"},
            {"device": "iphone17e-rdragon", "pubkey_sha256": "26431cd4…b0eb"},
            {"device": "moto-rdragon", "pubkey_sha256": "9acf9fbd…d54e"},
        ],
        "pin_rule": "missing or unpinned key → refused, never enrolled",
        "adapter_stance": ("request/queue only: the adapter never signs, "
                           "seals, enrolls, or mints. Signing happens only "
                           "on the pinned device, by the human, through "
                           "RGHOSTKEY (device unlock on the device; "
                           "biometric optional, never required; no held "
                           "unlock context, no timer, no auto-approve)."),
        "known_gaps": [
            "Android bridge has 3 pre-existing JSONException errors "
            "blocking assembleDebug (fix documented, not applied — "
            "add-only rule).",
            "TERAFORMR native rsign GDExtension dylib not built (game "
            "uses the web wallet panel, soft).",
            "Native approve UI unbuilt on Android (approve has no caller yet).",
        ],
    }


def run(model_dir=None, knowledge_dir=None, chain_port=None,
        wallet_snapshot=None, wallet_manifest=None,
        rtrackr_derived=None, rtrackr_cache=None) -> dict:
    """Full diagnostics report: services, engines, chain, keys, wallet, rtrackr, models, knowledge."""
    from .analyze import wallet_snapshot as _wallet_snapshot

    report = {
        "services": service_status(),
        "engines": engine_status(model_dir=model_dir),
        "chain": daemon_health(port=chain_port or DAEMON_PORT),
        "rghostkey": rghostkey_status(),
        "wallet": None,
        "rtrackr": rtrackr_feed(port=chain_port or DAEMON_PORT,
                                derived_path=rtrackr_derived,
                                cache_path=rtrackr_cache),
        "models": None,
        "knowledge": None,
        "note": ("Availability only: package authenticity, template "
                 "compatibility and inference NOT TESTED. Maintenance "
                 "execution NOT GRANTED."),
    }
    if wallet_snapshot is not None:
        report["wallet"] = _wallet_snapshot(wallet_snapshot, wallet_manifest)
    if model_dir is not None:
        report["models"] = gguf_inventory(model_dir)
    if knowledge_dir is not None:
        report["knowledge"] = knowledge_stats(knowledge_dir)
    return report
