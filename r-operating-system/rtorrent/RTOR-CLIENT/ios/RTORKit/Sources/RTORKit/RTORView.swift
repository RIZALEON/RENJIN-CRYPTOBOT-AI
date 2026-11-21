import SwiftUI
import UniformTypeIdentifiers
#if os(iOS)
import UIKit
#endif

/// ThundR Design Standard palette: twilight starfield, #39FF14 green, #8A2BE2 purple.
public enum RTORStyle {
    public static let green = Color(red: 0x39 / 255, green: 1, blue: 0x14 / 255)
    public static let purple = Color(red: 0x8A / 255, green: 0x2B / 255, blue: 0xE2 / 255)
    public static let ink = Color(red: 0.93, green: 0.92, blue: 0.95)
    public static let dim = Color(red: 0.66, green: 0.64, blue: 0.77)
}

struct RTORStarfield: View {
    var body: some View {
        GeometryReader { g in
            ZStack {
                LinearGradient(colors: [Color(red: 0.04, green: 0.03, blue: 0.15), Color(red: 0.10, green: 0.04, blue: 0.24), Color(red: 0.17, green: 0.06, blue: 0.31), Color(red: 0.07, green: 0.04, blue: 0.16)],
                               startPoint: .top, endPoint: .bottom)
                Canvas { ctx, size in
                    for i in 0..<90 {
                        let x = CGFloat((i * 7919) % 1000) / 1000 * size.width
                        let y = CGFloat((i * 104729) % 1000) / 1000 * size.height
                        let r: CGFloat = i % 7 == 0 ? 1.6 : 0.9
                        ctx.fill(Path(ellipseIn: CGRect(x: x, y: y, width: r, height: r)), with: .color(.white.opacity(i % 3 == 0 ? 0.7 : 0.4)))
                    }
                }
            }
            .frame(width: g.size.width, height: g.size.height)
        }
        .ignoresSafeArea()
    }
}

struct RTORCard<C: View>: View {
    let title: String
    @ViewBuilder var content: C
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title.uppercased()).font(.caption.weight(.semibold)).tracking(1.4).foregroundStyle(RTORStyle.green)
            content
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(red: 0.08, green: 0.05, blue: 0.16).opacity(0.75), in: RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(RTORStyle.purple.opacity(0.45)))
    }
}

/// Drop-in RTOR screen for any app: `RTORView()` (uses RTORLibrary.shared) or `RTORView(library: myLibrary)`.
public struct RTORView: View {
    @ObservedObject var lib: RTORLibrary
    @ObservedObject var mail: RTORMail
    @State private var magnet = ""
    @State private var picking = false

    public init(library: RTORLibrary = .shared) {
        lib = library
        mail = library.rmail
    }

    /// Hosts call this from .onOpenURL: magnet: links fill the leech box, file URLs are opened into the library.
    public static func handle(url: URL, library: RTORLibrary = .shared) -> String? {
        if url.scheme?.lowercased() == "magnet" { return url.absoluteString }
        library.open(url: url, source: "open-in")
        return nil
    }

