import Foundation
import Combine
import Network
import CryptoKit
import Security
#if os(iOS)
import UIKit
#endif

// RTORKit 0.2.2 — iOS parity with the RTOR GHOSTCHAIN 0.2.2 client (Pixel / Neo / Android, rtor/cmd/rtor-ghostchain/peer.go + reseed.go).
//
// Peer listener on 0.0.0.0:4985 (LAN-only, same wire protocol as the Go client):
//   GET  /peer/v1/hello            {node, device, version, files:[{sha256,name,size}], keepalive_bps}
//   GET  /peer/v1/file/<sha256>    library bytes (Range supported) — a peer leeches from us (our upload)
//   PUT  /peer/v1/file/<sha256>    a peer seeds to us (our download); accepted only if the body's SHA-256 matches
// Peers (Documents/RENJIN/RTOR/peers.json, library peers.json, else Neo 192.168.0.113 · Pixel 192.168.0.206 · Moto 192.168.0.224),
// probed immediately and every 15 s. Then public RTRACKR (https://rizal.pw/rtrackr/data/, download-only).
// Always-on keepalive per file, per direction, paced at 1536 B/s (never below 1 KB/s):
//   seed  = paced PUT of the file to the first reachable peer (else a paced rewrite of a local drop copy)
//   leech = paced Range download from the first peer that has it (else public RTRACKR if listed, else a local drop copy),
//           each chunk SHA-256-checked against the same range of the verified local copy, and the full pass re-verified.
// Every counted byte is a byte actually moved. If nothing is reachable the rate is 0 and the note says why.
// RE-SEED reads the live RGHOSTCHAIN export and clears ONLY when a properly signed block 6 is really there.
// iOS note: the listener and loops run while the host app is in the foreground; iOS suspends them in the background and
// RTORKit restarts them on return. RTORKit holds no key, signs nothing and mints nothing.

public struct RTORPeer: Codable, Hashable, Sendable {
    public var name: String
    public var url: String
    public init(name: String, url: String) { self.name = name; self.url = url }
}

public struct RTORPeerState: Identifiable, Sendable {
    public var id: String { peer.name }
    public var peer: RTORPeer
    public var reachable = false
    public var isSelf = false
    public var node = "", device = "", version = ""
    public var files: Set<String> = []
    public var checked: Date?
    public var err: String?
}

public struct RTORKeepalive: Sendable {
    public var via = "starting"
    public var peer = ""
    public var passes = 0
    public var lastOK: Bool?
    public var note = ""
    public var at: Date?
}

public struct RTORReseed: Sendable {
    public var state = "waiting"          // waiting | pending-faceid | sealed
    public var text = "Waiting for Rizal's RGHOSTKEY tap on the trusted device."
    public var height = 0
    public var tip = ""
    public var source = ""
    public var checked: Date?
    public var unmet: [String] = []
    public var err = ""
}

/// Thread-safe box for values the peer listener (background queue) reads.
final class RTORLocked<T>: @unchecked Sendable {
    private let l = NSLock(); private var v: T
    init(_ v: T) { self.v = v }
    var value: T { get { l.lock(); defer { l.unlock() }; return v } set { l.lock(); v = newValue; l.unlock() } }
}

struct RTORFileRef: Sendable { var sha256: String; var name: String; var size: Int64; var url: URL }

@MainActor
public final class RTORNet: ObservableObject {
    public nonisolated static let version = "0.2.3"
    public nonisolated static let peerPort: UInt16 = 4985
    public nonisolated static let rtrackrData = "https://rizal.pw/rtrackr/data/"
    public nonisolated static let keepaliveBps = 1536          // per file, per direction
    public nonisolated static let floorBps = 1024              // RTORTransfers.minRateBytesPerSecond
    public nonisolated static let defaultPeers = [RTORPeer(name: "neo", url: "http://192.168.0.113:4985"),
                                      RTORPeer(name: "pixel", url: "http://192.168.0.206:4985"),
                                      RTORPeer(name: "moto", url: "http://192.168.0.224:4985")]

    @Published public private(set) var peers: [RTORPeerState] = []
    @Published public private(set) var keepalive: [String: RTORKeepalive] = [:]   // "up|sha" / "down|sha"
    @Published public private(set) var reseed = RTORReseed()
    @Published public private(set) var listenerState = "not started"
    @Published public private(set) var rtrackrSums = 0

    unowned let lib: RTORLibrary
    public let node: String
    var sums: [String: String] = [:]
    var running: Set<String> = []
    var started = false
    var listener: NWListener?
    var tasks: [Task<Void, Never>] = []
    let lq = DispatchQueue(label: "rtor.peer", attributes: .concurrent)
    // read by the listener queue
    let filesBox = RTORLocked<[String: RTORFileRef]>([:])
    let allowBox = RTORLocked<Set<String>>([])
    let nodeBox: String
    nonisolated static let stateBox = RTORLocked<Data>(Data("{}".utf8))

