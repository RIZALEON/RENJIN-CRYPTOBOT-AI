# RTORKit — RTOR (Renjin Torrent) component

Seed/leech one file at a time, in any app. Opens .rzl, crypto files (public wallet/chain export JSON, public .pem/.crt),
.rtor, .torrent, .magnet and magnet: links (btih 40-hex / base32 v1, 64-hex, btmh v2, urn:sha256). Private keys are refused.

Add to a host app (Dragon Skull, ЯBOT, RCODE):
1. Xcode ▸ File ▸ Add Package Dependencies ▸ Add Local… ▸ this folder, or embed `RTORKit.framework`
   from `rtor/xcode/RTOR-CLIENT.xcodeproj` (target RTORKit).
2. `import RTORKit` and present `RTORView()` (or `RTORView(library: RTORLibrary(directory: …))`).
3. Optional: forward `.onOpenURL { RTORView.handle(url: $0) }` and copy the document types / magnet URL scheme from
   `rtor/ios/RTORApp` (see rtor/xcode/project.yml) into the host's Info.plist.

Drop points come from `SPACE-RID.json` (rid, space, rklowd_node, rmail_address, drop_paths) in the host's Documents folder,
the library folder, or the app bundle. Relative drop paths resolve inside Documents. RMAIL announces go to relay_8797
(127.0.0.1:8797/send, then the Neo hub) and stay queued if undelivered. RTORKit holds no keys and signs nothing.
