"""Tests for the ThundR Plugin Adapter (TPA) v0.1.

Run from the thundr-adapter root:

    python3 -m unittest discover -s tests -v

All fixtures are fake data created in temp dirs. No network, no ThundR
runtime, no live services: anything that would need a real brain is
tested for its honest offline answer instead. The Swift checks follow
the source-contract pattern of RIZALEON/RTHUNDR tests/test_contract.py
(assert on the Swift source; they do not compile or run Swift).
"""

import hashlib
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "python"))

from thundr_adapter import analyze, chain, chat, client, debug, diagnostics  # noqa: E402
from thundr_adapter import plugins, protocol, repair, rid, server, update  # noqa: E402
from thundr_adapter import visual  # noqa: E402
from thundr_adapter.protocol import Refused  # noqa: E402
from thundr_adapter.registry import Registry  # noqa: E402


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class TestProtocol(unittest.TestCase):
    def test_method_table(self):
        self.assertEqual(len(protocol.METHODS), 12)
        self.assertIn("adapter.hello", protocol.METHODS)
        self.assertIn("adapter.repair.apply", protocol.METHODS)
        self.assertIn("adapter.visual", protocol.METHODS)
        self.assertEqual(protocol.VERSION, "tpa.v1")

    def test_ok_envelope(self):
        env = protocol.ok("test-route", data={"a": 1})
        self.assertTrue(env["ok"])
        self.assertEqual(env["via"], "test-route")
        self.assertEqual(env["data"], {"a": 1})
        self.assertNotIn("error", env)

    def test_fail_envelope(self):
        env = protocol.fail("boom", via="test-route")
        self.assertFalse(env["ok"])
        self.assertEqual(env["error"], "boom")

    def test_refused_envelope(self):
        env = protocol.refused_reply("needs GO", via="test", rule="r1")
        self.assertFalse(env["ok"])
        self.assertTrue(env["refused"])
        self.assertEqual(env["rule"], "r1")

    def test_validate_request_ok(self):
        method, params = protocol.validate_request(
            {"method": "adapter.chat", "params": {"text": "hi"}})
        self.assertEqual(method, "adapter.chat")
        self.assertEqual(params, {"text": "hi"})

    def test_validate_request_defaults(self):
        method, params = protocol.validate_request({"method": "adapter.hello"})
        self.assertEqual((method, params), ("adapter.hello", {}))

    def test_validate_request_rejects(self):
        for bad in (None, [], "x", {}, {"method": "nope"},
                    {"method": "adapter.hello", "params": []}):
            with self.assertRaises(protocol.ProtocolError, msg=repr(bad)):
                protocol.validate_request(bad)

    def test_go_gated(self):
        self.assertEqual(protocol.GO_GATED_METHODS,
                         {"adapter.repair.apply", "adapter.update.apply"})
        self.assertTrue(protocol.GO_GATED_METHODS.isdisjoint(
            protocol.READ_ONLY_METHODS))

    def test_never_operations(self):
        self.assertEqual(protocol.NEVER_OPERATIONS,
                         {"sign", "seal", "enroll", "mint",
                          "send", "swap", "transfer"})
        self.assertEqual(protocol.hello_data()["never"],
                         ["enroll", "mint", "seal", "send", "sign", "swap",
                          "transfer"])


class TestRegistry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = Registry.load()

    def test_loads_bundled_snapshot(self):
        self.assertEqual(self.reg.data["schema"], "thundr.core.commands.v1")
        self.assertEqual(self.reg.version, "1.0.0")
        self.assertEqual(self.reg.count(), 124)
        self.assertTrue(str(self.reg.source).endswith("data/thundr-commands.json"))

    def test_get_and_search(self):
        cmd = self.reg.get("C001")
        self.assertIsNotNone(cmd)
        self.assertIn("open", cmd["cmd"])
        self.assertIsNone(self.reg.get("C999"))
        hits = self.reg.search("open app")
        self.assertGreater(len(hits), 0)
        self.assertEqual(hits[0]["id"], "C001")

    def test_by_group_and_host(self):
        self.assertGreater(len(self.reg.by_group("RDRAGON wrap")), 0)
        self.assertEqual(len(self.reg.by_host("macos")), 124)
        self.assertEqual(len(self.reg.by_host("no-such-host")), 0)

    def test_go_commands(self):
        goes = self.reg.go_commands()
        self.assertEqual(len(goes), 10)
        self.assertTrue(all(c["go"] for c in goes))

    def test_rules_exposed(self):
        self.assertIn("needs Rizal's GO", self.reg.refuse_reply)
        self.assertIn("Never remove", self.reg.rules["add_only"])
        self.assertEqual(len(self.reg.hosts), 7)
        self.assertEqual(len(self.reg.groups), 16)

    def test_stamp_is_stable(self):
        self.assertEqual(self.reg.stamp(), self.reg.stamp())
        self.assertEqual(len(self.reg.stamp()), 64)

    def test_alias_resolution(self):
        self.assertEqual(self.reg.resolve_alias("manual float"),
                         "AUTOMANUAL float")
        self.assertEqual(self.reg.resolve_alias("manual"), "AUTOMANUAL")
        self.assertEqual(self.reg.resolve_alias("help"), "help")


class TestRefuse(unittest.TestCase):
    """Every one of the 7 registry refuse patterns must refuse."""

    CASES = [
        ("optimize clean", "optimize clean / optimize deep (removes files)"),
        ("optimize deep", "optimize clean / optimize deep (removes files)"),
        ("OPTIMIZE CLEAN", "optimize clean / optimize deep (removes files)"),
        ("eggs install foo", "eggs install"),
        ("egg install foo", "eggs install"),
        ("self-evolution", "self-evolution"),
        ("self evolution now", "self-evolution"),
        ("rebirth go", "REBIRTH … go (real run)"),
        ("rebirth please go", "REBIRTH … go (real run)"),
        ("egg apply my.egg", "egg apply / approve endpoint"),
        ("api/egg/apply", "egg apply / approve endpoint"),
        ("api/approve", "egg apply / approve endpoint"),
        ("rscribe build --run", "rscribe build --run (real Apple build/sign)"),
        ("17e uninstall x", "17e uninstall/delete/rm/sign/keychain/wallet"),
        ("17e wallet", "17e uninstall/delete/rm/sign/keychain/wallet"),
        ("17e keychain list", "17e uninstall/delete/rm/sign/keychain/wallet"),
    ]
    ALLOWED = ["help", "status", "commands", "open terminal",
               "rebirth", "optimize", "17e status", "egg list"]

    @classmethod
    def setUpClass(cls):
        cls.reg = Registry.load()

    def test_all_seven_patterns_present(self):
        self.assertEqual(len(self.reg.refuse_patterns()), 7)

    def test_refused_cases(self):
        for text, label in self.CASES:
            matched, got_label, _ = self.reg.refuse_check(text)
            self.assertTrue(matched, msg=text)
            self.assertEqual(got_label, label, msg=text)

    def test_allowed_cases(self):
        for text in self.ALLOWED:
            self.assertFalse(self.reg.is_refused(text), msg=text)

    def test_chat_refuses(self):
        res = chat.route("optimize deep", registry=self.reg, try_mcr=False)
        self.assertFalse(res["ok"])
        self.assertTrue(res["refused"])
        self.assertIn("needs Rizal's GO", res["reply"])