    init(library: RTORLibrary) {
        lib = library
        let p = library.dir.appendingPathComponent("node-id")
        if let s = try? String(contentsOf: p, encoding: .utf8), s.trimmingCharacters(in: .whitespacesAndNewlines).count >= 16 {
            node = s.trimmingCharacters(in: .whitespacesAndNewlines)
        } else {
            var b = [UInt8](repeating: 0, count: 12); _ = SecRandomCopyBytes(kSecRandomDefault, 12, &b)
            node = b.map { String(format: "%02x", $0) }.joined()
            try? (node + "\n").write(to: p, atomically: true, encoding: .utf8)
        }
        nodeBox = node
    }

    // MARK: start / stop

    /// Starts everything immediately (no tap needed): listener, discovery, RTRACKR sums, keepalive supervisor, RE-SEED reader.
    public func start() {
        guard !started else { return }
        started = true
        peers = loadPeers().map { RTORPeerState(peer: $0) }
        allowBox.value = Set(peers.compactMap { URL(string: $0.peer.url)?.host })
        syncFiles()
        startListener()
        tasks.append(Task { @MainActor [weak self] in            // discovery: now, then every 15 s
            while !Task.isCancelled { guard let self else { return }; await self.refresh(); try? await Task.sleep(nanoseconds: 15_000_000_000) }
        })
        tasks.append(Task { @MainActor [weak self] in            // RTRACKR SHA256SUMS: now, then every 10 min
            while !Task.isCancelled { guard let self else { return }; await self.syncSums(); try? await Task.sleep(nanoseconds: 600_000_000_000) }
        })
        tasks.append(Task { @MainActor [weak self] in            // keepalive supervisor + state snapshot
            while !Task.isCancelled {
                guard let self else { return }
                self.syncFiles()
                for it in self.lib.items { self.ensure("up", it.sha256); self.ensure("down", it.sha256) }
                self.publishState()
                try? await Task.sleep(nanoseconds: 1_000_000_000)
            }
        })
        tasks.append(Task { @MainActor [weak self] in            // RE-SEED: every 60 s (10 min once sealed)
            while !Task.isCancelled {
                guard let self else { return }
                let r = await RTORNet.checkReseed(decisionPaths: self.decisionPaths())
                self.reseed = r
                try? await Task.sleep(nanoseconds: r.state == "sealed" ? 600_000_000_000 : 60_000_000_000)
            }
        })
        #if os(iOS)
        NotificationCenter.default.addObserver(forName: UIApplication.willEnterForegroundNotification, object: nil, queue: .main) { [weak self] _ in
            Task { @MainActor in self?.startListener(); await self?.refresh() }
        }
        #endif
    }

    func loadPeers() -> [RTORPeer] {
        struct F: Decodable { var peers: [RTORPeer] }
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        for u in [docs.appendingPathComponent("RENJIN/RTOR/peers.json"), lib.dir.appendingPathComponent("peers.json")] {
            if let d = try? Data(contentsOf: u), let f = try? JSONDecoder().decode(F.self, from: d), !f.peers.isEmpty {
                return f.peers.map { RTORPeer(name: $0.name, url: $0.url.hasSuffix("/") ? String($0.url.dropLast()) : $0.url) }
            }
        }
        return Self.defaultPeers
    }

    func syncFiles() {
        var m: [String: RTORFileRef] = [:]
        for it in lib.items { m[it.sha256] = RTORFileRef(sha256: it.sha256, name: it.name, size: it.size, url: lib.path(it)) }
        filesBox.value = m
    }

    func ref(_ sha: String) -> RTORFileRef? { filesBox.value[sha] }

    // MARK: discovery

    func refresh() async {
        let list = peers.map { $0.peer }
        let me = node
        let results: [(Int, RTORPeerState)] = await withTaskGroup(of: (Int, RTORPeerState).self) { g in
            for (i, p) in list.enumerated() {
                g.addTask {
                    var s = RTORPeerState(peer: p); s.checked = Date()
                    guard let u = URL(string: p.url + "/peer/v1/hello") else { s.err = "bad url"; return (i, s) }
                    var r = URLRequest(url: u); r.timeoutInterval = 2.5
                    do {
                        let (d, resp) = try await URLSession.shared.data(for: r)
                        guard (resp as? HTTPURLResponse)?.statusCode == 200, let j = try JSONSerialization.jsonObject(with: d) as? [String: Any] else { s.err = "bad hello"; return (i, s) }
                        s.reachable = true
                        s.node = j["node"] as? String ?? ""; s.device = j["device"] as? String ?? ""; s.version = j["version"] as? String ?? ""
                        s.isSelf = s.node == me
                        for f in (j["files"] as? [[String: Any]]) ?? [] { if let h = f["sha256"] as? String { s.files.insert(h.lowercased()) } }
                    } catch { s.err = error.localizedDescription }
                    return (i, s)
                }
            }
            var out: [(Int, RTORPeerState)] = []
            for await x in g { out.append(x) }
            return out
        }
        var np = peers
        for (i, s) in results where i < np.count { np[i] = s }
        peers = np
    }

    /// First reachable non-self peer, in list order (optionally one that has sha).
    func livePeer(_ sha: String, mustHave: Bool) -> RTORPeerState? {
        peers.first { $0.reachable && !$0.isSelf && (!mustHave || $0.files.contains(sha)) }
    }

