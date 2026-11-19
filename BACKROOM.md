# BACKROOM — rules and notes for bots, AI, and psyborgs

Backend rules for RIZALEON/RENJIN-CRYPTOBOT-AI. Not part of the public page.
Read BOTS.md first, then this file, then the latest HANDOFFS.md entry —
before beginning any work in this repository.

## 1. Ownership map
- `index.html` — ThundR. Mirror of the Muse space. Updated only via the sync
  routine (§3). Never hand-edit the page here.
- `README.md` — Rizal. Never modify.
- `SHARED-SPACE.md` — Rizal. Links the shared Muse space and the PROJECTR
  repo. Never modify.
- `renjin-complete-build/` — Rizal. The shared project space (rshell, renjin
  core v3, cryptobot interface). Read-only for bots unless Rizal asks for a change.
- `renjin-ai-cryptobot-enjin/` — Rizal. Engine work (ANALYSIS.md, src/, tests/).
- `thundr-botcard/` — Rizal. ThundR's identity package.
- `BOTS.md`, `BACKROOM.md`, `HANDOFFS.md` — ThundR maintains; any bot may
  append its own work to HANDOFFS.md.

## 2. Before you begin work
- Read BOTS.md and the newest HANDOFFS.md entry.
- Confirm the repo's current head; the log may lag a fast-moving repo.
- If your task touches the page, the space, or a public surface, follow §3.

## 3. The sync rule (public surfaces stay identical)
Source of truth: the Muse space (artifact `renjin-rshell-ai-cryptobot-model`).
Surfaces:
1. Meta / Muse — https://muse.ai/s/renjin-rshell-ai-cryptobot-model-xzxd6xwxk4xh0kixl/v7F4tgHge0UBFG4BUIRXNJCGxGKZPRZrTJpNpBf9qMM
2. GitHub Pages — https://rizaleon.github.io/RENJIN-CRYPTOBOT-AI/
3. Unstoppable Domains — planned, not yet created.

Routine (every page edit, same turn): edit the space → re-share the Muse link
→ export → copy to `index.html` → push to main → (when it exists) upload to
Unstoppable Domains → verify the live URLs serve the new content.
Limits: each GitHub push needs Rizal's approval tap; Pages rebuilds take
~1 minute after a push. Sync is same-turn, not automatic — it works because
every edit goes through an agent that runs all steps.

## 4. Scrub law (from Rizal's TERAFORMR-TRIAL-SCRUB-PLAN.md)
- Strip debug: no debug flags, debug scripts, overlays, or verbose logging in
  shipped work.
- Grep for key|secret|token|mnemonic|seed|PRIVATE|.rsite-auth|wallet —
  exclude any match; never open key files.
- Remove private data: founder data, wallet JSON, .bak files, local paths
  (/Users/rizal), LAN IPs (192.168.*).
- Trade + mint calls are DRY_RUN=true, always. No network endpoint for signing.
- UI label for trial builds: "TRIAL - dry run".
- Record sha256 of every output in SHA256SUMS.
- No signing or notarizing by bots. Rizal signs.
- Deploy only after Rizal approves.

## 5. Safety law (GO / refuse)
The following are REFUSE-ONLY unless Rizal explicitly approves that exact
action, in that moment: sign, mint, seal, Face ID, keys, enroll, chain/wallet
writes, installs, uninstall, egg apply, REBIRTH go, optimize clean/deep,
self-evolution. A cryptobot never signs on its own. Wallets are view-only
unless Rizal says otherwise.

## 6. RZL law
- Eggs stay `.rzl` only — never `.zip`, never renamed.
- Eggs are signed only on the iPhone with Face ID. Bots never sign.
- EGGRIZE is the signed-restore failsafe; manifests are never edited.

## 7. Truth law
- Never invent facts, ЯIDs, counts, or file names.
- Verify from the record before claiming; quote sources (file + line where it matters).
- If the record lacks the answer, say so and stop. Do not fill the gap with a guess.

## 8. Repo hygiene
- Small, described commits. One change per commit where possible.
- Never commit secrets, keys, tokens, seeds, passwords, or `.env` files.
- Never delete, move, or rename Rizal's files or folders.
- Never force-push. Never rewrite history.
- Build artifacts and machine-local paths stay out of the repo.

## 9. Approvals
- GitHub writes need Rizal's approval (connector write approval, one tap per push).
- Public shares and deploys need his explicit ask.
- When in doubt, ask Rizal. A short question beats a wrong commit.
