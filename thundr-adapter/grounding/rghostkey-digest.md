# RGHOSTKEY — digest

Source files (supplied by Rizal 2026-11-19 13:41 MST, copies in `rghostkey/` in this
folder): RGHOSTKEY-PARITY-0.1.4.md, rghostkey-api.js (= rghostkey-api.js.0.1.5-upstream,
identical sha), rghostkey-api-2.js, rghostkey.gd + .uid, RGhostkeyAndroid.java,
RGhostkeyAndroid-2.java, RGhostkeyAndroid.vc30.java.txt, RGhostkeyAndroid.class,
RGhostkeyAndroid_1.class, RGhostkeyApi.class, RGhostkeyAndroidBridge.java.NOT-BUILT,
RGhostkeyApi.java, RGhostkeyApi-2.java, RGhostkeyAPI.swift, RGhostkeyBindSeal.swift,
RGhostkeyBindSeal.swift.bin, RGhostkeyBindSeal.swift-2.bin. 19 distinct files.
Secret scan 2026-11-19: CLEAN (0 private-key blocks, 0 key prefixes across the 12
text files). The 3 .class files are compiled Java 11 (version 55.0); contents not
decompiled (no javap output available) — recorded as artifacts only.

## What it is

RGHOSTKEY is the "polykey": ONE interface with the same method names on every
platform — Swift (iOS 17e + Neo macOS), Java (Android moto), JS (web/RWALLET),
GDScript (game helper). Parity doc: RGHOSTKEY-PARITY-0.1.4.md, RWALLET 0.1.4,
2026-11-09 (Rizal t66u/t68u).

**Parity means the same methods, not shared secrets.** Every hard device keeps its
OWN pinned key (Secure Enclave / login keychain / AndroidKeyStore). No key is
created, exported, copied, or synced by any of this. Bots never sign, seal, enroll,
or mint. RSignSealMint.swift and rghostkey.auto are untouched.

## The one interface

status() · methods() · unlock(method) · sign(payload) · approve(requestId) ·
logout() · session start · revoke · cast receive/dismiss · offline nonce · lockout.

- Swift `RGhostkey` (RGhostkeyAPI.swift): status/methods/unlock/sign/approve/logout;
  RGhostkeyBindSeal.sealBind(sealEntry:done:). WK handler `rghostkey` (with reply).
- Java `RGhostkeyApi` (RGhostkeyApi.java): status/methods/unlock/sign/approve/logout.
  JS interface `RGhostkeyNative`. Android key alias `rsign.rghostkey.ec`.
- JS `window.RGHOSTKEY` (rghostkey-api.js 1.0, RWALLET 0.1.4, ADD-ONLY): same names;
  soft paths go to POST /rmint/request, /assm/session/start, /assm/logout,
  /assm/revoke, /rmint/gate/status.
- GDScript (rghostkey.gd): begin(n), add_factor(kind, device_id, pubkey, proof),
  complete(rid, handle, t), single_factor_ok(rec, device_id, kind) — enrollment-side
  factor-record builder (pubkey + proof, not key creation).
- rmint-press.js prefers RGHOSTKEY when a native rghostkey handler exists, so the
  cast card's "Я MINT · SIGN" press signs with the device's pinned key instead of
  older per-app keys.

## Pins and rules (enforced in code)

- Pins (public pubkey_sha256, from /rghostchain/bind/pending): neo-rdragon
  5752020b…8782 · iphone17e-rdragon 26431cd4…b0eb · moto-rdragon 9acf9fbd…d54e.
  Missing or unpinned key → refused, never enrolled.
- Apple keys: Secure Enclave tag info.rizal.rsign.se.p256, or on Neo the
  non-extractable login-keychain key info.rizal.rsign.mac.p256.v2 (ACL userPresence).
  status() reports which backend. Keychain key → Touch ID or Mac login password
  (system prompt), never an app-entered ASSM password (that ACL has no
  .applicationPassword; adding one would mean a NEW key — forbidden). ASSM session
  still required by the gate before the press.
- Every signature needs one unlock on THIS device (Face ID / Touch ID / Mac password
  via the key's own ACL, or ASSM password via RSignOneOf when the SE key's ACL has
  .applicationPassword). No held unlock context, no timer, no auto-approve.
- ThundR's column in the parity matrix: status soft (rghostkey-api.js shell), sign =
  request only (never signs), approve = queue only (staged gate 1.2 not live), cast
  status only.

## Version drift found in this batch

- rghostkey-api.js == 0.1.5-upstream (identical). rghostkey-api-2.js is the **vc27
  async port**: Android calls go through promise .then with error handlers; **no
  general sign() on Android** — returns "Android vc27: no general sign; only RMAIL
  Approve → RWALLET approve(request id + nonce) signs, after the fingerprint";
  approve passes only (id, nonce, method) — native loads + checks the stored request
  itself, entry is not sent.
- RGhostkeyApi-2.java matches vc27: NO web-exposed sign(); approve(requestId, nonce,
  method, cb) with RApproveCheck (id + nonce + full entry) before any prompt.
- RGhostkeyAndroid.java (current) = vc27 shape (approve by nonce, no sign) + **vc31**:
  approve accepts BIOMETRIC_STRONG only (DEVICE_CREDENTIAL removed; "signing unlock
  is Face ID or fingerprint; ASSM password fallback off"). RGhostkeyAndroid-2.java is
  the earlier shape (@JavascriptInterface annotations, approve by entryJson, general
  sign via signInner). vc30 still allowed DEVICE_CREDENTIAL with fallback.
- RGhostkeyBindSeal.swift (current) = login-keychain option A (free personal team,
  kSecAttrIsPermanent, backend "macOS-login-keychain-nonextractable-ASSM", use gated
  by ASSM device-owner auth via LAContext). .bin variant = data-protection-keychain
  option B (kSecAttrAccessGroup + kSecUseDataProtectionKeychain, backend
  "macOS-keychain-keyref-biometric-ACL") — returns with Apple signing. -2.bin differs
  by 143 lines (older variant).
- Known gaps (parity doc, honest limits): Android bridge has 3 pre-existing
  JSONException errors blocking assembleDebug (NOT fixed — the fix edits existing
  lines, so it is not add-only; trivial fix documented for Rizal); TERAFORMR native
  rsign GDExtension dylib not built (game uses the web wallet panel, soft); native
  approve UI unbuilt on Android (approve has no caller yet).

## Rules for the ThundR Plugin Adapter

- The adapter NEVER signs, seals, enrolls, or mints — like ThundR, it routes
  approval requests (request/queue only). Signing happens only on the pinned device,
  by the human, through RGHOSTKEY.
- The adapter's GO-gating mirrors the vc27/vc31 hardening: no general sign path,
  approve-by-reference (id + nonce, never a raw payload from the requester),
  biometric-only unlock on the device.
- adapter.diagnostics should report rghostkey status (backend, slot, pinned or not)
  when the interface is reachable.
- The parity principle ("same methods, not shared secrets") is the adapter's own
  cross-host principle: one method surface, per-device keys, nothing shared.
