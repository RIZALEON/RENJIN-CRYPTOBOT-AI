# ЯWALET — digest

Source files (supplied by Rizal 2026-11-19 13:43 MST, copies in `rwalet/` in this
folder): index.html.bin (unified FULL), index.html-2.bin (unified ALL),
Package.swift.bin / -2.bin / -3.bin (SolanaSwift dependency manifests),
rbox.web.rwalet.SHA256SUMS (70 entries), rwalet-defi.bundle.mjs (751 KB),
rshell.js.bin, RWALET.app_0_8bem.zip (17.1 MB, 2026-11-16), RWALET.app_1_uap0.zip
(14.8 MB, 2026-11-13), rwalet-neo-0.2.0_2_4hrq.tgz (18.5 MB),
rwalet-thundr-std.css, rtrackr-snapshot.json.bin (shared with the RTRACKR batch),
rbox-web-desk-rwalet.png (screenshot of the live app). 14 distinct files + screenshot.
Secret scan 2026-11-19: CLEAN (0 hits across the 8 text files checked).

## What it is

ЯWALET Neo unified **0.2.0** (bundle id io.rlab.rwalet.xcode, build 20261113,
macOS 27.0 SDK) — the Я ecosystem wallet: a web layer (unified FULL/ALL pages)
plus a native macOS app. PRIVATE staged build, unsigned, not for public drop.
Watch-only by design in the web layer: it holds no key; native ops refuse without
a device key.

Core law (stated on the page, in the banner, and in the screenshot):
- Sign/mint only on the owner's Face ID or RGHOSTKEY tap.
- Mail (RMAIL or the mesh) never triggers sign or mint.
- The page does not auto-run Sign, Mint, Send, or Swap.
- `window.RWALLET_PREVIEW=true` — preview unless the owner taps Face ID / RGHOSTKEY.

## The two web pages

- **unified FULL** (staged 2026-11-10): RGHOSTKEY / RSIGN / seats / Face ID seal,
  send, receive, swap, mint-press, transport, RMAIL, ThundR, market intent, roster.
  Scripts: rwallet-guard, rwallet-unified, rsign-verify, rid-link, rghostkey-api,
  rwallet-intent, rwallet-botlatch, rwallet-rvault, rtrackr-feed, rwallet-roster,
  vendor/rsocial-rmail, vendor/rsync-core, rmail-approve (v2, MEKANICA spec),
  rwallet-rmail-card, rwallet-rmail-panel, rwallet-thundr-panel, rwallet-ghost.
  Nav: RTRACKR (data/rtrackr-snapshot.json), roster (data/wallets-public.json),
  RMAIL hand-off (data/rmail-handoff.json), RTHUNDR (thundr/hub/index.html),
  LINUX RIZAL 1.1.1.6.
