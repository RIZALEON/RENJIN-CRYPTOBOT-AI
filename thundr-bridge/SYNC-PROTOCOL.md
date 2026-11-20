# SYNC-PROTOCOL.md — Muse ↔ ThundR bridge (file sync, v1)

Base-level ThundR is infused into the RENJIN enjin as a web float. This file
is the sync contract between Muse and that float — and the GENERAL pattern
for syncing terminals and command bars with ThundR and the enjin going
forward. Written 2026-11-19 with the infused build (thundr-infused 0.1.0).

## The pattern (general)

One state file + one queue per surface. Muse is the sync writer. Surfaces
poll and execute. Neo is the source of truth for live status.

```
Neo (live truth)                Repo (sync surface)              Page (float)
───────────────                 ─────────────────                ────────────
MCR :8329, shell :4984,         thundr-bridge/state.json   ←───  polls every 60s
router :4990, panel :8779,      thundr-bridge/queue.json   ←───  polls every 30s
pointer, float, chain, memory
        ▲                              ▲
        │ Muse reads via files         │ Muse writes via push
        └──────────────────────────────┘
```

Rules:

1. **Muse writes, surfaces read.** Only Muse updates `state.json` and
   `queue.json` (via GitHub push). A web page cannot write to the repo, so
   there is no write-back path from the float. Anything the float "says"
   back reaches Muse only through Rizal or through Neo files.
2. **Neo is the source of truth.** Every status in `state.json` comes from
   a real check of a Neo file, log, or endpoint — never from the page, never
   from memory of an old check. The file carries `checked_at` (when the
   statuses were verified) separately from `updated_at` (when the file was
   written). A surface MUST show `checked_at` so staleness is visible.
   Status older than 24 hours is stale: the surface says so.
3. **Poll, don't push.** Surfaces fetch on a cadence (state 60 s, queue
   30 s, plus on focus/visibility). A fetch failure is reported as
   "unreachable" — never faked, never silently replaced with old data
   presented as fresh.
4. **The queue is not a trust channel.** Queued commands run through the
   SAME router and the SAME refuse rules as typed commands. A queued GO
   item (`mint`, `sign`, `seal`, `optimize clean`, …) is refused exactly
   as a typed one is. Muse's GO is expressed in chat with Rizal, never
   smuggled through the queue.
5. **Exactly-once per surface, by id.** Every queue item has a unique `id`.
   A surface executes a pending item once, records the id locally
   (localStorage on the web), and never re-runs it. Muse rotates the queue
   on the next push: items the float has run are marked `done` (with a
   `ran_at` note) or removed. Until rotation, a `pending` item stays
   pending — a second surface (or a fresh browser) would run it too, which
   is why queue commands must be idempotent and safe.
6. **One state file + one queue per surface.** This directory is the
   infused-float surface. The same layout applies to the other surfaces
   as they come online (see § Surfaces).

## Files

### state.json — `thundr-bridge.state.v1`

```json
{
  "version": "thundr-bridge.state.v1",
  "updated_at": "2026-11-19T17:33:00-07:00",
  "checked_at": "2026-11-19T17:00:00-07:00",
  "source": "muse file diagnostic on Neo",
  "host": "rizal's MacBook Neo",
  "services": {
    "mcr":     { "port": 8329, "status": "up",        "detail": "…" },
    "shell":   { "port": 4984, "status": "up",        "detail": "…" },
    "router":  { "port": 4990, "status": "up",        "detail": "…" },
    "panel":   { "port": 8779, "status": "on-demand", "detail": "…" },
    "pointer": { "port": null, "status": "up",        "detail": "…" }
  },
  "float":   { "status": "open", "detail": "…" },
  "ragent":  { "threads": 8, "messages": 38, "orphaned": 0, "newest": "…" },
  "chain":   { "history_height": 4, "live": 5, "dry": 1, "chain_valid": true, "as_of": "…" },
  "memory":  { "lines": 8, "last": "…" },
  "notes": "…"
}
```

