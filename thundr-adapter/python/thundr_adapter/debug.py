"""Debugging helpers: log tails, transcript reads, self-tests.

Read-only and dry-run only. Nothing here executes a repair, restarts a
service, or writes a file. Log output is redacted the same way the MCR's
``/v1/thundr/mind`` endpoint redacts its transcript tail: lines matching
secret-like words are replaced wholesale, and long token-like runs are
collapsed, so a debug dump can never leak a credential.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

_REDACT_WORDS = re.compile(
    r"private|secret|seed|mnemonic|passw|api.?key|bearer|BEGIN.*KEY|wallet|casket|token",
    re.IGNORECASE,
)
_LONG_TOKEN = re.compile(r"[A-Za-z0-9+/=_-]{32,}")

MAX_TAIL_BYTES = 65536
MAX_LINE_CHARS = 4000


def redact_line(line: str) -> str:
    """Redact one log line (MCR /v1/thundr/mind pattern)."""
    if _REDACT_WORDS.search(line):
        return "[redacted]"
    return _LONG_TOKEN.sub("[...]", line)[:MAX_LINE_CHARS]


def log_tail(path: str | os.PathLike, count: int = 50) -> dict:
    """Return the last ``count`` lines of a log file, redacted.

    Reads at most the last 64 KiB (seeks from the end like the MCR tail).
    Refuses symlinks. Empty result when the file is missing — never an
    invented log.
    """
    target = Path(path)
    out = {"path": str(target), "exists": target.exists(),
           "is_symlink": target.is_symlink(), "lines": []}
    if not target.exists() or target.is_symlink() or not target.is_file():
        return out
    try:
        with open(target, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - MAX_TAIL_BYTES))
            raw = fh.read().decode("utf-8", "replace")
    except OSError as exc:
        out["error"] = str(exc)
        return out
    lines = [line for line in raw.splitlines() if line.strip()]
    out["lines"] = [redact_line(line) for line in lines[-count:]]
    out["total_lines_seen"] = len(lines)
    return out


def transcript_read(path: str | os.PathLike, since: int = 0,
                    limit: int = 50) -> dict:
    """Read a JSONL transcript (thundr-memory / thundr-shell style).

    ``since`` skips that many lines from the start of the file; ``limit``
    caps the returned records. Each record is returned as decoded JSON
    when it parses, else as redacted text. Missing file -> empty records.
    """
    target = Path(path)
    out = {"path": str(target), "exists": target.exists(), "records": []}
    if not target.exists() or target.is_symlink() or not target.is_file():
        return out
    try:
        raw = target.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        out["error"] = str(exc)
        return out
    picked = raw[since:since + limit] if limit > 0 else raw[since:]
    for line in picked:
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            out["records"].append(record if isinstance(record, dict)
                                  else {"text": str(record)[:500]})
        except ValueError:
            out["records"].append({"text": redact_line(line)})
    out["total_lines"] = len(raw)
    return out


def self_test(registry=None) -> dict:
    """Dry-run self-test of the adapter itself. Never executes repairs.

    Checks: the registry loads and carries the right schema; all refuse
    regexes compile and refuse their documented examples; the loopback
    client refuses a non-loopback URL; the protocol envelope round-trips.
    Each check reports pass/fail with a detail string.
    """
    from . import client as _client
    from . import protocol as _protocol
    from .registry import Registry

    checks = []

    def check(name: str, passed: bool, detail: str = ""):
        checks.append({"name": name, "pass": bool(passed), "detail": detail})

    # Registry loads.
    try:
        reg = registry or Registry.load()
        check("registry.loads", True,
              "%s (%d commands) from %s" % (reg.version, reg.count(), reg.source))
        check("registry.schema", reg.data.get("schema") == "thundr.core.commands.v1",
              "schema=%r" % reg.data.get("schema"))
    except Exception as exc:  # noqa: BLE001 - self-test reports, never raises
        reg = None
        check("registry.loads", False, "load failed: %s" % exc)
        check("registry.schema", False, "no registry loaded")

    # Refuse regexes refuse their documented examples.
    if reg is not None:
        examples = [
            ("optimize clean", True),
            ("optimize deep now", True),
            ("eggs install foo", True),
            ("self-evolution", True),
            ("rebirth go", True),
            ("egg apply my.egg", True),
            ("rscribe build --run", True),
            ("17e uninstall x", True),
            ("help", False),
            ("status", False),
        ]
        failed = [text for text, want in examples
                  if reg.is_refused(text) != want]
        check("refuse.patterns", not failed,
              "all 7 patterns behave" if not failed
              else "mismatched: %s" % ", ".join(failed))
    else:
        check("refuse.patterns", False, "no registry loaded")

    # Loopback client refuses non-loopback.
    try:
        _client.assert_loopback("https://example.com/v1/call")
        check("client.loopback_only", False, "non-loopback URL was accepted")
    except _client.NonLoopbackError:
        check("client.loopback_only", True, "non-loopback URL refused")
    try:
        _client.assert_loopback("http://127.0.0.1:8742/v1/call")
        check("client.loopback_ok", True, "loopback URL accepted")
    except _client.NonLoopbackError as exc:
        check("client.loopback_ok", False, str(exc))

    # Protocol envelope round-trips.
    try:
        method, params = _protocol.validate_request(
            {"method": "adapter.hello", "params": {}})
        env = _protocol.ok("self-test", data={"method": method})
        check("protocol.envelope", env.get("ok") is True and method == "adapter.hello",
              "validate + ok envelope")
    except Exception as exc:  # noqa: BLE001 - self-test reports, never raises
        check("protocol.envelope", False, str(exc))

    passed = sum(1 for c in checks if c["pass"])
    return {
        "checks": checks,
        "passed": passed,
        "failed": len(checks) - passed,
        "all_pass": passed == len(checks),
        "note": "Dry-run self-test. No repair, update, or service action was executed.",
    }
