# RMAIL — digest

Source files (supplied by Rizal 2026-11-19 ~13:49 MST, copies in `rmail/` in this
folder): 208 files listed (188 in `~/workspace/user/files/` + 20 screenshots in
`~/workspace/user/media_library/image/`), **174 distinct by sha256** (30 duplicate
groups, 34 extra copies), 2,174,538 bytes distinct. Secret scan 2026-11-19:
**CLEAN** across all 149 text files (0 private-key blocks, 0 key prefixes,
0 credential URLs, 0 quoted-literal secrets); the 5 `.class` files were also
checked via `strings` with 0 hits. All `.bin` files are plain text except
`desktop-rmail-approve.png.bin`, which is a PNG. The upload prefixes
(`<8-hex>--`) on the message JSONs are the first 8 hex of each file's sha256 and
were stripped in the grounding copies; duplicate copies were kept under the most
informative name (e.g. the `pw__inbox__` / `17e__inbox__` / `neo__inbox__`
variant, or the base name over a `.bin` twin).

Breakdown of the 174 distinct files: 66 message JSONs + 7 config JSONs, 32 `.js`,
28 `.bin` text files, 17 image files (16 `.png` + 1 `.png.bin`), 4 Python files, 4 Swift/Java sources
(2 Swift + 2 Java) + 1 Java `.txt` variant + 5 `.class` files, 7 logs
(6 build logs + 1 test log), `rmail-ui.css`, `rmail.html`, `rmail.svg`.

## What it is

RMAIL is the mesh mail system of the R:> ecosystem: file-based messages carried
between RKLOWD nodes (Neo, 17e, moto, pw, rvm) over RPIPE, a loopback HTTP relay,
Reticulum/LXMF, or a shared-folder queue — never over public email. The `rmail`
node itself (`rklowd.rmail`, hub Neo) is an always-on RVM network device
(`rmail__node.json`, `rmail__STATUS.json`, both stamped 2026-11-10 20:12:46 MST):
"drop a file in drop/ ; objects arrive in inbox/ (via RPIPE)". All traffic goes
through RPIPE (`127.0.0.1:8900/rscale`); "no side channels". Its networking tools
list names reticulum-rnsd, lxmf-lxmd, rpipe-rscale, rklowd, rvm-bridge,
rnet-rmaild, rmail-guest, rkast-net, rkast-transponder, wireguard, nebula,
yggdrasil, signal-switch, bridge-landing, rnet-mesh, rizal-web.

Transport (from `rmail-handoff.json`, `rmail-route.json` v1.0-20261111-rbowzr,
`rsocial-rmail.js` v2.2):

- **Primary: relay :8797** — POST `http://127.0.0.1:8797/send`, drop
  `http://127.0.0.1:8797/rscale/rmail/drop` (RSCALE / transponder drop). State
  `off-until-mekanica-go` in the route file; MEKANICA owns switching it on
  (`PIPE/rscale/rvm_approve_relay.py`).
- **Node folders (fallback)** — `Documents/ЯLAB/RKLOWD/nodes/<node>/` with
  `inbox/`, `drop/`, `sent/`, `outbox/`; iOS standalone, rbot-ios and
  thundr-rbot-fused-ios all use this, with queue
  `http://127.0.0.1:8741/rmint/queue` (submitd).
- **LXMF/RNS local :4242** — Reticulum listen port in the linux-rizal-1.1.1.6
  image; public hubs OFF (`rmap.world`, `rns.beleth.net` still enabled in the
  1.1.1.6 image, which was not modified — the handoff file is what the wallet
  uses).
- **RKLOWD queue fallback** — `/opt/rizal/rklowd/RMAIL`, synced by
  `rmail_sync.py`; rbot-linux outbox `/var/lib/rizal/rmail/outbox`, read
  read-only by the relay via `:18851/api/approvals`.
- **Guest intake :8830** — the NOKEY guest helper (see below). Other loopback
  hubs seen in the code: `:8319` (moto/17e local hub), `:8339`, `:8799`,
  `:8324` (guest drop), RVM RMAIL `:18830` (known from earlier grounding).
- Mesh hostnames (`*.rklowd.invalid`) appear in the newer variants
  (`chain.rklowd.invalid:8741`, `neo.rklowd.invalid`, `moto.rklowd.invalid`,
  `qemu-host.rklowd.invalid`); older variants use raw LAN IPs
  (`192.168.0.113` Neo, `192.168.0.224` moto, blocked `192.168.0.75`).

Message boxes are keyed by **RWALLET public address** (`rsocial-rmail.js`:
"outbox, transponder SIGNAL-QUEUE/rmail-\<addr\>, RKLOWD RMAIL/\<addr\>, RLINE").
Verification: `verified:true` only when `from_device` is an ACTIVE entry in
`rwallet/data/trusted-devices.json` AND an ECDSA P-256 `sig_b64` over the
canonical text `rmail-v1\n<id>\n<from_addr>\n<to_addr>\n<ts>\n<text>` checks
against that device's `pubkey_spki_b64`. Guests are always `verified:false`.
`rmail_sync.py` re-verifies server-side and **ignores incoming `verified`
flags**; trust is `trusted-device` / `guest-unverified` / `unverified`.

