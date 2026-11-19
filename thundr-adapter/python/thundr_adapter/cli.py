"""`thundr-adapter` command line: drive the adapter without writing code.

Works offline against the bundled registry snapshot when no ThundR tree
is present. The `serve` subcommand starts the loopback server; the rest
run locally in-process (no server needed).

    thundr-adapter hello
    thundr-adapter commands --group thundr
    thundr-adapter commands C042
    thundr-adapter commands --search "open app"
    thundr-adapter chat "help"
    thundr-adapter chat "what is the ghost chain?"
    thundr-adapter diagnostics [--model-dir DIR] [--knowledge-dir DIR] [--chain-port PORT] [--wallet-snapshot PATH] [--wallet-manifest PATH] [--rtrackr-derived PATH] [--rtrackr-cache PATH]
    thundr-adapter analyze file --path RELATIVE/PATH
    thundr-adapter analyze registry-diff
    thundr-adapter analyze hosts [--hosts-path PATH]
    thundr-adapter analyze components
    thundr-adapter analyze rgeneratr-assets --path RELATIVE/PATH
    thundr-adapter analyze rid --rid ЯID-0001-3QQS
    thundr-adapter analyze wallet-snapshot --path RELATIVE/PATH [--manifest PATH]
    thundr-adapter analyze rtrackr-feed [--derived PATH] [--cache PATH] [--chain-port PORT]
    thundr-adapter debug self-test
    thundr-adapter debug log-tail --path RELATIVE/PATH [--count N]
    thundr-adapter repair-propose
    thundr-adapter update-check
    thundr-adapter visual [float|float-window|orb|panels|shot|all]
    thundr-adapter serve [--port 8742]

Every command prints one JSON envelope (``--pretty`` for indented output)
and exits 0 on ``ok``, 1 otherwise. Refusals (including GO-gated
wallet/signing verbs) exit 2 so scripts can tell a GO/refuse refusal
from an ordinary error.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__, protocol
from .registry import Registry
from .server import Adapter


def _emit(envelope: dict, pretty: bool) -> int:
    print(json.dumps(envelope, ensure_ascii=False,
                     indent=2 if pretty else None))
    if envelope.get("ok"):
        return 0
    if envelope.get("refused") or envelope.get("go_gated"):
        return 2
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="thundr-adapter",
        description="ThundR Plugin Adapter %s (%s): communicate with, "
                    "diagnose, analyze, debug, repair-plan, update-check "
                    "and visualise ThundR — offline, loopback-only."
                    % (__version__, protocol.VERSION))
    parser.add_argument("--pretty", action="store_true",
                        help="indent the JSON envelope")
    parser.add_argument("--registry", metavar="PATH",
                        help="registry file (default: resolution order)")
    # Same options on every subparser, so `thundr-adapter chat help --pretty`
    # works as well as `thundr-adapter --pretty chat help`.
    common = argparse.ArgumentParser(add_help=False)
    # SUPPRESS so a subparser that does not see the flag leaves the
    # top-level value alone (argparse subparser defaults would clobber it).
    common.add_argument("--pretty", action="store_true",
                        default=argparse.SUPPRESS,
                        help="indent the JSON envelope")
    common.add_argument("--registry", metavar="PATH",
                        default=argparse.SUPPRESS,
                        help="registry file (default: resolution order)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("hello", parents=[common],
                   help="adapter identity, methods, safety stance")

    p_cmd = sub.add_parser("commands", parents=[common],
                           help="list / get / search registry commands")
    p_cmd.add_argument("id", nargs="?", help="command id, e.g. C042")
    p_cmd.add_argument("--group", help="filter by group (substring, case-insensitive)")
    p_cmd.add_argument("--host", help="filter by host, e.g. macos")
    p_cmd.add_argument("--search", metavar="WORDS", help="search id/cmd/does/group")
    p_cmd.add_argument("--limit", type=int, default=20)

    p_chat = sub.add_parser("chat", parents=[common], help="route one line of text to ThundR")
    p_chat.add_argument("text", nargs="+", help="the text to route")
    p_chat.add_argument("--no-mcr", action="store_true",
                        help="skip the live MCR brain attempt (registry only)")
    p_chat.add_argument("--model-dir",
                        help="directory holding .gguf files (for `models`)")

    p_diag = sub.add_parser("diagnostics", parents=[common], help="engine/model/knowledge health (read-only)")
    p_diag.add_argument("--model-dir", help="directory holding .gguf files")
    p_diag.add_argument("--knowledge-dir", help="directory holding knowledge .md files")
    p_diag.add_argument("--chain-port", type=int, default=None,
                        help="RGHOSTCHAIN daemon port (default 8741)")
    p_diag.add_argument("--wallet-snapshot",
                        help="rtrackr snapshot file (watch-only wallet state)")
    p_diag.add_argument("--wallet-manifest",
                        help="SHA256SUMS manifest to verify the snapshot against")
    p_diag.add_argument("--rtrackr-derived",
                        help="derived rtrackr-game-assets.json (fallback feed)")
    p_diag.add_argument("--rtrackr-cache",
                        help="cached rtrackr feed (last-resort fallback)")

    p_an = sub.add_parser("analyze", parents=[common], help="file info, registry diff, host parity")
    an_sub = p_an.add_subparsers(dest="kind", required=True)
    p_file = an_sub.add_parser("file", parents=[common], help="hash + structure of one file")
    p_file.add_argument("--path", required=True, help="path relative to the safe root")
    an_sub.add_parser("registry-diff", parents=[common], help="live registry vs bundled snapshot")
    p_hosts = an_sub.add_parser("hosts", parents=[common], help="hosts.json parity check")
    p_hosts.add_argument("--hosts-path", help="path to hosts.json")
    p_stamp = an_sub.add_parser("build-stamp", parents=[common], help="thundr-build.json vs registry")
    p_stamp.add_argument("--build-path", required=True)
    an_sub.add_parser("components", parents=[common],
                      help=".rzl parts catalog vs the RZL index (RbotLoadR, RVM, …)")
    p_rgen = an_sub.add_parser("rgeneratr-assets", parents=[common],
                               help="RGENERATR asset feed state (read-only)")
    p_rgen.add_argument("--path", required=True,
                        help="path to assets.json, relative to the safe root")
    p_rid = an_sub.add_parser("rid", parents=[common],
                              help="validate a ЯID checksum (RGHOSTCHAIN rule)")
    p_rid.add_argument("--rid", required=True, help="the ЯID to validate")
    p_wal = an_sub.add_parser("wallet-snapshot", parents=[common],
                              help="watch-only wallet/roster snapshot state")
    p_wal.add_argument("--path", required=True,
                       help="path to the snapshot, relative to the safe root")
    p_wal.add_argument("--manifest",
                       help="SHA256SUMS manifest to verify it against")
    p_rt = an_sub.add_parser("rtrackr-feed", parents=[common],
                             help="RTRACKR chain state: live API, derived, cache")
    p_rt.add_argument("--derived", help="derived game-assets JSON path")
    p_rt.add_argument("--cache", help="cached feed JSON path")
    p_rt.add_argument("--chain-port", type=int, default=8741,
                      help="daemon port for the live feed (default 8741)")

    p_dbg = sub.add_parser("debug", parents=[common], help="log tails, transcripts, self-test (dry-run)")
    dbg_sub = p_dbg.add_subparsers(dest="kind", required=True)
    dbg_sub.add_parser("self-test", parents=[common], help="dry-run adapter self-test")
    p_tail = dbg_sub.add_parser("log-tail", parents=[common], help="redacted tail of a log file")
    p_tail.add_argument("--path", required=True, help="path relative to the safe root")
    p_tail.add_argument("--count", type=int, default=50)
    p_tr = dbg_sub.add_parser("transcript", parents=[common], help="read a JSONL transcript")
    p_tr.add_argument("--path", required=True, help="path relative to the safe root")
    p_tr.add_argument("--since", type=int, default=0)
    p_tr.add_argument("--limit", type=int, default=50)

    sub.add_parser("repair-propose", parents=[common], help="propose a repair plan (never executes)")

    sub.add_parser("update-check", parents=[common], help="check for a newer canonical registry")

    p_vis = sub.add_parser("visual", parents=[common], help="float/orb/panel state (read-only)")
    p_vis.add_argument("kind", nargs="?", default="all",
                       choices=["all", "float", "float-window", "orb", "panels", "shot"])

    p_serve = sub.add_parser("serve", parents=[common], help="start the loopback HTTP server")
    p_serve.add_argument("--port", type=int, default=None,
                         help="port (default: $THUNDR_ADAPTER_PORT or 8742)")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    pretty = args.pretty
    if args.command == "serve":
        from .server import serve
        serve(port=args.port)
        return 0
    try:
        registry = Registry.load(args.registry)
    except (OSError, ValueError) as exc:
        return _emit(protocol.fail("registry load failed: %s" % exc,
                                   via="adapter.cli"), pretty)
    adapter = Adapter(registry=registry)
    cmd = args.command
    if cmd == "hello":
        return _emit(adapter.dispatch("adapter.hello", {}), pretty)
    if cmd == "commands":
        if args.id:
            return _emit(adapter.dispatch("adapter.commands.get",
                                          {"id": args.id}), pretty)
        params = {"limit": args.limit}
        if args.group:
            params["group"] = args.group
        if args.host:
            params["host"] = args.host
        if args.search:
            params["q"] = args.search
        return _emit(adapter.dispatch("adapter.commands.list", params), pretty)
    if cmd == "chat":
        from . import chat as _chat
        text = " ".join(args.text)
        return _emit(_chat.route(text, registry=registry,
                                 try_mcr=not args.no_mcr,
                                 model_dir=args.model_dir), pretty)
    if cmd == "diagnostics":
        return _emit(adapter.dispatch("adapter.diagnostics", {
            "model_dir": args.model_dir,
            "knowledge_dir": args.knowledge_dir,
            "chain_port": args.chain_port,
            "wallet_snapshot": args.wallet_snapshot,
            "wallet_manifest": args.wallet_manifest,
            "rtrackr_derived": args.rtrackr_derived,
            "rtrackr_cache": args.rtrackr_cache}), pretty)
    if cmd == "analyze":
        if args.kind == "file":
            return _emit(adapter.dispatch("adapter.analyze", {
                "kind": "file", "path": args.path}), pretty)
        if args.kind == "registry-diff":
            return _emit(adapter.dispatch("adapter.analyze",
                                          {"kind": "registry-diff"}), pretty)
        if args.kind == "hosts":
            return _emit(adapter.dispatch("adapter.analyze", {
                "kind": "hosts", "hosts_path": args.hosts_path}), pretty)
        if args.kind == "build-stamp":
            return _emit(adapter.dispatch("adapter.analyze", {
                "kind": "build-stamp", "build_path": args.build_path}), pretty)
        if args.kind == "components":
            return _emit(adapter.dispatch("adapter.analyze",
                                          {"kind": "components"}), pretty)
        if args.kind == "rgeneratr-assets":
            return _emit(adapter.dispatch("adapter.analyze", {
                "kind": "rgeneratr-assets", "feed_path": args.path}), pretty)
        if args.kind == "rid":
            return _emit(adapter.dispatch("adapter.analyze", {
                "kind": "rid", "rid": args.rid}), pretty)
        if args.kind == "wallet-snapshot":
            return _emit(adapter.dispatch("adapter.analyze", {
                "kind": "wallet-snapshot", "snapshot_path": args.path,
                "manifest_path": args.manifest}), pretty)
        if args.kind == "rtrackr-feed":
            return _emit(adapter.dispatch("adapter.analyze", {
                "kind": "rtrackr-feed", "derived_path": args.derived,
                "cache_path": args.cache,
                "chain_port": args.chain_port}), pretty)
    if cmd == "debug":
        if args.kind == "self-test":
            return _emit(adapter.dispatch("adapter.debug",
                                          {"kind": "self-test"}), pretty)
        if args.kind == "log-tail":
            return _emit(adapter.dispatch("adapter.debug", {
                "kind": "log-tail", "path": args.path,
                "count": args.count}), pretty)
        if args.kind == "transcript":
            return _emit(adapter.dispatch("adapter.debug", {
                "kind": "transcript", "path": args.path,
                "since": args.since, "limit": args.limit}), pretty)
    if cmd == "repair-propose":
        return _emit(adapter.dispatch("adapter.repair.propose", {}), pretty)
    if cmd == "update-check":
        return _emit(adapter.dispatch("adapter.update.check", {}), pretty)
    if cmd == "visual":
        return _emit(adapter.dispatch("adapter.visual",
                                      {"kind": args.kind}), pretty)
    return _emit(protocol.fail("unhandled command: %r" % cmd,
                               via="adapter.cli"), pretty)


if __name__ == "__main__":
    sys.exit(main())
