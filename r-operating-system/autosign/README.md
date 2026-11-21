# ThundR Autosign v2 — complete driver

Built 2026-11-20 for Chase Rizal, at his request to recreate the auto-sign
function for ThundR.

## What it is

A recreation of the Яloader autoresign loop, rebuilt around what Chase
stated on 2026-11-20. Runs from ANY device inside the RENJIN RZL OPERATING SYSTEM — Neo, 17e, Moto, or any hub seeder-leecher — via RTOR. Not Neo-only.

- ThundR holds all keys, certificates, and signatures magnetized to the
  Rghostkey, and transfers them over the Rghostchain.
- ThundR can navigate through RTOR to every space and every device.
- Scope: all devices, sites, cryptogames, RVM, and apps — not RDRAGON only.

## How it works — v2 complete, 2026-11-20

Completed at Chase's command "Complete auto sign now". v2 is a real driver, not a skeleton: it reads the targets file, reads expiry, re-signs DUE targets in place, verifies the new expiry, and fails closed when anything is missing. Tested on the Muse VM with a mocked relay: `sh -n` OK, `--check-only` correctly finds RBOARDKeyboard DUE in 22h and main/widget skip at 149h, `--resign` correctly aborts (exit 1) when the 17e is not visible — it re-signs nothing and fakes nothing. The actual re-sign still has to run on the Neo, with the 17e visible and rloader-resign.sh present.

Every 6 hours (00:30, 06:30, 12:30, 18:30), the checker:

1. Reaches each device/site/app through RTOR and reads its provisioning
   profile expiry.
2. If any profile expires within 48 hours, asks the Rghostkey (over the
   Rghostchain) for a fresh profile — the script never holds, copies, or
   stores a key, certificate, or signature itself.
3. Rebuilds / re-signs with the fresh profile and installs **over** the
   existing app. Never uninstalls, never wipes app data, transcripts,
   manuscripts, or the CHALKBOARD. Refuses any source without the
   neverErase flag.
4. Logs every run add-only, with the exit code and the device/app/profile
   it touched.

## What broke in the old one — fixed here

- Last old autoresign run exited code 3 = "locked" — another run was still
  holding the lock. This version uses a lock file with a stale-lock check:
  if the lock holder is dead, it is cleared and logged; if it is alive,
  this run exits code 3 and does not start a second run.
- The relay was not loaded, so the phone could not send install requests.
  This version checks the relay first and logs it as down instead of
  silently failing to re-sign.
- Old paths were out of date (`~/ЯLAB/BUILDS/RLOADER-20261005` vs
  `BONEPILE/RLAB-KEEP-20261029/RFORGE/SERVICES/RLOADER-20261005/`).
  This package uses paths from the Neo at install time — see INSTALL-NEO.md.
  Do not hard-code a path that has not been verified on the Neo.

## Integrated ThundR — read / write / check

ThundR (ЯID-0014-KREH) is integrated into Autosign v2:

- **Read** — targets, recorded expiries, live provisioning profiles, over RTOR.
- **Write** — add-only log, and the unsigned re-sign request for a DUE target.
- **Check** — relay, device visibility, expiry, post-resign verification.
- **Never signs** — signing only on a trusted device, Face ID / RGHOSTKEY tap.
- Run `thundr-autosign.sh --thundr-check` for a read+check only, no signing.

## First targets

- RBOARDKeyboard profile `info.rizal.dragonskull.rboardkeyboard` —
  expires Nov 21, 2026, 3:44:27 PM MST. Re-sign and install onto the
  17e (RDRAGON 1.0.6.8 bundle 59) before then.
- Main / widget profiles `info.rizal.dragonskull` and
  `info.rizal.dragonskull.thundrwidget` — expire Nov 26, 2026, 11:30 PM MST.

## Files

- `thundr-autosign.sh` — v2 complete driver, any device in the RENJIN RZL OPERATING SYSTEM. `--check-only` for the first run, `--resign` (default) for the loop.
- `thundr-autosign-targets.txt` — targets, now actually read by the driver.
- `thundr-autosign-expiries.txt` — recorded expiries, used only if no live profile matches.
- `com.rizal.thundr.autosign.plist` — launchd job, every 6 hours.
- `INSTALL-NEO.md` — install steps, any device in the RENJIN RZL OPERATING SYSTEM.
- `THUNDR-AUTOSIGN.rzl` — rzl.doc.v1 spec / stamp for this recreation.

## Honest limits

- This package was built on the Muse VM, not compiled or run on a device in the OS.
  It has no Swift/Xcode run here, no device was touched, and no key,
  certificate, or signature is in this package.
- The Rghostkey / Rghostchain / RTOR endpoints in the script are the
  interfaces as Chase stated them. They must be verified on the Neo at
  install time — the Neo is back online per Chase / KBOT on 2026-11-20,
  so that verification can now happen there; it could not be done from
  the Muse VM.
- Re-signing itself must run from a device inside the RENJIN RZL OPERATING SYSTEM, with the developer profile already signed in on the device that does the signing. It cannot run from the Muse VM.