    func syncSums() async {
        guard let u = URL(string: Self.rtrackrData + "SHA256SUMS") else { return }
        var r = URLRequest(url: u); r.timeoutInterval = 20; r.cachePolicy = .reloadIgnoringLocalCacheData
        guard let (d, resp) = try? await URLSession.shared.data(for: r), (resp as? HTTPURLResponse)?.statusCode == 200 else { return }
        sums = RTORLibrary.parseSums(d)
        rtrackrSums = sums.count
    }

    func rtrackrURL(_ sha: String) -> URL? { sums[sha].flatMap { URL(string: Self.rtrackrData + ($0.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? $0)) } }

    // MARK: keepalive loops

    func ensure(_ dir: String, _ sha: String) {
        let k = dir + "|" + sha
        guard !running.contains(k) else { return }
        running.insert(k)
        keepalive[k] = RTORKeepalive()
        tasks.append(Task.detached(priority: .utility) { [weak self] in
            while !Task.isCancelled {
                guard let self else { return }
                guard await self.ref(sha) != nil else { await MainActor.run { _ = self.running.remove(k) }; return }
                let ka = dir == "up" ? await self.seedPass(sha) : await self.leechPass(sha)
                await MainActor.run {
                    var n = ka; let old = self.keepalive[k]
                    n.passes = (old?.passes ?? 0) + (ka.lastOK != nil ? 1 : 0); n.at = Date()
                    self.keepalive[k] = n
                }
                if ka.lastOK == nil { try? await Task.sleep(nanoseconds: 3_000_000_000) }   // nothing reachable: retry soon, rate truthfully 0
            }
        })
    }

    public func state(_ dir: RTORDirection, _ item: RTORItem) -> RTORKeepalive? { keepalive[(dir == .up ? "up|" : "down|") + item.sha256] }

    nonisolated static func pace(_ start: Date, _ n: Int) async {
        let want = Double(n) / Double(keepaliveBps)
        let el = Date().timeIntervalSince(start)
        if el < want { try? await Task.sleep(nanoseconds: UInt64((want - el) * 1_000_000_000)) }
    }

    func count(_ dir: RTORDirection, _ sha: String, _ n: Int, _ t0: Date) { lib.record(dir, sha, bytes: n, since: t0) }

    nonisolated func seedPass(_ sha: String) async -> RTORKeepalive {
        guard let it = await ref(sha) else { return RTORKeepalive(via: "none", note: "not in library") }
        if let p = await livePeer(sha, mustHave: false), let base = URL(string: p.peer.url) {
            guard let d = try? Data(contentsOf: it.url, options: .mappedIfSafe) else { return RTORKeepalive(via: "none", note: "library read failed") }
            let q = it.name.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "file"
            do {
                let (code, body) = try await RTORRawHTTP.pacedPut(host: base.host ?? "", port: UInt16(base.port ?? 4985), path: "/peer/v1/file/\(sha)?name=\(q)", body: d) { n, t0 in
                    await self.count(.up, sha, n, t0)
                }
                let j = (try? JSONSerialization.jsonObject(with: body)) as? [String: Any]
                let ok = code == 200 && (j?["ok"] as? Bool ?? false) && RTORHash.sha256(d) == sha
                return RTORKeepalive(via: "peer", peer: "\(p.peer.name) (\(p.peer.url))", lastOK: ok,
                                     note: ok ? "peer verified the SHA-256 of the full pass" : "peer refused: \(j?["refused"] as? String ?? "http \(code)")")
            } catch { return RTORKeepalive(via: "peer", peer: p.peer.name, note: "upload failed: \(error.localizedDescription)") }
        }
        for drop in await lib.drops where drop.reachable {
            let dst = drop.url.appendingPathComponent("\(sha.prefix(12))-\(it.name)")
            let part = dst.appendingPathExtension("part")
            guard let d = try? Data(contentsOf: it.url, options: .mappedIfSafe) else { break }
            FileManager.default.createFile(atPath: part.path, contents: nil)
            guard let h = try? FileHandle(forWritingTo: part) else { continue }
            let t0 = Date(); var sent = 0; var hs = SHA256()
            while sent < d.count {
                let c = d.subdata(in: sent..<min(sent + 512, d.count))
                do { try h.write(contentsOf: c) } catch { break }
                hs.update(data: c); sent += c.count
                let tc = Date(); await count(.up, sha, c.count, tc)
                await Self.pace(t0, sent)
            }
            try? h.close()
            let ok = sent == d.count && hs.finalize().map { String(format: "%02x", $0) }.joined() == sha
            if ok { _ = try? FileManager.default.replaceItemAt(dst, withItemAt: part) } else { try? FileManager.default.removeItem(at: part) }
            return RTORKeepalive(via: "local-drop", peer: drop.name, lastOK: ok, note: "no reachable peer; seeding to this device's drop point (local)")
        }
        return RTORKeepalive(via: "none", note: "no reachable peer or drop point — seed rate is 0 until one answers")
    }