- **unified ALL** (staged 2026-11-11, MEKANICA UNIFIED-ALL, from FULL): adds
  rwallet-all.css, rwallet-all-registry.js ("every old wallet/vault/casket/pool
  function"), rwallet-all.js ("read-only handlers + POTLATCH drafts"),
  rwallet-pools-panel.js, rwallet-casket-panel.js. Extra nav: Linux shell
  127.0.0.1:8772, in-game ЯWALLET 127.0.0.1:8772/game, RVM TerraformЯ
  127.0.0.1:18323, RVM RMAIL 127.0.0.1:18830, ASSM ЯWALLET https://rizal.pw/rwallet/.

## rshell.js (MEKANICA 2026-11-11, Rizal t671u)

ONE shared window-logic file for both shells: mode "full" = TerraformЯ Linux shell
window; mode "overlay" = RTHUNDR (BAYS drawer + command routes inside ThundR
#th-chat). Transport: native host bridge window.webkit.messageHandlers.rshell, or
same-origin /x/<svc>/<path> (serve.py on Linux). Both enforce rshell-allow.json.
Loopback only. No keys, no signing, no minting, no Cloudflare. RMAIL Approve/Deny
renders ONLY via rmail-approve-v2.js (spec SCROLLS/RMAIL-APPROVE-DENY-SPEC-20261111.md).
"Approve never signs; it opens ASSM ЯWALLET Face ID. Decisions stay local/pending
unless the host enables its decision writer."

## Native stack (from the Package.swift manifests)

SolanaSwift (swift-tools 5.7.1) with secp256k1.swift, tweetnacl-swiftwrap 1.0.2
(Ed25519), task-retrying-swift 2.0.0 (the other two manifests are those deps).
The native app is the signing side (Touch ID / Face ID / SE key); the web layer
is the viewing side.

## DeFi bundle + checklist (rwalet-neo-0.2.0)

- rwalet-defi.bundle.mjs: Orca Whirlpools SDK 8.0.1 (swapInstructions, position
  instructions) + Jupiter v6 lite-api. Hash VERIFIED against rbox.web.rwalet.SHA256SUMS.
- CHECKLIST-20261111.md (function checklist vs INVENTORY-20261111): box-tested =
  headless Chrome against the web layer (mocked native host) + mainnet
  simulateTransaction (sigVerify:false). **NO Swift compile yet** (Neo load 150–196
  all session) — every native row is PARTIAL on those grounds.
- swap DONE (box): SOL→Я 36,317 CU · Я→SOL 32,074 CU · Jupiter SOL→USDC ≈100–120k CU
  · 1 SOL→Я ref 47,802 CU. Slippage default 50 bps, 900 bps refused (cap 300).
- liquidity add DONE (build)/PARTIAL (sim): stops only at "insufficient lamports"
  (Crown holds 0.0072 SOL). Liquidity remove DONE (box): 1% of the Crown's real
  Я/SOL position 24uK…RV7 — simulate 13,218 CU, harvest 25,591 CU, close preview
  46,440 CU. Staking DONE (create, ref)/PARTIAL: Native Stake program, 1 SOL min
  delegation enforced; Crown refused by the 1.0017 SOL minimum. Potlatch Create
  Pool DONE (ref)/PARTIAL: Я/USDC splash, ref sim 51,059 CU. Pool tracking DONE:
  token-pool.json + live poolInfo (liquidity 31,622,776,601, tick 153229).
- devnet MISSING (box): box can't reach api.devnet.solana.com (TLS EOF). App
  defaults DeFi to devnet; mainnet needs a tap + critical NSAlert.
- RMAIL approve/deny DONE (web): Approve opens only rwallet://approve?; Deny = bare
  rmail.decision signed:false. Backup/restore, key import, NFT, market: MISSING
  (not requested this phase; YCasketInbox key importer deliberately excluded).

## The two .app zips (same version, different packaging)

Both: ЯWALET 0.2.0, build 20261113, io.rlab.rwalet.xcode.
- zip0 (2026-11-16, 609 entries): debug/preview build — RWALET stub (40,592 B) +
  RWALET.debug.dylib (5.6 MB) + __preview.dylib; adds OwnerProfile.plist and
  ASSMAuthConfig.plist.
- zip1 (2026-11-13, 550 entries): plain build — real RWALET binary (589,168 B).
- Both embed the whole linux-rizal-1.1.1.6 tree under Resources/neo-8760/
  (Reticulum config, systemd units rnsd/lxmd/rizal-web, RVM device-profile,
  rizal.pw web content, RKLOWD RFORGE branches incl. rthundr-feature-granite-folder-supervisor-*).

## tgz package + style

rwalet-neo-0.2.0/: CHECKLIST-20261111.md, tools/ (sumsim.py, shot.py,
rmail_card_test.py, serve.py, defi_sim_test.py, approve_test.py,
native_mock_test.py, closure.py, seeds*.txt, excl*.txt), shots/ (v1–v6 phone/desk
screenshots, rmail approve cards, defi previews, defi-sim-crown.json), out/
(SHA256SUMS-20261111.txt + nested RWALET-NEO-UNIFIED-0.2.0-pkg-20261111.tgz).
rwalet-thundr-std.css: ThundR Design Standard 1.0.0 (2026-11-11), twilight look,
fonts VT323 / IBM Plex Mono / Noto Sans Tagalog / Press Start 2P, palette green
#39FF14 / purple #8A2BE2 / gold #FFE46B.

## SHA256SUMS verification (rbox.web.rwalet, 70 entries)

- VERIFIED: rwalet-defi.bundle.mjs ✓, rtrackr-feed.js ✓ (both match the manifest).
- RESOLVED (2026-11-19, RTRACKR digest): the manifest pins point at the -2
  variants, which are in the batch and match — rtrackr-snapshot-2.json =
  5b4fae78… ✓ and rtrackr-button-2.js = 2fd18328… ✓. The base
  rtrackr-snapshot.json.bin (877108ba…) and rtrackr-button.js (c5899928…) are
  the OLDER revisions, not the shipped ones. Lesson: verify against every
  numbered variant before calling a mismatch.

## Live screenshot (rbox-web-desk-rwalet.png, Wed Nov 18, 2026)

ЯWALET 0.2.0 unified running on Neo. Roster is watch-only, public addresses, no
keys. Я TOKEN: mint BB9uA5BuacDnWyDf5Npc9nMb9yFbyThsNrQPBYJ5Q1Lv, decimals 9,
supply 1,000,000, token program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA
(standard SPL Token program), mint authority BwpVNk1Btpnpy5HMTLwxB4Yfikfv6mE…
(cut off in frame). ORCA SPLASH POOL: Я/SOL, pool
HSroUxVkVKv6kX9e7dpoJtbFqKcL76BzrkuuRfAGxs9s, Я VAULT 8uYFzTDTDq18z1gPFGbVHGBLN2CVF3G,
SOL VAULT 9m3eqYYF7mP3gPvcrk9AKAKagdETqmb. Sources: baked rtrackr-snapshot.json
(Tue Nov 10, 2026 1:55 PM MT) + live Solana RPC https://solana-rpc.publicnode.com
(Wed Nov 18, 2026 2:35:59 PM MT). Я RVAULT SEALED: keys behind biometrics, never
shown/copied/exported; unlock/sign only through ЯCASKET (Face ID). Я BOTLATCH:
view-only; buy/sell/swap/send = ЯCASKET Face ID request; nothing signs here;
contracts.json + activity.json unavailable. Left panel: owner ЯID-0001-3QQS
(GHOSTMACHINE @chaserizal), ThundR CRYPTOBOT ЯID-0014-KREH, "Rizal the Younger
@chaserizal" Verified, R:\SOCIAL> READY_.

## Rules for the ThundR Plugin Adapter

- The wallet is WATCH-ONLY for the adapter. The adapter never signs, sends, swaps,
  mints, or moves anything — it may read roster / snapshot / pool state only.
- Approve flows route to rwallet://approve? + the owner's Face ID — the adapter
  queues the request, the wallet + human complete it. Approve never signs.
- The rshell transport pattern (loopback-only, rshell-allow.json allowlist,
  native bridge or same-origin /x/ proxy) is the precedent for the adapter's own
  allowlist design.
- The SHA256SUMS manifest pattern (pin every web asset, verify on load) is the
  precedent for the adapter's plugin verification.