class TestGoGated(unittest.TestCase):
    """The six parser verbs (live float ready reply) are GO-gated."""

    PARSER_VERBS = [
        "wallet balances",
        "casket verify",
        "signing status",
        "prompt faceid",
        "sign this /tmp/some-dir",
        "request approval mint this egg",
    ]
    MORE_GATED = ["wallet", "rwallet", "faceid", "approve", "mint",
                  "request mint foo", "request sign foo", "sign egg foo",
                  "egg-sign foo", "/wallet balances", "WALLET BALANCES"]
    NOT_GATED = ["status", "inventory", "jobs", "progress", "mcr",
                 "gizmo", "rcpm", "casket", "help"]

    @classmethod
    def setUpClass(cls):
        cls.reg = Registry.load()

    def test_parser_verbs_go_gated(self):
        for text in self.PARSER_VERBS:
            res = chat.route(text, registry=self.reg, try_mcr=False)
            self.assertFalse(res["ok"], msg=text)
            self.assertTrue(res.get("go_gated"), msg=text)
            self.assertEqual(res["via"], "adapter.chat/go-gated", msg=text)
            self.assertIn("Nothing was run", res["reply"], msg=text)
            self.assertIn("/rmint/request", res["reply"], msg=text)

    def test_more_gated_verbs(self):
        for text in self.MORE_GATED:
            res = chat.route(text, registry=self.reg, try_mcr=False)
            self.assertTrue(res.get("go_gated"), msg=text)

    def test_gated_never_reaches_mcr(self):
        # Even with the MCR attempt enabled, a gated verb answers locally.
        res = chat.route("wallet balances", registry=self.reg,
                         mcr_port=1, try_mcr=True)
        self.assertTrue(res.get("go_gated"))
        self.assertNotIn("mcr", res["via"])

    def test_read_only_live_verbs_not_gated(self):
        for text in self.NOT_GATED:
            res = chat.route(text, registry=self.reg, try_mcr=False)
            self.assertIsNone(res.get("go_gated"), msg=text)

    def test_refuse_still_beats_go_gated(self):
        res = chat.route("17e wallet", registry=self.reg, try_mcr=False)
        self.assertTrue(res.get("refused"))
        self.assertIsNone(res.get("go_gated"))