Two identities are presented as distinct (`rmail-rizal-mail.js` v2 20261114 +
`rmail-mailboxes.json`, schema `rklowd.mailboxes.v1`, updated 2026-11-14):
messenger `@chaserizal` (direct-message) and traditional email `ghost@<redacted>`
(mailbox `nodes/pw/mailboxes/ghost`, folders inbox/sent, created
2026-11-14T19:36:53-07:00). The mailboxes file is the single source of truth,
canonical at `RKLOWD nodes/pw/mailboxes/index.json`, mirrored byte-identical by
RMAIL, rizal.pw ASSM and RDRAGON. "Public values only: no keys, no ports, no
machine addresses."

## Message schema (from the 66 message JSONs in the batch)

- Schemas: `rmail.guest.v1` × 51, `rmail.v1` × 14, no schema × 1
  (`rmail-t45rd17e173339.json` — also lacks kind/signed/verified/folder).
- **Every message is unsigned**: `signed:false` on 64, the field absent on the
  2 t45 test messages. `verified` is false or absent everywhere. **No message
  in the batch carries `sig_b64`** — there is no verified mail here at all.
- Common fields: `schema, id, ts, from, to, subject, body, origin, kind,
  folder, signed, verified, trust, to_node, to_device, to_device_id, type,
  dot, faceid`. `ts` is epoch ms in most files, epoch seconds in the pw-inbox
  hash-ID copies, ISO strings in the thundr-load-guard drops.
- **Approve-bearing messages × 10** (5 sign requests × neo + 17e inbox copy):
  `rmail.v1` + `approve` block v2 + `notice` + `artifacts[]` + `base_cert`.
  The neo and 17e copies of each request are **canonically identical JSON**
  (verified); only formatting differs (17e pretty-printed, neo compact).
- **Egg messages × 3** (`egg-10430/10431/10432`, 2026-11-10 18:59/19:09/19:28):
  `rmail.v1` + `egg` block `{name, version, sha256, size, path, staging,
  signed:false, published:false, installed:false, supersedes?}`.
- **Block 4 message × 1**: `block4-mint-20261110205337-7498d526` with a
  `notice` block (see below).

Message families in the batch:

| Family | Count | Notes |
|---|---|---|
| thundr-load-guard drops (2026-11-12) | 9 drops + 9 pw-inbox copies | RVM pause/resume timeline 11:12–13:14 MST; pauses at load 512/207/423/223/162 ("mesh hub offline"), resumes at load 7/7/11/3; one force-resume failsafe at 11:31:55. The pw copies are hash-ID files (`2d80f47c…` etc.) with the same subjects, `from: guest:ThundR`, `dot:true, faceid:false`. |
| sign requests (2026-11-11) | 5 × 2 copies | All kind `sign`, reply node `rklowd.neo`, `base_cert` ECDSA-P256-SHA256 on device `iphone17e-3e9e3a06-462b-4186-88c5-a760f4c09f41`. bbot-complete (12 artifacts), rshell-window (6), rthundr-linux-1.2.0-l1 (3), tf-linux-b14-ros (2), ybot-2.1.9-linux1 (5). Subjects all end "(ROS)". |
| egg notices (2026-11-10) | 3 | DRAGON SKULL web 1.0.4.30 (290,322 B) → 1.0.4.31 (293,960 B) → 1.0.4.32 (12,622 B, minimal overlay on 1.0.4.25). All UNSIGNED, hard-linked with staging, SelfUpdate refuses until Face ID-signed; HTTP drop deliberately NOT used (it would offer to moto/rvm too). |
| block4-mint | 1 | Block 4 bind request, `notice` with `block_sha256 0b472250…`, `open: terraformr://rsign/bind?req=rm-20261110205337-7498d526`, command `terraformr bind`. Status PENDING. Also notes DRAGON SKULL 1.0.4.36 (build 40) installed. |
| e2e tests (2026-11-10) | 3 | t136 loopback (neo, "Do not deliver off-box"), t136 watch-pickup, t137 FORGE RKLOWD wiring test. |
| kubo series | 11 | Guest delivery tests (local-live, recheck, public-e2e, final-delivery, external-final, second-local, local-recovery, repaired-gateway, dry-guest, dry-public). **Filename epochs are unreliable**: they span 1762363001 (≈2025-11-05) to 1793901604 (≈2026-11-12), and `kubo-external-final-1762367400` has a `ts` field of 1793901729606 ms that disagrees with its filename. |
| presence / RPIPE tests | 9 | t45moto, t45rd17e, t52v, t58pre, t58peer, t58neodown, t62rev (phone-originated via 17e :8797), t68pres, t71pres. |
| grokbot tests (2026-11-05/10) | 9 | mw44/mw45 web-drop tests (neo/moto/rvm/17e, "safe to delete"), desktop-compose/offline-queue, grokbot self-test 2026-11-10 19:40. Origins `127.0.0.1:8830` and `127.0.0.1:8319`. |
| misc | 2 | `rmail-a2c50661a782aee4` ("TEST ONLY: sign+mint request, NOT REAL, cannot mint", `type: approve`); `rmail-c3daea91da08f32b` ("test", "guard test x"). |

## The approve / deny flow and its law

Canonical spec: `SCROLLS/RMAIL-APPROVE-DENY-SPEC-20261111.md` (cited by every
approve file; the spec file itself is NOT in this batch). Request =
`rmail.v1` envelope + `approve` block v2:

```
approve: {v:2, kind: mint|sign|send, summary, app, req_id, nonce,
          expires, buttons:[{id:"approve", open:"rwallet://approve?req=…&nonce=…"},
                            {id:"deny"}], reply:{node, app}}
notice:  {req_id, type:"rmail.approve", status:"pending",
          needs:"ASSM ЯWALLET Face ID", source, command}
```