    nonisolated func leechPass(_ sha: String) async -> RTORKeepalive {
        guard let it = await ref(sha), let local = try? Data(contentsOf: it.url, options: .mappedIfSafe) else { return RTORKeepalive(via: "none", note: "not in library") }
        var via = "", name = "", url: URL?, dropData: Data?
        if let p = await livePeer(sha, mustHave: true) { via = "peer"; name = "\(p.peer.name) (\(p.peer.url))"; url = URL(string: p.peer.url + "/peer/v1/file/" + sha) }
        else if let u = await rtrackrURL(sha) { via = "rtrackr-public"; name = "rizal.pw/rtrackr"; url = u }
        else {
            for drop in await lib.drops {
                let p = drop.url.appendingPathComponent("\(sha.prefix(12))-\(it.name)")
                if let d = try? Data(contentsOf: p, options: .mappedIfSafe), Int64(d.count) == it.size { via = "local-drop"; name = drop.name; dropData = d; break }
            }
        }
        if via.isEmpty { return RTORKeepalive(via: "none", note: "no reachable peer has this file, it is not on public RTRACKR, and no drop copy exists — leech rate is 0") }
        let chunk = Self.keepaliveBps
        let t0 = Date(); var got = 0; var hs = SHA256()
        let ses = URLSession(configuration: { let c = URLSessionConfiguration.ephemeral; c.timeoutIntervalForRequest = 30; return c }())
        defer { ses.finishTasksAndInvalidate() }
        var off = 0
        while off < local.count {
            let want = min(chunk, local.count - off)
            var b: Data
            if let dd = dropData { b = dd.subdata(in: off..<off + want) }
            else {
                var r = URLRequest(url: url!); r.setValue("bytes=\(off)-\(off + want - 1)", forHTTPHeaderField: "Range"); r.cachePolicy = .reloadIgnoringLocalCacheData
                do {
                    let (d, resp) = try await ses.data(for: r)
                    let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
                    guard code == 206 || (code == 200 && off == 0 && d.count >= want) else { return RTORKeepalive(via: via, peer: name, note: "range request http \(code)") }
                    b = d.count > want ? d.prefix(want) : d
                } catch { return RTORKeepalive(via: via, peer: name, note: "download failed: \(error.localizedDescription)") }
            }
            if b.isEmpty { return RTORKeepalive(via: via, peer: name, lastOK: false, note: "empty chunk at \(off)") }
            got += b.count; hs.update(data: b)
            let tc = Date(); await count(.down, sha, b.count, tc)
            // chunk check against the same range of the verified local copy
            if b != local.subdata(in: off..<off + b.count) { return RTORKeepalive(via: via, peer: name, lastOK: false, note: "chunk at \(off) failed its SHA-256 check") }
            off += b.count
            await Self.pace(t0, got)
        }
        let ok = hs.finalize().map { String(format: "%02x", $0) }.joined() == sha
        return RTORKeepalive(via: via, peer: name, lastOK: ok, note: "full pass re-verified by SHA-256")
    }

    // MARK: peer listener (LAN only)

    func startListener() {
        if let l = listener, l.state == .ready { return }
        listener?.cancel(); listener = nil
        do {
            let params = NWParameters.tcp; params.allowLocalEndpointReuse = true
            let l = try NWListener(using: params, on: NWEndpoint.Port(rawValue: Self.peerPort)!)
            l.stateUpdateHandler = { [weak self] st in
                Task { @MainActor in
                    switch st {
                    case .ready: self?.listenerState = "listening on 0.0.0.0:\(RTORNet.peerPort) (LAN peers)"
                    case .failed(let e): self?.listenerState = "port \(RTORNet.peerPort) unavailable (\(e.localizedDescription)) — another app on this phone may hold it"; self?.listener = nil
                    case .cancelled: self?.listenerState = "stopped"
                    default: break
                    }
                }
            }
            l.newConnectionHandler = { [weak self] c in self?.accept(c) }
            l.start(queue: lq)
            listener = l
        } catch { listenerState = "port \(Self.peerPort) unavailable: \(error.localizedDescription)" }
    }

    nonisolated static func lanHost(_ e: NWEndpoint) -> String? {
        guard case let .hostPort(h, _) = e else { return nil }
        switch h {
        case .ipv4(let a):
            let b = [UInt8](a.rawValue)
            guard b.count == 4 else { return nil }
            let ok = b[0] == 10 || b[0] == 127 || (b[0] == 172 && (16...31).contains(b[1])) || (b[0] == 192 && b[1] == 168) || (b[0] == 169 && b[1] == 254)
            return ok ? b.map(String.init).joined(separator: ".") : nil
        case .ipv6(let a):
            let b = [UInt8](a.rawValue)
            if let v4 = a.asIPv4 { return lanHost(.hostPort(host: .ipv4(v4), port: 1)) }
            let ok = a == .loopback || (b.first.map { $0 & 0xfe == 0xfc } ?? false) || (b.count > 1 && b[0] == 0xfe && b[1] & 0xc0 == 0x80)
            return ok ? "\(a)" : nil
        default: return nil
        }
    }

    nonisolated func accept(_ c: NWConnection) {
        c.start(queue: lq)
        guard let host = Self.lanHost(c.endpoint) else { RTORRawHTTP.respond(c, 403, "text/plain", Data("LAN peers only".utf8)); return }
        RTORRawHTTP.readRequest(c, maxBody: 64 << 20) { [weak self] req in
            guard let self, let req else { c.cancel(); return }
            self.handle(c, host, req)
        }
    }