    public var body: some View {
        ZStack {
            RTORStarfield()
            ScrollView {
                VStack(spacing: 14) {
                    HStack(spacing: 6) {
                        Text("R:>").font(.title2.monospaced().bold()).foregroundStyle(RTORStyle.green)
                        Text("RTOR").font(.title2.bold()).foregroundStyle(RTORStyle.ink)
                        Text("· Renjin Torrent").font(.title3).foregroundStyle(RTORStyle.purple)
                        Spacer()
                    }
                    if !lib.lastMessage.isEmpty {
                        Text(lib.lastMessage).font(.footnote.monospaced()).foregroundStyle(RTORStyle.ink)
                            .frame(maxWidth: .infinity, alignment: .leading).padding(10)
                            .background(RTORStyle.purple.opacity(0.25), in: RoundedRectangle(cornerRadius: 10))
                    }
                    RTORCard(title: "Open a file to seed") {
                        Button { picking = true } label: { Label("Choose file", systemImage: "doc.badge.plus").bold() }
                            .buttonStyle(.borderedProminent).tint(RTORStyle.purple)
                        Text(".rzl · crypto files (public wallet/chain JSON, public .pem/.crt) · .rtor · .torrent · .magnet · SHA256SUMS · any file. Private keys are refused.")
                            .font(.caption).foregroundStyle(RTORStyle.dim)
                    }
                    RTORCard(title: "Leech by magnet") {
                        TextField("magnet:?xt=urn:sha256:… / urn:btih:…", text: $magnet, axis: .vertical)
                            .font(.footnote.monospaced()).textInputAutocapitalization(.never).autocorrectionDisabled()
                            .padding(8).background(Color.black.opacity(0.35), in: RoundedRectangle(cornerRadius: 8)).foregroundStyle(RTORStyle.ink)
                        HStack {
                            Button("Leech") { Task { await lib.leech(magnet) } }.buttonStyle(.borderedProminent).tint(RTORStyle.purple)
                            Button("Renjin Core v3") { magnet = RTORMagnet.renjinCoreV3 }.buttonStyle(.bordered).tint(RTORStyle.green)
                            Button("Add RGHOSTCHAIN") { magnet = RTORMagnet.rghostchainLeech; Task { await lib.leech(RTORMagnet.rghostchainLeech) } }.buttonStyle(.bordered).tint(RTORStyle.green)
                        }
                        Text("Looks in this library, then the space's RKLOWD / RMAIL drop points, then exact-source URLs. Accepted only on SHA-256 match.")
                            .font(.caption).foregroundStyle(RTORStyle.dim)
                    }
                    RTORCard(title: "Files") {
                        if lib.items.isEmpty { Text("No files yet.").foregroundStyle(RTORStyle.dim) }
                        ForEach(lib.items) { it in
                            VStack(alignment: .leading, spacing: 4) {
                                HStack {
                                    Text(it.name).foregroundStyle(RTORStyle.ink).lineLimit(1)
                                    Spacer()
                                    Text(it.type.rawValue).font(.caption2).padding(.horizontal, 6).overlay(Capsule().stroke(RTORStyle.purple)).foregroundStyle(RTORStyle.ink)
                                }
                                Text(String(it.sha256.prefix(24)) + "… · " + ByteCountFormatter.string(fromByteCount: it.size, countStyle: .file))
                                    .font(.caption2.monospaced()).foregroundStyle(RTORStyle.dim)
                                HStack(spacing: 6) {
                                    ForEach(it.verified, id: \.self) { v in
                                        Text(v.method).font(.caption2).foregroundStyle(v.ok ? RTORStyle.green : .red)
                                    }
                                    Spacer()
                                    Text("\(it.seededTo.count) drop copies").font(.caption2).foregroundStyle(RTORStyle.dim)
                                }
                                let _ = lib.rateTick
                                TimelineView(.periodic(from: .now, by: 1)) { _ in
                                    HStack(alignment: .top) {
                                        RTORRateView(title: "Seeding ↑", rate: lib.rate(.up, it))
                                        RTORRateView(title: "Leeching ↓", rate: lib.rate(.down, it))
                                    }
                                }
                                HStack {
                                    Button("Seed") { lib.seed(it) }.buttonStyle(.borderedProminent).tint(RTORStyle.purple).controlSize(.small)
                                    Button("Copy magnet") { copy(it.magnet); magnet = it.magnet }.buttonStyle(.bordered).tint(RTORStyle.green).controlSize(.small)
                                    ShareLink(item: lib.fileURL(it)) { Image(systemName: "square.and.arrow.up") }.controlSize(.small)
                                }
                            }
                            .padding(.vertical, 6)
                            Divider().overlay(RTORStyle.purple.opacity(0.3))
                        }
                    }
                    RTORCard(title: "Space · ЯID") {
                        if let s = lib.space {
                            row("ЯID", s.rid ?? "—"); row("space", s.space ?? "—"); row("RKLOWD node", s.rklowdNode ?? "—"); row("RMAIL", s.rmailAddress ?? "—")
                            ForEach(lib.drops) { d in row("drop " + d.name, d.reachable ? "reachable" : "not reachable", d.reachable ? RTORStyle.green : .red) }
                        } else {
                            Text("No SPACE-RID.json found (Documents, library folder or app bundle).").font(.caption).foregroundStyle(.yellow)
                        }
                        Button("Reload") { lib.reloadSpace() }.buttonStyle(.bordered).tint(RTORStyle.green).controlSize(.small)
                    }
                    RTORCard(title: "RMAIL · relay_8797") {
                        row("outbox pending", "\(mail.pending)", mail.pending > 0 ? .yellow : RTORStyle.green)
                        Button("Retry outbox") { Task { await mail.flush() } }.buttonStyle(.bordered).tint(RTORStyle.green).controlSize(.small)
                        Text("Mail never signs or mints. Undelivered mail stays queued.").font(.caption).foregroundStyle(RTORStyle.dim)
                    }
                    RTORCard(title: "Re-seed") {
                        Text("Waiting for Rizal's RGHOSTKEY tap on the trusted device. RTOR holds no key and signs nothing.").font(.caption).foregroundStyle(.yellow)
                    }
                    Text("No measured RTOR speed exists yet. No peers or swarm are shown until a device run proves them. No real money moves.")
                        .font(.caption2).foregroundStyle(RTORStyle.dim)
                }
                .padding(16)
            }
        }
        .preferredColorScheme(.dark)
        .fileImporter(isPresented: $picking, allowedContentTypes: UTType.rtorOpenable, allowsMultipleSelection: true) { r in
            if case .success(let urls) = r { for u in urls { lib.open(url: u) } }
        }
        .onOpenURL { u in if let m = RTORView.handle(url: u, library: lib) { magnet = m } }
    }

