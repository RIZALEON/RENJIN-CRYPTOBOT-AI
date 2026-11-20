# ThundR for macOS — pure .RZL Xcode project

**ThundR** — Chase Rizal's purple thunder-imp cryptobot for TerraformR /
PROJECT R / RENJIN — as a native macOS app, built pure .RZL.

- Bundle id: `com.rizal.thundr`
- Target: macOS 14+, SwiftUI, one app target, **no external dependencies,
  no Swift Package dependencies**
- Brain: RENJIN Core v3 (pure RZL JS in WKWebView) — see below
- Version: 0.1.11 (egg version, one source of truth in `egg-version.js`)

## What it is

A SwiftUI macOS app that hosts the R:> Shell in a WKWebView. The sidebar
shows live Trackers (corpus-v2 158 lessons, loss 27.631 → 3.26, held-out
3.246, chain 9 entries, chain_ok true, grounded 8/10, state hash) and the
ThundR Plugin Adapter status. The prompt bar asks the engine; answers
are retrieval-first quotes from corpus-v2, or "Unknown."

Files:

```
ThundR.xcodeproj/project.pbxproj   — Xcode project, one macOS app target
ThundR/
  Sources/
    ThundRApp.swift                — @main SwiftUI app entry
    ContentView.swift              — sidebar + Trackers + WKWebView shell + prompt
    PureRZLBrain.swift             — pure RZL brain: bundle resources, ask/status/chain verify
    ThundRPluginAdapter.swift      — thundr-plugin v0.1.0, rzl.thundr.plugin.v1
    Tokenizer.swift                — tok.v1, vocab 313 (copy of the pure tokenizer)
  Info.plist                       — com.rizal.thundr, macOS 14+, version 0.1.11
  ThundR.entitlements              — App Sandbox on; loopback-only network client
  Assets.xcassets/                 — AppIcon set (drop ThundR art in — see below)
  Resources/
    yaseed-core-v3.js              — ЯENJIN 0.1 core v3 (DIM 64 / HID 128 / CTX 32)
    yaseed-core-v2.js              — core v2 (reference)
    rzl-ask.js                     — MIND v2 retrieval, BM25 0.7 + RZL embeddings 0.3
    rzl-embed.js                   — rzl-embed.v1
    egg-version.js                 — version 0.1.11, one source of truth
    model-config-v2.js             — rzl-model.v2 config
    corpus-v2.txt                  — 158 lessons
    corpus-v1.txt                  — 112 lessons (history)
    store-v3.json                  — persisted trained state
                                   — state:current 16f9dd002f25a26ddc7df8a6d2ef39ea898326df1414f6139663416ec9eb9b08
    thundr-plugin-bridge.js        — JS side of the plugin adapter
    rcode-host-adapter.js          — RCODE host adapter (reference)
    thundr-plugin-adapter.rzl      — rzl.doc.v1 adapter spec / stamp
    PURE-RZL-LAW.md / STARFIELD-LAW.md / CITATION.md
    shell/
      R-SHELL-MERGED.html          — merged R:> Shell (Trackers + trained engine) — default
      RSHELL-RENJIN.html           — Neo one-file shell (MODEL/SYNC/EVOLVE)
```

## Pure RZL rules — read this first

This project is **pure .RZL, from scratch, ground up**. That means:

- **NO Qwen / llama.cpp / Llama / any other AI company's model, weights,
  or code in it.** The old RTHUNDR brain (`LocalBrain.swift`: fused
  llama.cpp + Qwen3 1.7B Q8 + BM25) is the non-pure brain this project
  REPLACES. It is not included, not linked, not referenced in code.
  A grep for `qwen|llama` over this project returns zero hits in source
  (this README is the only place those names appear, to say they are
  excluded).
- The model is the founding RZL model, scaled: ternary weights
  (-1/0/+1), 49,152 weights, trained only on RZL-authored corpus text.
- `.rzl` is the only file extension the pure RZL AI bot enjin model
  will ever have. Never `.zip`, never `.rzl.zip`.
- Bots never sign. Keys never leave the device. Every mint / sign / pay
  needs one unlock on a hard device. Repairs and updates are
  propose-first, with Decider approval. Never erase.

## How to open / build / run on MacBook Neo

