# ThundR Plugin Adapter (TPA) v0.1

An integrated plugin adapter that lets any bot or AI — including Muse —
communicate with ThundR, run diagnostics, analysis, debugging, repairs,
updates, and coding + visual integrations. The target is the macOS
RTHUNDR app from the THUNDR-CRYPTOBOT Xcode workspace (canonical 1.2.0).

Offline-first, loopback-only, GO-gated. The adapter routes, reports, and
proposes. It never signs, seals, enrolls, mints, sends, swaps, or
transfers anything; it never writes the chain, the wallet, or a feed.

**Spec:** [`ADAPTER.md`](ADAPTER.md) — protocol, safety rules, transport,
plugin format, grounding trace. **Muse skill:**
`~/workspace/custom-skills/thundr-adapter/SKILL.md`.

## Layout

```
thundr-adapter/
  ADAPTER.md            the spec (start here)
  README.md             this file
  grounding/            grounding files (read-only; never modified)
    thundr-commands.json  canonical 124-command registry
    hosts.json            host map
    gen-thundr-core.py    codegen pattern
    thundr_chat.py        chat handler
    controlroom.py        MCR command centre
    thundr-float-live-2026-11-19.png   live float screenshot
    rzl-index-digest.md / rzl-index.txt   .rzl parts catalog
    rbotloadr-0.0.1/      RbotLoadR loader draft
    rgeneratr/            RGENERATR adapter spec + assets snapshot
    rghostchain-digest.md / rghostchain/   ledger + submit daemon
    rghostkey-digest.md / rghostkey/       polykey interface
    rwalet-digest.md / rwalet/             watch-only wallet
    rtrackr-digest.md / rtrackr/           public tracker / read layer
  python/thundr_adapter/  reference implementation (stdlib only, Py 3.9+)
    protocol.py     tpa.v1 envelope, 12 methods, errors, never-ops
    registry.py     registry loader + queries + refuse enforcement
    server.py       loopback-only HTTP server (127.0.0.1:8742)
    client.py       loopback-only client
    diagnostics.py  engines, GGUF inventory, chain, keys, wallet, rtrackr
    analyze.py      file info, diffs, components, asset feeds, RID, wallet
    debug.py        log tails, transcripts, self-test (dry-run)
    repair.py       propose plans (never executes); apply by reference + GO
    update.py       check stamps; apply content-bound + GO
    visual.py       float/orb/panel state; float-window layout
    chat.py         route text: refuse → GO-gate → help/engines → MCR → registry
    chain.py        RGHOSTCHAIN read-only access + RTRACKR feed + DRY queues
    rid.py          ЯID checksum validation (daemon's rule, verbatim)
    plugins.py      plugin manifest load + sha256 verification
    cli.py          `thundr-adapter` CLI
    data/           bundled registry snapshot + stamp metadata
  swift/
    ThundRAdapter.swift   native-side adapter (Foundation only;
                          written-but-uncompiled — no Xcode on this VM)
  tests/
    test_adapter.py   unittest suite (run: python3 -m unittest discover -s tests -v)
```

## Quickstart

```sh
cd ~/workspace/thundr-adapter
PYTHONPATH=python python3 -m thundr_adapter hello
PYTHONPATH=python python3 -m thundr_adapter chat "help" --no-mcr
PYTHONPATH=python python3 -m thundr_adapter chat "models" --no-mcr
PYTHONPATH=python python3 -m thundr_adapter diagnostics
PYTHONPATH=python python3 -m thundr_adapter analyze components
PYTHONPATH=python python3 -m thundr_adapter analyze rid --rid ЯID-0001-3QQS
PYTHONPATH=python python3 -m thundr_adapter repair-propose
PYTHONPATH=python python3 -m thundr_adapter update-check
PYTHONPATH=python python3 -m thundr_adapter visual float-window
PYTHONPATH=python python3 -m thundr_adapter serve   # loopback http://127.0.0.1:8742
```

Every command prints one JSON envelope and exits 0 on `ok`, 1 on error,
2 on a GO/refuse refusal. `--pretty` indents the output.

## Safety (the short version)

- **Refuse rules:** the registry's 7 refuse regexes are enforced at the
  adapter layer for every agent. A match is refused; nothing runs.
- **GO-gated:** wallet/signing verbs (`wallet balances`, `casket verify`,
  `signing status`, `prompt faceid`, `sign this`, `request approval`)
  map to the LIVE `/rmint/request` flow. The adapter hands
  them back for Rizal's explicit GO — his command is sufficient
  authorization, no biometric step required; it never forwards them.
- **Never:** sign, seal, enroll, mint, send, swap, transfer — not even
  with GO. No method exists for them. Signing happens only on the
  pinned device, by the human, through RGHOSTKEY.
- **Repairs/updates:** propose-only until GO. Apply is by reference
  (plan id + nonce; the server loads the stored plan) and content-bound
  (updates refuse when the registry changed since the check). v0.1
  executes nothing mutating.
- **Chain:** read-only. GET `/health`, `/rtrackr/assets`, `/market/view`,
  `/market/verify` only. Submit/register/ingest POSTs are refused by name.
- **Wallet:** watch-only. Roster / snapshot / pool state only.
- **Truth law:** when no live brain is reachable, the adapter says so
  and answers only from the registry. It never fakes a live reply.

## Tests

```sh
python3 -m unittest discover -s tests -v
```

126 tests, all passing (2026-11-19): protocol shapes, all 7 refuse
patterns, GO-gated verbs, engine verbs + preference, loopback-only
client, diagnostics on fixture dirs, registry diff, component check,
asset-feed live gate, chain read-only rules, RID checksums, plan store
approve-by-reference, never-operations, wallet snapshot + manifest
verification, RTRACKR feed fallback order, DRY-only queue, server
end-to-end on an ephemeral loopback port, Swift source contracts.

## Unverified

- Swift is written-but-uncompiled (no Xcode here).
- No live ThundR tested against (MCR, Granite relay, daemon all
  unreachable from this VM; tested against fake local servers).
- Port 8742 assumed free on the Mac, not verified there.
- See ADAPTER.md §16 for the full honest-limits list.
