# ThundR Plugin Adapter (TPA) v0.1 — Specification

## 1. Purpose

The ThundR Plugin Adapter lets any bot or AI — including Muse — communicate
with ThundR, run diagnostics, analysis, debugging, repairs, updates, and
coding + visual integrations, through one JSON protocol over loopback HTTP
or a local CLI. The target is the macOS RTHUNDR app from the
THUNDR-CRYPTOBOT Xcode workspace (canonical 1.2.0), confirmed live by
Rizal on 2026-11-19 (§3).

The adapter is a **plugin adapter, not a ThundR replacement**. It routes,
reports, and proposes. It never signs, seals, enrolls, mints, sends, swaps,
or transfers anything; it never writes the chain, the wallet, or a feed.
Every interface claim in this spec traces to a grounding file (§15).

## 2. Protocol — tpa.v1

Protocol version `tpa.v1`, adapter version `0.1.1`. Twelve methods, stable;
new methods arrive as tpa.v2, never by silently changing these.

| Method | Reads / writes | Notes |
|---|---|---|
| `adapter.hello` | read | identity, versions, methods, safety stance |
| `adapter.commands.list` | read | registry commands, filterable by group/host/text |
| `adapter.commands.get` | read | one command by id |
| `adapter.chat` | read | route one line of text (§5) |
| `adapter.diagnostics` | read | services, engines, chain, keys, wallet, rtrackr, models, knowledge |
| `adapter.analyze` | read | file info, registry diff, host parity, build stamp, components, asset feeds, RID, wallet snapshot, rtrackr feed |
| `adapter.debug` | read | redacted log tails, transcripts, self-test (dry-run) |
| `adapter.repair.propose` | plan only | returns a plan, never executes |
| `adapter.repair.apply` | GO-gated | apply-by-reference (§6); v0.1 executes nothing mutating |
| `adapter.update.check` | read | canonical vs bundled registry, build stamp, open items |
| `adapter.update.apply` | GO-gated | refresh bundled snapshot only, content-bound (§6) |
| `adapter.visual` | read | float/orb/panel state, float-window layout, shot hook (documented, never executed) |

### Envelope

Modelled on the `LocalBrain.call(tool:text:done:)` bridge result
(`{ok, via, reply}`):

```json
{"ok": true,  "via": "<route>", "data": {...}}
{"ok": true,  "via": "<route>", "reply": "<text>"}
{"ok": false, "via": "<route>", "error": "<reason>"}
{"ok": false, "via": "<route>", "refused": true, "reply": "<refuse reply>"}
{"ok": false, "via": "<route>", "go_gated": true, "error": "go-gated", "reply": "<handoff>"}
```

`via` always names the route that answered, so a caller can tell a live
brain reply from a registry fallback from an offline note. Nothing ever
fakes a live brain reply: when no brain is reachable, `via` says so.

## 3. The live target — the macOS float

Described from Rizal's screenshot of the running RTHUNDR app
(2026-11-19 13:33 MST, `grounding/thundr-float-live-2026-11-19.png`).
This window is the visual integration target for `adapter.visual`.

- **Window:** a floating panel over other apps; purple border, green
  corner brackets. The ThundR imp sits above it with a "ThundR · awake"
  label and a lightning bolt.
- **Header (green text):** `⚡ THUNDR · RDOS · SANDISK GRANITE 4.2 3B ·
  127.0.0.1:4983` + a SANDISK tag chip; red ✕ close button top-right.
- **R:> shell row:** green-bordered input with prompt `R:\>` and quick
  commands `models · use qwen · use granite · …`, plus a green SEND button.
- **Status bar:** `Qwen 1.7B · UP` pill, `idle`, a level bar, `q:0`, clock.
- **Reply area:** dark body; parser replies carry a green `via parser`
  attribution. The ready reply reads: "ThundR ready. Try: wallet
  balances · casket verify · signing status · prompt faceid · sign this
  <dir> · request approval <what>".

The adapter reports this layout (`adapter.visual`, kind `float-window`)
and the float/scout host states. It never opens, moves, types into, or
screenshots the window.

## 4. Engines

Two engines, as the float shows them:

- **Granite 4.2 3B (primary):** the SANDISK relay on `127.0.0.1:4983`.
  Diagnostics probes `GET /health` (the Linux brain's `granite_health`
  pattern, 1.2 s timeout) and reports UP / unreachable / HTTP code.