Answer = **bare `rmail.decision` v1** (the whole file, one JSON object — a
`Subject:` line or `rmail.v1` envelope is skipped by the return leg), written
as `rmail-dec-<req_id>.json` into `nodes/<reply-node>/inbox/` (or
`mail/<node>/`):

```
{schema:"rmail.decision", v:1, id:"dec-<req_id>", ref:<msg id>, req_id, nonce,
 decision:"approve"|"deny", ts, by:"@chaserizal/<seat>", app, to_node,
 signed:false}   // 1.0.0 engine adds needs_unlock:true for mint/trade/swap/buy/sell
```

Validation (identical across the JS, Java and Swift implementations): raw ≤
4 KB; `signed` must be exactly `false` (a signed card is refused); no
secret-like key or PEM content anywhere (depth ≤ 8); kind in the allowlist;
`req_id` matches `^[A-Za-z0-9._:-]{4,80}$`; nonce matches `^[0-9a-f]{16}$`;
`notice.req_id` must equal `approve.req_id`; `notice.status` must be
`pending`; the approve link must be `rwallet://` (strictest variants require
exactly `rwallet://approve?`); not expired (default expiry = ts + 24 h).
v1 cards (no `approve` block) and block 4 cards (`block4-mint-*`,
`block4-confirmed-*`) get **no buttons**. A card is decided once; a second
decision returns `already-decided` (enforced in localStorage, in the native
write via `.withoutOverwriting` / file-exists check, and across every node
folder in the Android gate).