class TestEngines(unittest.TestCase):
    """Engine verbs (R:> shell quick commands) + both-engine diagnostics."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config_dir = Path(self.tmp.name) / "config"
        self.reg = Registry.load()

    def tearDown(self):
        self.tmp.cleanup()

    def test_models_panel(self):
        res = chat.route("models", registry=self.reg, try_mcr=False,
                         config_dir=self.config_dir)
        self.assertTrue(res["ok"])
        self.assertEqual(res["via"], "adapter.chat/models")
        self.assertEqual(res["engine"], "qwen")  # default preference
        self.assertEqual(res["panel"], "models")
        self.assertIn("MODELS", res["reply"])
        self.assertIn("Qwen 1.7B", res["reply"])
        self.assertIn("Granite 4.2 3B", res["reply"])
        self.assertIn("use qwen · use granite · models", res["reply"])

    def test_use_qwen_records_preference(self):
        res = chat.route("use qwen", registry=self.reg, try_mcr=False,
                         config_dir=self.config_dir)
        self.assertTrue(res["ok"])
        self.assertEqual(res["engine"], "qwen")
        self.assertIn("Active engine → Qwen 1.7B", res["reply"])
        self.assertIn("adapter's preference", res["reply"])
        self.assertEqual(
            diagnostics.load_engine_preference(self.config_dir), "qwen")

    def test_use_granite_records_preference_and_reports_relay_down(self):
        res = chat.route("use granite", registry=self.reg, try_mcr=False,
                         config_dir=self.config_dir)
        self.assertTrue(res["ok"])
        self.assertEqual(res["engine"], "granite")
        self.assertIn("Active engine → Granite 4.2 3B", res["reply"])
        # Nothing listens on :4983 on this VM: the reply must say so.
        self.assertIn("Granite unavailable", res["reply"])
        self.assertEqual(
            diagnostics.load_engine_preference(self.config_dir), "granite")

    def test_granite_preferred_but_down_falls_back_to_qwen(self):
        chat.route("use granite", registry=self.reg, try_mcr=False,
                   config_dir=self.config_dir)
        res = chat.route("models", registry=self.reg, try_mcr=False,
                         config_dir=self.config_dir)
        self.assertEqual(res["engine"], "granite")  # preference kept
        # ...but the active marker stays on Qwen: the relay is down.
        qwen_line = [ln for ln in res["reply"].splitlines()
                     if "Qwen 1.7B" in ln][0]
        self.assertIn("← active", qwen_line)

    def test_engine_preference_validation(self):
        with self.assertRaises(ValueError):
            diagnostics.save_engine_preference("renjin",
                                               config_dir=self.config_dir)
        # Missing file and bad content both fall back to qwen.
        self.assertEqual(
            diagnostics.load_engine_preference(self.config_dir), "qwen")
        self.config_dir.mkdir(parents=True, exist_ok=True)
        (self.config_dir / "engine-choice.json").write_text(
            json.dumps({"engine": "nope"}))
        self.assertEqual(
            diagnostics.load_engine_preference(self.config_dir), "qwen")

    def test_granite_health_unreachable_here(self):
        health = diagnostics.granite_health()
        self.assertFalse(health["up"])
        self.assertEqual(health["detail"], "unreachable")

    def test_engine_status_with_qwen_model(self):
        model_dir = Path(self.tmp.name) / "models"
        model_dir.mkdir()
        (model_dir / "Qwen3-1.7B-Q8_0.gguf").write_bytes(b"FAKE-QWEN" * 10)
        status = diagnostics.engine_status(model_dir=model_dir,
                                           config_dir=self.config_dir)
        self.assertEqual(status["qwen"]["model"], "Qwen 1.7B")
        self.assertTrue(status["qwen"]["model_present"])
        self.assertEqual(status["granite"]["model"], "Granite 4.2 3B")
        self.assertFalse(status["granite"]["up"])
        self.assertEqual(status["preferred"], "qwen")
        self.assertEqual(status["active"], "qwen")

    def test_engine_status_empty_model_dir(self):
        model_dir = Path(self.tmp.name) / "empty-models"
        model_dir.mkdir()
        status = diagnostics.engine_status(model_dir=model_dir,
                                           config_dir=self.config_dir)
        self.assertFalse(status["qwen"]["model_present"])
        self.assertIsNone(status["qwen"]["up"])  # liveness not probeable

    def test_diagnostics_run_reports_engines_and_4983(self):
        report = diagnostics.run()
        self.assertIn("engines", report)
        self.assertIn("granite", report["engines"])
        self.assertIn("qwen", report["engines"])
        by_port = {e["port"]: e for e in report["services"]}
        self.assertIn(4983, by_port)
        self.assertIn("Granite 4.2 3B", by_port[4983]["service"])
        self.assertFalse(by_port[4983]["up"])


class _FakeDaemonHandler(BaseHTTPRequestHandler):
    """Canned RGHOSTCHAIN daemon: serves a fixed /health + /rtrackr/assets."""

    payload = {}

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/health":
            body = self.payload.get("health", {})
        elif self.path == "/rtrackr/assets":
            body = self.payload.get("assets", {"assets": []})
        else:
            self.send_response(404)
            self.end_headers()
            return
        data = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _start_fake_daemon(payload):
    handler = type("FakeDaemon", (_FakeDaemonHandler,),
                   {"payload": payload})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


class TestChain(unittest.TestCase):
    """Read-only against RGHOSTCHAIN: the four writes are refused by name."""

    HEALTH_LIVE = {
        "ok": True, "service": "rghostchain-submitd", "real_flag": True,
        "real_blocks": 12, "real_valid": True,
        "dry_blocks": 3, "dry_valid": True,
        "verifier_present": True,
        "trust_registry_path_present": True,
        "trust_registry_pin_valid": True,
    }
    HEALTH_DRY = dict(HEALTH_LIVE, real_flag=False, dry_blocks=5,
                      trust_registry_pin_valid=False)

    def test_refused_writes(self):
        for path in sorted(chain.CHAIN_REFUSED_WRITES):
            for method in ("POST", "GET", "PUT", "DELETE"):
                with self.assertRaises(Refused, msg="%s %s" % (method, path)):
                    chain.check_chain_call(method, path)
            with self.assertRaises(Refused, msg=path):
                chain.chain_get(path, port=1)

    def test_unknown_paths_refused(self):
        # /rghostchain/bind/pending is a real daemon endpoint but NOT on
        # the adapter's read allowlist: refused like any other unknown path.
        for path in ("/nope", "/rghostchain/bind/pending", "/rmint/gate",
                     "/rghostchain/source/upload"):
            with self.assertRaises(Refused, msg=path):
                chain.check_chain_call("GET", path)

    def test_read_paths_allowed(self):
        for path in sorted(chain.CHAIN_READ_PATHS):
            chain.check_chain_call("GET", path)  # must not raise
        with self.assertRaises(Refused):
            chain.check_chain_call("POST", "/health")

    def test_daemon_health_unreachable(self):
        health = chain.daemon_health(port=1)
        self.assertFalse(health["up"])
        self.assertEqual(health["mode"], "unknown")
        self.assertIsNone(health["real"])
        self.assertIsNone(health["tips"])
        self.assertIn("not tip hashes", health["tips_note"])

    def test_daemon_health_live_capable(self):
        httpd = _start_fake_daemon({"health": self.HEALTH_LIVE})
        try:
            health = chain.daemon_health(
                port=httpd.server_address[1])
        finally:
            httpd.shutdown()
            httpd.server_close()
        self.assertTrue(health["up"])
        self.assertTrue(health["real_flag"])
        self.assertIn("live-capable", health["mode"])
        self.assertEqual(health["real"], {"blocks": 12, "valid": True})
        self.assertEqual(health["dry"], {"blocks": 3, "valid": True})
        self.assertTrue(health["verifier_present"])
        self.assertIn("operational", health["minter_gate"]["status"])
        self.assertTrue(health["minter_gate"]["registry_pin_valid"])

    def test_daemon_health_dry_only(self):
        httpd = _start_fake_daemon({"health": self.HEALTH_DRY})
        try:
            health = chain.daemon_health(
                port=httpd.server_address[1])
        finally:
            httpd.shutdown()
            httpd.server_close()
        self.assertTrue(health["up"])
        self.assertFalse(health["real_flag"])
        self.assertIn("dry-only", health["mode"])
        self.assertIn("unavailable", health["minter_gate"]["status"])

    def test_chain_get_fake_daemon(self):
        httpd = _start_fake_daemon({
            "health": self.HEALTH_LIVE,
            "assets": {"assets": [{"asset_id": "x"}]},
        })
        try:
            port = httpd.server_address[1]
            status, body = chain.chain_get("/health", port=port)
            self.assertEqual(status, 200)
            self.assertEqual(body["service"], "rghostchain-submitd")
            status, body = chain.chain_get("/rtrackr/assets", port=port)
            self.assertEqual(status, 200)
            self.assertEqual(body["assets"][0]["asset_id"], "x")
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_is_live_asset(self):
        live = {"rid": "ЯID-0014-KREH", "kind": "cryptobot",
                "status": "live", "on_chain": True,
                "block_hash": "a" * 64}
        self.assertTrue(chain.is_live_asset(live))
        signed = dict(live, status="registered", sig="deadbeef")
        self.assertTrue(chain.is_live_asset(signed))
        # The standing example: ThundR's wallet-RID row is registered
        # but unsealed — never live.
        registered = {"rid": "ЯID-0014-KREH", "kind": "wallet.asset.rid",
                      "status": "registered", "on_chain": False,
                      "block_hash": None}
        self.assertFalse(chain.is_live_asset(registered))
        no_sig = dict(live, status="registered")
        self.assertFalse(chain.is_live_asset(no_sig))
        self.assertFalse(chain.is_live_asset({}))
        self.assertFalse(chain.is_live_asset(None))

    def test_rtrackr_feed_live(self):
        feed = json.loads((ROOT / "grounding" / "rtrackr"
                           / "rtrackr-game-assets.json").read_text())
        httpd = _start_fake_daemon({"assets": feed})
        try:
            out = chain.rtrackr_feed(port=httpd.server_address[1])
        finally:
            httpd.shutdown()
            httpd.server_close()
        self.assertTrue(out["source"].startswith("live:"))
        self.assertEqual(out["generated"], "2026-11-18T23:28:34-07:00")
        self.assertTrue(out["schema_ok"])
        self.assertEqual(out["live"], 5)
        self.assertEqual(out["dry"], 1)
        self.assertTrue(out["chain_valid"])
        self.assertEqual(out["history_height"], 4)
        by_key = {(a["rid"], a["kind"]): a for a in out["assets"]}
        bot = by_key[("ЯID-0014-KREH", "cryptobot")]
        self.assertTrue(bot["is_live"])
        self.assertEqual(bot["block_height"], 2)
        wallet = by_key[("ЯID-0014-KREH", "wallet.asset.rid")]
        self.assertFalse(wallet["is_live"])
        self.assertEqual(wallet["status"], "registered")

    def test_rtrackr_feed_fallback_order(self):
        feed_path = (ROOT / "grounding" / "rtrackr"
                     / "rtrackr-game-assets.json")
        # Daemon down + derived given: derived serves.
        out = chain.rtrackr_feed(port=1, derived_path=feed_path)
        self.assertTrue(out["source"].startswith("derived:"))
        self.assertEqual(out["live"], 5)
        # Daemon down + cache only: cache serves.
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache.json"
            cache.write_bytes(feed_path.read_bytes())
            out = chain.rtrackr_feed(port=1, cache_path=cache)
            self.assertTrue(out["source"].startswith("cache:"))
        # Nothing at all: source None, honestly.
        out = chain.rtrackr_feed(port=1)
        self.assertIsNone(out["source"])
        self.assertEqual(out["assets"], [])
        self.assertIn("no RTRACKR source", out["detail"])

    def test_queue_dry_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = chain.queue_dry_event(
                {"kind": "test", "rid": "ЯID-0001-3QQS"}, home_dir=tmp)
            self.assertTrue(out["queued"])
            self.assertEqual(out["record"]["mode"], "dry")
            lines = (Path(tmp) / "dry-queue.jsonl").read_text().splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0])["kind"], "test")
            with self.assertRaises(Refused):
                chain.queue_dry_event({"mode": "live"}, home_dir=tmp)
            with self.assertRaises(Refused):
                chain.queue_dry_event("not-a-dict", home_dir=tmp)

    def test_queue_minter_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = chain.queue_minter_request(
                {"minter": "thundr", "rid": "ЯID-0014-KREH",
                 "kind": "cryptobot"}, home_dir=tmp)
            self.assertTrue(out["queued"])
            self.assertEqual(out["status"], "queued for ThundR/GIZMO")
            self.assertEqual(out["record"]["schema"],
                             "rzl.rmint.minter-request.v1")
            lines = (Path(tmp) / "rmint-minter-requests.jsonl"
                     ).read_text().splitlines()
            self.assertEqual(len(lines), 1)
            with self.assertRaises(Refused):
                chain.queue_minter_request({"minter": "mallory"},
                                           home_dir=tmp)
            # gizmo is allowed too.
            chain.queue_minter_request({"minter": "gizmo"}, home_dir=tmp)


class TestRid(unittest.TestCase):
    """ЯID checksum: the daemon's rid_for, ported verbatim."""

    def test_known_vectors(self):
        self.assertEqual(rid.rid_for(1), "ЯID-0001-3QQS")
        self.assertEqual(rid.rid_for(14), "ЯID-0014-KREH")
        self.assertTrue(rid.rid_ok("ЯID-0001-3QQS"))
        self.assertTrue(rid.rid_ok("ЯID-0014-KREH"))

    def test_validate_rid(self):
        good = rid.validate_rid("ЯID-0001-3QQS")
        self.assertTrue(good["valid"])
        self.assertEqual(good["seq"], 1)
        bad = rid.validate_rid("ЯID-0001-3QQQ")
        self.assertFalse(bad["valid"])
        self.assertEqual(bad["expected"], "ЯID-0001-3QQS")
        self.assertIn("checksum mismatch", bad["reason"])

    def test_validate_rid_malformed(self):
        for text in ("", "foo", "ЯID-1-3QQS", "ЯID-0001-3QQ",
                     "RID-0001-3QQS", "ЯID-0001-3QQO"):
            res = rid.validate_rid(text)
            self.assertFalse(res["valid"], msg=text)
            self.assertIn("malformed", res["reason"], msg=text)


