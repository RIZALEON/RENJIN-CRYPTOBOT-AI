"""Loopback-only HTTP server for the ThundR Plugin Adapter.

Transport rules (grounded in the project's own servers):

* Bind ``127.0.0.1`` only, like the MCR endpoint (``controlroom.py``:
  "127.0.0.1-only JSON endpoint", default 8329) and thundr-shell.py.
  The adapter port comes from ``THUNDR_ADAPTER_PORT`` (default 8742).
  8741 is the ThundR gate, 8329 the MCR, 8796 the Linux web shell, 8080
  the backup LLM, 4983 the Granite relay — 8742 is free of known ThundR
  services. (Assumed free on the Mac; verify with diagnostics if unsure.)
* Per-start Bearer token, like thundr-shell.py: created at each start
  with ``secrets.token_urlsafe(32)``, written mode 0600 to the token
  file, NEVER printed. Every ``/v1/call`` needs
  ``Authorization: Bearer <token>``. Only ``GET /health`` is open, and
  it returns identity only (no data).
* Host/Origin checks, like the MCR ``_origin_ok`` — but stricter: the
  MCR allows one LAN IP for the iOS widget; the adapter allows loopback
  only (no LAN), because it is a plugin adapter, not a widget backend.
* ``safe_path`` sandboxing for file methods, copied from
  ``controlroom.py``: a relative path must resolve inside the safe root
  (``THUNDR_ADAPTER_ROOT`` env, default the ThundR root when it exists,
  else the adapter tree). Anything escaping the root is refused.

Endpoints:
  GET  /health     identity only, no auth
  GET  /v1/methods method list (auth required)
  POST /v1/call    {"method": "adapter.…", "params": {...}} (auth required)
"""

from __future__ import annotations

import json
import os
import re
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import analyze as _analyze
from . import chain as _chain
from . import chat as _chat
from . import debug as _debug
from . import diagnostics as _diagnostics
from . import plugins as _plugins
from . import protocol as _protocol
from . import repair as _repair
from . import rid as _rid
from . import update as _update
from . import visual as _visual
from .protocol import Refused
from .registry import Registry

DEFAULT_PORT = 8742
DEFAULT_HOST = "127.0.0.1"
MAX_BODY_BYTES = 65536

_LOOPBACK_HOST = re.compile(r"^(127\.0\.0\.1|localhost)(:\d+)?$")
_LOOPBACK_ORIGIN = re.compile(r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$")


def home_dir() -> Path:
    """Adapter state dir: $THUNDR_ADAPTER_HOME or ~/.config/thundr-adapter."""
    env = os.environ.get("THUNDR_ADAPTER_HOME")
    if env:
        return Path(env)
    return Path.home() / ".config" / "thundr-adapter"


def token_path(explicit=None) -> Path:
    if explicit is not None:
        return Path(explicit)
    return home_dir() / "token"


def default_root() -> Path:
    """Safe root for file methods: the ThundR tree when present, else the
    adapter tree itself. Override with THUNDR_ADAPTER_ROOT."""
    env = os.environ.get("THUNDR_ADAPTER_ROOT")
    if env:
        return Path(env)
    thundr_root = Path.home() / "R/ЯLAB/RCRYPTOFORGE"
    if thundr_root.is_dir():
        return thundr_root
    return Path(__file__).resolve().parent.parent.parent


def safe_path(relative: str, root: Path | None = None) -> Path:
    """Resolve ``relative`` inside the safe root (controlroom.py pattern)."""
    base = Path(root) if root is not None else default_root()
    candidate = (base / relative).resolve()
    if candidate != base and base.resolve() not in candidate.parents:
        raise ValueError("blocked: path leaves the safe root")
    return candidate


def new_token() -> str:
    return secrets.token_urlsafe(32)


def write_token_file(token: str, path: Path | None = None) -> Path:
    """Write the per-start token mode 0600. Never print the token itself."""
    target = token_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, (token + "\n").encode("utf-8"))
    finally:
        os.close(fd)
    os.chmod(target, 0o600)
    return target


