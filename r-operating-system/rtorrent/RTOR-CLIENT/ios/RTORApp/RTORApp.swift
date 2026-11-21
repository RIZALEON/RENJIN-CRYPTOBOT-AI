import SwiftUI
import RTORKit

/// RTOR standalone app (info.rizal.rtor): opens .rzl, crypto files, .rtor, .torrent, .magnet and magnet: links.
@main
struct RTORApp: App {
    var body: some Scene {
        WindowGroup { RTORView() }
    }
}
