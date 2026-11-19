# RTRACKR — digest

Source files (supplied by Rizal 2026-11-19 13:42 MST, copies in `rtrackr/` in this
folder): rtrackr_export.py, rtrackr_feed.gd + .uid, rtrackr-button.js/-2/-3,
rtrackr-feed.js/-2 + .0.1.5-upstream, rtrackr-game-assets.js/.json,
rtrackr-snapshot.json/-2 + .json.bin, rtrackr.css/-2 + .css.bin, rtrackr.js/-2/-3 +
.js.bin. 21 files, 19 distinct by content (see Inventory). Secret scan 2026-11-19:
CLEAN across all 18 text files (0 private-key blocks, 0 key prefixes, 0
credential URLs). All files are plain text; the `.bin` files are text saved with a
.bin extension, not binaries.

## What it is

RTRACKR is the public tracker / read layer for RGHOSTCHAIN. The chain itself stays
local (never public); RTRACKR publishes a scrubbed, signed-or-baked public view at
https://rizal.pw/rtrackr/ — registry rows (RID, name, kind, mode, block hash,
status), the Я token, the Orca pool, holders, and wallets. Everything here is
public state: no keys, seeds, or local paths. The snapshot's own note: "Public
snapshot only. … This file is static and is read from the same site path only."

Two public data products:
- **Chain export** — `rtrackr_export.py` (v1, 20261030) reads the REAL chain +
  registry and writes `rtrackr-export/rghostchain.json` + SHA256SUMS (schema
  `rzl.rtrackr.export.v1`). It refuses a DRY chain, verifies the chain via
  `rghostchain.verify`, strips any key matching
  pass|secret|private|seed|mnemonic|apikey|api_key|keychain (records the stripped
  keys), and includes only registry entries with status live AND backed by a real
  chain block hash. `--site` copies the export to `<site>/rtrackr/data/`.
- **Game-asset feed** — the daemon's derived feed (`rzl.rtrackr.game-assets.v1`),
  consumed by the game and the web wallets. The `.js` form sets `window.RTRACKR`.

## Data flow

```
RGHOSTCHAIN (local, real chain + registry)
  ├─ rtrackr_export.py ──► rtrackr-export/rghostchain.json + SHA256SUMS ──► rizal.pw/rtrackr/data/
  │     (read-only, verifies, strips secrets, live+on-chain entries only)
  ├─ rghostchain_submitd GET /rtrackr/assets ──► live feed (127.0.0.1:8741)
  │     └─ derived rtrackr-game-assets.json / .js (window.RTRACKR) ──► game + web wallets
  └─ market bake (tools/rtrackr-market-bake.json) ──► rtrackr-snapshot.json (static, baked)
        (public Solana RPC / GeckoTerminal / Orca / Jupiter — no live fetch on the page)
```

