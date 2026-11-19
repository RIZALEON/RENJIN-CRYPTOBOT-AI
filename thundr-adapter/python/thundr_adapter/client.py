"""Loopback-only HTTP client for the ThundR Plugin Adapter.

Same stance as the Linux port's ``http_json`` helper
(``lib/rthundr/brain.py``): refuse anything that is not 127.0.0.1 or
localhost. The adapter never talks to the network; a non-loopback URL is
a programming error, not a request, so it raises instead of returning a
quiet failure.

Usage::

    client = Client.from_token_file()          # default 127.0.0.1:8742
    res = client.call("adapter.diagnostics")
    res = client.call("adapter.chat", {"text": "help"})
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from . import server as _server  # token-file location lives in server.py
from .protocol import METHODS, ProtocolError

DEFAULT_BASE_URL = "http://127.0.0.1:8742"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class NonLoopbackError(ValueError):
    """Raised when a URL points anywhere but loopback."""


def assert_loopback(url: str) -> urllib.parse.ParseResult:
    """Parse ``url`` and refuse it unless it is http(s) to loopback."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise NonLoopbackError("refused non-http(s) URL: %r" % (url,))
    host = (parsed.hostname or "").lower()
    if host not in LOOPBACK_HOSTS:
        raise NonLoopbackError(
            "refused non-loopback URL: %r (adapter is loopback-only)" % (url,)
        )
    return parsed


class Client:
    """Minimal JSON client for one adapter server (loopback only)."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL, token: str | None = None,
                 timeout: float = 5.0):
        assert_loopback(base_url)
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    @classmethod
    def from_token_file(cls, base_url: str | None = None,
                        token_file: str | os.PathLike | None = None,
                        timeout: float = 5.0) -> "Client":
        """Build a client reading the per-start Bearer token from its 0600 file."""
        url = base_url or os.environ.get(
            "THUNDR_ADAPTER_URL", DEFAULT_BASE_URL)
        path = _server.token_path(token_file)
        try:
            token = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise FileNotFoundError(
                "adapter token file not found at %s (is the server running?)"
                % path) from exc
        if not token:
            raise ValueError("adapter token file is empty: %s" % path)
        return cls(url, token=token, timeout=timeout)

    def call(self, method: str, params: dict | None = None) -> dict:
        """Call one tpa.v1 method. Returns the decoded envelope dict."""
        if method not in METHODS:
            raise ProtocolError("unknown method: %r" % (method,))
        body = json.dumps({"method": method, "params": params or {}}).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/v1/call", data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("Authorization", "Bearer " + self.token)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            raw = exc.read() or b""
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return {"ok": False, "via": "client",
                    "error": "adapter unreachable at %s: %s" % (self.base_url, exc)}
        try:
            decoded = json.loads(raw.decode("utf-8", "replace"))
        except ValueError:
            return {"ok": False, "via": "client",
                    "error": "adapter returned non-JSON (%d bytes)" % len(raw)}
        if not isinstance(decoded, dict):
            return {"ok": False, "via": "client",
                    "error": "adapter returned a non-object response"}
        return decoded

    def health(self) -> dict:
        """GET /health (no auth needed; returns identity only, no data)."""
        req = urllib.request.Request(self.base_url + "/health", method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8", "replace"))
        except Exception as exc:  # noqa: BLE001 - health is best-effort
            return {"ok": False, "via": "client",
                    "error": "adapter unreachable at %s: %s" % (self.base_url, exc)}