class TestClientLoopback(unittest.TestCase):
    def test_non_loopback_refused(self):
        for url in ("https://example.com/v1/call",
                    "http://192.168.0.1:8742/v1/call",
                    "http://10.0.0.5/v1/call",
                    "http://github.com/",
                    "ftp://127.0.0.1/x"):
            with self.assertRaises(client.NonLoopbackError, msg=url):
                client.assert_loopback(url)
            with self.assertRaises(client.NonLoopbackError, msg=url):
                client.Client(url)

    def test_loopback_accepted(self):
        for url in ("http://127.0.0.1:8742/v1/call",
                    "http://localhost:8742/",
                    "http://127.0.0.1:1/"):
            client.assert_loopback(url)

    def test_unreachable_returns_envelope(self):
        c = client.Client("http://127.0.0.1:1", timeout=1.0)
        res = c.call("adapter.hello")
        self.assertFalse(res["ok"])
        self.assertIn("unreachable", res["error"])


class TestDiagnostics(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        # Fake GGUF files with known bytes + sha.
        self.model_a = b"FAKE-GGUF-A" * 100
        self.model_b = b"FAKE-GGUF-B" * 50
        (self.dir / "fake-a.gguf").write_bytes(self.model_a)
        (self.dir / "fake-b.gguf").write_bytes(self.model_b)
        (self.dir / "notes.txt").write_text("not a model")
        os.symlink(self.dir / "fake-a.gguf", self.dir / "link.gguf")
        (self.dir / "MODEL-IDENTITY.json").write_text(json.dumps({
            "primary": {"file": "fake-a.gguf", "bytes": len(self.model_a),
                        "sha256": sha256_bytes(self.model_a),
                        "family": "fake"},
            "fallback": {"file": "fake-b.gguf", "bytes": len(self.model_b),
                         "sha256": "0" * 64, "family": "fake"},
        }))

    def tearDown(self):
        self.tmp.cleanup()

    def test_gguf_inventory(self):
        inv = diagnostics.gguf_inventory(self.dir)
        self.assertEqual(inv["count"], 2)
        self.assertEqual(inv["bytes"], len(self.model_a) + len(self.model_b))
        self.assertEqual(inv["skipped_symlinks"], ["link.gguf"])
        by_name = {f["file"]: f for f in inv["files"]}
        self.assertEqual(by_name["fake-a.gguf"]["sha256"],
                         sha256_bytes(self.model_a))
        self.assertEqual(by_name["fake-b.gguf"]["bytes"], len(self.model_b))

    def test_identity_verification(self):
        inv = diagnostics.gguf_inventory(self.dir)
        identity = inv["identity"]
        self.assertTrue(identity["present"])
        self.assertFalse(identity["all_ok"])
        specs = {s["role"]: s for s in identity["specs"]}
        self.assertTrue(specs["primary"]["ok"])
        self.assertFalse(specs["fallback"]["ok"])
        self.assertIn("sha256 mismatch", specs["fallback"]["reason"])

    def test_missing_dir(self):
        inv = diagnostics.gguf_inventory(self.dir / "nope")
        self.assertFalse(inv["exists"])
        self.assertEqual(inv["count"], 0)

    def test_symlinked_dir_refused(self):
        link = self.dir / "linked-dir"
        os.symlink(self.dir, link)
        inv = diagnostics.gguf_inventory(link)
        self.assertTrue(inv["dir_is_symlink"])
        self.assertEqual(inv["count"], 0)

    def test_knowledge_stats(self):
        kdir = self.dir / "knowledge"
        kdir.mkdir()
        (kdir / "a.md").write_text("one\ntwo\nthree\n")
        (kdir / "b.md").write_text("four\n")
        stats = diagnostics.knowledge_stats(kdir)
        self.assertEqual(stats["files"], 2)
        self.assertEqual(stats["lines"], 4)

    def test_service_status_shape(self):
        # Nothing is listening on this VM; every service must read unreachable.
        statuses = diagnostics.service_status()
        self.assertEqual(len(statuses), 7)
        for entry in statuses:
            self.assertIn("up", entry)
            self.assertIn("detail", entry)
        self.assertFalse(any(e["up"] for e in statuses))
        by_port = {e["port"]: e for e in statuses}
        self.assertIn("submit daemon", by_port[8741]["service"])

    def test_run_reports_chain_and_rghostkey(self):
        report = diagnostics.run()
        self.assertIn("chain", report)
        self.assertFalse(report["chain"]["up"])
        self.assertEqual(report["chain"]["mode"], "unknown")
        self.assertIn("rghostkey", report)
        key = report["rghostkey"]
        self.assertFalse(key["reachable"])
        self.assertIn("approve", key["interface"])
        self.assertEqual(key["parity"], "same methods, not shared secrets")
        self.assertEqual(len(key["pinned_slots"]), 3)
        self.assertEqual(key["pinned_slots"][0]["device"], "neo-rdragon")
        self.assertIn("never signs", key["adapter_stance"])
        self.assertEqual(len(key["known_gaps"]), 3)
        self.assertIn("rtrackr", report)
        self.assertIsNone(report["rtrackr"]["source"])
        self.assertIsNone(report["wallet"])

    def test_run_reports_wallet_and_rtrackr_when_given(self):
        snap = (ROOT / "grounding" / "rwalet"
                / "rtrackr-snapshot.json.bin")
        manifest = (ROOT / "grounding" / "rwalet"
                    / "rbox.web.rwalet.SHA256SUMS")
        feed = (ROOT / "grounding" / "rtrackr"
                / "rtrackr-game-assets.json")
        report = diagnostics.run(chain_port=1, wallet_snapshot=snap,
                                 wallet_manifest=manifest,
                                 rtrackr_derived=feed)
        self.assertEqual(report["wallet"]["entries"], 11)
        self.assertFalse(report["wallet"]["verification"]["match"])
        self.assertTrue(
            report["rtrackr"]["source"].startswith("derived:"))
        self.assertEqual(report["rtrackr"]["live"], 5)


class TestAnalyze(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_file_info(self):
        target = self.dir / "hello.txt"
        target.write_text("hello\nworld\n")
        info = analyze.file_info(target)
        self.assertTrue(info["exists"])
        self.assertEqual(info["bytes"], 12)
        self.assertEqual(info["lines"], 2)
        self.assertEqual(info["sha256"], sha256_bytes(b"hello\nworld\n"))

    def test_file_info_refuses_symlink(self):
        target = self.dir / "real.txt"
        target.write_text("x")
        link = self.dir / "link.txt"
        os.symlink(target, link)
        info = analyze.file_info(link)
        self.assertTrue(info["is_symlink"])
        self.assertNotIn("sha256", info)

    def test_registry_diff(self):
        reg = Registry.load()
        live = json.loads(json.dumps(reg.data))
        live["commands"] = [c for c in live["commands"] if c["id"] != "C001"]
        live["commands"].append({"id": "C999", "cmd": "test", "does": "fake"})
        changed = dict(live["commands"][0])
        changed["does"] = "CHANGED"
        live["commands"][0] = changed
        diff = analyze.registry_diff(live, reg.data)
        self.assertFalse(diff["in_sync"])
        self.assertEqual(diff["added"], ["C999"])
        self.assertEqual(diff["removed"], ["C001"])
        self.assertIn(changed["id"], diff["changed"])
        self.assertEqual(analyze.registry_diff(reg.data, reg.data)["in_sync"], True)

    def test_host_check(self):
        hosts = {
            "schema": "thundr.core.hosts.v2",
            "root": str(self.dir),
            "staging": str(self.dir / "staging"),
            "web": [{"id": "h1", "page": "a/float.html", "state": "wired"},
                    {"id": "h2", "page": "b/float.html", "state": "wired"}],
            "native": [],
        }
        (self.dir / "a").mkdir()
        (self.dir / "a" / "float.html").write_text("<html></html>")
        hosts_path = self.dir / "hosts.json"
        hosts_path.write_text(json.dumps(hosts))
        out = analyze.host_check(hosts_path)
        self.assertEqual(out["wired"], 1)
        self.assertEqual(out["missing"], 1)

    def test_component_check(self):
        out = analyze.component_check()
        self.assertEqual(out["total_rzl_files"], 1388)
        self.assertEqual(out["scan_date"], "2026-11-04")
        by_name = {c["name"]: c for c in out["components"]}
        self.assertEqual(len(by_name), 7)
        # Gap #0 closed as a draft on 2026-11-19: not missing.
        loader = by_name["RbotLoadR"]
        self.assertEqual(loader["status"], "0.0.1 UNSIGNED DRAFT, verified")
        self.assertEqual(loader["version"], "0.0.1")
        self.assertEqual(loader["sha256"],
                         "d1ea6a6a5435ab90ecb2f623f2e4670f602753eb00e3d237c8b1612c97c84aed")
        self.assertEqual(loader["size_bytes"], 7160)
        self.assertEqual(by_name["RVM"]["status"], "COMPLETE as runtime")
        self.assertEqual(by_name["RGENERATR"]["status"], "PARTIAL")
        self.assertIn("rgen_asset_adapter.py", by_name["RGENERATR"]["note"])
        self.assertEqual(by_name["ЯSEED"]["status"], "COMPLETE")
        # Gaps: RbotLoadR-missing is gone; three remain.
        self.assertEqual(len(out["gaps"]), 3)
        self.assertFalse(any("RbotLoadR" in g for g in out["gaps"]))
        self.assertTrue(any("RGENERATR" in g for g in out["gaps"]))
        self.assertTrue(any("RMIND" in g for g in out["gaps"]))
        self.assertTrue(any("RbotLoadR 0.0.1" in s
                            for s in out["awaiting_signing"]))

    def test_rgeneratr_assets_snapshot(self):
        # The real 2026-10-30 snapshot from grounding (read-only fixture).
        snapshot = (ROOT / "grounding" / "rgeneratr"
                    / "rgeneratr-assets-snapshot.json")
        out = analyze.rgeneratr_assets(snapshot)
        self.assertTrue(out["exists"])
        self.assertTrue(out["schema_ok"])
        self.assertEqual(out["schema"], "rzl.rgeneratr.assets.v1")
        self.assertEqual(out["owners"], 1)
        self.assertEqual(len(out["assets"]), 1)
        self.assertEqual(out["live"], 0)
        self.assertEqual(out["preview"], 1)
        asset = out["assets"][0]
        self.assertEqual(asset["asset_id"], "rid-asset-0001-genesis")
        self.assertEqual(asset["label"], "GAME-MINTED GENESIS")
        self.assertEqual(asset["owner_handle"], "@chaserizal")
        self.assertEqual(asset["rid"], "ЯID-0001-3QQS")
        self.assertTrue(asset["status"].startswith("preview"))
        self.assertFalse(asset["seal_sig_present"])
        self.assertIsNone(asset["block"])
        self.assertEqual(asset["chain_verify"]["nft_mint_blocks_for_rid"], 0)
        self.assertEqual(asset["rtracker_status"], "dry")
        self.assertFalse(asset["live_gate"]["eligible"])
        self.assertTrue(asset["gate_consistent"])
        self.assertIn("no verified nft_mint block", asset["preview_reason"])
        self.assertIn("seal has no signature", asset["preview_reason"])
        self.assertFalse(out["sidecar"]["present"])

    def _write_feed(self, assets, sidecar=True, schema=None):
        feed = {
            "schema": schema or "rzl.rgeneratr.assets.v1",
            "generated": "2026-11-19T00:00:00-07:00",
            "sources": {"chain": "fake/chain.jsonl",
                        "registry": "fake/registry.json"},
            "owners": [{"rid": "ЯID-0001-3QQS", "handle": "@chaserizal",
                        "assets": assets}],
        }
        path = self.dir / "assets.json"
        raw = json.dumps(feed).encode("utf-8")
        path.write_bytes(raw)
        if sidecar:
            (self.dir / "assets.json.sha256").write_text(
                sha256_bytes(raw) + "  assets.json\n")
        return path

    @staticmethod
    def _asset(asset_id, status, minted, sealed):
        return {
            "asset_id": asset_id, "kind": "wallet.asset.rid",
            "label": asset_id, "owner_handle": "@chaserizal",
            "rid": "ЯID-0001-3QQS", "genesis": 1, "serial": 1,
            "status": status, "seal_hash": "a" * 64,
            "seal_sig_present": sealed,
            "block": ({"hash": "b" * 64, "height": 2, "ts": "x"}
                      if status == "live" else None),
            "chain_verify": {"ok": True, "errors": [], "blocks": 2,
                             "nft_mint_blocks_for_rid": 1 if minted else 0},
            "rtracker_status": "live" if minted else "dry",
            "rtracker_asset_hash": "c" * 64,
            "wallet": {"display": asset_id, "balance": 1,
                       "unit": "RID-ASSET", "transferable": False},
        }

    def test_rgeneratr_assets_live_gate(self):
        path = self._write_feed([
            self._asset("rid-live", "live", True, True),
            self._asset("rid-fake-live", "live", False, False),
            self._asset("rid-preview-ready", "preview — pending", True, True),
        ])
        out = analyze.rgeneratr_assets(path)
        self.assertTrue(out["sidecar"]["present"])
        self.assertTrue(out["sidecar"]["match"])
        self.assertEqual(out["live"], 2)
        self.assertEqual(out["preview"], 1)
        by_id = {a["asset_id"]: a for a in out["assets"]}
        self.assertTrue(by_id["rid-live"]["gate_consistent"])
        self.assertNotIn("flag", by_id["rid-live"])
        fake = by_id["rid-fake-live"]
        self.assertFalse(fake["gate_consistent"])
        self.assertIn("INCONSISTENT", fake["flag"])
        ready = by_id["rid-preview-ready"]
        self.assertTrue(ready["live_gate"]["eligible"])
        self.assertIn("writer has not flipped it", ready["flag"])

    def test_rgeneratr_assets_sidecar_mismatch(self):
        path = self._write_feed(
            [self._asset("rid-x", "preview — pending", False, False)])
        (self.dir / "assets.json.sha256").write_text("0" * 64 + "\n")
        out = analyze.rgeneratr_assets(path)
        self.assertTrue(out["sidecar"]["present"])
        self.assertTrue(out["sidecar"]["readable"])
        self.assertFalse(out["sidecar"]["match"])

    def test_rgeneratr_assets_missing_and_bad_schema(self):
        out = analyze.rgeneratr_assets(self.dir / "nope.json")
        self.assertFalse(out["exists"])
        self.assertEqual(out["assets"], [])
        path = self._write_feed(
            [self._asset("rid-x", "preview — pending", False, False)],
            sidecar=False, schema="wrong.schema")
        out = analyze.rgeneratr_assets(path)
        self.assertFalse(out["schema_ok"])
        self.assertEqual(len(out["assets"]), 1)

    def _write_snapshot(self, entries, manifest_pin=None):
        snap = {
            "schema": "rzl.rpotlatch.rtrackr.snapshot.v2",
            "generated": "2026-11-19T00:00:00-07:00",
            "generated_label": "test",
            "entries": entries,
            "holders": [{"a": 1}],
            "wallets": [{"b": 2}, {"b": 3}],
            "token": {"name": "Я", "symbol": "Я", "chain": "solana",
                      "mint": "BB9uA5BuacDnWyDf5Npc9nMb9yFbyThsNrQPBYJ5Q1Lv",
                      "decimals": 9, "supply_ui": 1000000},
            "pool": {"dex": "orca", "pair": "Я/SOL", "address": "HSroUx",
                     "liquidity_usd": 4.06, "price_usd": 0.0000367},
        }
        path = self.dir / "snap.json"
        raw = json.dumps(snap).encode("utf-8")
        path.write_bytes(raw)
        manifest = None
        if manifest_pin is not None:
            # True pins the file's own hash (a matching manifest).
            pin = sha256_bytes(raw) if manifest_pin is True else manifest_pin
            manifest = self.dir / "SHA256SUMS"
            manifest.write_text("%s  data/snap.json\n" % pin)
        return path, manifest, raw

    def test_wallet_snapshot_synthetic(self):
        entries = [
            {"rid": "ЯID-0001-3QQS", "name": "owner", "kind": "wallet.asset.rid",
             "mode": "live", "block_hash": "a" * 64, "status": None},
            {"rid": "ЯID-0014-KREH", "name": "ThundR wallet", "kind": "wallet.asset.rid",
             "mode": None, "block_hash": None, "status": "registered"},
        ]
        path, manifest, raw = self._write_snapshot(entries, manifest_pin=True)
        out = analyze.wallet_snapshot(path, manifest)
        self.assertTrue(out["exists"])
        self.assertTrue(out["schema_ok"])
        self.assertEqual(out["entries"], 2)
        self.assertEqual(out["distinct_rids"], 2)
        self.assertEqual(out["live_rows"], 1)
        self.assertEqual(len(out["registered_unsealed"]), 1)
        self.assertEqual(out["registered_unsealed"][0]["rid"], "ЯID-0014-KREH")
        self.assertEqual(out["token"]["decimals"], 9)
        self.assertEqual(out["pool"]["pair"], "Я/SOL")
        self.assertTrue(out["verification"]["checked"])
        self.assertTrue(out["verification"]["match"])
        self.assertEqual(out["verification"]["verdict"], "verified")

    def test_wallet_snapshot_mismatch_reported(self):
        path, manifest, _raw = self._write_snapshot(
            [], manifest_pin="0" * 64)
        out = analyze.wallet_snapshot(path, manifest)
        self.assertFalse(out["verification"]["match"])
        self.assertIn("MISMATCH", out["verification"]["verdict"])

    def test_wallet_snapshot_no_manifest(self):
        path, _m, _raw = self._write_snapshot([])
        out = analyze.wallet_snapshot(path)
        self.assertFalse(out["verification"]["checked"])

    def test_wallet_snapshot_real_files(self):
        # Grounding fixtures: the real baked snapshot + manifest. The
        # manifest pins point at the -2 variants, so the base snapshot
        # (older revision) mismatches — and the -2 file matches.
        snap = (ROOT / "grounding" / "rwalet"
                / "rtrackr-snapshot.json.bin")
        manifest = (ROOT / "grounding" / "rwalet"
                    / "rbox.web.rwalet.SHA256SUMS")
        out = analyze.wallet_snapshot(snap, manifest)
        self.assertTrue(out["schema_ok"])
        self.assertEqual(out["entries"], 11)
        self.assertEqual(out["distinct_rids"], 4)
        self.assertEqual(out["wallets"], 4)
        self.assertFalse(out["verification"]["match"])
        self.assertTrue(out["verification"]["pin_found"])
        self.assertIn("MISMATCH", out["verification"]["verdict"])
        rids = {r["rid"] for r in out["registered_unsealed"]}
        self.assertIn("ЯID-0014-KREH", rids)
        snap2 = (ROOT / "grounding" / "rtrackr"
                 / "rtrackr-snapshot-2.json")
        check = analyze.verify_manifest_pin(snap2, manifest)
        self.assertTrue(check["pin_found"])
        self.assertTrue(check["match"])
        bundle = (ROOT / "grounding" / "rwalet"
                  / "rwalet-defi.bundle.mjs")
        check = analyze.verify_manifest_pin(bundle, manifest)
        self.assertTrue(check["match"])


class TestDebug(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_log_tail_redacts(self):
        log = self.dir / "app.log"
        log.write_text("hello world\nmy password is hunter2\n"
                       "token abcdefghijklmnopqrstuvwxyz0123456789ABCD\n"
                       "last line\n")
        tail = debug.log_tail(log, count=10)
        self.assertEqual(len(tail["lines"]), 4)
        self.assertEqual(tail["lines"][0], "hello world")
        self.assertEqual(tail["lines"][1], "[redacted]")
        self.assertEqual(tail["lines"][2], "[redacted]")
        self.assertNotIn("hunter2", json.dumps(tail))

    def test_log_tail_missing(self):
        tail = debug.log_tail(self.dir / "nope.log")
        self.assertFalse(tail["exists"])
        self.assertEqual(tail["lines"], [])

    def test_transcript_read(self):
        tr = self.dir / "t.jsonl"
        tr.write_text('{"text": "one"}\n{"text": "two"}\nnot json\n')
        out = debug.transcript_read(tr, limit=2)
        self.assertEqual(len(out["records"]), 2)
        self.assertEqual(out["records"][0]["text"], "one")
        self.assertEqual(out["total_lines"], 3)

    def test_self_test_all_pass(self):
        res = debug.self_test()
        self.assertTrue(res["all_pass"])
        self.assertEqual(res["failed"], 0)


class TestRepair(unittest.TestCase):
    def test_propose_never_executes(self):
        plan = repair.propose({"models": {"exists": False, "dir": "/nonexistent"}})
        self.assertFalse(plan["executed"])
        self.assertIn("NOT EXECUTED", plan["title"])
        self.assertGreater(plan["step_count"], 0)
        self.assertTrue(all(s["executed"] is False for s in plan["steps"]))

    def test_propose_empty_findings(self):
        plan = repair.propose({})
        self.assertEqual(plan["steps"][0]["action"], "investigate")

    def test_apply_refuses_without_go(self):
        plan = repair.propose({})
        with self.assertRaises(Refused):
            repair.apply(plan)
        with self.assertRaises(Refused):
            repair.apply(plan, go=False)

    def test_apply_with_go_executes_nothing_mutating(self):
        plan = repair.propose({"models": {"exists": False, "dir": "/nonexistent"}})
        report = repair.apply(plan, go=True)
        self.assertFalse(report["executed_anything"])
        self.assertEqual(len(report["applied"]), 0)
        self.assertGreater(len(report["refused"]), 0)

    def test_apply_refuses_never_operations_even_with_go(self):
        plan = {"title": repair.NOT_EXECUTED, "steps": [
            {"id": "R01", "action": "sign", "target": "x",
             "detail": "sign this", "executed": False},
            {"id": "R02", "action": "mint", "target": "y",
             "detail": "mint this", "executed": False},
            {"id": "R03", "action": "swap", "target": "z",
             "detail": "swap this", "executed": False},
            {"id": "R04", "action": "noop", "target": "w",
             "detail": "no-op", "executed": False},
        ], "step_count": 4, "executed": False}
        report = repair.apply(plan, go=True)
        refused = {r["action"]: r for r in report["refused"]}
        self.assertIn("sign", refused)
        self.assertIn("mint", refused)
        self.assertIn("swap", refused)
        self.assertIn("never performed by the adapter",
                      refused["sign"]["reason"])
        self.assertIn("RGHOSTKEY", refused["mint"]["reason"])
        self.assertEqual([a["action"] for a in report["applied"]], ["noop"])

    def test_plan_store_approve_by_reference(self):
        store = repair.PlanStore()
        plan = repair.propose({})
        plan_id, nonce = store.store(plan)
        self.assertTrue(plan_id.startswith("tpa-plan-"))
        self.assertEqual(store.load(plan_id, nonce), plan)
        with self.assertRaises(Refused):
            store.load(plan_id, "wrong-nonce")
        with self.assertRaises(Refused):
            store.load("tpa-plan-nope", nonce)
        plan_id2, nonce2 = store.store(repair.propose({}))
        self.assertNotEqual(plan_id, plan_id2)
        self.assertNotEqual(nonce, nonce2)
        self.assertEqual(len(store), 2)


class TestUpdate(unittest.TestCase):
    def test_check_no_canonical(self):
        # On this VM there is no canonical registry; live == bundled.
        res = update.check()
        self.assertFalse(res["update_available"])
        self.assertTrue(res["in_sync"])
        self.assertEqual(res["live_stamp"], res["bundled_stamp"])

    def test_check_open_items(self):
        res = update.check()
        items = res["open_items"]
        self.assertEqual(len(items["items"]), 3)
        self.assertFalse(any("RbotLoadR" in i for i in items["items"]))
        self.assertTrue(any("RGENERATR" in i for i in items["items"]))
        self.assertTrue(any("RMIND" in i for i in items["items"]))
        # Gap #0 closed as a draft: it awaits signing, not building.
        self.assertTrue(any("RbotLoadR 0.0.1" in s
                            for s in items["awaiting_signing"]))
        self.assertIn("never auto-fixes", items["note"])

    def test_apply_refuses_without_go(self):
        with self.assertRaises(Refused):
            update.apply()
        with self.assertRaises(Refused):
            update.apply(go=False)

    def test_apply_content_bound(self):
        # A canonical file distinct from the bundled snapshot, with a
        # wrong expected stamp: refused before anything is written.
        with tempfile.TemporaryDirectory() as tmp:
            from thundr_adapter.registry import BUNDLED_SNAPSHOT
            canonical = Path(tmp) / "thundr-commands.json"
            canonical.write_bytes(BUNDLED_SNAPSHOT.read_bytes())
            with self.assertRaises(Refused) as ctx:
                update.apply(go=True, canonical_path=canonical,
                             expected_stamp="0" * 64)
            self.assertIn("changed since the check", str(ctx.exception))


class TestPlugins(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.entry = self.dir / "example.py"
        self.entry.write_text("# fake plugin entry\nVALUE = 1\n")
        self.manifest = {
            "schema": "tpa.plugin.v1",
            "name": "example-plugin",
            "version": "0.1.0",
            "description": "A fake plugin for tests.",
            "entry": "example.py",
            "sha256": sha256_bytes(self.entry.read_bytes()),
            "capabilities": [
                {"name": "example.echo", "method": "adapter.chat",
                 "description": "Echoes text."}
            ],
        }
        self.manifest_path = self.dir / "example.tpa-plugin.json"
        self.manifest_path.write_text(json.dumps(self.manifest))

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_and_verify_ok(self):
        manifest = plugins.load_manifest(self.manifest_path)
        self.assertEqual(manifest["name"], "example-plugin")
        check = plugins.verify(manifest, self.dir)
        self.assertTrue(check["ok"])
        self.assertEqual(check["sha256"], self.manifest["sha256"])

    def test_verify_rejects_tampered_entry(self):
        self.entry.write_text("# tampered\n")
        manifest = plugins.load_manifest(self.manifest_path)
        check = plugins.verify(manifest, self.dir)
        self.assertFalse(check["ok"])
        self.assertIn("sha256 mismatch", check["reason"])

    def test_verify_rejects_symlink_entry(self):
        target = self.dir / "real.py"
        target.write_text("# real\n")
        link = self.dir / "linked.py"
        os.symlink(target, link)
        manifest = dict(self.manifest, entry="linked.py",
                        sha256=sha256_bytes(target.read_bytes()))
        check = plugins.verify(manifest, self.dir)
        self.assertFalse(check["ok"])
        self.assertIn("symlinked", check["reason"])

    def test_verify_rejects_escape(self):
        manifest = dict(self.manifest, entry="../escape.py")
        check = plugins.verify(manifest, self.dir)
        self.assertFalse(check["ok"])

    def test_load_rejects_bad_manifest(self):
        bad = self.dir / "bad.json"
        bad.write_text(json.dumps({"schema": "wrong"}))
        with self.assertRaises(plugins.PluginError):
            plugins.load_manifest(bad)

    def test_capability_registry(self):
        reg = plugins.CapabilityRegistry()
        manifest = plugins.load_manifest(self.manifest_path)
        report = reg.register(manifest, self.dir)
        self.assertTrue(report["verified"])
        self.assertEqual(report["registered"], ["example.echo"])
        self.assertEqual(reg.get("example.echo")["plugin"], "example-plugin")
        # Second registration of the same capability is skipped, not doubled.
        report2 = reg.register(manifest, self.dir)
        self.assertEqual(report2["registered"], [])
        self.assertEqual(len(report2["skipped"]), 1)


class TestChat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = Registry.load()

    def test_help_is_deterministic(self):
        res = chat.route("help", registry=self.reg, try_mcr=False)
        self.assertTrue(res["ok"])
        self.assertEqual(res["via"], "adapter.chat/registry-help")
        self.assertIn("124 known", res["reply"])

    def test_commands_get(self):
        res = chat.route("commands C001", registry=self.reg, try_mcr=False)
        self.assertTrue(res["ok"])
        self.assertIn("C001", res["reply"])

    def test_offline_answer_is_honest(self):
        # MCR port 1 refuses instantly; nothing can fake a brain reply.
        res = chat.route("tell me a story about dragons",
                         registry=self.reg, mcr_port=1, try_mcr=True)
        self.assertTrue(res["ok"])
        self.assertIn("No live ThundR brain is reachable", res["reply"])
        self.assertIn("MCR :1 did not answer", res["reply"])

    def test_empty_question(self):
        res = chat.route("   ", registry=self.reg, try_mcr=False)
        self.assertFalse(res["ok"])


class TestServer(unittest.TestCase):
    """Live loopback server on an ephemeral port (bind 127.0.0.1 only)."""

    TOKEN = "test-token-not-a-secret"

    @classmethod
    def setUpClass(cls):
        adapter = server.Adapter()
        handler = server.make_handler(adapter, cls.TOKEN)
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.httpd.daemon_threads = True
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever,
                                      daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:%d" % cls.port

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def test_health_open(self):
        c = client.Client(self.base)
        res = c.health()
        self.assertTrue(res["ok"])
        self.assertEqual(res["service"], "thundr-adapter")

    def test_call_requires_auth(self):
        c = client.Client(self.base)
        res = c.call("adapter.hello")
        self.assertFalse(res["ok"])
        self.assertIn("bearer token", res["error"].lower())

    def test_call_with_auth(self):
        c = client.Client(self.base, token=self.TOKEN)
        res = c.call("adapter.hello")
        self.assertTrue(res["ok"])
        self.assertEqual(res["data"]["protocol"], "tpa.v1")

    def test_analyze_components_via_server(self):
        c = client.Client(self.base, token=self.TOKEN)
        res = c.call("adapter.analyze", {"kind": "components"})
        self.assertTrue(res["ok"])
        by_name = {x["name"]: x for x in res["data"]["components"]}
        self.assertEqual(by_name["RbotLoadR"]["status"],
                         "0.0.1 UNSIGNED DRAFT, verified")
        self.assertEqual(len(res["data"]["gaps"]), 3)

    def test_analyze_rgeneratr_assets_via_server(self):
        c = client.Client(self.base, token=self.TOKEN)
        res = c.call("adapter.analyze", {
            "kind": "rgeneratr-assets",
            "feed_path": "grounding/rgeneratr/rgeneratr-assets-snapshot.json"})
        self.assertTrue(res["ok"])
        self.assertEqual(res["data"]["owners"], 1)
        self.assertEqual(res["data"]["preview"], 1)
        self.assertEqual(res["data"]["assets"][0]["asset_id"],
                         "rid-asset-0001-genesis")

    def test_visual_float_window_via_server(self):
        c = client.Client(self.base, token=self.TOKEN)
        res = c.call("adapter.visual", {"kind": "float-window"})
        self.assertTrue(res["ok"])
        self.assertIn("GRANITE 4.2 3B", res["data"]["header"])
        self.assertIn("127.0.0.1:4983", res["data"]["header"])

    def test_hello_lists_never_operations(self):
        c = client.Client(self.base, token=self.TOKEN)
        res = c.call("adapter.hello")
        self.assertEqual(res["data"]["never"],
                         ["enroll", "mint", "seal", "send", "sign", "swap",
                          "transfer"])

    def test_analyze_rid_via_server(self):
        c = client.Client(self.base, token=self.TOKEN)
        res = c.call("adapter.analyze",
                     {"kind": "rid", "rid": "ЯID-0001-3QQS"})
        self.assertTrue(res["ok"])
        self.assertTrue(res["data"]["valid"])
        res = c.call("adapter.analyze",
                     {"kind": "rid", "rid": "ЯID-0001-3QQQ"})
        self.assertTrue(res["ok"])
        self.assertFalse(res["data"]["valid"])

    def test_analyze_wallet_snapshot_via_server(self):
        c = client.Client(self.base, token=self.TOKEN)
        res = c.call("adapter.analyze", {
            "kind": "wallet-snapshot",
            "snapshot_path": "grounding/rwalet/rtrackr-snapshot.json.bin",
            "manifest_path": "grounding/rwalet/rbox.web.rwalet.SHA256SUMS"})
        self.assertTrue(res["ok"])
        self.assertEqual(res["data"]["entries"], 11)
        self.assertFalse(res["data"]["verification"]["match"])

    def test_analyze_rtrackr_feed_via_server(self):
        c = client.Client(self.base, token=self.TOKEN)
        res = c.call("adapter.analyze", {
            "kind": "rtrackr-feed", "chain_port": 1,
            "derived_path": "grounding/rtrackr/rtrackr-game-assets.json"})
        self.assertTrue(res["ok"])
        self.assertTrue(res["data"]["source"].startswith("derived:"))
        self.assertEqual(res["data"]["live"], 5)

    def test_repair_apply_by_reference_via_server(self):
        c = client.Client(self.base, token=self.TOKEN)
        proposed = c.call("adapter.repair.propose", {})
        self.assertTrue(proposed["ok"])
        plan_id = proposed["data"]["plan_id"]
        nonce = proposed["data"]["nonce"]
        # Wrong nonce: refused.
        res = c.call("adapter.repair.apply",
                     {"plan_id": plan_id, "nonce": "wrong", "go": True})
        self.assertFalse(res["ok"])
        self.assertTrue(res["refused"])
        # Payload instead of reference: refused.
        res = c.call("adapter.repair.apply",
                     {"plan": proposed["data"], "go": True})
        self.assertFalse(res["ok"])
        self.assertIn("approve by reference", res["error"])
        # Right id + nonce, no GO: refused.
        res = c.call("adapter.repair.apply",
                     {"plan_id": plan_id, "nonce": nonce})
        self.assertFalse(res["ok"])
        self.assertTrue(res["refused"])
        # Right id + nonce + GO: applies the stored plan (v0.1: nothing
        # mutating, steps refused individually).
        res = c.call("adapter.repair.apply",
                     {"plan_id": plan_id, "nonce": nonce, "go": True})
        self.assertTrue(res["ok"])
        self.assertFalse(res["data"]["executed_anything"])

    def test_unknown_method(self):
        c = client.Client(self.base, token=self.TOKEN)
        res = c.call("adapter.hello")  # sanity: client validates method names
        self.assertTrue(res["ok"])

    def test_origin_check(self):
        import urllib.request
        req = urllib.request.Request(
            self.base + "/health",
            headers={"Origin": "https://evil.example.com"}, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                body = json.loads(resp.read())
        except Exception as exc:  # noqa: BLE001 - HTTPError carries the body
            body = json.loads(exc.read())
        self.assertFalse(body["ok"])
        self.assertIn("local origin", body["error"])

    def test_safe_path_blocks_escape(self):
        with self.assertRaises(ValueError):
            server.safe_path("../../etc/passwd", ROOT)
        inside = server.safe_path("tests", ROOT)
        self.assertTrue(str(inside).startswith(str(ROOT)))

    def test_token_file_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = server.write_token_file("tok", Path(tmp) / "token")
            self.assertEqual(oct(path.stat().st_mode & 0o777), "0o600")


class TestVisual(unittest.TestCase):
    def test_orb_state_no_root(self):
        out = visual.orb_state(root="/nonexistent-root-xyz")
        self.assertFalse(out["root_exists"])
        self.assertEqual(out["found"], [])

    def test_shot_hook_never_executes(self):
        hook = visual.shot_hook()
        self.assertFalse(hook["executed"])
        self.assertIn("GO", hook["note"])

    def test_panel_state(self):
        panels = visual.panel_state()
        self.assertIn("profile", panels["panels"])
        self.assertIn("ghostmachine", panels["panels"])

    def test_float_window_layout(self):
        layout = visual.float_window()
        self.assertIn("GRANITE 4.2 3B", layout["header"])
        self.assertIn("127.0.0.1:4983", layout["header"])
        self.assertIn("use qwen", layout["shell"])
        self.assertIn("use granite", layout["shell"])
        self.assertIn("wallet balances", layout["ready_reply"])
        self.assertIn("Qwen 1.7B", layout["status_bar"])

    def test_run_includes_float_window(self):
        report = visual.run()
        self.assertIn("float_window", report)
        self.assertEqual(report["float_window"]["app"].split(" (")[0],
                         "RTHUNDR")


class TestSwiftContract(unittest.TestCase):
    """Source-contract checks on swift/ThundRAdapter.swift.

    Same pattern as RIZALEON/RTHUNDR tests/test_contract.py: assert on
    the Swift source text. These do NOT compile Swift (no Xcode here).
    """

    @classmethod
    def setUpClass(cls):
        cls.swift = (ROOT / "swift" / "ThundRAdapter.swift").read_text()

    def test_honest_header(self):
        self.assertIn("written-but-uncompiled", self.swift)
        self.assertIn("no Xcode", self.swift)

    def test_method_names(self):
        for method in protocol.METHODS:
            self.assertIn('"%s"' % method, self.swift, msg=method)

    def test_refuse_rules_present(self):
        self.assertIn("^optimize\\\\s+(clean|deep)\\\\b", self.swift)
        self.assertIn("^17e\\\\s+(uninstall|delete|rm|sign|keychain|wallet)\\\\b",
                      self.swift)
        self.assertIn("refuseRules", self.swift)

    def test_help_before_brain(self):
        help_at = self.swift.index('["help", "commands", "functions", "?"]')
        brain_at = self.swift.index("No live ThundR brain is reachable")
        self.assertLess(help_at, brain_at)

    def test_no_network(self):
        self.assertNotIn("URLSession", self.swift)
        self.assertNotIn("URLRequest", self.swift)

    def test_no_execution(self):
        self.assertIn("Maintenance execution NOT GRANTED", self.swift)
        self.assertIn("no approval/apply handler", self.swift)
        self.assertIn("REPAIR PROPOSAL — NOT EXECUTED", self.swift)

    def test_envelope_shape(self):
        self.assertIn('"ok": true', self.swift)
        self.assertIn('"via": via', self.swift)

    def test_go_gated_verbs(self):
        self.assertIn("goGatedPattern", self.swift)
        self.assertIn("goGatedCheck", self.swift)
        self.assertIn('"go_gated": true', self.swift)
        self.assertIn("prompt faceid", self.swift)
        self.assertIn("request approval", self.swift)
        self.assertIn("/rmint/request", self.swift)

    def test_engine_verbs_and_relay(self):
        self.assertIn("modelsText", self.swift)
        self.assertIn('"models", "list models", "model"', self.swift)
        self.assertIn('"use qwen", "engine qwen"', self.swift)
        self.assertIn('"use granite", "engine granite"', self.swift)
        self.assertIn("4983", self.swift)
        self.assertIn("Granite 4.2 3B", self.swift)


class TestSpecText(unittest.TestCase):
    """Source-contract checks on ADAPTER.md (v0.1.1).

    Guards the t31u mail-rule correction, the command-authorization
    policy (Rizal's explicit GO is sufficient; biometric optional,
    never required), the AUTOMANUAL doctrine, and the ONE RULE in §6
    against regressions:
    the spec must name the superseded rule as superseded, never state
    it as live law, and never state a biometric as a requirement.
    """

    @classmethod
    def setUpClass(cls):
        cls.spec = (ROOT / "ADAPTER.md").read_text()

    def test_mail_rule_is_t31u(self):
        self.assertIn("t31u policy, 2026-11-11", self.spec)
        self.assertIn("mail CAN trigger", self.spec)
        self.assertIn("mail never", self.spec)
        self.assertIn("auto-signs", self.spec)
        self.assertIn("Rizal's explicit command (GO) authorizes",
                      self.spec)
        self.assertIn("no biometric step is required", self.spec)

    def test_stale_mail_rule_not_stated_as_law(self):
        self.assertNotIn("triggers sign or mint", self.spec)
        self.assertNotIn("only on the owner's Face ID", self.spec)
        self.assertNotIn("seal completes only on", self.spec)
        self.assertNotIn("Biometric-only", self.spec)

    def test_automanual_doctrine_present(self):
        self.assertIn("AUTOMANUAL doctrine (index and quote, never dump)",
                      self.spec)
        self.assertIn("UNIFIED §x.y", self.spec)
        self.assertIn("spec-only in v0.1.1", self.spec)

    def test_adapter_version(self):
        self.assertEqual(protocol.ADAPTER_VERSION, "0.1.1")
        self.assertIn("adapter version `0.1.1`", self.spec)

    def test_one_rule_in_section_6(self):
        self.assertIn("ONE RULE (RSOL BOTKARD TEMPLATE, Rizal 2026-11-19)",
                      self.spec)
        self.assertIn("YOU CAN NEVER ERASE OR REMOVE A SKILL OR MEMORY",
                      self.spec)
        self.assertIn("Repairs and updates are add-only", self.spec)


if __name__ == "__main__":
    unittest.main()