class Adapter:
    """The method dispatcher: pure logic, no HTTP. The server wraps it."""

    def __init__(self, registry: Registry | None = None, root: Path | None = None):
        self.registry = registry or Registry.load()
        self.root = Path(root) if root is not None else default_root()
        self.plugins = _plugins.CapabilityRegistry()
        # Repair plans, approve-by-reference (RGHOSTKEY vc27/vc31 mirror):
        # propose() stores the plan; apply() loads it by id + nonce.
        self.plans = _repair.PlanStore()

    def dispatch(self, method: str, params: dict) -> dict:
        """Run one tpa.v1 method. Always returns an envelope, never raises
        for expected failures (Refused becomes a refusal envelope)."""
        try:
            handler = getattr(self, "_m_" + method.replace(".", "_"), None)
            if handler is None:
                return _protocol.fail("unknown method: %r" % method, via="adapter")
            return handler(params)
        except Refused as exc:
            return _protocol.refused_reply(exc.reply, via="adapter/" + method,
                                           rule=exc.rule)
        except (ValueError, OSError) as exc:
            return _protocol.fail(str(exc), via="adapter/" + method)
        except Exception as exc:  # noqa: BLE001 - the envelope must survive
            return _protocol.fail("internal error: %s: %s"
                                  % (type(exc).__name__, exc),
                                  via="adapter/" + method)

    # -- methods ------------------------------------------------------
    def _m_adapter_hello(self, _params):
        return _protocol.ok("adapter", data=_protocol.hello_data())

    def _m_adapter_commands_list(self, params):
        group = params.get("group")
        host = params.get("host")
        query = params.get("q") or params.get("search")
        if query:
            cmds = self.registry.search(str(query), limit=int(params.get("limit", 20)))
        elif group:
            cmds = self.registry.by_group(str(group))
        elif host:
            cmds = self.registry.by_host(str(host))
        else:
            cmds = self.registry.all()
        return _protocol.ok("adapter.registry", data={
            "count": len(cmds), "registry_version": self.registry.version,
            "source": str(self.registry.source), "commands": cmds})

    def _m_adapter_commands_get(self, params):
        cmd_id = str(params.get("id", "")).strip()
        cmd = self.registry.get(cmd_id)
        if cmd is None:
            return _protocol.fail("no such command: %r" % cmd_id,
                                  via="adapter.registry")
        return _protocol.ok("adapter.registry", data=cmd)

    def _m_adapter_chat(self, params):
        text = str(params.get("text", ""))
        return _chat.route(text, registry=self.registry,
                           model_dir=params.get("model_dir"))

    def _m_adapter_diagnostics(self, params):
        return _protocol.ok("adapter.diagnostics", data=_diagnostics.run(
            model_dir=params.get("model_dir"),
            knowledge_dir=params.get("knowledge_dir"),
            chain_port=params.get("chain_port"),
            wallet_snapshot=params.get("wallet_snapshot"),
            wallet_manifest=params.get("wallet_manifest"),
            rtrackr_derived=params.get("rtrackr_derived"),
            rtrackr_cache=params.get("rtrackr_cache")))

    def _m_adapter_analyze(self, params):
        kind = str(params.get("kind", "file"))
        if kind == "file":
            rel = str(params.get("path", ""))
            return _protocol.ok("adapter.analyze",
                                data=_analyze.file_info(safe_path(rel, self.root)))
        if kind == "registry-diff":
            import json as _json
            bundled = _json.loads(_bundled_path().read_text(encoding="utf-8"))
            return _protocol.ok("adapter.analyze", data=_analyze.registry_diff(
                self.registry.data, bundled))
        if kind == "hosts":
            hosts = params.get("hosts_path")
            path = safe_path(hosts, self.root) if hosts else None
            if path is None:
                default = self.root / "cryptoapp/ThundR/THUNDR-CORE/hosts.json"
                path = default if default.is_file() else None
            if path is None:
                return _protocol.fail("hosts.json not found", via="adapter.analyze")
            return _protocol.ok("adapter.analyze",
                                data=_analyze.host_check(path, root=self.root))
        if kind == "build-stamp":
            build = params.get("build_path")
            if not build:
                return _protocol.fail("build_path is required for build-stamp",
                                      via="adapter.analyze")
            return _protocol.ok("adapter.analyze", data=_analyze.build_stamp_check(
                safe_path(build, self.root), self.registry.data))
        if kind == "components":
            return _protocol.ok("adapter.analyze",
                                data=_analyze.component_check())
        if kind == "rgeneratr-assets":
            feed = params.get("feed_path")
            if not feed:
                return _protocol.fail(
                    "feed_path is required for rgeneratr-assets",
                    via="adapter.analyze")
            return _protocol.ok("adapter.analyze",
                                data=_analyze.rgeneratr_assets(
                                    safe_path(feed, self.root)))
        if kind == "rid":
            return _protocol.ok("adapter.analyze",
                                data=_rid.validate_rid(str(params.get("rid", ""))))
        if kind == "wallet-snapshot":
            snap = params.get("snapshot_path")
            if not snap:
                return _protocol.fail(
                    "snapshot_path is required for wallet-snapshot",
                    via="adapter.analyze")
            manifest = params.get("manifest_path")
            return _protocol.ok("adapter.analyze",
                                data=_analyze.wallet_snapshot(
                                    safe_path(snap, self.root),
                                    safe_path(manifest, self.root)
                                    if manifest else None))
        if kind == "rtrackr-feed":
            derived = params.get("derived_path")
            cache = params.get("cache_path")
            return _protocol.ok("adapter.analyze", data=_chain.rtrackr_feed(
                port=int(params.get("chain_port") or 8741),
                derived_path=safe_path(derived, self.root) if derived else None,
                cache_path=safe_path(cache, self.root) if cache else None))
        return _protocol.fail("unknown analyze kind: %r" % kind, via="adapter.analyze")

    def _m_adapter_debug(self, params):
        kind = str(params.get("kind", "self-test"))
        if kind == "log-tail":
            rel = str(params.get("path", ""))
            return _protocol.ok("adapter.debug", data=_debug.log_tail(
                safe_path(rel, self.root), count=int(params.get("count", 50))))
        if kind == "transcript":
            rel = str(params.get("path", ""))
            return _protocol.ok("adapter.debug", data=_debug.transcript_read(
                safe_path(rel, self.root), since=int(params.get("since", 0)),
                limit=int(params.get("limit", 50))))
        if kind == "self-test":
            return _protocol.ok("adapter.debug",
                                data=_debug.self_test(registry=self.registry))
        return _protocol.fail("unknown debug kind: %r" % kind, via="adapter.debug")

    def _m_adapter_repair_propose(self, params):
        findings = params.get("findings") or {}
        if not isinstance(findings, dict):
            return _protocol.fail("findings must be an object", via="adapter.repair")
        if not findings:
            findings = _diagnostics.run()
        plan = _repair.propose(findings)
        plan_id, nonce = self.plans.store(plan)
        plan["plan_id"] = plan_id
        plan["nonce"] = nonce
        return _protocol.ok("adapter.repair", data=plan)

    def _m_adapter_repair_apply(self, params):
        # Approve-by-reference (RGHOSTKEY vc27/vc31 mirror): the caller
        # sends plan_id + nonce + go, never the plan payload. The stored
        # plan is what gets applied, so a tampered payload cannot be
        # smuggled in. The in-process repair.apply(plan, go=True) keeps
        # its direct signature for local/CLI use (no network boundary).
        if "plan" in params:
            return _protocol.fail(
                "approve by reference: send plan_id + nonce + go, not the "
                "plan payload", via="adapter.repair")
        go = params.get("go") is True
        plan = self.plans.load(str(params.get("plan_id", "")),
                               str(params.get("nonce", "")))
        return _protocol.ok("adapter.repair",
                            data=_repair.apply(plan, go=go))

    def _m_adapter_update_check(self, params):
        return _protocol.ok("adapter.update",
                            data=_update.check(
                                canonical_path=params.get("canonical_path"),
                                build_path=params.get("build_path")))

    def _m_adapter_update_apply(self, params):
        go = params.get("go") is True
        return _protocol.ok("adapter.update",
                            data=_update.apply(go=go, canonical_path=params.get(
                                "canonical_path"),
                                expected_stamp=params.get("live_stamp")))

    def _m_adapter_visual(self, params):
        kind = str(params.get("kind", "all"))
        if kind == "float":
            return _protocol.ok("adapter.visual",
                                data=_visual.float_state(root=self.root))
        if kind == "float-window":
            return _protocol.ok("adapter.visual",
                                data=_visual.float_window())
        if kind == "orb":
            return _protocol.ok("adapter.visual",
                                data=_visual.orb_state(root=self.root))
        if kind == "panels":
            return _protocol.ok("adapter.visual",
                                data=_visual.panel_state(registry=self.registry))
        if kind == "shot":
            return _protocol.ok("adapter.visual", data=_visual.shot_hook())
        return _protocol.ok("adapter.visual",
                            data=_visual.run(registry=self.registry, root=self.root))