Feed readers (rtrackr-feed.js, rtrackr_feed.gd) resolve in this order:
GET `<api>/rtrackr/assets` → derived `rtrackr-game-assets.json` → `window.RTRACKR`
(derived .js) → cached copy (localStorage `rtrackr.feed.cache.v1` / game
`user://assets/rtrackr-cache.json`). Offline = show the cached feed and queue
events; `flush()` sends them when back online. Queue is DRY only — `queue()` throws
on mode live, and the game build never sends "live" from its queue. Mint order is
fixed (Rizal's rule 12:41): submit first, then register with the mint block hash;
register requires {rid, block_index, block_hash, mode} and 404s unless the block is
an nft_mint with payload.rid == rid.

A LIVE mint from the game is a REQUEST, not a mint: `minter_request()` (2026-11-18
pt62u) queues a `rzl.rmint.minter-request.v1` record for minter thundr or gizmo only
(`user://assets/rmint-minter-requests.json`), flushed to POST `/rmint/minter/request`.
The game never sends mode "live" to submitd itself and holds no key; the minter
adds its own minter proof. `is_live(asset)` = on_chain true AND a non-empty sig
(JS also accepts status "live").

## The files

- `rtrackr_export.py` (4,219 B) — the exporter, above. Stdlib only.
- `rtrackr-feed.js` (3,604 B) — feed reader for every RWALLET (20261030). API
  `http://127.0.0.1:8741`. Exports load/forRid/card/isLive/queue/pending/flush/mintEvents.
- `rtrackr_feed.gd` (6,224 B, uid `uid://bwcslcktthgpv`) — the same reader for the
  Godot game RWALLET card, plus the DRY submit queue and the minter-request queue.
- `rtrackr.js` (19,632 B) / `-2` (29,491 B) / `-3` (32,810 B) / `.js.bin` (6,650 B)
  — the explorer page script. Same-origin fetch only, `cache:'no-store'`, from
  `/rtrackr/data/{rghostchain.json, rtoken.json, token-pool.json,
  token-wallets.json, economy-rates.json}`. Live panels use public Solana RPC
  (api.mainnet-beta.solana.com, solana-rpc.publicnode.com) and link out to
  explorer.solana.com, solana.fm, dexscreener.com, jup.ag.
- `rtrackr-button.js` (656 B) / `-2` (711 B) / `-3` (657 B) — a plain-link button
  injected into the ASSM profile ЯWALLET (`.csp-rwx`), pointing at
  `/rtrackr/#rid/ЯID-0001-3QQS`. Add-only, no pop-up.
- `rtrackr.css` (2,473 B) / `-2` (2,579 B) / `.css.bin` (1,522 B) — explorer styles.
- `rtrackr-snapshot.json` (26,615 B) / `-2` (26,595 B) — the baked public snapshot
  (below). `rtrackr-game-assets.js` (9,075 B) / `.json` (10,106 B) — the derived
  game-asset feed (below).

## Snapshot contents (baked 2026-11-10, schema rzl.rpotlatch.rtrackr.snapshot.v2)

Generated 2026-11-10T13:55:41-07:00 ("Tuesday, Nov 10, 2026, 1:55 PM MT").
Sources: signed registry `rzl.rtrackr.registry.v1` (updated 2026-11-01) +
Ghostroot unsigned branch (`rzl.rtrackr.ghostroot.registry.v1`) + baked market
facts. 11 registry entries: 4 distinct RIDs (ЯID-0001-3QQS owner, ЯID-0014-KREH
ThundR, ЯID-0015-0HJP, plus ЯID-0016-CG2C GHOSTCUBE). Kinds: wallet.asset.rid,
cryptobot, ghostcube. Modes: live / dry / ghostroot-unsigned. The ThundR wallet
row appears twice as `registered` with NO block hash — registered but no sealed
block behind it (see Discrepancies).

- **Я token**: mint BB9uA5BuacDnWyDf5Npc9nMb9yFbyThsNrQPBYJ5Q1Lv, 9 decimals,
  supply 1,000,000, SPL Token program, created 2026-09-18 9:07 PM MT. Metadata on
  GitHub (RIZALEON/RIZALBOT, seat-wallet-landing branch, twin/ya-metadata.json).
- **Authority**: mint authority still SET (Crown wallet
  BwpVNk1Rtncpv5HMTLwxB4Yfjkfv6mFaBQUTpjneH1F9) — new Я can still be minted.
  Freeze authority REVOKED (null) — accounts cannot be frozen.
- **Pool**: Orca splashpool Я/SOL, HSroUxVkVKv6kX9e7dpoJtbFqKcL76BzrkuuRfAGxs9s,
  created 2026-10-13. Price ~$0.0000367 (FDV ~$36.72), liquidity $4.06, 24h volume
  $0 (0 buys/sells all windows), 1.00% LP fee, 0% locked liquidity. DexScreener has
  no pair; GeckoTerminal market_cap_usd is null.
- **Holders**: 5 token accounts hold 100% of supply — Crown 89.9989%, pool vault
  6.74%, watched holder 3.26%, previous desktop 9 Я, previous mobile 2 Я. OpenSea's
  "Unbalanced ownership" flag is threshold wording, not the measured share.
- **Wallets**: 5 public Solana addresses (2 current, 3 previous RBOT seats) + 10
  RID-linked rows (TerraformR in-game, RWALLET web, 3 DeviceWalletSeat rows with
  EMPTY pubkeys — not seated — rizal.pw, RDRAGONSKULL iOS/Android, ThundR link,
  GHOSTCUBE). Missing list: BSC GENESIS FIRST MINT details blank (awaiting Rizal);
  current seat pubkeys empty; no published Rcoin→Rtoken market rate; DexScreener no
  pair; GeckoTerminal market cap null.

## Game-asset feed (generated 2026-11-18T23:28:34-07:00)

Schema `rzl.rtrackr.game-assets.v1`, source "rmint-hybrid 1.0.0 (live chain)",
live 5, dry 1, chain_valid true, history_height 4, 5 blocks. The `.js` and `.json`
payloads are identical (verified). Assets: genesis (block 0, live) ·
wallet.asset.rid ЯID-0001-3QQS (block 1, live) · cryptobot ЯID-0014-KREH ThundR
(block 2, live) · cryptobot ЯID-0015-0HJP (block 3, live) ·
rghostkey.bind+device_approval+basecode.v1 ЯID-0001-3QQS (block 4, live) ·
wallet.asset.rid ЯID-0014-KREH (status `registered`, on_chain false, no block).
Note: "status test = TEST copy of RGHOSTCHAIN, not the live chain. Player mints are
unsigned by owner rule (t11u)."

## Version drift

- **rtrackr.js**: `.bin` (6,650 B) is OLDEST — the v1 explorer (20261030 header),
  no kind labels, no cryptoupdate, no R TOKEN. Base (19,632 B) adds 20261101
  BATIBABOT kind labels/icons + cryptoupdate special-casing and 20261107 R TOKEN
  (Solana) public trackers. `-2` (29,491 B) adds 20261114 POOL-INTEGRATE (Decider
  t237u: Orca Я/SOL pool panel) + 20261114 WALLETS (Decider t239u: every Я wallet
  panel, holders, OpenSea holdings, live getSignatures). `-3` (32,810 B) is
  NEWEST — adds 20261114 RATE-100 (Rizal GO 9:15 PM MT: 100 Rcoins = 1 Rtoken),
  rtoken events v1, rtoken page.
- **rtrackr-feed.js** == `.0.1.5-upstream` (byte-identical). `-2` differs ONLY in
  the API host: `http://chain.rklowd.invalid:8741` instead of loopback — the RKLOWD
  mesh-host variant.
- **rtrackr-button.js**: base label "RTRACKR · RGHOSTCHAIN explorer". `-2` and `-3`
  relabel to "RTRACKR · RGHOSTCHAIN + R TOKEN"; `-2` additionally switches the font
  stack to Menlo, RIZAL Mono, Noto Sans Tagalog, Noto Sans Mayan Numerals. `-2` is
  newest (confirmed by the manifest pin — see below).
- **rtrackr.css**: `.bin` (1,522 B) is OLDEST — lacks the 20261101 kind chips and
  20261105 R TOKEN sections. Base adds those. `-2` adds a 20261114 wallets-table
  section — newest.
- **rtrackr-snapshot.json** == `.json.bin` (byte-identical). `-2` differs in exactly
  one place: rows 6–7 of `wallets.rid_linked` rename "RDRAGONSKULL" → "RDRAGON"
  (iOS + Android 1.0.3 RWALLET). `-2` is the newer revision (confirmed by the
  manifest pin).

## Discrepancies and notable findings

1. **Manifest pins point at the -2 variants.** `rbox.web.rwalet.SHA256SUMS` (from
   the ЯWALET batch) pins `rtrackr-button.js` = the hash of this batch's
   **rtrackr-button-2.js**, and `data/rtrackr-snapshot.json` = the hash of
   **rtrackr-snapshot-2.json**. `rtrackr-feed.js` matches its pin. So the shipped
   bundle carries the -2 copies; the base button/snapshot files in this batch are
   the older revisions. (Verified by hash comparison against the manifest.)
2. **ThundR's wallet row is registered but unsealed.** In both the snapshot
   (entries, duplicated) and the game feed, wallet.asset.rid ЯID-0014-KREH is
   `registered`, on_chain false, no block hash. The snapshot's RID-linked row says
   it plainly: "marked registered but no sealed block behind the wallet-RID row."
   The cryptobot row for ThundR (block 2) IS live — only the wallet-RID row is
   unsealed.
3. **Snapshot entries are duplicated across views.** The 11 entries mix two
   presentations of the same rows (mode-based rows + status-based rows): e.g. the
   ThundR wallet row and the ThundR/0HJP cryptobot rows each appear twice with
   different block-hash spellings of the same blocks. Count RIDs, not rows.
4. **GeckoTerminal disagrees with the chain on mint authority.** GeckoTerminal
   reports mint_authority null; on-chain getAccountInfo (slot 467860307) shows it
   set (Crown wallet). The snapshot records both and trusts the chain.
5. **A typo'd mobile address is a valid pubkey with no account.** PUBLIC-NUMBERS
   and wallets-public-2.1.7 list a dropped-h variant of the previous mobile seat;
   it is a valid 32-byte pubkey but has no account on chain (0 SOL). The double-h
   address is the live holder. The snapshot flags this explicitly.
6. **Orca API data is stale.** The Orca pool document was last updated 2026-10-20;
   the snapshot uses it only for fee/vaults/pool type and re-checks vault balances
   live (they match).
7. **Feed -2 uses a mesh hostname** (`chain.rklowd.invalid`) — `.invalid` is not a
   public TLD; that variant only resolves inside the RKLOWD mesh.

## Rules for the ThundR Plugin Adapter

- RTRACKR is the adapter's read surface for chain state: GET /rtrackr/assets
  (live feed), the derived game-assets feed, and the baked snapshot / export are
  all READ-ONLY public state. The adapter may read them; it must never call the
  submit/register/ingest POSTs (same rule as the chain).
- Prefer the live feed when the daemon answers; fall back to derived → cached, in
  the feed reader's own order. Always report which source served the data and its
  timestamp — the snapshot is baked (2026-11-10) and goes stale; the game feed
  (2026-11-18) is newer.
- Live vs preview: an asset is LIVE only when on_chain is true and a signature is
  present (status "live" alone is the JS shortcut). The ThundR wallet-RID row is
  the standing example of registered-but-not-live — report it as such, never as
  minted.
- The adapter queues DRY events only, in the feed's shape (submit then register,
  register only after the mint block is confirmed). It never queues or sends live
  events; a live mint is a minter request routed to ThundR/GIZMO, never a direct
  submit.
- Public addresses in the snapshot are public by design (published on rizal.pw) —
  the adapter may surface them as read-only roster data, same as the explorer does.
  It must never treat a snapshot value as a live balance: every value carries a
  source and a fetched time.
