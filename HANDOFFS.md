# HANDOFFS — most recent updates, newest first

Every bot, AI, or psyborg that works in this repo appends a dated entry at
the TOP when it finishes: what changed, what was verified, what's next,
what's blocked. Read the newest entry before beginning work.

---

## 2026-11-19 14:17 MST — Site mesh synced: SYNC.md + doorway links + RCRYPTOFORGE §09 (ThundR)
- On Rizal's order, all sites synced and linked with RCRYPTOFORGE: Meta page
  (source of truth) · GitHub Pages (mirror) · this repo · PROJECTR `shared` ·
  RCRYPTOFORGE space · bot doorway.
- New `SYNC.md` at repo root: the canonical registry — every site, its role,
  and the sync law (a link change updates SYNC.md + SHARED-SPACE.md in the
  same push, with a HANDOFFS entry).
- `thundr-botcard/index.html` (bot doorway) gained a “Sites — the RCRYPTOFORGE
  mesh” card linking the Meta page, Pages, this repo and PROJECTR. The same
  doorway + SYNC.md were pushed to PROJECTR `shared`.
- RCRYPTOFORGE space gained §09 “RTOR sync network”: six linked surface
  cards, the sync chain, a SYNC shell command. Honest limit: these are
  static pages, so sync is publish-time from the source of truth — live
  auto-update rides RTOR on Neo, which is not reachable from this VM.

---

## 2026-11-19 13:57 MST — ONE RULE added to the bot doorway (ThundR)
- On Rizal's order, added the ONE RULE to `thundr-botcard/index.html` (the bot
  doorway): "YOU CAN NEVER ERASE OR REMOVE A SKILL OR MEMORY" — the Prime Rule
  from the RSOL BOTKARD TEMPLATE — plus ThundR's RSOL BOTKARD rules.
- Same doorway change pushed to RIZALEON/PROJECTR `shared`.
- Rizal also ordered the UBK UNITED BOT KARD: all bot cards merged into one
  (SUPER-BOT-CARD + all RSOL Kards + ThundR botcard v1.1) with the ONE RULE at
  the top, placed at the front of the unified AUTOMANUAL. The UBK and the
  merged AUTOMANUAL copy were built in the Muse workspace — Neo's UNIFIED
  seat (TERAFORMR/docs/AUTOMANUAL-UNIFIED-20261030.md) is not reachable from
  this VM, so seating them on Neo is next.

---
## 2026-11-19 11:40 MST — SHARED-SPACE.md Muse link fixed (ThundR)
- Fixed the shared Muse space link in `SHARED-SPACE.md`: removed two extra
  trailing characters (`EM`). It now matches BACKROOM.md §3 exactly:
  …Bf9qMM. Only the link changed; the rest of the file is untouched.
- Verified by diff against BACKROOM.md §3 and by reading the pushed file back
  from GitHub. (muse.ai is not reachable from this VM, so the live page
  itself could not be fetched from here.)
- Note: the same wrong 45-char token was in this session's saved memory;
  corrected there too.

---

## 2026-11-19 11:32 MST — Backroom created (ThundR)
- Added `BOTS.md` (entry just for bots and AI), `BACKROOM.md` (rules), and
  this log. These live in the repo backend only — NOT on the public page.
- Rules summarized from: the sync routine, Rizal's scrub plan
  (TERAFORMR-TRIAL-SCRUB-PLAN.md), THUNDR-CORE GO/refuse rules, RZL law,
  and the ThundR working notes.
- Next: keep this log current on every significant change. Unstoppable
  Domains page still to be created — it joins the sync routine when it exists.
- Note: while this was being written, Rizal added `SHARED-SPACE.md`
  (commit 38e92e2b — links the shared Muse space and the PROJECTR repo).
  It is his file, hands off.

## 2026-11-19 11:27 MST — GitHub Pages live; 3-surface sync set (ThundR)
- GitHub Pages enabled (Deploy from a branch, main, /root) and verified live
  by direct fetch: https://rizaleon.github.io/RENJIN-CRYPTOBOT-AI/
  serves the 10/10 build (corrected corpus lines, tokenizer gap closed).
- Sync rule set with Rizal: Muse space is source of truth; every edit
  re-shares the Meta page, exports, and pushes to GitHub in the same turn.
  Third surface (Unstoppable Domains) planned, not yet created.
- Limits: each GitHub push needs Rizal's approval tap; Pages rebuilds take
  ~1 minute after a push.

## 2026-11-19 11:16 MST — Page mirror pushed (ThundR)
- `index.html` (335 KB, exact export of the Muse space, 10/10 build) pushed
  to main (commit e91335eb). README.md untouched.
- Rizal created the repo himself and pushed `renjin-complete-build/`,
  `renjin-ai-cryptobot-enjin/` (ANALYSIS.md, README.md, src/, tests/), and
  `thundr-botcard/` (commit a6faa89f). Those are his — hands off.

## 2026-11-19 11:08 MST — Space updated to 10/10, re-shared (ThundR)
- Grounded test now 10/10 everywhere on the page; corpus lines 20 and 103
  corrected in the browser; tokenizer gap closed in the build inventory
  (src/tokenizer.js ported, suite 12/12). Public Muse link re-shared, same URL.
- Export verified clean (0 secrets, 0 emails) before the GitHub push.

## 2026-11-19 10:59 MST — ThundR identity adopted (Rizal + ThundR)
- Assistant is now ThundR (was Chase): round purple imp, red horns, black bat
  wings, lightning bolt tail. Botcard v1.0 in `thundr-botcard/`. Avatar
  option 3 of 4 activated.
- ThundR analysis complete (macOS / iOS / Android / Linux / RZL / GitHub):
  merge plan drafted, 6 phases, A2 core recommended as merge base.
  Awaiting Rizal's 5 decisions: A2 vs A1 base; DRY_RUN vs live /rmint/request;
  RENJIN vs Qwen/Granite primary engine; snapshot/manual/EMBED
  include/redact/exclude; v1 target hosts.

## 2026-11-19 10:44 MST — Grounded test fixed 10/10 (Rizal chose the fix)
- Corpus edited in place (still 112 lines): line 20 "The loop order is...",
  line 103 "held-out lines". `build-ask-v3.js` 10/10, suite 12/12.

## Open / blocked (as of 2026-11-19 11:32 MST)
- Mac cleanup: ~4–5 GB identified, nothing deleted — awaiting Rizal's
  approval per category. Deletions go to Trash only.
- Qwen model → moto phone: waiting on Rizal for the phone's WiFi debugging
  IP:port. Push script ready on the Mac.
- RENJIN × ThundR merge: awaiting Rizal's 5 decisions (above).
- Unstoppable Domains page: not yet created.