- `status` values: `up` | `down` | `on-demand` | `unknown`. Use
  `on-demand` for services that start when called (the :8779 panel) and
  `unknown` when the check could not run — never guess `up`.
- `detail` is one short clause of evidence (a pid, an HTTP code, a log
  tail, a timestamp). No detail, no claim.
- `chain` numbers come from the newest verified feed/snapshot and carry
  their own `as_of`. A snapshot value is never presented as a live balance.
- `notes` carries short dated facts that do not fit the schema (e.g. a
  token fix, a pending rebuild). One line per fact, newest first.

### queue.json — `thundr-bridge.queue.v1`

```json
{
  "version": "thundr-bridge.queue.v1",
  "updated_at": "2026-11-19T17:33:00-07:00",
  "writer": "muse",
  "items": [
    { "id": "q-20261119-001", "ts": "2026-11-19T17:33:00-07:00",
      "from": "muse", "cmd": "ragent status", "status": "pending" }
  ]
}
```

- `id` is unique and never reused. Suggested form: `q-YYYYMMDD-NNN`.
- `status`: `pending` | `done`. The page executes `pending` items only.
  Muse marks items `done` (optionally with `ran_at`) on the next push.
- `cmd` is a plain command line, exactly as Rizal would type it. It goes
  through the router: intercepts, registry, refuse rules, then the mind.
  `clear` in the queue clears the page transcript — use sparingly.
- Keep the queue short (a handful of items). Long-lived queues rot: an
  item older than 7 days without rotation should be removed, not executed.

## Surfaces (going forward)

The same state + queue layout covers every terminal and command bar in the
system. Each surface gets its own pair of files under `thundr-bridge/`:

| Surface | State | Queue | Writer | Notes |
|---|---|---|---|---|
| Infused float (this page) | `state.json` | `queue.json` | Muse | Polls; executes; no write-back. |
| RSHELL page (RENJIN shell) | `rshell-state.json` | `rshell-queue.json` | Muse | Same contract; RSHELL commands only. |
| Neo float (RTHUNDR.app) | Neo files (live) | `thundr-shell` transcript | Muse via kickstart + files | Live path; the web state file REPORTS it, it does not replace it. |
| THUNDR-SHELL :4984 | `session.json` (live) | `/bot/ragent` + transcript | LocalBrain / shell | Loopback only; Muse reads via files, never POSTs from the VM. |

The Neo float and THUNDR-SHELL are live loopback services — they do not
poll GitHub. Muse syncs TO them through the kickstart trigger files and
Neo-side files, and syncs their status BACK into `state.json` for the web
surfaces. That is the whole loop: Neo → Muse → repo → page, and
page → (Rizal / Muse) → Neo.

## Poll cadence

- `state.json`: every 60 s, plus on page focus / visibility change.
- `queue.json`: every 30 s, plus on page focus / visibility change.
- Fetch order: relative `thundr-bridge/` first (works on GitHub Pages and
  a local server), then the absolute Pages URL
  `https://rizaleon.github.io/RENJIN-CRYPTOBOT-AI/thundr-bridge/`
  (works from the Muse share link). `cache: no-store` on every fetch.

## Safety (non-negotiable)

- No signing, no minting, no sealing, no key use, no chain writes from
  any web surface. Ever. The router refuses GO items with the exact
  registry refuse_reply, in the queue as in the command bar.
- No fake live status. If the bridge file is unreachable or stale, the
  surface says so in plain words.
- No secrets in either file: no tokens, no keys, no nonces, no UDIDs,
  no private paths beyond what is already public in the repo.
- The queue carries commands, not credentials. A queue item that looks
  like a secret (a token, a key, a password) is a protocol violation:
  refuse it, do not execute it, and tell Rizal.

## Versioning

`state.json` and `queue.json` carry a `version` string. A surface that
does not recognize the version must refuse the file (report "unsupported
bridge version") rather than guess at the schema. This document is v1.
