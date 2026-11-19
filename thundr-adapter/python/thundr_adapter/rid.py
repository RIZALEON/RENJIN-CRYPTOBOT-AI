"""ЯID validation: the RGHOSTCHAIN checksum, ported verbatim.

From rghostchain_submitd.py (grounding/rghostchain/):

    CROCK = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'
    RID_RE = re.compile(r'^ЯID-(\\d{4})-([0-9A-HJKMNP-TV-Z]{4})$')

    def rid_for(seq):
        s = f'{seq:04d}'
        v = int.from_bytes(hashlib.sha256(f'ЯID-{s}'.encode()).digest()[:3],
                           'big') >> 4
        return f'ЯID-{s}-' + ''.join(CROCK[(v >> (5 * i)) & 31]
                                     for i in (3, 2, 1, 0))

    def rid_ok(r):
        m = RID_RE.match(r or '')
        return bool(m) and rid_for(int(m.group(1))) == r

The checksum is the first 20 bits of sha256("ЯID-<seq4>"), rendered as
four Crockford base32 characters. Known-good vectors from the project:
ЯID-0001-3QQS (@chaserizal, the genesis owner) and ЯID-0014-KREH
(ThundR, from the RGENERATR spec header). Validation is pure arithmetic
— no chain call, no secret, no network.
"""

from __future__ import annotations

import hashlib
import re

CROCK = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
RID_RE = re.compile(r"^ЯID-(\d{4})-([0-9A-HJKMNP-TV-Z]{4})$")


def rid_for(seq: int) -> str:
    """The canonical ЯID for a sequence number (daemon's rid_for)."""
    text = "%04d" % seq
    value = int.from_bytes(
        hashlib.sha256(("ЯID-" + text).encode("utf-8")).digest()[:3],
        "big") >> 4
    return "ЯID-%s-" % text + "".join(
        CROCK[(value >> (5 * i)) & 31] for i in (3, 2, 1, 0))


def rid_ok(rid: str) -> bool:
    """True when the RID matches the format and its checksum (daemon's rid_ok)."""
    match = RID_RE.match(rid or "")
    return bool(match) and rid_for(int(match.group(1))) == rid


def validate_rid(rid: str) -> dict:
    """Validate one RID, with the expected value when the checksum fails."""
    text = (rid or "").strip()
    out = {"rid": text, "valid": False, "seq": None, "expected": None}
    match = RID_RE.match(text)
    if not match:
        out["reason"] = ("malformed: expected ЯID-<4 digits>-<4 Crockford "
                         "base32 chars>")
        return out
    seq = int(match.group(1))
    out["seq"] = seq
    expected = rid_for(seq)
    out["expected"] = expected
    if expected == text:
        out["valid"] = True
        out["reason"] = "checksum valid"
    else:
        out["reason"] = "checksum mismatch (expected %s)" % expected
    return out