- **Qwen 1.7B (fallback):** in-process llama.cpp in the macOS app. Its
  liveness is reported by the app status bar ("Qwen 1.7B · UP, idle,
  q:0") and cannot be probed from the adapter; diagnostics reports Qwen
  model-file presence from the GGUF inventory instead, and says so.

`adapter.diagnostics` reports both engines, the preferred engine, and
the active engine (Granite when preferred and up, else Qwen — the Linux
brain's `status-live` rule).

### Engine-switch verbs

The R:> shell quick commands are covered by `adapter.chat`, mirroring
the Linux brain's picker exactly (`models` / `use qwen` / `use granite`,
plus `engine qwen` / `engine granite` aliases):

- `models` answers the MODELS panel deterministically: both engines,
  their state, the active marker, and the command footer.
- `use qwen` / `use granite` record the **adapter's** engine preference
  (`~/.config/thundr-adapter/engine-choice.json`, atomic tmp + replace,
  mirroring the Linux brain's `_save_choice`). The reply says so
  plainly: the live macOS float keeps its own engine choice, set by
  typing the same verb in the R:> shell. The adapter never claims a
  mechanism to flip the app's engine, because none is known.

## 5. Chat routing

`adapter.chat` routes one line of text, in this order (mirroring
`thundr_chat.handle` and `LocalBrain.call`):

1. **Refuse check** — the registry's 7 refuse regexes (§6). A match is
   refused with the registry's own `refuse_reply`; nothing runs.
2. **GO-gated wallet/signing verbs** — the parser's six verbs (§6).
   Answered with a GO-gated handoff, never forwarded to any executor.
3. **Aliases** — `manual [words]` → `AUTOMANUAL [words]` (words kept).

### AUTOMANUAL doctrine (index and quote, never dump)

The AUTOMANUAL is the adapter's doctrine source: `adapter.analyze` /
`adapter.chat` answer law, organ, and command-doctrine questions from it
by section citation — index and quote (heading + ≤5 lines), never dump.
Seat naming is mandatory in answers: "UNIFIED §x.y …" / "game MANUAL §n …",
never "the manual" alone. The manual's own laws bind the adapter:
add-only (REQ-23), never-delete, Gate 2 WAIT, bots never sign/mint/seal/
hold keys, ALL-OS SYNC LAW (no platform ships alone). The -2 variant is
the newest revision (U35 rate leaf); when the adapter checks a manual
copy, the presence of §2.4.9.14 distinguishes it. `AUTOMANUAL` is a bot
command (alias AM): route it to index/quote, and confirm verbs against
COMMANDS-MASTER after the md lookup. The C1–C7 conflicts are the standing
example of "report the conflict, don't pick a side from one source" —
report both readings with sources.

Bot pick order: game MANUAL → thundr-knowledge → UNIFIED →
crypto leaf → Drive mirror. KNOW/AUTOMANUAL.md is a fragile BONEPILE
symlink — prefer UNIFIED.
4. **Deterministic help / listings / engine verbs** — from the registry
   or diagnostics, no model. Help is routed BEFORE any brain call,
   exactly like `NativeCommands.reply` runs before model load.
5. **Live brain** — POST to the MCR loopback endpoint
   `http://127.0.0.1:8329/v1/call/thundr_chat` (2 s timeout). Only an `ok`
   answer is returned, with `via: "mcr:8329"`.
6. **Registry fallback** — the closest known command, or an honest
   offline note. Never a faked brain reply.

## 6. Safety rules

### The 7 refuse regexes (registry, enforced for every agent)

From `thundr-commands.json` (schema `thundr.core.commands.v1`), matched
case-insensitively:

| Pattern | Label |
|---|---|
| `^optimize\s+(clean\|deep)\b` | optimize clean / optimize deep (removes files) |
| `^eggs?\s+install\b` | eggs install |
| `^self[- ]?evolution\b` | self-evolution |
| `^rebirth\b.*\bgo\b` | REBIRTH … go (real run) |
| `^(egg\s+apply\|api/egg/apply\|api/approve)\b` | egg apply / approve endpoint |
| `^rscribe\s+build\b.*--run\b` | rscribe build --run (real Apple build/sign) |
| `^17e\s+(uninstall\|delete\|rm\|sign\|keychain\|wallet)\b` | 17e uninstall/delete/rm/sign/keychain/wallet |

Refusal reply (the registry's own words): "needs Rizal's GO. ThundR
never signs, mints, seals, installs, removes files or writes the
chain/wallet. Nothing was run."

### GO-gated wallet/signing verbs

The parser's six verbs — `wallet balances`, `casket verify`, `signing
status`, `prompt faceid`, `sign this <dir>`, `request approval <what>`
— plus close variants (`wallet`, `rwallet`, `signing`, `sign egg`,
`egg-sign`, `faceid`, `approve`, `mint`, `request mint`, `request
sign`) map to the LIVE `/rmint/request` flow, the
highest-sensitivity surface. They are GO-gated: the adapter answers
with a handoff (`go_gated: true`) and never forwards them to the MCR
or any executor. Rizal's explicit GO for that exact action is
sufficient authorization — no biometric step is required (Face ID /
Touch ID stay available on the device, never required). Read-only
live verbs (`status`, `inventory`, `jobs`, `progress`, `mcr`, `gizmo`,
`rcpm`, bare `casket`) are NOT gated and route normally.

The adapter is deliberately stricter than the registry here: the
registry marks RWALLET go:false as an everyday chat verb, but the
adapter is a bot channel, and bot input cannot request, confirm, or
send on the live flow (the Linux brain's bot-tagged guard).

### Never-operations (HARD RULE)

The adapter NEVER signs, seals, enrolls, mints, sends, swaps, or
transfers — not even with GO. There is no tpa.v1 method for any of
these, `adapter.hello` lists them under `never`, and `repair.apply`
refuses a plan step naming one of them. Signing happens only on the
pinned device, by the human, through RGHOSTKEY (§12). The wallet is
watch-only (§13).

ONE RULE (RSOL BOTKARD TEMPLATE, Rizal 2026-11-19):
YOU CAN NEVER ERASE OR REMOVE A SKILL OR MEMORY.
Repairs and updates are add-only; nothing in the adapter deletes,
overwrites, or prunes a skill, a memory, or a grounding file. This sits
at the top of the UBK UNITED BOT KARD and on the bot/AI door notice
(BOTS.md); seating at the front of the unified AUTOMANUAL is built and
awaiting the Neo write.

### GO design (RGHOSTKEY vc27/vc31 mirror)

- **No general sign path.** There is no sign method at all.
- **Approve-by-reference.** `adapter.repair.propose` stores the plan
  server-side and returns `plan_id` + `nonce`. `adapter.repair.apply`
  takes `plan_id` + `nonce` + `go` and loads the STORED plan itself;
  a caller-sent plan payload is refused. The approver never sends the
  payload, so a tampered plan cannot be smuggled into apply — the
  vc27 shape (approve by id + nonce, native loads the stored request).
- **Content-bound updates.** `adapter.update.apply` takes the
  `live_stamp` from `adapter.update.check` and refuses when the
  canonical registry changed since the check, so an approval can never
  land on different content than was reviewed — the bind flow's
  content-bound approval shape.
- **No unlock method on the adapter.** The adapter has no unlock
  method; any device unlock happens on the device, never through the
  adapter. A biometric (Face ID / Touch ID) is available on the
  device but never required — Rizal's explicit command (GO) is
  sufficient authorization for sign/mint/seal/approve.
- **No held unlock context, no timer, no auto-approve.** Plans live
  only for the server process lifetime (in-memory, like the per-start
  token); a stored plan is a proposal, not an authorization.

### Chain: read-only (HARD RULE)

The adapter is READ-ONLY against RGHOSTCHAIN. It may call GET
`/health`, GET `/rtrackr/assets`, GET `/market/view`, GET
`/market/verify` on the daemon (`127.0.0.1:8741`). It must NEVER call
POST `/rghostchain/submit`, POST `/rtrackr/register`, POST
`/rtrackr/ingest`, or POST `/market/submit`. The refused list is
encoded in `chain.py` (`CHAIN_REFUSED_WRITES`) and enforced by
`check_chain_call` before any request is made; there is no code path
in this package that POSTs to the chain. See §11.

## 7. Transport + port map

Loopback-only, offline-first. The server binds `127.0.0.1` only
(refuses any other host); the client refuses any non-loopback URL
(the Linux port's `http_json` stance). No external network anywhere.

| Port | Service |
|---|---|
| 8741 | RGHOSTCHAIN submit daemon / ThundR gate |
| 8742 | ThundR Plugin Adapter (default; `THUNDR_ADAPTER_PORT`) |
| 8329 | MCR command centre (`MCR_PORT`) |
| 4983 | Granite 4.2 3B relay (macOS, SANDISK) |
| 8080 | Backup local LLM |
| 8796 | Linux web shell |
| 4979 / 8777 | Granite relays (Linux) |
| 4984 | THUNDR-SHELL (default when no session file) |

Port 8742 is free of known ThundR services; it is assumed free on the
Mac, not verified there.

**Auth:** per-start Bearer token (`secrets.token_urlsafe(32)`), written
mode 0600 to `~/.config/thundr-adapter/token`, never printed — the
thundr-shell.py pattern. Only `GET /health` is open (identity only);
`/v1/methods` and `/v1/call` need the token. Host/Origin checks are
stricter than the MCR's: loopback only, no LAN IP. File methods are
sandboxed with `safe_path` (controlroom.py pattern) inside the safe
root (`THUNDR_ADAPTER_ROOT`, default the ThundR tree when present,
else the adapter tree). Request bodies are capped at 64 KiB.

## 8. Plugin manifest format

Schema `tpa.plugin.v1`. A plugin is a manifest + one entry file; the
adapter verifies the entry's SHA-256 before registering any capability,
and registers capabilities only — it never executes plugin code.

```json
{
  "schema": "tpa.plugin.v1",
  "name": "example-plugin",
  "version": "0.1.0",
  "description": "What it does.",
  "entry": "example.py",
  "sha256": "<sha256 of the entry file>",
  "capabilities": [
    {"name": "example.echo", "method": "adapter.chat",
     "description": "Echoes text."}
  ]
}
```

Rules: the entry must be a regular file inside the plugin directory
(symlinks refused, path escapes refused); the SHA-256 must match
exactly; a capability name registers once (a second registration is
skipped, not doubled). The verification pattern follows the SHA256SUMS
manifest precedent (§10): pin every asset, verify on load.

## 9. The .rzl parts catalog (RZL index)

The RZL index (`RZL_INDEX.pdf`, 81 pp, scan date 2026-11-04; digest in
`grounding/rzl-index-digest.md`; 1,388 `.rzl` files across `~/R` +
iCloud) is the parts catalog for the THUNDR × RENJIN build.
`adapter.analyze` (kind `components`) reports each component's status
against this table and flags the gaps. The full 4,286-line index text
stays in `grounding/`; the adapter carries the digest table only.

| # | Component | Pieces | Unique | Size | Status |
|---|---|---|---|---|---|
| 0 | RbotLoadR | 1 | 1 | 7,160 B | 0.0.1 UNSIGNED DRAFT, verified |
| 1 | RVM | 155 | 13 | 272.49 MB | COMPLETE as runtime |
| 2 | RGENERATR | 27 | 2 | 13.09 MB | PARTIAL |
| 3 | RBATIBABOX | 137 | 52 | 985.37 MB | PRESENT |
| 4 | RMIND | 7 | 7 | 73.18 MB | PRESENT as memory docs only |
| 5 | ЯSEED | 255 | 42 | 69.15 MB | COMPLETE |
| 6 | OTHER pure .RZL | 777 | 423 | 3,883.18 MB | skills, docs, eggs, logs |

Open gaps (also reported by `adapter.update.check`, report-only, never
auto-fixed): RGENERATR is PARTIAL and UNSIGNED (only RGENERATOR 2.1.9);
RMIND has no runner (memory docs only); RVM-LINUX-0.1.0 is not pure
(raw `.bin` kernel/disk images). Gap #0 is closed as a draft:
RbotLoadR 0.0.1 awaits owner signing (RGHOSTKEY; biometric optional, never required).

Notes: the table's pieces sum to 1,359 against the index total of
1,388; the digest does not account for the remaining 29 — an open
question for the index, not an adapter error. "ThundR" appears 225×
in the index; "renjin" 0× (the index predates the RENJIN naming).
ЯSEED is the pure-`.rzl` model ancestor of RENJIN (ternary weights,
tokenizer, generate/train) — the RENJIN core v3 descends from this line.

### RbotLoadR 0.0.1 — the egg-handling reference

RbotLoadR 0.0.1 (supplied 2026-11-19, `grounding/rbotloadr-0.0.1/`) is
a single-file HTML+JS pure `.rzl` loader — one HTML file with a `.rzl`
extension, NOT a ZIP — derived from RCOMMAND/HARDSHELL/opener. It opens
rzl.v1 eggs by picker/drag-drop, verifies every manifest component
(sha256 + size), mounts the egg's `index.html` with a read-only
`window.RZL_VFS`, and also reads ENJIN-ASSEMBLY (`rzl.enjin.assembly.v1`)
pins. No network, no signing, no chain append. Manifest schema
`rzl.rghostchain.enjin_egg.payload.v1`, draft, NOT_APPENDED, role
loader, sig plan "owner signs with RGHOSTKEY / Face ID later" (the
manifest's words; biometric optional since the 2026-11-19 order).
Verified 2026-11-19: sha256
`d1ea6a6a5435ab90ecb2f623f2e4670f602753eb00e3d237c8b1612c97c84aed`
matches the manifest, size 7,160 B, `.rzl` and `.html` byte-identical.

Its **verify-then-mount** pattern (sha256 + size per component,
read-only VFS, no network/signing/append) is the reference for the
adapter's own egg handling: the adapter verifies before it trusts, mounts
read-only, and never signs or appends.

## 10. Precedents the adapter follows

**RGENERATR — one writer, preview-until-live.** RGENERATR is the asset
adapter: one writer (`rgen_asset_adapter.py` reads the local
RGHOSTCHAIN jsonl + RTRACKR registry, never writes the chain) produces
`out/assets.json` (schema `rzl.rgeneratr.assets.v1`) + a `.sha256`
sidecar. Readers (TerraformЯ game wallet, ЯBOT wallet, rizal.pw
RWALLET, RTRACKR) never edit the feed. Rule: "One place, one writer."
Assets stay PREVIEW until a verified `nft_mint` block exists for the
rid AND the seal has a signature; seals are written on the phone by
RSIGN on Rizal's command (ES256/P-256, never a private key; biometric
optional, never required) and moved phone→Neo over USB via devicectl. The adapter mirrors this shape:
repairs/updates are propose-only until GO, the same as
preview-until-seal. `adapter.analyze` (kind `rgeneratr-assets`) knows
the feed shape (status / seal_hash / seal_sig_present / block /
chain_verify) and evaluates the live gate per asset, flagging any feed
whose status disagrees with the gate. Snapshot 2026-10-30: one owner
(@chaserizal, ЯID-0001-3QQS), one asset (rid-asset-0001-genesis
"GAME-MINTED GENESIS"), status "preview — awaiting signed seal".

**rshell transport — allowlist design.** rshell.js (MEKANICA
2026-11-11) is one shared window-logic file for both shells, loopback
only, enforcing `rshell-allow.json`, over either the native host bridge
(`window.webkit.messageHandlers.rshell`) or a same-origin `/x/`
proxy. "No keys, no signing, no minting, no Cloudflare." The adapter's
own allowlist design follows it: loopback-only transport, explicit
allow/refuse lists (chain read paths, refuse regexes, safe actions),
and "Approve never signs; it opens ASSM ЯWALLET Face ID" (rshell.js,
2026-11-11; the biometric step is optional since the 2026-11-19 order
— Rizal's command is sufficient).

**SHA256SUMS manifest — verify on load.** `rbox.web.rwalet.SHA256SUMS`
(70 entries) pins every web asset; the adapter's plugin verification
(§8) and snapshot verification (§13) follow the same pattern: pin,
verify, report mismatches, never silently trust a file.

## 11. RGHOSTCHAIN + RTRACKR

RGHOSTCHAIN is the ledger of the Я ecosystem: an append-only chain of
blocks recording the minting of bots, digital assets, and identities.
Block types: genesis · cryptobot_mint · nft_mint · transfer · note ·
convert · index. The submit daemon (`rghostchain_submitd.py`, 755
lines, stdlib only, no secrets) binds `127.0.0.1:8741`. DRY by default
(DRY-SUBMIT chain); LIVE needs all three: server started with `--real`
(Rizal), an RSIGN seal verified with `owner_rid == asset.rid`, and
mode `live`. Since 2026-11-18 (pt62u), LIVE mints additionally need a
minter proof from ThundR's or GIZMO's own registered key in the
sha-pinned registry, else 403; the block records minter /
minter_device / minted_by. Gate 2 (live wallet/mint authority) stays
closed until the required checks are built and the owner opens it.

`adapter.diagnostics` reports the daemon's health from GET `/health`
(counts + validity for the real and DRY chains, DRY vs LIVE mode, and
the minter-gate status from the trust-registry pin state). Tips
(latest block hashes) are NOT in `/health` and are reported as unknown
rather than invented.

### RTRACKR — the adapter's read surface for chain state

RTRACKR is the public tracker / read layer at https://rizal.pw/rtrackr/:
the chain stays local; RTRACKR publishes a scrubbed public view
(registry rows, Я token, Orca pool, holders, wallets). The adapter
reads chain state through RTRACKR — GET `/rtrackr/assets` (live feed),
the derived game-assets feed, the baked snapshot / export — all
READ-ONLY, never the submit/register/ingest POSTs.

**Fallback order** (the feed readers' own order, `rtrackr-feed.js` /
`rtrackr_feed.gd`): live API → derived JSON → cached copy. Every
report names the source that served the data and its timestamp. The
snapshot is baked (2026-11-10) and goes stale; the game feed
(2026-11-18) is newer. Never treat a snapshot value as a live balance.

**Live vs registered.** An asset is LIVE only when `on_chain` is true
and a signature is present (status "live" alone is the JS shortcut).
Standing example: ThundR's wallet-RID row (ЯID-0014-KREH) is
REGISTERED but UNSEALED — `on_chain` false, no block hash — in both
the snapshot and the game feed, while the ThundR cryptobot row
(block 2) IS live. Report it as such, never as minted. Snapshot
entries duplicate rows across views: count RIDs, not rows.

**Queues.** The adapter queues DRY events only, in the feed's shape
(submit then register, register only after the mint block is
confirmed); `queue()` throws on live, and so does the adapter. A live
mint is a minter request (`rzl.rmint.minter-request.v1`) queued for
ThundR or GIZMO only — never a direct submit, never posted by the
adapter (the chain stays read-only from here).

**ЯID validation.** RIDs are validated by the ЯID checksum (sha256 of
`ЯID-<seq4>`, 20 bits, Crockford base32), ported verbatim from the
daemon. `adapter.analyze` (kind `rid`) validates one RID and shows the
expected value on a checksum mismatch. Known-good vectors:
ЯID-0001-3QQS (@chaserizal) and ЯID-0014-KREH (ThundR).

**Honest notes.** GeckoTerminal disagrees with the chain on mint
authority (reports null; on-chain it is set to the Crown wallet — the
snapshot trusts the chain). A typo'd mobile address in the public
numbers is a valid pubkey with no account (the double-h address is the
live holder). Orca API data is stale (last updated 2026-10-20). Feed
-2 uses the mesh hostname `chain.rklowd.invalid:8741`, which resolves
only inside the RKLOWD mesh.

## 12. RGHOSTKEY — the key layer

RGHOSTKEY is the "polykey": ONE interface with the same method names on
every platform — status / methods / unlock / sign / approve / logout +
session start / revoke / cast receive-dismiss / offline nonce / lockout
— in Swift (`RGhostkeyAPI.swift`, WK handler `rghostkey`), Java
(`RGhostkeyApi`, JS interface `RGhostkeyNative`), JS
(`window.RGHOSTKEY`), and GDScript (factor-record builder).

**Parity principle — the adapter's cross-host principle.** Parity
means the same methods, NOT shared secrets. Every hard device keeps
its own pinned key (Secure Enclave tag `info.rizal.rsign.se.p256` /
login keychain `info.rizal.rsign.mac.p256.v2` / AndroidKeyStore alias
`rsign.rghostkey.ec`); nothing is created, exported, copied, or
synced. The adapter follows the same principle across its hosts: the
Python reference implementation and the Swift native adapter expose
the same tpa.v1 method names; no secret is shared between them (the
server token is per-start, mode 0600, never printed).

**Pins** (public `pubkey_sha256`, truncated as the parity record
prints them): neo-rdragon `5752020b…8782`, iphone17e-rdragon
`26431cd4…b0eb`, moto-rdragon `9acf9fbd…d54e`. Missing or unpinned key
→ refused, never enrolled.

**HARD RULE.** The adapter NEVER signs, seals, enrolls, or mints —
like ThundR it routes approval requests (request/queue only). Signing
happens only on the pinned device, by the human, through RGHOSTKEY.
ThundR's column in the parity matrix: status soft, sign = request
only, approve = queue only.

**Diagnostics.** RGHOSTKEY is an in-app interface with no loopback
endpoint the adapter can call (and the MCR exposes no key status), so
`adapter.diagnostics` reports it honestly as not reachable, with the
known interface, backends, pinned slots, and stance — not a faked
live read.

**Known gaps (honest limits).** The Android bridge has 3 pre-existing
JSONException errors blocking assembleDebug (fix documented, not
applied — the add-only rule); the TERAFORMR native rsign dylib is not
built (the game uses the web wallet panel, soft); the native approve
UI is unbuilt on Android (approve has no caller yet).

## 13. ЯWALET — watch-only

ЯWALET Neo unified 0.2.0 (`io.rlab.rwalet.xcode`, build 20261113) is
the Я ecosystem wallet: a web layer (unified FULL/ALL pages) plus a
native macOS app. PRIVATE staged build, unsigned. The web layer is
watch-only by design (holds no key); the native app signs via Touch ID
/ Face ID / SE key (SolanaSwift + TweetNaCl + secp256k1). Core law:
Rizal's explicit command (GO) authorizes sign/mint; mail CAN trigger
a seal — it queues/opens an Approve card (t31u policy, 2026-11-11,
superseding the old "mail never triggers" rule) — and the seal
completes on Rizal's explicit approve command; no biometric step is
required (Face ID / Touch ID remain available on the device, never
required); mail never auto-signs, the panel never signs locally; the
page does not auto-run Sign, Mint, Send, or Swap;
`window.RWALLET_PREVIEW=true`.

**HARD RULE: the wallet is WATCH-ONLY for the adapter.** The adapter
never signs, sends, swaps, mints, or moves anything — it reads roster
/ snapshot / pool state only (`adapter.diagnostics` wallet section,
`adapter.analyze` kind `wallet-snapshot`). Approve flows route to
`rwallet://approve?` carrying Rizal's explicit approve decision; the
adapter queues the request, the wallet + human complete it. No
biometric step is required. Approve never signs.

**Verification.** Snapshots are verified against their SHA256SUMS
manifest pin when one is given, and mismatches are reported, never
silently trusted. The manifest pins point at the -2 variants
(`rtrackr-snapshot-2.json` and `rtrackr-button-2.js` match their
pins); the base snapshot/button files are older revisions and do NOT
match. The DeFi bundle hash IS verified against the manifest.

**Honest notes.** The DeFi bundle (Orca Whirlpools SDK 8.0.1 + Jupiter
v6) is box-simulated on mainnet, but NO Swift compile has happened
yet, so native wallet rows are PARTIAL. Backup/restore, key import,
NFT, and market are MISSING (not requested this phase).

## 14. Muse usage

Muse drives the adapter through the CLI (no server needed) or the
loopback server (for other bots/AIs). See the skill
`~/workspace/custom-skills/thundr-adapter/SKILL.md` for the full
method. Quickstart:

```sh
cd ~/workspace/thundr-adapter
PYTHONPATH=python python3 -m thundr_adapter hello
PYTHONPATH=python python3 -m thundr_adapter chat "help" --no-mcr
PYTHONPATH=python python3 -m thundr_adapter diagnostics --model-dir <dir>
PYTHONPATH=python python3 -m thundr_adapter analyze components
PYTHONPATH=python python3 -m thundr_adapter analyze rid --rid ЯID-0001-3QQS
PYTHONPATH=python python3 -m thundr_adapter serve   # loopback :8742
```

Rules for Muse: never ask the adapter to sign, seal, enroll, mint,
send, swap, or transfer — it will refuse. Route wallet/signing verbs
to Rizal (type them in the R:> shell) or get his explicit GO for the
exact action. Treat every adapter answer's `via` as the truth about
where it came from; never present a registry fallback as a live brain
reply. Repairs and updates are propose-only until Rizal's GO, and GO
is per exact plan, by reference (plan id + nonce).

## 15. Grounding trace

Every interface claim traces to one of these. Grounding files live in
`grounding/` and are never modified by the adapter.

| Claim | Source |
|---|---|
| 124 commands, 7 refuse regexes, 10 GO commands, rules | `grounding/thundr-commands.json` (thundr.core.commands.v1, v1.0.0) |
| Host map, wired states | `grounding/hosts.json` (thundr.core.hosts.v2) |
| Content stamp, idempotent codegen | `grounding/gen-thundr-core.py` |
| Chat dispatch order | `grounding/thundr_chat.py` |
| MCR loopback :8329, safe_path, origin checks | `grounding/controlroom.py` |
| NativeCommands help-before-model, NativeMaintenance diagnostics, LocalBrain.call envelope | `rthundr-bundle` (RIZALEON/RTHUNDR, `feature/native-diagnostics`) |
| Engine (Granite + Qwen), ModelSelect exact identity, liveCmd regex | A2 Swift core (`rthundr-1b2eecd/src/`) |
| Loopback-only http_json, engine picker, models panel, bot-tagged guard, signing guard | Linux Python port (`linux-src/`) |
| Live float layout, engines, quick commands, parser verbs | `grounding/thundr-float-live-2026-11-19.png` (screenshot 2026-11-19) |
| .rzl parts catalog, component table, gaps | `grounding/rzl-index-digest.md` (+ `rzl-index.txt`, 4,286 lines) |
| RbotLoadR 0.0.1 loader, verify-then-mount | `grounding/rbotloadr-0.0.1/` |
| One-writer asset feed, preview-until-live | `grounding/rgeneratr/RGENERATR-ADAPTER-SPEC-20261030.md` + snapshot |
| Chain read-only rule, daemon endpoints, DRY/LIVE, minter gate, RID checksum | `grounding/rghostchain-digest.md` + `rghostchain_submitd.py` |
| Polykey interface, parity principle, pins, vc27/vc31 hardening, gaps | `grounding/rghostkey-digest.md` + sources |
| Watch-only wallet, rshell allowlist, SHA256SUMS pins, DeFi PARTIAL | `grounding/rwalet-digest.md` + sources |
| RTRACKR read surface, fallback order, live-vs-registered, -2 pins | `grounding/rtrackr-digest.md` + sources |
| Ownership, sync, scrub/GO/RZL/truth law | `~/workspace/github-pages/RENJIN-CRYPTOBOT-AI/BACKROOM.md`, `BOTS.md` |

## 16. Honest limits (unverified)

- **Swift uncompiled.** `swift/ThundRAdapter.swift` is
  written-but-uncompiled (no Xcode on this VM). Source-contract tests
  assert on its text; it has not been compiled or run.
- **No live ThundR tested against.** All live-service behavior
  (MCR :8329, Granite :4983, daemon :8741) is tested against fake
  local servers or reported unreachable. The adapter has not run
  against the real Mac services.
- **Port 8742 assumed free.** No known ThundR service uses it; not
  verified on the Mac.
- **Engine preference is adapter-local.** `use qwen` / `use granite`
  in the adapter record the adapter's preference only; the live float
  keeps its own engine choice.
- **RGHOSTKEY not reachable.** The adapter cannot call the in-app
  key interface; diagnostics reports it as such.
- **Component check is a catalog report**, not a live filesystem
  scan (scan date 2026-11-04 + the 2026-11-19 RbotLoadR draft).
- **RTRACKR snapshot is baked** (2026-11-10) and goes stale; the
  game feed (2026-11-18) is newer. Neither is a live balance.
- **The adapter never sees the live float window.** The float layout
  is a static description from the 2026-11-19 screenshot.
- **AUTOMANUAL doctrine is spec-only in v0.1.1;** no live manual copy
  is bundled — the adapter cites section headings from the digest, not
  from a mounted manual.
- **Face ID / biometric is optional, never required (2026-11-19
  order);** Rizal's explicit command (GO) is sufficient authorization
  for sign/mint/seal/approve. The adapter itself never signs, seals,
  enrolls, or mints.