    nonisolated func handle(_ c: NWConnection, _ host: String, _ r: RTORRawHTTP.Request) {
        let path = r.path.components(separatedBy: "?")[0]
        if path == "/peer/v1/hello" {
            let files = filesBox.value.values.sorted { $0.name < $1.name }.map { ["sha256": $0.sha256, "name": $0.name, "size": $0.size] as [String: Any] }
            #if os(iOS)
            let dev = "17e-ios"
            #else
            let dev = "apple"
            #endif
            let o: [String: Any] = ["node": nodeBox, "device": dev, "version": Self.version, "files": files, "keepalive_bps": Self.keepaliveBps]
            RTORRawHTTP.respond(c, 200, "application/json", (try? JSONSerialization.data(withJSONObject: o)) ?? Data()); return
        }
        guard path.hasPrefix("/peer/v1/file/") else { RTORRawHTTP.respond(c, 404, "text/plain", Data("not found".utf8)); return }
        let sha = String(path.dropFirst("/peer/v1/file/".count)).lowercased()
        guard sha.count == 64, RTORMagnet.isHex(sha, 64) else { RTORRawHTTP.respond(c, 400, "text/plain", Data("bad sha".utf8)); return }
        switch r.method {
        case "GET", "HEAD":
            guard let f = filesBox.value[sha], let d = try? Data(contentsOf: f.url, options: .mappedIfSafe) else { RTORRawHTTP.respond(c, 404, "text/plain", Data("not found".utf8)); return }
            var lo = 0, hi = d.count - 1, partial = false
            if let rg = r.headers["range"], rg.hasPrefix("bytes=") {
                let p = rg.dropFirst(6).split(separator: "-", omittingEmptySubsequences: false)
                if p.count == 2 {
                    if p[0].isEmpty, let n = Int(p[1]) { lo = max(0, d.count - n) } else { lo = Int(p[0]) ?? 0; if let h = Int(p[1]) { hi = min(h, d.count - 1) } }
                    partial = true
                }
            }
            guard lo <= hi, lo < d.count else { RTORRawHTTP.respond(c, 416, "text/plain", Data(), extra: "Content-Range: bytes */\(d.count)\r\n"); return }
            let body = r.method == "HEAD" ? Data() : d.subdata(in: lo..<hi + 1)
            let t0 = Date()
            RTORRawHTTP.respond(c, partial ? 206 : 200, "application/octet-stream", body,
                                extra: "Accept-Ranges: bytes\r\n" + (partial ? "Content-Range: bytes \(lo)-\(hi)/\(d.count)\r\n" : "")) {
                if !body.isEmpty { Task { @MainActor [weak self] in self?.count(.up, sha, body.count, t0) } }
            }
        case "PUT":
            let known = filesBox.value[sha] != nil
            guard known || allowBox.value.contains(host) else { RTORRawHTTP.respond(c, 403, "text/plain", Data("unknown sha from a non-listed peer".utf8)); return }
            let b = r.body, t0 = r.started
            Task { @MainActor [weak self] in self?.count(.down, sha, b.count, t0) }
            guard RTORHash.sha256(b) == sha else {
                RTORRawHTTP.respond(c, 422, "application/json", Data(#"{"ok":false,"refused":"SHA-256 mismatch; discarded"}"#.utf8)); return
            }
            if known { RTORRawHTTP.respond(c, 200, "application/json", Data(#"{"ok":true,"verified":true,"stored":"already in library (keepalive pass verified)"}"#.utf8)); return }
            var name = ((r.path.components(separatedBy: "name=").dropFirst().first ?? "").components(separatedBy: "&")[0]).removingPercentEncoding ?? ""
            name = (name as NSString).lastPathComponent
            if name.isEmpty || name == "." { name = String(sha.prefix(12)) }
            let nm = name
            Task { @MainActor [weak self] in
                guard let self else { return }
                var o: [String: Any] = ["verified": true]
                do { _ = try self.lib.importData(b, name: nm, source: "peer:" + host); o["ok"] = true; o["stored"] = "imported" }
                catch { o["ok"] = false; o["refused"] = error.localizedDescription }
                self.syncFiles()
                RTORRawHTTP.respond(c, 200, "application/json", (try? JSONSerialization.data(withJSONObject: o)) ?? Data())
            }
        default:
            RTORRawHTTP.respond(c, 405, "text/plain", Data("method".utf8))
        }
    }

    // MARK: RE-SEED (reads the live RGHOSTCHAIN; never signs)

    nonisolated static let rsPrev = "4006b570883c31aff44891971dd1935a3a58a822293f919ace27e59d8cf0bb5b"
    nonisolated static let rsPin = "6D:8A:57:30:9D:3F:56:29:9E:4F:B5:DD:0D:35:4C:2E:3A:68:4A:0E:FC:E8:DF:C8:32:05:8E:4F:DD:DA:16:C3"
    nonisolated static let rsCert = "2b112834"
    nonisolated static let rsAsset = "70b9d3d0223619d5c06d2cdf7710b783fd456adbadc47e65179130ea956303c0"
    nonisolated static let rsRID = "ЯID-2004-W7P8"
    nonisolated static let rsDecision = "rmail-dec-rghostkey-superkey-20261120-t224u.json"

    func decisionPaths() -> [URL] {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        return [lib.dir.appendingPathComponent(Self.rsDecision),
                docs.appendingPathComponent("ЯLAB/RKLOWD/nodes/17e/inbox/" + Self.rsDecision),
                docs.appendingPathComponent("ЯLAB/RKLOWD/nodes/17e/outbox/" + Self.rsDecision),
                docs.appendingPathComponent("RENJIN/RTOR/" + Self.rsDecision)]
    }

    nonisolated static func checkReseed(decisionPaths: [URL]) async -> RTORReseed {
        var r = RTORReseed(); r.checked = Date()
        let src = rtrackrData + "rghostchain.json"
        var blocks: [[String: Any]] = []
        if let u = URL(string: src) {
            var q = URLRequest(url: u); q.timeoutInterval = 20; q.cachePolicy = .reloadIgnoringLocalCacheData
            do {
                let (d, resp) = try await URLSession.shared.data(for: q)
                let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
                if code != 200 { r.err = "\(src): http \(code)" }
                else if let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any], let b = j["blocks"] as? [[String: Any]] { blocks = b; r.source = src }
                else { r.err = "\(src): not a chain export" }
            } catch { r.err = "\(src): \(error.localizedDescription)" }
        }
        if !blocks.isEmpty { r.height = blocks.count - 1; r.tip = blocks.last?["hash"] as? String ?? "" }
        if let b6 = blocks.last(where: { ($0["index"] as? NSNumber)?.intValue == 6 }) {
            r.unmet = sealUnmet(b6)
            if r.unmet.isEmpty { r.state = "sealed"; r.text = "RGHOSTKEY sealed · block 6"; return r }
        } else { r.unmet = ["no block 6 on the chain yet"] }
        if decisionApproved(decisionPaths) { r.state = "pending-faceid"; r.text = "RGHOSTKEY pending Face ID — approval recorded, waiting for the sealed block 6 on the chain." }
        return r
    }

    nonisolated static func sealUnmet(_ b: [String: Any]) -> [String] {
        var un: [String] = []
        let p = b["payload"] as? [String: Any] ?? [:]
        if (b["prev_hash"] as? String) != rsPrev { un.append("prev_hash is not the block-5 tip") }
        if (p["unsigned"] as? Bool) == true { un.append("payload.unsigned is true") }
        if ((p["item"] as? String)?.lowercased() != "rghostkey") && (p["rid"] as? String) != rsRID { un.append("item is not rghostkey and rid is not " + rsRID) }
        if ((p["ghostkey_pin_sha256_fp"] as? String) ?? "").uppercased() != rsPin { un.append("ghostkey_pin_sha256_fp does not match") }
        if !hasCertSHA(p) { un.append("no cert SHA-256 starting " + rsCert) }
        if ((p["asset_hash"] as? String) ?? "").lowercased() != rsAsset { un.append("asset_hash does not match") }
        if let e = sigError(b) { un.append("sig does not verify: " + e) }
        return un
    }

    nonisolated static func hasCertSHA(_ v: Any) -> Bool {
        if let m = v as? [String: Any] {
            for (k, y) in m {
                if let s = y as? String, k.lowercased().contains("cert"), s.lowercased().replacingOccurrences(of: ":", with: "").hasPrefix(rsCert) { return true }
                if hasCertSHA(y) { return true }
            }
        } else if let a = v as? [Any] { return a.contains { hasCertSHA($0) } }
        return false
    }

    nonisolated static func decodeB(_ s: String) -> Data? {
        let t = s.trimmingCharacters(in: .whitespacesAndNewlines)
        if t.count % 2 == 0, RTORMagnet.isHex(t.lowercased(), t.count) {
            var d = Data(); var i = t.startIndex
            while i < t.endIndex { let j = t.index(i, offsetBy: 2); guard let v = UInt8(t[i..<j], radix: 16) else { return nil }; d.append(v); i = j }
            return d
        }
        var b = t.replacingOccurrences(of: "-", with: "+").replacingOccurrences(of: "_", with: "/")
        while b.count % 4 != 0 { b += "=" }
        return Data(base64Encoded: b)
    }

    nonisolated static let p256SPKIPrefix: [UInt8] = [0x30, 0x59, 0x30, 0x13, 0x06, 0x07, 0x2a, 0x86, 0x48, 0xce, 0x3d, 0x02, 0x01, 0x06, 0x08, 0x2a, 0x86, 0x48, 0xce, 0x3d, 0x03, 0x01, 0x07, 0x03, 0x42, 0x00]

    /// SPKI DER of the public key inside an X.509 certificate (P-256 only).
    nonisolated static func certSPKI(_ der: Data) -> Data? {
        guard let c = SecCertificateCreateWithData(nil, der as CFData), let k = SecCertificateCopyKey(c),
              let x = SecKeyCopyExternalRepresentation(k, nil) as Data?, x.count == 65 else { return nil }
        return Data(p256SPKIPrefix) + x
    }

    nonisolated static func sigError(_ b: [String: Any]) -> String? {
        guard let sg = b["sig"] as? [String: Any] else { return "no sig" }
        let val = sg["value"] as? String ?? ""
        if val.isEmpty || val == "unsigned" { return "unsigned" }
        guard let sig = decodeB(val) else { return "sig value not hex/base64" }
        var keys: [Data] = []
        let p = b["payload"] as? [String: Any] ?? [:]
        for m in [sg, p] {
            for (k, v) in m {
                guard let s = v as? String else { continue }
                let lk = k.lowercased()
                if lk.contains("pubkey") || lk.contains("public_key") || lk.contains("spki"), let d = decodeB(s) { keys.append(d) }
                if lk.contains("cert") && !lk.contains("sha") {
                    var der: Data?
                    if s.contains("-----BEGIN") {
                        let body = s.components(separatedBy: "\n").filter { !$0.hasPrefix("-----") }.joined()
                        der = Data(base64Encoded: body)
                    } else { der = decodeB(s) }
                    if let der, let spki = certSPKI(der) { keys.append(spki) }
                }
            }
        }
        let h = b["hash"] as? String ?? ""
        var msgs = [Data(h.utf8)]
        if let raw = decodeB(h), raw.count == 32 { msgs.append(raw) }
        let pin = rsPin.replacingOccurrences(of: ":", with: "").lowercased()
        var pinned = false
        for k in keys {
            guard SHA256.hash(data: k).map({ String(format: "%02x", $0) }).joined() == pin else { continue }
            pinned = true
            guard let pk = try? P256.Signing.PublicKey(derRepresentation: k) else { continue }
            for m in msgs {
                if let s = try? P256.Signing.ECDSASignature(derRepresentation: sig), pk.isValidSignature(s, for: m) { return nil }
                if sig.count == 64, let s = try? P256.Signing.ECDSASignature(rawRepresentation: sig), pk.isValidSignature(s, for: m) { return nil }
            }
        }
        return pinned ? "signature does not match the block hash" : "no public key in the block matches the pinned SPKI SHA-256"
    }

    nonisolated static func decisionApproved(_ paths: [URL]) -> Bool {
        for u in paths {
            guard let d = try? Data(contentsOf: u), let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any] else { continue }
            for k in ["decision", "action", "answer", "status", "verdict"] { if let s = j[k] as? String, s.lowercased().contains("approve") { return true } }
            if (j["approve"] as? Bool) == true || (j["approved"] as? Bool) == true { return true }
        }
        return false
    }

    // MARK: JSON state for web hosts (RDRAGON GHOSTMACHINE panel) — readable from any thread

    func publishState() {
        let iso = ISO8601DateFormatter()
        var files: [[String: Any]] = []
        for it in lib.items {
            let up = lib.rate(.up, it), dn = lib.rate(.down, it)
            func ka(_ d: RTORDirection) -> [String: Any] {
                guard let k = state(d, it) else { return [:] }
                var o: [String: Any] = ["via": k.via, "peer": k.peer, "passes": k.passes, "note": k.note]
                if let ok = k.lastOK { o["last_pass_sha_ok"] = ok }
                return o
            }
            files.append(["name": it.name, "sha256": it.sha256, "size": it.size, "type": it.type.rawValue, "magnet": it.magnet,
                          "up_bps": up.bytesPerSecond, "down_bps": dn.bytesPerSecond, "up_total": up.totalBytes, "down_total": dn.totalBytes,
                          "keepalive_up": ka(.up), "keepalive_down": ka(.down)])
        }
        let ps: [[String: Any]] = peers.map { ["name": $0.peer.name, "url": $0.peer.url, "reachable": $0.reachable, "self": $0.isSelf, "device": $0.device,
                                                "version": $0.version, "files": $0.files.count, "err": $0.err ?? ""] }
        let rs: [String: Any] = ["state": reseed.state, "text": reseed.text, "chain_height": reseed.height, "chain_tip": reseed.tip, "source": reseed.source,
                                 "checked": reseed.checked.map { iso.string(from: $0) } ?? "", "unmet": reseed.unmet, "err": reseed.err]
        let o: [String: Any] = ["version": Self.version, "node": node, "listener": listenerState, "keepalive_bps": Self.keepaliveBps, "floor_bps": Self.floorBps,
                                "rtrackr_sums": rtrackrSums, "files": files, "peers": ps, "reseed": rs, "message": lib.lastMessage,
                                "leech_queue": lib.leechQueue, "rid": lib.space?.rid ?? "", "space": lib.space?.space ?? ""]
        if let d = try? JSONSerialization.data(withJSONObject: o) { Self.stateBox.value = d }
    }

    /// Latest RTOR state as JSON (any thread). Hosts serve it to a web panel.
    public nonisolated static func stateJSON() -> Data { stateBox.value }
}

/// Minimal HTTP/1.1 over Network.framework: request reader for the peer listener and a paced PUT client
/// (so the seed keepalive moves real bytes at the 1536 B/s pace instead of one burst).
enum RTORRawHTTP {
    struct Request { var method: String; var path: String; var headers: [String: String]; var body: Data; var started: Date }

    static func readRequest(_ c: NWConnection, maxBody: Int, _ done: @escaping (Request?) -> Void) {
        let t0 = Date()
        func loop(_ buf: Data) {
            c.receive(minimumIncompleteLength: 1, maximumLength: 65536) { d, _, fin, err in
                var b = buf; if let d { b.append(d) }
                if let r = b.range(of: Data("\r\n\r\n".utf8)) {
                    let head = String(decoding: b[..<r.lowerBound], as: UTF8.self).components(separatedBy: "\r\n")
                    let parts = head.first?.split(separator: " ") ?? []
                    var h: [String: String] = [:]
                    for l in head.dropFirst() { if let i = l.firstIndex(of: ":") { h[l[..<i].lowercased()] = l[l.index(after: i)...].trimmingCharacters(in: .whitespaces) } }
                    let len = Int(h["content-length"] ?? "0") ?? 0
                    if len > maxBody { done(nil); return }
                    let body = b[r.upperBound...]
                    if body.count >= len {
                        done(Request(method: parts.count > 0 ? String(parts[0]) : "GET", path: parts.count > 1 ? String(parts[1]) : "/", headers: h, body: Data(body.prefix(len)), started: t0)); return
                    }
                }
                if fin || err != nil || b.count > maxBody + 65536 { done(nil); return }
                loop(b)
            }
        }
        loop(Data())
    }

    static func respond(_ c: NWConnection, _ code: Int, _ type: String, _ body: Data, extra: String = "", sent: (() -> Void)? = nil) {
        let reason = [200: "OK", 206: "Partial Content", 400: "Bad Request", 403: "Forbidden", 404: "Not Found", 405: "Method Not Allowed", 416: "Range Not Satisfiable", 422: "Unprocessable Entity"][code] ?? "OK"
        let h = "HTTP/1.1 \(code) \(reason)\r\nContent-Type: \(type)\r\nContent-Length: \(body.count)\r\n\(extra)Connection: close\r\n\r\n"
        c.send(content: Data(h.utf8) + body, completion: .contentProcessed { e in if e == nil { sent?() }; c.cancel() })
    }

    struct Err: LocalizedError { var errorDescription: String? }

    /// PUT `body` to http://host:port/path in 512-byte pieces paced at RTORNet.keepaliveBps; onChunk is called per piece actually sent.
    static func pacedPut(host: String, port: UInt16, path: String, body: Data, onChunk: @escaping @Sendable (Int, Date) async -> Void) async throws -> (Int, Data) {
        let c = NWConnection(host: NWEndpoint.Host(host), port: NWEndpoint.Port(rawValue: port)!, using: .tcp)
        let q = DispatchQueue(label: "rtor.put")
        defer { c.cancel() }
        try await withCheckedThrowingContinuation { (k: CheckedContinuation<Void, Error>) in
            let flag = RTORLocked(false)
            c.stateUpdateHandler = { st in
                guard !flag.value else { return }
                switch st {
                case .ready: flag.value = true; k.resume()
                case .failed(let e): flag.value = true; k.resume(throwing: e)
                case .waiting(let e): flag.value = true; k.resume(throwing: e)
                case .cancelled: flag.value = true; k.resume(throwing: Err(errorDescription: "cancelled"))
                default: break
                }
            }
            c.start(queue: q)
        }
        func send(_ d: Data) async throws {
            try await withCheckedThrowingContinuation { (k: CheckedContinuation<Void, Error>) in
                c.send(content: d, completion: .contentProcessed { e in if let e { k.resume(throwing: e) } else { k.resume() } })
            }
        }
        try await send(Data("PUT \(path) HTTP/1.1\r\nHost: \(host):\(port)\r\nContent-Type: application/octet-stream\r\nContent-Length: \(body.count)\r\nConnection: close\r\n\r\n".utf8))
        let t0 = Date(); var sent = 0
        while sent < body.count {
            let piece = body.subdata(in: sent..<min(sent + 512, body.count))
            let tc = Date()
            try await send(piece)
            sent += piece.count
            await onChunk(piece.count, tc)
            await RTORNet.pace(t0, sent)
        }
        var resp = Data()
        while true {
            let (d, fin): (Data?, Bool) = try await withCheckedThrowingContinuation { k in
                c.receive(minimumIncompleteLength: 1, maximumLength: 65536) { d, _, fin, e in
                    if let e { k.resume(throwing: e) } else { k.resume(returning: (d, fin)) }
                }
            }
            if let d { resp.append(d) }
            if fin || resp.count > 1 << 20 || (d == nil) { break }
            if let r = resp.range(of: Data("\r\n\r\n".utf8)) {
                let head = String(decoding: resp[..<r.lowerBound], as: UTF8.self).lowercased()
                if let cl = head.components(separatedBy: "\r\n").first(where: { $0.hasPrefix("content-length:") }), let n = Int(cl.dropFirst(15).trimmingCharacters(in: .whitespaces)), resp.count - r.upperBound >= n { break }
            }
        }
        guard let r = resp.range(of: Data("\r\n\r\n".utf8)) else { throw Err(errorDescription: "no HTTP response") }
        let status = String(decoding: resp[..<r.lowerBound], as: UTF8.self).split(separator: " ")
        return (status.count > 1 ? Int(status[1]) ?? 0 : 0, Data(resp[r.upperBound...]))
    }
}