1. Copy this folder to the Neo (it is not pushed to GitHub).
2. Open `ThundR.xcodeproj` in Xcode.
3. **App icon:** drop ThundR art into
   `ThundR/Assets.xcassets/AppIcon.appiconset/` (the purple thunder imp;
   the avatar file is `ThundR-profile.webp` in the ThundR botcard package)
   and into the sidebar `Image("ThundR")` — add a `ThundR` image set to
   `Assets.xcassets/` with the avatar PNG/WebP. The project builds
   without it (the image will be blank), but add it before shipping.
4. Signing: the project uses Automatic signing (`CODE_SIGN_STYLE =
   Automatic`). Pick Chase's team in Signing & Capabilities on first
   open. The entitlements file enables App Sandbox; the network-client
   entitlement is loopback-only (see below).
5. Build & Run (⌘R). The app opens with the sidebar Trackers and the
   R:> Shell in the main pane. Type in the `R:\>` prompt and hit Enter.
6. Try: `ask` a corpus question (e.g. "What is the Ghost Chain?"),
   `Chain Verify`, switch shells with the radio buttons.

## Network — offline-first

- No internet. The webview loads only from the app bundle.
- External link clicks inside the shell are refused by the app.
- App Transport Security: `NSAllowsArbitraryLoads = false`.
- The **only** network entitlement is `com.apple.security.network.client`,
  and it exists only for loopback: rvm-out posts to the botbridge at
  `127.0.0.1:4873` when present. No server entitlement — nothing in
  this app listens. Delete that entitlement key for a fully network-free
  build; rvm-out will simply be unavailable and the shell keeps working.

## What is NOT included

- **No model weights from other companies.** No GGUF, no llama.cpp,
  no vendor framework. The only "weights" are the pure RZL ternary
  weights inside `store-v3.json`.
- **No keys, no signing material, no provisioning.** No GHOSTKEY ring,
  no device key, no release key. The Ghost Chain key is generated
  per-install inside the WebView (WebCrypto ECDSA P-256, non-extractable);
  the native build should move it to Secure Enclave / Keychain.
- **No Xcode project / knowledge / app state from RTHUNDR.** Those live
  on the Neo and are not in this folder.
- **No live device ЯENJIN pairing.** This app runs its own in-WebView
  copy of the engine. Pairing via botbridge / ЯLINK is a later step,
  with Decider approval.
- **No ThundR avatar image file.** Drop it in as described above
  (licence / source: Chase's ThundR botcard package).

## Known limits — honest, not hidden

- **Swift was NOT compiled here.** This VM has no Swift / Xcode
  toolchain. The Swift files were static-checked only (balanced braces,
  no obvious errors). First build on the Neo is the real compile test;
  fix whatever Xcode reports there.
- **Free generation is NOT fixed.** Greedy generation returns spaces,
  sampled generation returns gibberish. Retrieval-first quoting is the
  askable path. `ask()` quotes the best corpus line or answers
  "Unknown." — it never invents.
- **Grounded test: 8/10** in the local log (not 10/10). Two misses
  remain: loop order (line 79 vs 20) and held-out set (line 103 vs 102).
  Fix is corpus growth, then re-run `build-ask-v3.js`.
- **The `addTurn` error** (plain chat with ЯSEED in ThundR) is still
  pending a fix on the Neo.
- The core's module sandbox used the `Function` constructor; the merged
  shell replaces those two founding modules with ordinary JavaScript and
  refuses any other source string. That change is in the shell HTML,
  not in the core JS.
- `PureRZLBrain.swift` talks to the shell page through
  `window.__thundrAsk` / `window.__thundrChainVerify` if the page
  exposes them; if not, it falls back to its Swift-side scorer over the
  bundled corpus. The fallback is a scorer, not the JS engine — the
  page path is the real one.
- Single-copy rule from RTHUNDR is not enforced in this new target yet:
  do not run this app and RTHUNDR.app against the same store at once
  until the handover rule is wired in.

## Verification done on the VM (2026-11-19)

- Every JS file passes `node --check`.
- `project.pbxproj` parses as a valid pbxproj (required sections present,
  all file references resolve to files in the folder).
- Grep for `qwen|llama|Qwen|Llama` over the whole project: zero hits
  in source code (README only, explaining the exclusion).
- `store-v3.json` state:current matches the recorded hash
  `16f9dd00…eb9b08`; `corpus-v2.txt` is the 158-lesson file.
- Swift files: syntax sanity-checked without a compiler (no swiftc on
  the VM). Not compiled — see limits above.
