#!/usr/bin/env python3
"""Renjin Ghostkey public-cert pin check (t180u). Public cert only. No signing."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
from pathlib import Path

PRIV_RE = re.compile(
    br"BEGIN (ENCRYPTED )?PRIVATE KEY|BEGIN OPENSSH PRIVATE KEY|BEGIN EC PRIVATE KEY"
)
CERT_RE = re.compile(
    br"-----BEGIN CERTIFICATE-----(.*?)-----END CERTIFICATE-----", re.S
)

MARKER_UID = "ЯID-0001-3QQS".encode("utf-8")
MARKER_SN = b"RZL111682"
MARKER_CN = b"Renjin Ghostkey"

def default_root() -> Path:
    env = os.environ.get("RCRYPTOFORGE")
    if env:
        return Path(env)
    return Path.home() / "R/ЯLAB/RCRYPTOFORGE"

def load_pin(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def pem_to_der(data: bytes) -> bytes:
    if PRIV_RE.search(data):
        raise ValueError("Refusing to read a private key. Pass only the public certificate.")
    m = CERT_RE.search(data)
    if not m:
        raise ValueError("File does not look like an X.509 certificate.")
    return base64.b64decode(re.sub(br"\s+", b"", m.group(1)))

def fingerprint_sha256(der: bytes) -> str:
    h = hashlib.sha256(der).hexdigest().upper()
    return ":".join(h[i : i + 2] for i in range(0, len(h), 2))

def file_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def openssl_subject(cert: Path):
    import shutil
    import subprocess
    bins = [
        "/opt/homebrew/opt/openssl@3/bin/openssl",
        "/opt/homebrew/bin/openssl",
        shutil.which("openssl"),
    ]
    for b in bins:
        if not b or not Path(b).exists():
            continue
        try:
            out = subprocess.check_output(
                [b, "x509", "-in", str(cert), "-noout", "-subject", "-nameopt", "utf8,sep_comma_plus"],
                stderr=subprocess.DEVNULL,
            )
            text = out.decode("utf-8", "replace").strip()
            if text.startswith("subject="):
                text = text[len("subject="):].lstrip()
            return text
        except Exception:
            continue
    return None

def verify(cert_path: Path, pin: dict, require_file_sha: bool) -> dict:
    data = cert_path.read_bytes()
    der = pem_to_der(data)
    fp = fingerprint_sha256(der)
    fsha = file_sha256(data)
    want_fp = str(pin["fingerprint_sha256"]).upper()
    want_sha = str(pin["file_sha256"]).lower()
    marks = {
        "uid": MARKER_UID in der,
        "serialNumber": MARKER_SN in der,
        "cn": MARKER_CN in der,
    }
    subject = openssl_subject(cert_path) or str(pin.get("subject", ""))
    reasons = []
    if fp != want_fp:
        reasons.append("fingerprint mismatch")
    if require_file_sha and fsha != want_sha:
        reasons.append("file sha256 mismatch")
    if not all(marks.values()):
        missing = [k for k, v in marks.items() if not v]
        reasons.append("subject markers missing: " + ",".join(missing))
    ok = not reasons
    return {
        "ok": ok,
        "verdict": "PASS" if ok else "FAIL",
        "subject": subject,
        "fingerprint_sha256": fp,
        "file_sha256": fsha,
        "pin_fingerprint_sha256": want_fp,
        "pin_file_sha256": want_sha,
        "markers": marks,
        "reasons": reasons,
        "cert_path": str(cert_path),
        "kind": pin.get("kind", "public cert only"),
        "owner_rid": pin.get("owner_rid", ""),
        "not_after": pin.get("not_after", ""),
    }

def format_result(r: dict) -> str:
    lines = [
        "GHOSTKEY %s  (public cert only · no signing)" % r["verdict"],
        "subject: %s" % r["subject"],
        "fingerprint: %s" % r["fingerprint_sha256"],
        "file sha256: %s" % r["file_sha256"],
        "owner RID: %s" % r.get("owner_rid", ""),
        "notAfter: %s" % r.get("not_after", ""),
        "cert: %s" % r.get("cert_path", ""),
    ]
    if r["reasons"]:
        lines.append("reasons: " + "; ".join(r["reasons"]))
    return "\n".join(lines)

def main(argv=None) -> int:
    root = default_root()
    ap = argparse.ArgumentParser(description="Verify the pinned Renjin Ghostkey public certificate.")
    ap.add_argument("cert", nargs="?", default=str(root / "RENJIN/ghostkey/out/RGHOSTKEY-v1-20261120.pem"))
    ap.add_argument("--pin", default=str(root / "RENJIN/ghostkey/ghostkey-pin.json"))
    ap.add_argument("--require-file-sha", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    cert = Path(args.cert)
    pin_path = Path(args.pin)
    if not cert.is_file():
        print("GHOSTKEY FAIL  cert not found: %s" % cert, file=sys.stderr)
        return 1
    if not pin_path.is_file():
        print("GHOSTKEY FAIL  pin not found: %s" % pin_path, file=sys.stderr)
        return 1
    pin = load_pin(pin_path)
    official = cert.resolve() == (root / "RENJIN/ghostkey/out/RGHOSTKEY-v1-20261120.pem").resolve()
    r = verify(cert, pin, require_file_sha=args.require_file_sha or official)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(format_result(r))
    return 0 if r["ok"] else 1

if __name__ == "__main__":
    sys.exit(main())
