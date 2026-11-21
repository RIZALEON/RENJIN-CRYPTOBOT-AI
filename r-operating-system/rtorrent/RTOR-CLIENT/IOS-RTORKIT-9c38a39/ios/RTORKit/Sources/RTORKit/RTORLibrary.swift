import Foundation
import Combine
import SwiftUI

public struct RTORVerify: Codable, Hashable, Sendable { public var method: String; public var ok: Bool; public var detail: String }

public struct RTORItem: Codable, Identifiable, Hashable, Sendable {
    public var id: String { sha256 }
    public var sha256: String
    public var name: String
    public var type: RTORFileType
    public var size: Int64
    public var imported: Date
    public var source: String
    public var btihV1: String?
    public var btmhV2: String?
    public var verified: [RTORVerify]
    public var magnet: String
    public var seededTo: [String] = []
    public var detail: [String: String] = [:]
}

/// The RTOR file library: open, hash-verify, seed and leech one file at a time. No keys, no signing, no invented peers.
@MainActor
public final class RTORLibrary: ObservableObject {
    public static let shared = RTORLibrary()

    @Published public internal(set) var items: [RTORItem] = []
    @Published public private(set) var space: RTORSpace?
    @Published public var lastMessage: String = ""
    /// Magnets leeching keeps re-checking (always on).
    @Published public private(set) var leechQueue: [String] = []
    /// Bumps whenever a byte counter moves, so views refresh their rates.
    @Published public internal(set) var rateTick: Int = 0
    var upMeters: [String: RTORMeter] = [:]
    var downMeters: [String: RTORMeter] = [:]
    var alwaysOnTask: Task<Void, Never>?
    public let rmail: RTORMail
    /// 0.2.2 peer network (LAN peer on 4985, always-on seed/leech keepalive, RTRACKR fallback, RE-SEED chain reader).
    public private(set) lazy var net: RTORNet = RTORNet(library: self)

    let dir: URL
    var sums: [String: String] = [:]

    /// - Parameter directory: where the library lives (default Application Support/RTOR). A host app may pass its own.
    public init(directory: URL? = nil) {
        let fm = FileManager.default
        let base = directory ?? fm.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("RTOR", isDirectory: true)
        dir = base
        try? fm.createDirectory(at: base.appendingPathComponent("files"), withIntermediateDirectories: true)
        rmail = RTORMail(outbox: base.appendingPathComponent("rmail-outbox.json"))
        load()
        reloadSpace()
        startAlwaysOn()
    }