def _bundled_path() -> Path:
    from .registry import BUNDLED_SNAPSHOT
    return BUNDLED_SNAPSHOT


def make_handler(adapter: Adapter, token: str):
    """Build the request handler class bound to one adapter + token."""

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):  # keep stdout clean; no request logging
            pass

        def _origin_ok(self):
            host = self.headers.get("Host") or ""
            if not _LOOPBACK_HOST.match(host):
                return None
            origin = self.headers.get("Origin")
            if origin in (None, "null", "file://") or _LOOPBACK_ORIGIN.match(origin or ""):
                return origin or "null"
            return None

        def _send(self, code, body, origin=None):
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            if origin:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Methods", "GET, POST")
                self.send_header("Access-Control-Allow-Headers",
                                 "Content-Type, Authorization")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _authed(self):
            auth = self.headers.get("Authorization") or ""
            return auth == "Bearer " + token

        def do_GET(self):
            origin = self._origin_ok()
            if origin is None:
                return self._send(403, {"ok": False, "error": "local origin only"})
            path = self.path.split("?")[0]
            if path == "/health":
                return self._send(200, {
                    "ok": True, "service": "thundr-adapter",
                    "protocol": _protocol.VERSION,
                    "version": _protocol.ADAPTER_VERSION,
                    "bind": "127.0.0.1:%d" % self.server.server_address[1],
                }, origin)
            if path == "/v1/methods":
                if not self._authed():
                    return self._send(401, {"ok": False, "error": "bearer token required"})
                return self._send(200, {"ok": True, "via": "adapter",
                                        "data": {"methods": list(_protocol.METHODS)}}, origin)
            return self._send(404, {"ok": False, "error": "unknown path: %s" % path})

        def do_POST(self):
            origin = self._origin_ok()
            if origin is None:
                return self._send(403, {"ok": False, "error": "local origin only"})
            if self.path.split("?")[0] != "/v1/call":
                return self._send(404, {"ok": False, "error": "unknown path"})
            if not self._authed():
                return self._send(401, {"ok": False, "error": "bearer token required"})
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > MAX_BODY_BYTES:
                return self._send(400, {"ok": False,
                                        "error": "body must be 1..%d bytes" % MAX_BODY_BYTES})
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                method, params = _protocol.validate_request(body)
            except (ValueError, _protocol.ProtocolError) as exc:
                return self._send(400, {"ok": False, "error": str(exc)})
            res = adapter.dispatch(method, params)
            return self._send(200 if res.get("ok") else 400, res, origin)

    return Handler


def serve(port: int | None = None, host: str = DEFAULT_HOST,
          registry: Registry | None = None, root: Path | None = None,
          token_file: Path | None = None):
    """Start the loopback server (blocking). Returns nothing; Ctrl-C stops it.

    Refuses to bind any host but 127.0.0.1. Prints the port and the token
    FILE path (never the token) on start.
    """
    if host != "127.0.0.1":
        raise ValueError("adapter binds 127.0.0.1 only; refused host %r" % host)
    port = int(port if port is not None
               else os.environ.get("THUNDR_ADAPTER_PORT", DEFAULT_PORT))
    token = new_token()
    written = write_token_file(token, token_file)
    adapter = Adapter(registry=registry, root=root)
    httpd = ThreadingHTTPServer((host, port), make_handler(adapter, token))
    httpd.daemon_threads = True
    print("thundr-adapter %s (%s) listening on http://127.0.0.1:%d"
          % (_protocol.ADAPTER_VERSION, _protocol.VERSION, port))
    print("token file: %s (mode 0600; token never printed)" % written)
    print("safe root: %s" % adapter.root)
    print("registry: %s (%d commands)"
          % (adapter.registry.source, adapter.registry.count()))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nthundr-adapter stopped.")
    finally:
        httpd.server_close()
