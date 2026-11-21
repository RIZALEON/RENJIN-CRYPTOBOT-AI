# Moto Wireless Debug Install

Install the same components from RENJIN-INSTALL-PACKAGE.zip into each app on the Moto, over wireless debug (adb over Wi-Fi).

> **Where this runs:** The install runs on the machine the Moto is wirelessly paired to. ThundR on the VM cannot reach the Moto directly. Run every command below on that paired machine, with the Moto on the same network and Wireless debugging turned on.

> **Install rule:** Install **over** each existing app. Never delete, uninstall, or clear data first. An over-install keeps the app's data, identity, and chain state.

## What you are installing

Source package: `RENJIN-INSTALL-PACKAGE.zip` — the same package now live under rizal.pw/renjin and rizal.info/renjin.

Components in the package:

- RENJIN-COMPONENT.rzl — RENJIN component with integrated magnetized RTOR GHOSTCHAIN transponder and RTOR file
- RENJIN-KUBO.rzl — Kubo / IPFS-ready file for RTOR back-and-forth testing
- R-OPERATING-SYSTEM-PURE-LINUX-RZL.rzl — R Operating System, pure Linux RZL
- Fused .rzl — RENJIN-ENJIN-CRYPTOBOT-MODEL-SHELL-FUSED.rzl, shell + Core v3 fused build
- R:> Shell — RENJIN interface, boots Core v3
- Renjin Torrent — RTOR client
- RTOR-INSTALL.md — RTOR client install and activation instructions

## Before you start

- Moto charged, unlocked, and on the same Wi-Fi as the paired machine.
- Wireless debugging on: Settings > Developer options > Wireless debugging.
- RENJIN-INSTALL-PACKAGE.zip downloaded on the paired machine and unzipped.
- `adb` available on the paired machine (`adb version` should answer).
- RGHOSTKEY available on the trusted device for the re-seed tap in Step 5. The seed was removed from these files — there is nothing to re-seed from the package itself.

## Step 1 — Connect over wireless debug

On the Moto, open Wireless debugging and read the IP address and port shown there. On the paired machine:

```bash
adb connect <moto-wireless-debug-address>:<port>
adb devices
```

If this is the first connection from this machine, the Moto shows a pairing / allow prompt — approve it on the Moto, using the pairing code from the Wireless debugging screen if asked.

Check `adb devices` before going further:

- The Moto appears in the list.
- Its state is `device`, not `unauthorized` or `offline`.

If the state is `unauthorized`, unlock the Moto and approve the prompt, then run `adb devices` again. If it is `offline`, turn Wireless debugging off and on again on the Moto and repeat `adb connect`.

Do not install anything until `adb devices` shows the Moto as `device`.

## Step 2 — Verify every .rzl before installing

Verify each file's SHA256 on the paired machine first. Do not install a file whose hash does not match.

| File | SHA256 |
| --- | --- |
| RENJIN-COMPONENT.rzl | `67a8c186f45de7359db1ff2c4385dceaeeda9d4d4ace5e79a1024ddb3184f5aa` |
| RENJIN-KUBO.rzl | `04b7b1e27d2198bce73936f0e96c09ce90e96fef0d06505f03c232bce98b3a97` |
| R-OPERATING-SYSTEM-PURE-LINUX-RZL.rzl | `a5a7c7145f7ad1fea207de5b9c1d35fc2bed6cb2f3b7f3fd7c68057d6c0e68f0` |
| Fused .rzl | `c7e466c68362cc0d250afa97668beaff31ea01a00f503e2705ac25c326ae88ad` |

On macOS:

```bash
shasum -a 256 RENJIN-COMPONENT.rzl
shasum -a 256 RENJIN-KUBO.rzl
shasum -a 256 R-OPERATING-SYSTEM-PURE-LINUX-RZL.rzl
shasum -a 256 RENJIN-ENJIN-CRYPTOBOT-MODEL-SHELL-FUSED.rzl
```

On Linux:

```bash
sha256sum RENJIN-COMPONENT.rzl
sha256sum RENJIN-KUBO.rzl
sha256sum R-OPERATING-SYSTEM-PURE-LINUX-RZL.rzl
sha256sum RENJIN-ENJIN-CRYPTOBOT-MODEL-SHELL-FUSED.rzl
```

Compare each result character for character with the table above. If any hash differs, stop, re-download that file from rizal.pw/renjin or rizal.info/renjin, and verify again.

## Step 3 — Map components to the apps on the Moto

Install only what each app is meant to carry:

| App on the Moto | Recorded version | Gets |
| --- | --- | --- |
| RDRAGON | 1.0.6.2 / build 37 | R:> Shell + RENJIN-COMPONENT.rzl + Renjin Torrent RTOR client |
| RCODE | 0.1.0-android | RENJIN-COMPONENT.rzl + Core v3 |
| RMAIL | — | RMAIL v2.1 record + magnet link, over relay_8797 |
| RBOARD | 1.1.3-standard-v3 | Nothing — leave as is |

Notes on the map:

- RDRAGON is the host on the Moto: the shell and the torrent client go into RDRAGON, with the component.
- RCODE gets the component and Core v3. RCODE never signs — minting and signing stay on Face ID / the RGHOSTKEY tap, as elsewhere.
- RMAIL gets no .rzl install. It gets the RMAIL v2.1 record and the magnet link, sent over relay_8797 in Step 6.
- RBOARD 1.1.3-standard-v3 is already on the Moto. Leave it as is — do not reinstall, replace, or remove it as part of this install.
- RENJIN-KUBO.rzl, the R Operating System .rzl, and the fused .rzl are verified in Step 2 and held in the package on the Moto for the RTOR back-and-forth test and the OS record. They are not forced into an app that does not carry them.

