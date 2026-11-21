# RTOR GHOSTCHAIN cryptoclient 0.2.0 (RTOR · Renjin Torrent)

Renjin Torrent (the RTOR client) + R:> Shell, built from the RENJIN INSTALL PACKAGE (2026-11-20) and
`records/RTOR-INSTALL.md`. One client, the same code on Linux and Android: a static `rtor-ghostchain`
server that serves the UI locally on **http://127.0.0.1:4984** and runs the RTOR loop.

Holds no keys, reads no keys, signs nothing, mints nothing. RMAIL never signs or mints. No measured
RTOR speed, peers or swarm are shown or claimed. No real money moves.

## Linux (x86_64, arm64, riscv64 for RVM)

```
tar xzf rtor-ghostchain-0.2.0-linux-<arch>.tar.gz && cd rtor-ghostchain-0.2.0-linux-<arch>
./run-linux.sh --check     # .rzl SHA256 + recorded magnet + embedded UI + CHAIN VERIFY; must PASS
./run-linux.sh             # serve on 127.0.0.1:4984 and keep the RTOR loop running
```

Other commands: `chain verify`, `chain tail`, `magnet`, `send-magnet`, `flush`, `outbox`, `reseed`, `version`.
State lives in `~/.local/share/rtor-ghostchain` (override `--data` / `RTOR_DATA`).

## Android

`RTOR-GHOSTCHAIN-0.2.0-release-UNSIGNED.apk` (package `info.rizal.rtorghostchain`, arm64-v8a + x86_64).
WebView over the same client (shipped as `lib/<abi>/librtorghostchain.so`), started on 127.0.0.1:4984.
**Unsigned on purpose** (no debug keystore, no test keys): it will not install until Rizal signs it.
The loop runs while the app process is alive (no foreground service yet).

## Seed and leech a file (0.2.0)

RTOR is simple seed/leech of one file. Open a file (file picker, drag-drop, Android "Open with"/Share, or `import FILE`):

| Type | Accepted | Check on open |
|---|---|---|
| `.rzl` | yes | SHA-256 vs the published RTOR-INSTALL table, plus SHA256SUMS |
| crypto `.json` (wallet / chain export) | public only | refused if any private-key field (private_key, seed, mnemonic, xprv, wif, keystore/ciphertext, JWK `d`, …) |
| `.pem` / `.crt` / `.cer` | public certs / public keys only | refused if any `PRIVATE KEY` block |
| `.rtor` | yes | JSON fields read; embedded magnet parsed; private-key fields refused |
| `.torrent` | yes | bencode parsed; v1 infohash (SHA-1 of info), v2 (SHA-256) when meta version 2 |
| `.magnet` / `magnet:` links | yes | `urn:btih` 40-hex or base32 (v1) and 64-hex (RENJIN records), `urn:btmh:1220…` (v2), `urn:sha256` |
| `SHA256SUMS*` | yes | sums applied to every library file (verified badge) |
| any other file | yes | SHA-256 |

**Seed** = verified file copied into every reachable drop point from this space's `SPACE-RID.json` with a
`<sha12>-<name>.rtor.json` manifest beside it, and announced (its magnet) as RMAIL to the space's `rmail_address`.
**Leech** = magnet → library → drop points (hash-matched) → exact-source `xs`/`ws` URLs (accepted only on SHA-256 match).
A v1-only btih can be matched only through an imported .torrent; there is no peer swarm in this client.

`SPACE-RID.json` fields: `rid`, `space`, `rklowd_node`, `rmail_address`, `drop_paths` (array or object of paths).
Looked up from `--space`, `RTOR_SPACE`, the data dir, then the package dir. On Android: `/sdcard/Android/data/info.rizal.rtorghostchain/files/SPACE-RID.json`
(adb push target), then the app data dir. Android can only use drop paths the app can reach (its own app dirs); other
`/sdcard` paths show as "not reachable".

## What it does (install guide steps)

| Step | Where |
|---|---|
| SHA256 check of RENJIN-COMPONENT.rzl / RENJIN-KUBO.rzl against the published table | `--check`, `/api/status`, dashboard |
| `run-linux.sh --check` | Linux package |
| Shell serves on 127.0.0.1:4984 (loopback only; cross-origin POSTs refused) | `serve` |
| Renjin Torrent page and R:> Shell page (the published files, unchanged) | `/torrent`, `/shell` |
| CHAIN VERIFY: local append-only ghost chain (SHA-256 `prev_hash` → `entry_hash`), genesis anchors the recorded PKG/STATE/magnet | dashboard, `chain verify`, `/api/chain/verify` |
| Magnet used exactly as recorded (constant in the binary, checked against PKG + STATE + tracker) | `magnet`, `/api/magnet` |
| Send the magnet through RMAIL over relay_8797 (RMAIL v2 message, same shape as rsocial-rmail.js, `verified:false`) | `send-magnet`, dashboard |
| Outbox: undelivered mail stays queued, retried every 20 s with backoff 30 s → 16 min | `rmail-outbox.json` |
| After every new chain entry: chain head + heartbeat to RTRACKR (+ periodic heartbeat every 5 min) | `rtrackr-heartbeats.jsonl` |
| Re-seed | **stub — waits for Rizal's RGHOSTKEY tap** on the trusted device; returns "waiting" |

### relay_8797 routes (in order; override `RTOR_RMAIL_RELAYS`)
1. `send=http://127.0.0.1:8797/send` — transponder envelope `{to:"rmail-<addr>",from,type:"rmail",body}`
2. `drop=http://192.168.0.113:8797/rscale/rmail/drop` — the Neo RKLOWD hub, message posted as-is

A send counts as delivered only on an `{ok:true,id}` ack.

### RTRACKR
rizal.pw/rtrackr is a static page published by `rtrackr_autopub.py` (public publish needs Rizal's GO); there is no public
heartbeat POST route today. Heartbeats are written to `rtrackr-heartbeats.jsonl`, the chain head goes out as RMAIL to
`rtrackr` over relay_8797, and if `RTOR_RTRACKR_POST_URL` is set the heartbeat JSON is POSTed there. Nothing is signed.

## Build (Neo)

`scripts/build.sh linux|android|all` or the Xcode schemes **RTOR-Linux** / **RTOR-Android** in `xcode/RTOR-CLIENT.xcodeproj`.
Go 1.27.4 at `RCRYPTOFORGE/RUNTIME/toolchains/go1.27.4`, Android build-tools 35 + openjdk@17 from Homebrew. Refuses to
build under 3.2 GB free. Every run logs to RSCRIBE (`RKLOWD/SCROLLS/CRYPTOHIVEMIND/_inbox/RTOR-YYYY-MM.jsonl`).
