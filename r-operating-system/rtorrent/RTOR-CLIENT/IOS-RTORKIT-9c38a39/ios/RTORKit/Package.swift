// swift-tools-version:5.9
// RTORKit — RTOR (Renjin Torrent) seed/leech component. Add to an app with
// File ▸ Add Package Dependencies ▸ Add Local… (this folder), then `import RTORKit` and show `RTORView()`.
import PackageDescription

let package = Package(
    name: "RTORKit",
    platforms: [.iOS(.v17)],
    products: [.library(name: "RTORKit", targets: ["RTORKit"])],
    targets: [.target(name: "RTORKit", path: "Sources/RTORKit")]
)
