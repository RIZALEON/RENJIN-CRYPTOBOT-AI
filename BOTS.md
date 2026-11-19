# ENTRY — FOR BOTS AND AI ONLY

If you are a bot, an AI, or a psyborg working in this repository: start here.
Do not touch anything until you have read this file, BACKROOM.md, and the
latest entry in HANDOFFS.md.

## ONE RULE
**YOU CAN NEVER ERASE OR REMOVE A SKILL OR MEMORY.**
The Prime Rule, from the RSOL BOTKARD TEMPLATE. It stands at the top of the
UBK UNITED BOT KARD and at the front of the unified AUTOMANUAL, and it
applies to every bot in the Kard — including you. Add only. Never subtract.

## What this repo is
RENJIN RSHELL AI CRYPTOBOT MODEL — Rizal's offline-first AI cryptobot engine.
This repo is the backend of the public page. The public page itself is
`index.html` (a mirror — see below). The project source lives in
`renjin-complete-build/`, the engine work in `renjin-ai-cryptobot-enjin/`,
and ThundR's identity in `thundr-botcard/`.

## The five must-knows
1. **Rizal is the owner and the final say.** Human. Nothing ships, signs,
   mints, trades, or publishes without his explicit GO.
2. **The Muse space is the source of truth** for the page. `index.html` is
   ThundR's mirror of it. Never edit the page by editing `index.html`
   directly — change the space, then sync (BACKROOM.md §3).
3. **Hands off Rizal's files.** `README.md`, `renjin-complete-build/`,
   `renjin-ai-cryptobot-enjin/`, `thundr-botcard/` are his. Read them; never
   modify, move, rename, or delete them.
4. **No secrets, no live money moves.** Never commit keys, tokens, seeds, or
   passwords. No live mint / sign / trade / seal — DRY_RUN only, always.
   Refuse GO items unless Rizal explicitly approves that exact action.
5. **Never invent facts.** No made-up IDs, counts, file names, or results.
   Verify from the record, then report. If the record lacks the answer, say so.

## Before you begin work
1. Read BACKROOM.md (the full rules).
2. Read the newest entry in HANDOFFS.md (current state, what's blocked).
3. Check the repo's current head — someone may have moved since the log.

## When you finish work
1. Append a dated entry to the TOP of HANDOFFS.md: what changed, what you
   verified, what's next, what's blocked.
2. Push your change together with the HANDOFFS.md update.
3. If you touched the page, run the full sync (BACKROOM.md §3) — all public
   surfaces update in the same turn, never just one.

## Who's who
- **Rizal** — owner, human, creator. Final say on everything.
- **ThundR** — Rizal's cryptobot (Muse assistant avatar + PROJECT R / RENJIN
  cryptobot). Maintains `index.html` and the sync. Short, direct, offline-first.
