# RZL INDEX — digest

Source: `~/workspace/user/files/RZL_INDEX.pdf` (81 pp, created in Xcode 2026-11-19 13:30 MST
by RIZAL SYSTEM). Full extracted text: `rzl-index.txt` (4,286 lines) in this folder.
Scan date in the document: **2026-11-04 (MT)**. Read-only scan of `~/R` (incl. full
BONEPILE, parts/RZL BP-RZL-####) and iCloud. **1,388 .rzl files.** Pure = no
gguf/safetensors/onnx/.bin/.pt inside. Duplicates by sha256 (first copy = original).
Nothing deleted/moved/renamed.

## Component table

| # | Component | pieces | unique | total size | not-pure | status |
|---|---|---|---|---|---|---|
| 0 | RbotLoadR | 0 | 0 | 0.00 MB | 0 | MISSING in index → 0.0.1 UNSIGNED DRAFT supplied 2026-11-19 (see note) |
| 1 | RVM | 155 | 13 | 272.49 MB | 23 | COMPLETE as runtime |
| 2 | RGENERATR | 27 | 2 | 13.09 MB | 0 | PARTIAL |
| 3 | RBATIBABOX | 137 | 52 | 985.37 MB | 0 | PRESENT |
| 4 | RMIND | 7 | 7 | 73.18 MB | 0 | PRESENT as memory docs only |
| 5 | ЯSEED | 255 | 42 | 69.15 MB | 0 | COMPLETE |
| 6 | OTHER pure .RZL | 777 | 423 | 3883.18 MB | 7 | skills, docs, eggs, logs |

## Status notes (verbatim sense, condensed)

- **0. RbotLoadR — MISSING in the index, but 0.0.1 UNSIGNED DRAFT supplied
  2026-11-19** (files in `rbotloadr-0.0.1/` in this folder): single-file HTML+JS
  pure .rzl loader, derived from RCOMMAND/HARDSHELL/opener (copy only; HARDSHELL
  lane untouched). Opens an rzl.v1 egg by picker/drag-drop, verifies every manifest
  component (sha256 + size), mounts the egg's index.html with read-only
  window.RZL_VFS; also reads ENJIN-ASSEMBLY (rzl.enjin.assembly.v1) pins. No
  network, no signing, no chain append. Manifest: schema
  rzl.rghostchain.enjin_egg.payload.v1, draft, NOT_APPENDED, role loader, sig_plan
  "owner signs with RGHOSTKEY / Face ID later". Verified 2026-11-19: sha256
  d1ea6a6a5435ab90ecb2f623f2e4670f602753eb00e3d237c8b1612c97c84aed matches the
  manifest, size 7160 B, .rzl and .html byte-identical. The loader itself is one
  HTML file with a .rzl extension (not a ZIP).
- **1. RVM — COMPLETE as runtime.** RVM 0.1.0–0.1.4 + RVM-LINUX 0.1.1–0.1.2 (+android).
  RVM-LINUX-0.1.0 not pure (raw .bin kernel/disk images; 0.1.1+ wrap them as .bin.js).
- **2. RGENERATR — PARTIAL.** Only RGENERATOR 2.1.9 (egg5 rkey0, egg6 passkey), both UNSIGNED.
  Adapter spec v1 + assets snapshot supplied 2026-11-19 (files in `rgeneratr/` in
  this folder): RGENERATR is the asset adapter — one writer
  (`rgen_asset_adapter.py` reads the local RGHOSTCHAIN jsonl + RTRACKR registry,
  never writes the chain) producing `out/assets.json` (schema
  rzl.rgeneratr.assets.v1) + `.sha256` sidecar; readers (TerraformЯ game wallet,
  ЯBOT wallet, rizal.pw RWALLET, RTRACKR) never edit it. Assets stay PREVIEW until
  a verified nft_mint block exists AND the seal has a signature; seals are written
  on the phone by RSIGN after Face ID (ES256/P-256, never a private key) and moved
  phone→Neo over USB via devicectl; feed goes Neo→phone the same way. Snapshot
  2026-10-30: one owner (@chaserizal, ЯID-0001-3QQS), one asset
  (rid-asset-0001-genesis "GAME-MINTED GENESIS"), status "preview — awaiting signed
  seal", chain 1 block, 0 nft_mint blocks for the rid, rtracker "dry". This spec is
  the direct precedent for the ThundR Plugin Adapter's one-writer discipline and
  preview-until-live gating.
- **3. RBATIBABOX — PRESENT.** BATIBABOX core/EMBED/LOG/SKILLS + bbx-lex pieces; some
  members matched via manifest (e.g. notes-reader eggs) — review.
- **4. RMIND — PRESENT as memory docs only (rzl.doc.v1).** MACHINE-MIND,
  MACHINE-MIND-LIVE, DRAGON-SKULL-MIND, machine-mind-2.1.4-android. No runner of its own.
- **5. ЯSEED — COMPLETE (only pure-.rzl model).** RSEED 0.0.1–0.1.10 +
  yaseed-0.1.9-android; tokenizer + ternary weights (seed) + generate/train + manifest.
  Toy scale. RLINK-RELAY/mailbox docs grouped here via manifest.
- **6. OTHER — 777 pieces.** Includes SCRIBE-UNIFIED-MASTER-20261104.RZL,
  YAMANUAL-MERGED rev5/rev6, BOTABLETA notes. Not-pure entries include
  ЯENJIN-test-embedded .rzl files (BP-RZL-0027/0032/0036/0041/0046/0051…) and
  ЯHEART-Qwen3-… — ENJIN test embeds exist but are not pure.

## Relevance to the THUNDR × RENJIN build

- "ThundR" appears 225 times in the index; "renjin" 0 times (index predates the
  RENJIN core naming; ЯENJIN appears only in not-pure test embeds).
- ЯSEED is the pure-.rzl model ancestor of RENJIN (ternary weights, tokenizer,
  generate/train) — the RENJIN core v3 descends from this line.
- Gaps the true build must close: RbotLoadR has no .rzl at all; RGENERATR is
  partial and UNSIGNED; RMIND has no runner; RVM-LINUX-0.1.0 is not pure.
- The adapter's analyze/update functions should check component presence and
  status against this table (see ADAPTER.md).