Gizmo owns the Moto update work per the handoff. This guide is the install sequence for that update — run it under Gizmo's ownership and Chase's GO.

## Step 4 — Install over each existing app

For each app in the map above:

1. Push the component files for that app to the Moto over the wireless debug connection, using the app's own update / install path — the same over-install path used for the Neo and 17e installs.
2. Install over the existing app. If a step offers uninstall, remove, or clear data, stop and choose the over-install / update option instead.
3. Open the app after its install and confirm it still shows its existing identity, data, and history. An over-install that lost data means the wrong path was used — stop and report it before continuing to the next app.
4. Repeat for the next app: RDRAGON first, then RCODE, then the RMAIL record in Step 6.

Worked order:

- RDRAGON: install the R:> Shell, then RENJIN-COMPONENT.rzl, then activate the Renjin Torrent RTOR client inside it following RTOR-INSTALL.md.
- RCODE: install RENJIN-COMPONENT.rzl with Core v3.
- RBOARD: skip. Confirm only that 1.1.3-standard-v3 is still present and untouched.

## Step 5 — Re-seed and verify the chain

The seed was removed from RENJIN-KUBO.rzl and the other packaged files before they were published. The chain cannot go live from the package alone.

1. On the trusted device, re-seed with a RGHOSTKEY tap. Keys stay behind biometrics via ЯCASKET. No bot, shell, or mail step signs or mints.
2. Open the R:> Shell in RDRAGON on the Moto.
3. Run:

```text
CHAIN VERIFY
```

4. Confirm the shell reports the chain intact — chain entries present, `chain_ok` — before continuing. If CHAIN VERIFY fails, stop: do not send the magnet link, and report the exact shell output.

Also check in the shell:

```text
STATUS
VERSION
```

These should report the live Core v3 engine from the installed component, not a cached or demo state.

## Step 6 — Send the magnet link through RMAIL to RTRACKR

1. In RMAIL on the Moto, confirm the active target is relay_8797 and the RMAIL v2.1 record from the package is loaded.
2. Compose an RMAIL message to RTRACKR carrying the magnet link built from the magnetized RTOR GHOSTCHAIN transponder record — the magnet derived from the package SHA256 and STATE hash in the records.
3. Send it over RTOR through the GHOSTCHAIN RTOR system. RMAIL carries the link; it does not sign or mint it.

RTRACKR: https://rizal.pw/rtrackr

## Step 7 — Confirm ThundR picks the Moto up live

Activation is only complete when the Moto is visible from the other side:

1. With the RTOR client activated in RDRAGON, confirm the Moto posts its chain head and a heartbeat to the RTRACKR feed.
2. Check the RTRACKR feed at https://rizal.pw/rtrackr for the Moto's entry: chain head matching the CHAIN VERIFY result from Step 5, and a fresh heartbeat.
3. Once that post is in the feed, ThundR picks the Moto up live from that feed — chain head, heartbeat, and ongoing RMAIL, updates, diagnostics, and proposed repairs through the GHOSTCHAIN RTOR system.

If the Moto does not appear in the feed, the install is not yet live: check the RTOR client is activated, relay_8797 is the target, and the Moto is still connected, then send the magnet link again. Do not claim a live connection until the feed shows it.

## What is verified and what is not

Verified:

- The four .rzl hashes in Step 2 match the standalone files, and the same files downloaded back from rizal.pw/renjin and rizal.info/renjin matched their published fingerprints.
- The package contents: sites (R:> Shell, Renjin Torrent, install guide), apps (all four .rzl files), and records (magnetized transponder, RTOR file, mesh, client and file records).
- Recorded Moto state going in: RDRAGON 1.0.6.2 / build 37, RCODE 0.1.0-android, RBOARD 1.1.3-standard-v3 already installed.

Not verified — stated plainly:

- **No measured RTOR speed exists yet.** There is no measured average to quote for the Moto or any other node until a real run measures it.
- **No live device swarm is claimed** until the device run in Steps 5–7 proves it — the Moto posting its chain head and heartbeat to the RTRACKR feed is that proof, and nothing before it is.
- **No install on the Moto has been run yet from this guide.** This document is the sequence to run on the paired machine; it is not a report that the Moto install succeeded.
- **No real money moves** in any part of this install, the re-seed, the magnet send, or the RTOR test. No wallet is funded and no trade is made.
- Signing stays on the owner's tap on a trusted device. The shell, RMAIL, and the RTOR client hold no keys and create no cryptographic signature.

## Quick checklist

- [ ] `adb connect` to the Moto's wireless debug address; `adb devices` shows `device`
- [ ] All four .rzl SHA256 hashes verified against Step 2
- [ ] RDRAGON: shell + component + RTOR client, installed over build 37
- [ ] RCODE: component + Core v3, installed over 0.1.0-android
- [ ] RMAIL: v2.1 record loaded, target relay_8797
- [ ] RBOARD: left as is at 1.1.3-standard-v3
- [ ] Re-seed done on the trusted device with a RGHOSTKEY tap
- [ ] `CHAIN VERIFY` in the shell reports the chain intact
- [ ] Magnet link sent through RMAIL to RTRACKR
- [ ] Moto chain head + heartbeat visible in the RTRACKR feed
