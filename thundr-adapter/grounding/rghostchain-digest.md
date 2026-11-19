# RGHOSTCHAIN — digest

Source files (supplied by Rizal 2026-11-19 13:40 MST, copies in `rghostchain/` in this
folder): RGHOSTCHAIN-PUBLIC-GUIDE.md, RGHOSTCHAIN-SUBMIT.md,
rghostchain_submitd.py (755 lines), rghostchain_submitd.py.orig (746 lines),
hdr-before_rghostchain_bind_pending.txt.

## What it is

RGHOSTCHAIN is the ledger of the Я (R) ecosystem: an append-only chain of blocks
recording the minting of bots, digital assets, and identities. Public state on
RTRACKR (https://rizal.pw/rtrackr/). Public guide is DRAFT, NOT PUBLISHED (scrubbed,
prepared 2026-10-31, awaiting owner review).

- Blocks link by hash; a new block is accepted only on the current tip.
- Block types: genesis · cryptobot_mint · nft_mint · transfer · note · convert · index.
- Mint categories: wallet.asset.rid · game.asset · game.species · cryptobot ·
  cryptotool · cryptosocial · cryptoscience · cryptoart · cryptoarticle. Bots use
  cryptobot_mint; other categories use nft_mint.
- Every mint is sealed by the owner from a trusted device before writing; the seal
  must point at the current tip; used serial/signature/seal is refused (replay guard).
- RCOIN/RTOKEN: 100 Rcoins = 1 Rtoken (Rizal GO 2026-11-14 9:15 PM MT), rounded down,
  fewer than 100 refused; daily cap 100. (Superseded 10:1 on 2026-11-14.)
- Gate 2 (wallet + mint authority with live value) stays closed until the required
  checks are built and the owner opens it.
- Я token on Solana (public facts): mint BB9uA5BuacDnWyDf5Npc9nMb9yFbyThsNrQPBYJ5Q1Lv,
  1,000,000 supply, 9 decimals, no freeze authority; Orca Whirlpool SOL/Я pool
  HSroUxVkVKv6kX9e7dpoJtbFqKcL76BzrkuuRfAGxs9s.

## Submit daemon (rghostchain_submitd.py, stdlib only, no secrets)

Lives on Neo at ~/ЯLAB/RCRYPTOFORGE/GHOSTMACHINE/RGHOSTCHAIN/rghostchain_submitd.py.
Binds 127.0.0.1:8741 only by default (20261110-lan: optional --host/SUBMITD_BIND with
a home-network source allow-list; mint/pin/ASSM gates unchanged).

Endpoints: GET /health (block counts + validity, real and DRY chains) ·
POST /rghostchain/submit {asset, mode dry|live} (appends only) ·
POST /rtrackr/register {rid, block_index, block_hash, mode} (idempotent per
(rid, block_hash); never changes status/on_chain/mode — those come from the chain;
live always wins over DRY) · GET /rtrackr/assets (game-asset feed) ·
POST /rtrackr/ingest (rebuild feed from chains + registry).

- DRY by default: writes nft_mint blocks to DRY-SUBMIT/chain/rghostchain.jsonl; the
  real chain is never touched.
- LIVE needs ALL three: server started with --real (Rizal), an rsign_seal that
  RWALLET/rwallet/rsign-verify.js verifies with owner_rid == asset.rid, and
  mode:"live". No fallback.
- Mint first, then register: submit never registers; the client calls
  /rtrackr/register just after with the returned block refs.
- RIDs are checked against the ЯID checksum (rid_for: sha256 of "ЯID-<seq4>", 20
  bits, Crockford base32). Secret-looking payload fields are refused.
- Feed: RGHOSTCHAIN/rtrackr/derived/rtrackr-game-assets.json (.js sets window.RTRACKR);
  the game reads it offline via asset_registry.gd or online via fetch_rtrackr().
- Tests: test_submitd_regfix.py (temp copies; the real chain is not written).
- STAGED-MARKET-20261110: DRY market lane (POST /market/submit, GET /market/view,
  GET /market/verify — DRY only, writes market.jsonl only). Not running; :8741 unchanged.
- Bind flow: BIND_PURPOSE 'rghostkey.bind', BIND/pending.json — content-bound
  rghostkey.bind approval; legacy generic seals refused.

## Current .py vs .orig (the only diff)

2026-11-18 pt62u (Rizal "Unlock it and integrate it now", 7:05 PM MT): a
ThundR/GIZMO-only LIVE minter gate. LIVE mints need a minter proof from ThundR's or
GIZMO's OWN registered key in the sha-pinned registry (rmint_minters.check against
KR.load_pinned); anyone else → 403. The payload records minter / minter_device /
minted_by='cryptobot:<name>' on the block itself. RSIGN seal check, replay guard,
chain hash/sequence checks, and append-only write are unchanged.

## hdr-before_rghostchain_bind_pending.txt

A captured HTTP response header (no body): HTTP/1.0 200 OK, Server BaseHTTP/0.6
Python/3.9.6, Date Tue, 10 Nov 2026 19:51:27 GMT, Content-Type application/json,
Content-Length 6942643 (~6.9 MB), Access-Control-Allow-Origin: *. Diagnostic artifact
from the daemon before the bind-pending state.

## Rules for the ThundR Plugin Adapter

- The adapter is READ-ONLY against the chain: it may call GET /health,
  GET /rtrackr/assets, GET /market/view, GET /market/verify. It must NEVER call
  POST /rghostchain/submit, POST /rtrackr/register, POST /rtrackr/ingest, or
  POST /market/submit.
- Diagnostics should report the daemon's health (tips, counts, validity), the DRY
  vs LIVE mode, and the ThundR/GIZMO minter gate status.
- The adapter's GO-gating mirrors the bind flow (content-bound approval, never
  a generic seal).
- Port map (loopback): :8741 submit daemon/gate · :8742 adapter (TPA default) ·
  :8329 MCR · :4983 Granite relay · :8080 backup LLM · :8796 Linux web shell.
