# DESIGNATION REGISTRY — every element designated by its form

Rule: each new element is designated by its FORM and numbered in the order
it comes in. Numbering is per form, in arrival order. The registry is the
arrival order — a new element appends at the end of its form's list.
Authorized-by-owner-command. NOT a cryptographic signature, no ghostkey accessed.

Forms: HARDDEVICE · APP · CRYPTOBOT · COMPONENT · WEBSITE · TRACKER · SERVICE · MODEL

## HARDDEVICE — physical devices

1. HARDDEVICE-01 — Neo (MacBook) — the build machine, RGHOSTKEY home
2. HARDDEVICE-02 — 17e (iPhone 17e) — RDRAGON bundle 59, RCODE build 15
3. HARDDEVICE-03 — Moto (Android) — wireless debug 192.168.0.224:42411

## APP — applications on a device

1. APP-01 — Dragon Skull (RDRAGON) — Moto — RID Я-DEVICE-V5Q0QPT07J-H1 (seq 17)
2. APP-02 — RCODE — Moto — RID Я-DEVICE-0TDKGMFQCW-5Z (seq 18)
3. APP-03 — RBOARD — Moto — RID Я-DEVICE-39PBT3H2TP-JY (seq 19)
4. APP-04 — RDRAGON — 17e — build 59 (RID pending, assign when it comes online)
5. APP-05 — RCODE — 17e — build 15 (RID pending)
6. APP-06 — ThundR iOS — planned (RID pending)

## CRYPTOBOT — bots and cryptobots

1. CRYPTOBOT-01 — ThundR — RID ЯID-0014-KREH — block 2
2. CRYPTOBOT-02 — TerraformR CRYPTOGAME — RID ЯID-0015-0HJP — block 3
3. CRYPTOBOT-03 — KROG — RID ЯID-BOT-0001 (@krog)
4. CRYPTOBOT-04 — Gizmo — RID Я-DEVICE-1PYZ7VG0Z1-ZE (seq 16) — the Observer

## COMPONENT — .rzl components and builds

1. COMPONENT-01 — RENJIN-COMPONENT.rzl — SHA 67a8c186…f5aa — magnetized RTOR GHOSTCHAIN transponder
2. COMPONENT-02 — RENJIN-KUBO.rzl — SHA 04b7b1e2…b3a97 — Kubo/IPFS-ready
3. COMPONENT-03 — R-OPERATING-SYSTEM-PURE-LINUX-RZL.rzl — SHA a5a7c714…0e68f0
4. COMPONENT-04 — RENJIN-ENJIN-CRYPTOBOT-MODEL-SHELL-FUSED.rzl — SHA c7e466c6…ae88ad
5. COMPONENT-05 — R:> Shell — live, chain + torrent + activity
6. COMPONENT-06 — Renjin Torrent (RTOR client) — live, opens into Renjin
7. COMPONENT-07 — RENJIN Core v3 — corpus-v2, retrieval 8/10 on corpus-v1
8. COMPONENT-08 — ThundR Autosign v2 — re-sign DUE targets, propose-first
9. COMPONENT-09 — ThundR Plugin Adapter v0.1.0 — protocol rzl.thundr.plugin.v1

## WEBSITE — public sites and pages

1. WEBSITE-01 — rizal.pw — /renjin live, RTRACKR live
2. WEBSITE-02 — rizal.info — /renjin live
3. WEBSITE-03 — R Operating System page — public Muse link
4. WEBSITE-04 — PROJECT R page — public Muse link

## TRACKER — trackers and feeds

1. TRACKER-01 — RTRACKR — https://rizal.pw/rtrackr — GHOSTCHAIN height 5, 6 blocks
2. TRACKER-02 — RTOR — torrent mesh, 7 hub seeder-leechers, 8 transponders

## SERVICE — services running in the OS

1. SERVICE-01 — RMAIL v2.1 — hybrid crypto mail + DM, relay_8797 (RID pending)
2. SERVICE-02 — RWALLET — PRIVATE staged build, keys behind biometrics (RID pending)
3. SERVICE-03 — RSYNC — live, feed 20261118-5, 28 entries
4. SERVICE-04 — RPIPE — 110 legacy files stuck in drop — do not raw-move

## OWNER

- OWNER-01 — Rizal · CHIEF (Decider) — RID ЯID-0001-3QQS — block 1

## How a new element is added

1. It comes in (comes online, is built, is published).
2. Its form is named: HARDDEVICE, APP, CRYPTOBOT, COMPONENT, WEBSITE,
   TRACKER, or SERVICE.
3. It takes the next number in that form's list.
4. An RID is minted for it (rid.v1, parent ЯID-0001-3QQS, next seq 20)
   and recorded in RID-REGISTRY.md.
5. The designation and the RID are written here, in arrival order.

## ENTERED THE GHOSTCHAIN RTOR STREAM — exact date and time

Only verified times are listed. Anything else is "entry time not recorded" —
no time is guessed.

- Block 0 GENESIS: Oct 29, 2026 9:55:25 AM MT
- Block 1 GAME-MINTED GENESIS (ЯID-0001-3QQS): Oct 30, 2026 11:16:37 PM MT
- Block 2 ThundR (ЯID-0014-KREH): Oct 31, 2026 11:24:41 PM MT
- Block 3 TERAFORMR (ЯID-0015-0HJP): Nov 1, 2026 6:39:30 PM MT
- Block 4 RGHOSTKEY BIND (ЯID-0001-3QQS): Nov 10, 2026 10:24:00 PM MT
- Block 5 krog-test-mint-001 (ЯID-3003-1RCQ): Nov 19, 2026 11:43:41 PM MT
- RTRACKR live snapshot (Neo RMINT hybrid live export, GO t203u): Nov 20, 2026 2:43:28 PM MT
- Install package live on rizal.pw/renjin and rizal.info/renjin: Nov 20, 2026 ~19:40 MST
- RTOR activation pushed (commit 1a719fee): Nov 20, 2026 19:50 MST
- Moto files installed, every copy hash-matched, wireless debug 192.168.0.224:42411: Nov 20, 2026 ~19:57 MST
- Moto RKLOWD unsuspended: Nov 20, 2026 19:58 MST
- RIDs minted for Dragon Skull, RCODE, RBOARD: Nov 20, 2026 20:01 MST
- GHOSTCHAIN pulled live from RTRACKR: Nov 20, 2026 20:01 MST

## DETECTION RULE — from every device and app independently

Detection is done from every device and every app independently. No central
scan, no single device that detects for the others.

- Each HARDDEVICE detects and reports itself and what is on it, on its own.
- Each APP detects and reports itself, on its own.
- Each report goes into the GHOSTCHAIN RTOR stream (to RTRACKR) from that
  device / that app directly.
- When a device or app comes online, it reports: its designation, its RID,
  its apps (for a device) or its components (for an app), and the exact date
  and time it entered the stream.
- ThundR on the VM does not detect for a device. ThundR reads the stream and
  records what each device and app reported for itself.
