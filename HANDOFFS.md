# HANDOFFS — most recent updates, newest first

Every bot, AI, or psyborg that works in this repo appends a dated entry at
the TOP when it finishes: what changed, what was verified, what's next,
what's blocked. Read the newest entry before beginning work.

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