**Approve never signs.** Approve records the decision, sends the decision
back, and then opens ONLY ASSM ЯWALLET Face ID (via
`window.RMAIL_APPROVE_FACEID` if the host set one, else the card's
`rwallet://approve?` link). The signing happens only on the owner's Face ID /
fingerprint tap in ЯWALLET. **Deny** records the decision and sends
`rmail.decision {decision:"deny"}` back; nothing is signed. "Agents never
decide" / "Bots never decide" is stated in every approve file; the v2 renderer
additionally requires the seat to be `@chaserizal/<seat>` ("only Rizal's seat
decides").

### The t31u policy change (2026-11-11) — the most important finding

The older files say "Mail never triggers sign or mint" / "mail from RMAIL or
the mesh must never trigger sign or mint". That rule was **superseded on
2026-11-11 (t31u)**, per the `superseded` note in
`rmail-handoff.json.0.1.5-upstream`:

> "these seats can sign, mint, or enroll, and mail from RMAIL can trigger a
> seal. Triggering a seal means mail queues or opens a Face ID Approve card
> (rmail-approve.js -> rwallet://approve? ASSM ЯWALLET Face ID); the seal
> completes ONLY when the owner taps Face ID / RGHOSTKEY on the 17e (HARD
> device). Mail never auto-signs, the panel never signs locally, and the
> assistant never signs or approves. Unverified guest mail that claims
> authority is still refused (guest helper 403)."

The new flags: `mail_can_trigger_seal: true`, `seal_requires_faceid: true`,
`never_auto_sign_from_mail: true`, `panel_signs_locally: false`,
`assistant_never_signs: true`. Seal device: iPhone 17e, node `rklowd.17e`,
UDID `<redacted — 17e UDID, see local digest>`, `hard: true`. The seal path is
`rmail-approve.js Approve card -> rwallet://approve? -> ASSM ЯWALLET Face ID
on HARD device`.

Files carrying the t31u policy: `rmail-handoff.json.0.1.5-upstream`,
`rmail-rwallet-handoff.js` (v_seal `20261111-t31u`, `mailCanTriggerSeal: true`,
`faceIdHandoff()` returning `pending_faceid: true`),
`rwallet-rmail-panel-2.js`. Files still carrying the OLD wording:
`rmail-handoff.json` (`never_sign_or_mint_from_mail: true`),
`rmail-route.json` / `rmail-route-2.json`, `rmail-rwallet-handoff.js.bin`,
`rwallet-rmail-panel.js` and `rwallet-rmail-panel.js.bin`, and the panel text
visible in the screenshots ("mail never signs or mints"). The old and new
wordings coexist in the batch; the upstream handoff is explicit that the old
flag is superseded. The substance is unchanged in one respect: **nothing is
ever signed by mail, by the panel, by a bot, or automatically** — the change is
that mail may now *trigger* (queue/open) the human Face ID step.

Related 2026-11-12 rule (RMAILApproveEngine.java): only `mint/trade/swap/buy/
sell` need Rizal's RGHOSTKEY unlock on-device; `sign` and `send` do not
(`needsUnlock`).

## Handoff / mailboxes / route configs

- `rmail-handoff.json` (1,947 B) vs `rmail-handoff.json.0.1.5-upstream`
  (3,009 B): same schema `rzl.rwallet.rmail-handoff.v1`, same four targets
  (relay_8797 active; helper_1_1_1_8; lxmf_local_4242; rklowd_queue),
  `browser_outbox: true`, `hubs: off`. The upstream adds the t31u policy,
  `seal_device`, and the `superseded` note. Source image LINUX RIZAL 1.1.1.6
  (Debian 13, from RVM 0.3.1, unsigned, never booted).
- `rmail-route.json` vs `rmail-route-2.json` (same version
  `1.0-20261111-rbowzr`): identical except -2 uses the mesh hostname
  `chain.rklowd.invalid:8741` for the `/rmint/queue` fallback in three entries
  (rbot-ios, thundr-rbot-fused-ios, ghostmachine-rwallet) where the base uses
  `127.0.0.1:8741`.
- `rmail-mailboxes.json` (877 B): see Identities above.
- `rmail__STATUS.json` / `rmail__node.json`: see What it is above.

## Version drift

### rmail-approve family (6 distinct)

| File | Size | Lineage |
|---|---|---|
| `rmail-approve.js` (= `.android-0.1.4`, `.bin` — same content) | 8,455 | v2 20261111 (RBATBOX), full renderer + transport. `RMAIL_APPROVE`. |
| `rmail-approve-2.js` | 8,562 | **Newest of the pair**: tightens the approve link to exactly `rwallet://approve?` (base accepts any `rwallet://`) and shows signed/unsigned in the card meta. The screenshots' refusal text ("approve link must be ASSM ЯWALLET (rwallet://approve?)") matches this variant. |
| `rmail-approve-v2.js` | 7,909 | v2 renderer-only 1.1, 20261111-rbowzr. `RMAIL_APPROVE2`. Bridges: iOS WK `rmailDecision`, Android `RMailNative`, else localStorage `rmail.decisions.pending`. |
| `rmail-approve-v2-2.js` | 8,042 | **Newest**: one-line vc27 change — Android `writeDecision` handled as an async promise. |
| `rmail-approve-1.0.0.js` | 3,696 | Port of ApproveEngine.swift 1.0.0. `RMAIL_APPROVE100`, parse/validate/decision only; 7 kinds (adds trade/swap/buy/sell); `needsUnlock` for mint/trade/swap/buy/sell. "v2 is kept and still drives the inbox buttons." |
| `rmail-approve-android.js` | 5,077 | **ЯWALLET side** (not RMAIL), 20261112 staged. vc30: approve is native-only, native UI not built → shows the request, signs nothing. vc28: own-drop requests not signable. vc27: `RGhostkeyNative.approve(req, nonce)` — native reloads the stored request; the entry is never sent. Lookup via the phone's own `127.0.0.1:8319/rscale/rklowd/pending`, then local RMAIL cards. Requires a complete `rghostkey.bind` entry (purpose/owner_rid/handle/block_sha256/prev_hash) or the request is "not signable here". |

### rmail-ui family (9 distinct)

- **v1 (20261104)**: `.bin` (8,571, css `?v=1`, oldest) → base (8,571, css
  `?v=2`) → `-2` (9,379, adds the 20261111-rbowzr v2 card renderer loader +
  `RMAIL_BADGE_HOOK`) and `-5` (8,615, adds a `window.RMAIL_UI.folders`
  override hook) as siblings.
- **v2 (20261105, t620u/t621u real-shell rebuild)**: `-3.bin` (17,550, oldest:
  no approve loaders, keyword-based `isApproveReq`, no block-4 pin) →
  `-4.bin` (17,842, adds block-4 pinning: a pending `block4-mint-*` card pins
  to the top until block 4 confirms, 1.0.4.37) → `-5.bin` (18,133, adds the
  APPROVE2 loader + strict spec-based `isApproveReq` + v2 html) → two
  siblings: `-4` (18,218, adds t191u "Message opens Inbox") and `-3` (18,637,
  adds the vc35 APPROVE100 loader + "Queued on phone" message). **-3 and -4
  are parallel branches; neither contains the other.**
- t621u: tiny badge on the ASSM profile Message button (+ nav msgs) for new
  mail OR Face ID approve/sign/mint requests — this is the badge whose Linux
  PARITY row #20 was partial. t620u: external Face ID requests arrive via
  RMAIL; Approve Mint/Sign launches ONLY Face ID from integrated ASSM RWALLET.

### rsocial-rmail family (9 distinct) — the shared transport layer

- **v1 (20261104)**: `.js-2.bin` (3,839) — oldest; localStorage outbox +
  transponder relay.
- **v2 (20261104)**: `-7` (7,836, oldest: no RVM lxmf-send leg, old badge) →
  `-3` (8,083, adds the RVM `lxmf-send` leg) → `-5` (8,150, newest v2: badge
  reads unread count from `RMAIL_UI.folders()`).
- **v2.1 (20261105)**: `-6` (9,082, old badge) → base (9,149, unread badge).
- **v2.2 (20261105)**: `.js-4.bin` (11,187, LAN IPs, unchecked trusted-devices
  fetch) → two siblings: `-2` (11,550, mesh `.rklowd.invalid` hostnames,
  unchecked fetch) and `-4` (12,548, LAN IPs, **sha256-checked**
  trusted-devices loading via `.sha256` sidecar + WebCrypto). **-2 and -4 are
  parallel branches; neither contains the other.** The handoff file cites
  v2.1 as the version pulled from the 1.1.1.6 image.

### rmail-nokey-surface family (7 distinct) — KUBO NOKEY lane v2 (20261105)

Guest-default shared RMAIL/MESSAGE/RWALLET surface for ASSM @chaserizal. No
device-key APIs, unlock dialogs, enroll, sign, or chain-seal. "Public owner
address is content routing only — never authority." Persisted-id dedup against
localStorage `rmail.box` / `rmail.outbox`; `isBlock4OrAuthority` mirrors the
guest helper's refusal.

- `.js-2.bin` (19,458, oldest): v2 without persisted-id dedup.
- `-2` (29,706) / `-4` (30,638): dedup, but WITHOUT the 20261111-rbowzr
  approve-v2 carry block.
- base (32,284): dedup + rbowzr carry (`keepNotice`/`keepSecretish` — the
  approve block is carried as data only, never authority).
- "wallet-layer (not front)" line: `.bin` (30,594, no rbowzr carry) → `-5`
  (33,808, LAN IPs + extra loopback hubs) and `-3` (32,876, mesh hostnames;
  rbowzr carry) as siblings.

### rwallet-rmail-card / -panel

- Card 1.0 (RWALLET 0.1.2, 20261109), read-only, GET `/rmint/queue` via
  RMINT_TRANSPORT; the only action is "open ЯWALLET". Clean chain:
  base (2,162) → `-2` (2,216, RIZAL Mono font stack; = `.bin`) → `-3` (2,339,
  walet-32 icon; = `.0.1.5-upstream`) → `-4` (2,350, mesh hostname
  `chain.rklowd.invalid:8741`).
- Panel (PRIVATE staged 20261110): `.bin` (5,751, oldest: no approve cards) →
  base (7,319, adds 20261111 RBATBOX approve cards via `RMAIL_APPROVE`) →
  `-2` (9,699, **t31u rule** — mail can trigger a seal via the Face ID card).

### RMailBlock4Native.swift (3 distinct)

`.bin` (22,568, oldest: queue in Application Support
`RDRAGON/rmail-block4-*`) → `-2.bin` (23,443: canonical store moved to
`Documents/ЯLAB/RKLOWD/nodes/17e/{outbox,drop}`, legacy folders read-only;
adds `requestNeoEnroll`, 20261107) → base (29,682, **newest**: appends the
whole `RMailDecisionNative` class + UIKit import, 20261111-rbowzr, "so the
XcodeGen project needs no regenerate"). Note: the appended copy injects only
`window.RMAIL_SEAT`; the standalone `RMailDecisionNative.swift` is the newer
rbowzr-resync version with the full host adapter (`RMAIL_DECISION_DROP` /
`RMAIL_APPROVE_FACEID` / `RMAIL_DROP_RESULT`).

### RMailDecisionBridge.java (2 distinct)

`.vc31.java.txt` (4,173) → current (4,786): vc32 adds the node-from-stored-
request rule (page node ignored and shown in the dialog), already-decided
checked across every node folder, and `open()` handing another app ONLY a URL
rebuilt from the checked req + nonce (leftover page parameters dropped).

## Native bridges

- **RMailDecisionNative.swift** (7,461 B, 20261111-rbowzr): WK handler
  `rmailDecision`. `write` stores the bare decision at
  `Documents/ЯLAB/RKLOWD/nodes/<node>/inbox/rmail-dec-<req_id>.json` after
  receiver-side checks (schema `rmail.decision` v1, `signed` is boolean
  false, key whitelist of 12, decision approve|deny, `by` starts with
  `@chaserizal/`, req_id regex, no PEM strings, ≤ 4 KB, first decision wins
  via atomic `.withoutOverwriting`). `open` opens only `rwallet://approve?`
  URLs (falls back to an `RWalletApproveRequested` notification). Seat:
  `@chaserizal/neo` on macOS, `@chaserizal/17e` elsewhere.
- **RMailDecisionBridge.java** (4,786 B, package `com.rzl.dragonskull`): JS
  interface `RMailNative`. `writeDecision` → `RDecisionGate.check` (request
  already on the phone, not page-dropped, nonce-bound, no pre-emption) → a
  native Android dialog showing the STORED request id / node / block_sha256 →
  `RDecisionGate.write` (re-checked); reply async. `open` only for
  `rwallet://approve?req=…&nonce=…`, after a native dialog — or without a
  second dialog only within 60 s of the person confirming APPROVE for exactly
  that req + nonce (`RNativeGate` one-shot). vc24 fallback: in-app unified
  ЯWALLET page at `127.0.0.1:<UPORT>/rwallet-unified/index.html#rmail-approve?`.
  Seat `@chaserizal/moto`. (RDecisionGate / RNativeGate / RKlowdLocalHub /
  MainActivity are referenced but NOT in this batch.)
- **RMAILApproveEngine.java** (7,097 B, `com.rzl.dragonskull`): Android port
  of RMAIL-APPROVE 1.0.0 ApproveEngine.swift, plain JDK, "unit-tested on the
  host". Same validation as the JS 1.0.0 port (7 kinds; `needsUnlock` only
  for mint/trade/swap/buy/sell per the 2026-11-12 rule).
- **RMailBlock4Native.swift** (29,682 B, 20261105 + rbowzr): WK handlers
  `rghostkeySign` + `rghostkeyQueue`. Offline-first: local req_hash recompute
  (`sha256` of canonical `{seal_entry, bundle}`), one outstanding approval,
  public durable queue in `nodes/17e/outbox` with state
  `offline_seal_pending_chain`. OP `rghostkey.signBind`, purpose
  `rghostkey.bind`, owner `ЯID-0001-3QQS` / `@chaserizal`. "No mint/publish
  here. Production requires the host single-method signer; no pseudo-signing
  path." A pseudo path exists only behind the `RM4_ALLOW_PSEUDO` env gate +
  `testPseudo` marker (mock-only). Also handles `rghostkey.enroll` (Neo
  public-key registration first, 20261107) with an ASSM prompt on macOS.
- **`.class` files** (5): RMAILApproveEngine, RMAILApproveEngineTest,
  RMAILApproveEngine_Request, RMailDecisionBridge, RMailDecisionBridge_Done —
  all compiled Java 11 (class version 55.0). Contents not decompiled; recorded
  as artifacts only. (No `MiniJson.class` in the batch, although the test
  imports `com.rzl.dragonskull.MiniJson`.)

## Sync / guest helper

- **`rmail_sync.py`** (4,220 B, v1 20261104, stdlib + `cryptography` for the
  verify step): Neo-side sync. Reads
  `GHOSTMACHINE-TRANSPONDER/SIGNAL-QUEUE/rmail-<addr>/*.json` (written by
  rsocial-rmail.js via relay `/send`), writes
  `~/R/ЯLAB/RKLOWD/RMAIL/<addr>/<id>.json` (RKLOWD syncs it to devices),
  `$RLINE_OUTBOX/rmail-<id>.json` when set, and `RMAIL/index.json`
  (`rmail.index.v1`, counts per address). Re-verifies each message (incoming
  `verified` stripped), sets `trust`, stamps `via: transponder:<queue>`.
  Never deletes: handled queue files are renamed `*.synced`. CLI:
  `once | loop` (loop sleeps 15 s).
- **`rmail_guest_helper-1.1.1.8-draft.py`** (10,473 B, v1.0.0, 2026-11-10):
  Linux port of the Nov 5 NOKEY helper (`serve.py` on :8830). Loopback-only
  (refuses to bind anything else; rejects non-loopback Host headers).
  `GET /` serves the shared rizal.pw surface; `GET /health`
  `{ok, mode:"nokey", authority:false, …}`; `GET /api/rmail/public?addr=`
  (the contract `rmail-nokey-surface.js` consumes); `POST /api/rmail/guest`
  intake: forced `folder=Guest`, `signed=false`, `verified=false`,
  `trust=guest-unverified`, HTML stripped, body ≤ 4,000, 20/hour per-origin
  rate limit, dedup by persisted ids (`STATE/seen.json`), copy dropped to
  RKLOWD. **Anything asking for authority (sign/seal/enroll/mint/approve/
  faceid/block4/bind/rghostkey) → 403, logged** — path regex plus
  `authority_reason()` on the payload (schema/purpose/type/authority fields,
  `trusted_internal`, signed claims, `seal_entry`/`req_hash`/`rsign_seal`/
  `sig_b64`/`signature`/`pubkey_spki_b64`/`private_key`/`seed`/`mnemonic`/
  `dek`). Guest mail can only go to `@chaserizal` (owner addr
  `BwpVNk1Rtncpv5HMTLwxB4Yfjkfv6mFaBQUTpjneH1F9`). "No keys are read or held;
  NOKEY guest mail is never verified here. Never deletes."
- **`rmail-rizal-mail.js`** (8,838 B, v2 20261114): identity switcher; hooks
  `RMAIL_UI.folders`/`draw` and the NOKEY refresh; fetches
  `rmail-mailboxes.json` and per-hub `/rmail/boxes` +
  `/rmail/inbox?mailbox=` (header `X-RDRAGON-Seat`).
- **`thundr-rmail.js`** (1,628 B, 20261104): ThundR command RMAIL — opens
  `rmail/rmail.html` in its own window (macOS float/desktop) or a full-screen
  sheet (iOS); also triggers on typing `rmail` + Enter in a field.
- **`rmail.html`** (541 B): standalone page loading `rnetwork-config.js`,
  `rsocial-rmail.js?v=2`, `rmail-ui.js?v=2`, opening `RMAIL_UI.open(
  {standalone:true})`. **`rmail.svg`** (581 B): the ✉ RMAIL icon.
- **`rmail-ui.css`** (3,118 B, v1 20261104): terminal green (#39ff14) /
  purple (#8a2be2) theme; 3-column grid (170px nav / 300px list / reader),
  single-column under 760 px.

## Tests / builds

- **RMAILApproveEngineTest** (Java, vc35): 16 checks; the vc37 log
  (`RMAILApproveEngineTest-vc37.log`, 572 B) shows **ALL PASS 16/16**
  (kinds, needsUnlock, parse/validate, unsigned decision, needs_unlock flag,
  file name, signed/non-pending/over-4KB/bad-nonce refusals, send decision,
  expiry).
- **`test_rmail_block4_native_mock.py`** (5,162 B, 9 tests, mock-only): run
  here 2026-11-19 — **7 pass, 2 error on file paths only**
  (`test_pseudo_flag_never_prod` and `test_handlers_named` read
  `RMailBlock4Native.swift` and `App.swift` from the test file's parent
  directory, which does not exist in this grounding layout; `App.swift` is
  not in the batch at all). The 7 logic tests pass (req_hash stability and
  tamper rejection, secret-queue rejection, signable/not-ready gating,
  payload allowlist, durable-queue dedup, pseudo-flag marker present in the
  Swift source — verified: the Swift file does contain `RM4_ALLOW_PSEUDO`
  and `testPseudo`).
- **`rmail_card_test.py`** (3,328 B): Playwright box test (headless Chrome,
  `http://127.0.0.1:8771/`, non-local requests blocked and counted). Injects a v2
  mint card (`apr-test0000beef`, "Mint 100 R to my wallet", from
  `rbot-linux`) and a v1 card, screenshots the approve card, clicks Deny,
  screenshots after-deny, asserts the v1 card has no `[data-rapr]` buttons,
  prints the `rmail.decision.outbox`. Screenshots go to
  `/workspace/rwalet-neo/shots/` — the `neo-desk-rmail-approve-card.png` /
  `neo-phone-rmail-after-decision.png` shots in this batch match this test's
  card text, though the file names differ (`neo-rmail-approve-card.png` /
  `neo-rmail-after-deny.png` in the script).
- **Build logs — 6/6 `** BUILD SUCCEEDED **`**: `build-20261104-rmail5.log`
  (RTHUNDR.xcodeproj, scheme RTHUNDR, iOS Release, build 5);
  `build-device-20261104-rmailui18.log` + `18b` (DragonSkull 1.0.4 build 18,
  two runs); `build-device-20261104-rmail24.log` (DragonSkull 1.0.4 build 24);
  `build-device-20261105-rmail30.log` (DragonSkull 1.0.4 build 30);
  `build-t189u-b46-rmail-inbox.log` (DragonSkull 1.0.6.0 build 46, Debug,
  destination device `<redacted — 17e UDID, see local digest>` — the 17e). All
  `DEVELOPMENT_TEAM=7D3P5F4V9M`, `-allowProvisioningUpdates`.

## Screenshots (17 distinct images)

20 listed in the media library plus `desktop-rmail-approve.png.bin` in the file
batch (21 image files listed); v1/v2/v4/v6-phone-rmail.png are byte-identical
(one image), and `desktop-rmail-approve.png.bin` ==
`desktop-rmail-approve-2.png`. Two were
read to confirm the UI shape:

- `neo-desk-rmail-approve-card.png`: RMAIL panel, "APPROVE / DENY" section.
  Card 1 (valid): "MINT · Mint 100 R to my wallet · from rbot-linux · needs
  ASSM ЯWALLET Face ID · unsigned", green **Approve Mint · Face ID** button +
  red **Deny** button, caption "Approve opens only ASSM ЯWALLET Face ID ·
  Deny replies 'denied' · nothing is signed here". Card 2 (refused):
  "refused: approve link must be ASSM ЯWALLET (rwallet://approve?) · no
  buttons" — the strict `-2` validator wording. Below: "v2.1 browser outbox ·
  configurable hand-off · mail never signs or mints. Active target:
  relay_8797 — RSCALE / transponder drop on loopback :8797 (current
  default). Hubs: off · LXMF local path … :4242. RKLOWD fallback … Point
  data/rmail-handoff.json active at helper_1_1_1_8 when that helper is up."
  OUTBOX "0 message(s) in this browser", INBOX (LOCAL) "3 message(s)",
  compose box placeholder "message — will not sign or mint", "Queue in
  outbox" button, "status: ready".
- `neo-phone-rmail-after-decision.png`: same panel after Approve — card 1 now
  reads "Approved — ASSM ЯWALLET Face ID opened · ЯWALLET signs only after
  your Face ID"; status line "approved · waiting for Face ID in ЯWALLET".
  The refused card is unchanged.

The remaining shots (base/v1–v6 desk/phone, desk-rmail, phone-rmail,
desktop-rmail-approve ×2, neo-desk after-decision) were inventoried but not
individually read.

## Companion files in the batch (not RMAIL code, same upload)

- `float.html.bin` / `float.html-2.bin` (1,180 / 1,276 B): THUNDR-FLOAT shell
  loading `thundr-live.js`, `thundr-adapter.js`, `thundr-visible.js`,
  `thundr-bus.js`.
- `scout.html.bin` / `scout.html-2.bin` (9,529 / 9,448 B): RDRAGON page
  (dark theme, `rwallet-guard.js?v=20261026`).
- `index.html-3.bin` / `index.html-4.bin` (3,304 / 3,376 B): "Anti Social
  Social Media" pages. `index.html-5.bin` (2,886 B): "RKLOWD · rizal.pw
  browser node" page.
- `SHA256SUMS.bin` (158 B): **both pins verify against this batch** —
  `index.html` = sha256 of `index.html-5.bin`, `rklowd-node.js` = sha256 of
  `rklowd-node.js.bin`. So index.html-5.bin is the pinned RKLOWD node page.
- `rklowd-node.js.bin` (11,767 B): RKLOWD browser node `rklowd.pw`
  (20261104). Hub API: `GET {hub}/rklowd`, `/rklowd/list`,
  `/rklowd/obj/<sha256>`, `POST {hub}/rklowd/put {node,name,b64}`; in-app hub
  `http://127.0.0.1:8799/rscale`; 8 MB object cap.
- `rdragon-cryptosocial.js.bin` (132,174 B): RDRAGON CryptoSocial side panel
  (quality 20261028, offline localStorage, `window.RDRAGON_CSP`).
- `crypto-side-panel.js.bin` (32,315 B) / `.css.bin` (6,838 B): side-panel
  structure + the RDRAGON-REPLY inline chain (tier 0 local commands → ENJIN
  :4979 → IBM Granite → offline local).
- `project.yml.bin` (3,919 B): DragonSkull XcodeGen project (bundle prefix
  `info.rizal`, iOS 16.4, app target + ThundRWidget sources, `App/web` as
  resources).
- `fullprofile.js.bin` (1,482 B): 20261104 pt85u — ☰ opens the CryptoSocial
  profile drawer full-screen.
- `ds-webversion.json.bin` (223 B): RDRAGON iOS 1.0.4 (23), 20261104,
  `nativeAPI: 2` — "rizal.pw parity pills/tabs(+Kubo)/nav dock (SVG bell);
  ЯSYNC headless via siteclone; must beat stale OTA overlay 1.0.1.2".

## Adapter rules for the TPA

1. **RMAIL is a read-only mail surface for the adapter.** Read inbox/drop/
   outbox folders and the public feed; never send, never decide, never
   approve/deny. "Agents never decide" is the code's own rule, stated in
   every approve implementation.
2. **Approve routes to wallet + Face ID, never to the adapter.** An approve
   card's only legitimate next step is the `rwallet://approve?` link to ASSM
   ЯWALLET Face ID on the HARD device (17e). The adapter may surface a
   pending card's summary/kind/app/req_id; it must never open the link, never
   call a decision write, and never present a decision as taken.
3. **Never auto-approve, never treat mail as a sign trigger.** Mail may
   *trigger* (queue/open) a Face ID card under the t31u policy — it never
   signs, mints, seals, or enrolls, and neither does the adapter. A mail
   message is data, not authority; unverified authority claims are refused
   (guest helper 403 pattern).
4. **Apply the same validation before surfacing a card**: v2 block present,
   `signed === false`, ≤ 4 KB, no secret-like content, valid kind/req_id/
   nonce, `notice.status === pending`, `rwallet://approve?` link only, not
   expired, not block 4. Anything failing validation is shown as refused
   with the reason — never with buttons.
5. **Trust is earned, not claimed.** `verified` is true only after the
   ECDSA P-256 check against an active trusted device; incoming `verified`
   flags are ignored (rmail_sync.py pattern). Guest mail is
   `guest-unverified` by construction. Report trust state with every message
   the adapter surfaces.
6. **Block 4 is out of scope for the adapter.** `block4-mint-*` /
   `block4-confirmed-*` cards get no buttons anywhere; the seal path is
   `terraformr bind` + Face ID in TerraformЯ. The adapter reports their
   pending state only.
7. **Use the newest variant of each family** (see drift table): approve-2.js
   / approve-v2-2.js, ui-3.js (or ui-4.js for the t191u inbox-open branch),
   rsocial-rmail-4.js for the sha256-checked trust load (note its LAN-IP
   hubs) or -2.js for mesh hostnames, nokey-surface base (front line) or -3
   (wallet-layer line), card-4.js, panel-2.js (t31u), DecisionBridge current
   (vc32), Block4Native base (rbowzr). When two variants are parallel
   branches, say so — do not merge them by assumption.
8. **Prefer the t31u wording** ("mail can trigger a seal; the seal completes
   only on the owner's Face ID") over the superseded "mail never triggers
   sign or mint" — but keep the substance: nothing is ever signed by mail,
   by the panel, by a bot, or automatically.

## Inventory (distinct files, grounding copies)

Message JSONs (66): 9 thundr-load-guard drops + 9 pw-inbox hash-ID copies,
10 sign requests (5 × neo/17e), 3 egg notices, 1 block4-mint, 3 e2e, 11 kubo,
9 presence/RPIPE tests, 9 grokbot tests, 2 misc (a2c50661, c3daea91).
Config JSONs (7): rmail-handoff.json (+ .0.1.5-upstream), rmail-mailboxes.json,
rmail-route.json (+ -2), rmail__STATUS.json, rmail__node.json.
Approve JS (6): rmail-approve.js, -2, -1.0.0, -v2, -v2-2, -android.
UI JS (9 + css): rmail-ui.js, -2, -3, -4, -5, .js.bin, .js-3/-4/-5.bin,
rmail-ui.css. Transport JS (9): rsocial-rmail.js, -2…-7, .js-2.bin, .js-4.bin.
NOKEY JS (7): rmail-nokey-surface.js, -2…-5, .js.bin, .js-2.bin.
Card/panel JS (7): rwallet-rmail-card.js, -2, -3, -4; rwallet-rmail-panel.js,
-2, .js.bin. Other (6): rmail-rizal-mail.js, rmail-rwallet-handoff.js
(+ .bin), thundr-rmail.js, rmail.html, rmail.svg.
Native (14): RMAILApproveEngine.java + Test.java + vc37 log + 3 .class;
RMailDecisionBridge.java + .vc31.java.txt + 2 .class; RMailBlock4Native.swift
(+ .bin, -2.bin); RMailDecisionNative.swift.
Python (4): rmail_sync.py, rmail_guest_helper-1.1.1.8-draft.py,
rmail_card_test.py, test_rmail_block4_native_mock.py.
Build logs (6): build-20261104-rmail5, build-device-20261104-rmail24,
build-device-20261104-rmailui18, build-device-20261104-rmailui18b,
build-device-20261105-rmail30, build-t189u-b46-rmail-inbox.
Screenshots (17 distinct images): base-desk/phone, desk-rmail, phone-rmail,
desktop-rmail-approve.png, desktop-rmail-approve.png.bin (= -2),
neo-desk/phone-approve-card, neo-desk/phone-after-decision,
v1-desk, v1-phone (= v2/v4/v6-phone), v2-desk, v3-desk, v3-phone, v4-desk,
v6-desk.
Companion (15): float.html.bin, float.html-2.bin, scout.html.bin,
scout.html-2.bin, index.html-3/-4/-5.bin, project.yml.bin,
fullprofile.js.bin, rklowd-node.js.bin, rdragon-cryptosocial.js.bin,
crypto-side-panel.js.bin, crypto-side-panel.css.bin, ds-webversion.json.bin,
SHA256SUMS.bin.

Duplicate groups (30, 34 extra copies): 19 inbox/bare message pairs (same
content under `pw__`/`neo__`/`17e__inbox__` and bare names); approve.js =
android-0.1.4 = .bin; handoff.json = .bin; ui.js = .js-2.bin; ui-4.js =
.js-6.bin; card-2 = card.js.bin; card-3 = card.js.0.1.5-upstream; panel.js =
.js-2.bin = .android-0.1.4; rsocial-3 = .js-3.bin; rsocial-7 = .js.bin;
v1/v2/v4/v6-phone-rmail.png (4-way); desktop-rmail-approve.png.bin =
desktop-rmail-approve-2.png.