    func copy(_ s: String) {
        #if os(iOS)
        UIPasteboard.general.string = s
        #endif
    }

    @ViewBuilder func row(_ k: String, _ v: String, _ c: Color = RTORStyle.ink) -> some View {
        HStack { Text(k).foregroundStyle(RTORStyle.dim); Spacer(); Text(v).font(.caption.monospaced()).foregroundStyle(c).lineLimit(1) }
    }
}

/// One always-on direction: ON badge (no off state), measured rate, last transfer, total.
struct RTORRateView: View {
    let title: String
    let rate: RTORRate
    static func fmt(_ b: Double) -> String { b >= 1_048_576 ? String(format: "%.2f MB/s", b / 1_048_576) : b >= 1024 ? String(format: "%.2f KB/s", b / 1024) : String(format: "%.0f B/s", b) }
    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: 4) {
                Text("ON").font(.caption2.bold()).padding(.horizontal, 5).background(RTORStyle.green, in: Capsule()).foregroundStyle(.black)
                Text(title).font(.caption2).foregroundStyle(RTORStyle.ink)
            }
            Text(Self.fmt(rate.bytesPerSecond)).font(.caption.monospaced()).foregroundStyle(RTORStyle.green)
            if let n = rate.note { Text(n).font(.caption2).foregroundStyle(RTORStyle.dim) }
            if let lb = rate.lastBytes, let lr = rate.lastBytesPerSecond { Text("last \(lb) B · \(Self.fmt(lr))").font(.caption2.monospaced()).foregroundStyle(RTORStyle.dim) }
            Text("total \(rate.totalBytes) B").font(.caption2.monospaced()).foregroundStyle(RTORStyle.dim)
        }.frame(maxWidth: .infinity, alignment: .leading)
    }
}