    var documents: URL { FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0] }

    /// SPACE-RID.json is looked up in Documents (Files app / host-app drop), then the library folder, then the app bundle.
    public func reloadSpace() {
        var c = [documents.appendingPathComponent("SPACE-RID.json"), dir.appendingPathComponent("SPACE-RID.json")]
        if let b = Bundle.main.url(forResource: "SPACE-RID", withExtension: "json") { c.append(b) }
        space = RTORSpace.load(c)
    }

    public var drops: [RTORSpace.Drop] { space?.drops(base: documents) ?? [] }

    func path(_ it: RTORItem) -> URL { dir.appendingPathComponent("files").appendingPathComponent(it.sha256) }

    func load() {
        struct S: Codable { var items: [RTORItem]; var sums: [String: String] }
        let dec = JSONDecoder(); dec.dateDecodingStrategy = .iso8601
        if let d = try? Data(contentsOf: dir.appendingPathComponent("library.json")), let s = try? dec.decode(S.self, from: d) {
            items = s.items; sums = s.sums
        }
    }

    func save() {
        struct S: Codable { var items: [RTORItem]; var sums: [String: String] }
        let enc = JSONEncoder(); enc.dateEncodingStrategy = .iso8601; enc.outputFormatting = [.prettyPrinted, .sortedKeys]
        if let d = try? enc.encode(S(items: items, sums: sums)) { try? d.write(to: dir.appendingPathComponent("library.json"), options: .atomic) }
    }

    static func parseSums(_ d: Data) -> [String: String] {
        var out: [String: String] = [:]
        for line in String(decoding: d, as: UTF8.self).split(whereSeparator: \.isNewline) {
            let f = line.split(whereSeparator: { $0 == " " || $0 == "\t" }).map(String.init)
            if f.count >= 2, RTORMagnet.isHex(f[0], 64) {
                out[f[0].lowercased()] = ((f.last!.hasPrefix("*") ? String(f.last!.dropFirst()) : f.last!) as NSString).lastPathComponent
            }
        }
        return out
    }

    func applySums() {
        for i in items.indices {
            if let n = sums[items[i].sha256], !items[i].verified.contains(where: { $0.method == "SHA256SUMS" }) {
                items[i].verified.append(RTORVerify(method: "SHA256SUMS", ok: true, detail: "listed as " + n))
            }
        }
    }

    /// Open a file URL (Files, share sheet, "Open in", drag-drop). Security-scoped access is handled here.
    @discardableResult
    public func open(url: URL, source: String = "open") -> Result<RTORItem?, Error> {
        let scoped = url.startAccessingSecurityScopedResource()
        defer { if scoped { url.stopAccessingSecurityScopedResource() } }
        do {
            let d = try Data(contentsOf: url)
            var sumsDir: [String: String] = [:]
            for n in ["SHA256SUMS", "SHA256SUMS.txt"] {
                if let s = try? Data(contentsOf: url.deletingLastPathComponent().appendingPathComponent(n)) { sumsDir.merge(Self.parseSums(s)) { a, _ in a } }
            }
            return .success(try importData(d, name: url.lastPathComponent, source: source, sums: sumsDir))
        } catch {
            lastMessage = error.localizedDescription
            return .failure(error)
        }
    }

    /// Returns nil for a SHA256SUMS file (its sums are applied to the library).
    public func importData(_ d: Data, name: String, source: String, sums extra: [String: String] = [:]) throws -> RTORItem? {
        let upper = name.uppercased()
        if upper.hasPrefix("SHA256SUMS") || upper.hasSuffix(".SHA256") {
            let s = Self.parseSums(d); sums.merge(s) { _, b in b }; applySums(); save()
            lastMessage = "SHA256SUMS: \(s.count) sums applied"
            return nil
        }
        guard d.count <= 512 << 20 else { throw RTORError.refused("larger than 512 MB") }
        let sha = RTORHash.sha256(d)
        if let old = items.first(where: { $0.sha256 == sha }) { lastMessage = "already in library: " + old.name; return old }
        let c = try RTORClassifier.classify(name: name, data: d, sha: sha)
        var v = c.verified + [RTORVerify(method: "sha256", ok: true, detail: "computed on open")]
        if let n = extra[sha] { v.append(RTORVerify(method: "SHA256SUMS", ok: true, detail: "beside the file: " + n)) }
        else if let e = extra.first(where: { $0.value == name }) { v.append(RTORVerify(method: "SHA256SUMS", ok: false, detail: "listed as \(e.key.prefix(12))… (mismatch)")) }
        var it = RTORItem(sha256: sha, name: name, type: c.type, size: Int64(d.count), imported: Date(), source: source, btihV1: c.btihV1, btmhV2: c.btmhV2,
                          verified: v, magnet: RTORMagnet.forFile(sha256: sha, name: name, size: Int64(d.count), btihV1: c.btihV1, btmhV2: c.btmhV2), detail: c.detail)
        if let n = sums[sha] { it.verified.append(RTORVerify(method: "SHA256SUMS", ok: true, detail: "listed as " + n)) }
        try d.write(to: path(it), options: .atomic)
        items.insert(it, at: 0); save()
        lastMessage = "opened \(name) · \(c.type.rawValue)"
        return it
    }

    public func fileURL(_ it: RTORItem) -> URL { path(it) }

    /// Seed: copy the verified file + a .rtor.json manifest into every reachable drop point, and announce its magnet over RMAIL.
    public func seed(_ item: RTORItem) {
        guard let d = try? Data(contentsOf: path(item)), RTORHash.sha256(d) == item.sha256 else { lastMessage = "stored file failed SHA-256 re-check; not seeding"; return }
        var placed: [String] = [], notes: [String] = []
        let man: [String: Any] = ["schema": "rzl.rtor.seed.v1", "name": item.name, "sha256": item.sha256, "size": item.size, "type": item.type.rawValue,
                                  "magnet": item.magnet, "ts": ISO8601DateFormatter().string(from: Date()), "signed": false,
                                  "rid": space?.rid ?? "", "space": space?.space ?? "", "rklowd_node": space?.rklowdNode ?? "", "rmail_address": space?.rmailAddress ?? ""]
        let mb = (try? JSONSerialization.data(withJSONObject: man, options: [.prettyPrinted, .sortedKeys])) ?? Data()
        for drop in drops {
            guard drop.reachable else { notes.append("\(drop.name): not reachable"); continue }
            let dst = drop.url.appendingPathComponent("\(item.sha256.prefix(12))-\(item.name)")
            let t0 = Date()
            do { try d.write(to: dst, options: .atomic); record(.up, item.sha256, bytes: d.count, since: t0); try mb.write(to: dst.appendingPathExtension("rtor.json"), options: .atomic); placed.append(dst.path) }
            catch { notes.append("\(drop.name): \(error.localizedDescription)") }
        }
        if let i = items.firstIndex(where: { $0.sha256 == item.sha256 }) { items[i].seededTo += placed; save() }
        let to = space?.rmailAddress ?? "rtrackr"
        rmail.queue(to: to, text: "RTOR seed: \(item.name) (\(item.size) B)\n\(item.magnet)\nsha256 \(item.sha256)" + (space?.rid.map { "\nrid " + $0 } ?? ""), type: "rtor-seed")
        lastMessage = "seeding \(item.name): \(placed.count) drop point copies" + (notes.isEmpty ? "" : " · " + notes.joined(separator: "; ")) + " · RMAIL announce queued to \(to)"
    }

    /// Leech: library → drop points (hash match) → exact-source URLs (accepted only on SHA-256 match).
    public func leech(_ magnetText: String) async { await leech(magnetText, fromQueue: false) }

    func leech(_ magnetText: String, fromQueue: Bool) async {
        let m: RTORMagnet
        do { m = try RTORMagnet(parsing: magnetText) } catch { lastMessage = error.localizedDescription; return }
        let want = Set(m.hashes)
        if let it = items.first(where: { want.contains($0.sha256) || ($0.btmhV2.map { want.contains($0) } ?? false) || (m.btihV1 != nil && $0.btihV1 == m.btihV1) }) {
            leechQueue.removeAll { $0 == magnetText }
            lastMessage = "already have \(it.name) (library)"; return
        }
        for drop in drops where drop.reachable && !want.isEmpty {
            let files = (try? FileManager.default.contentsOfDirectory(at: drop.url, includingPropertiesForKeys: [.fileSizeKey])) ?? []
            for f in files where !f.lastPathComponent.hasSuffix(".rtor.json") {
                let sz = (try? f.resourceValues(forKeys: [.fileSizeKey]))?.fileSize ?? 0
                if let x = m.size, Int64(sz) != x { continue }
                let t0 = Date()
                guard sz <= 512 << 20, let d = try? Data(contentsOf: f) else { continue }
                let h = RTORHash.sha256(d)
                if want.contains(h) { record(.down, h, bytes: d.count, since: t0) }
                if want.contains(h) {
                    let name = m.name ?? String(f.lastPathComponent.dropFirst(13))
                    do { _ = try importData(d, name: name, source: "leech:drop:" + drop.name); leechQueue.removeAll { $0 == magnetText }; ensureSeeded(); lastMessage = "leeched \(name) from drop \(drop.name)" }
                    catch { lastMessage = error.localizedDescription }
                    return
                }
            }
        }
        for s in m.sources where s.hasPrefix("http://") || s.hasPrefix("https://") {
            guard !want.isEmpty, let u = URL(string: s) else { continue }
            do {
                let t0 = Date()
                let (d, _) = try await URLSession.shared.data(from: u)
                let h = RTORHash.sha256(d)
                guard want.contains(h) else { continue }   // mismatch: discarded
                record(.down, h, bytes: d.count, since: t0)
                _ = try importData(d, name: m.name ?? u.lastPathComponent, source: "leech:" + s)
                leechQueue.removeAll { $0 == magnetText }; ensureSeeded()
                lastMessage = "leeched \(m.name ?? u.lastPathComponent) from \(u.host ?? s)"; return
            } catch { lastMessage = error.localizedDescription }
        }
        if !want.isEmpty && !leechQueue.contains(magnetText) { leechQueue.append(magnetText) }
        if !fromQueue { lastMessage = "no copy found in the library, drop points or exact sources. Queued: leeching stays on and re-checks every 30 s. RTOR has no peer swarm; seed it on another device's drop point first." }
    }
}
