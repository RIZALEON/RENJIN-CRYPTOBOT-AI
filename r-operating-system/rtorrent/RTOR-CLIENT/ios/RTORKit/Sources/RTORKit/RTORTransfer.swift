import Foundation

/// Measured transfer rates for always-on seeding (upload into drop points) and leeching (download from drops / sources).
/// Real byte counters over a sliding window; nothing is estimated. Idle = 0 B/s with the note "idle — no peer/drop transfer".
public enum RTORDirection: String, Sendable { case up, down }

public struct RTORRate: Sendable {
    public var on: Bool = true            // always on (no off state)
    public var bytesPerSecond: Double = 0 // sliding window
    public var totalBytes: Int64 = 0
    public var lastBytes: Int64?
    public var lastBytesPerSecond: Double?
    public var note: String? { bytesPerSecond == 0 ? "idle — no peer/drop transfer" : nil }
}

final class RTORMeter {
    var samples: [(Date, Int64)] = []
    var total: Int64 = 0
    var last: (Int64, Double)?
    func add(_ n: Int64, seconds: Double) {
        samples.append((Date(), n)); total += n
        last = (n, Double(n) / max(seconds, 1e-6))
        prune()
    }
    func prune() { let cut = Date().addingTimeInterval(-RTORTransfers.window); samples.removeAll { $0.0 < cut } }
}

public enum RTORTransfers {
    public static let window: TimeInterval = 10
    /// Any per-direction throttle is held at 1 KB/s or more. RTORKit writes are local and unthrottled (limit 0 = unlimited).
    public static let minRateBytesPerSecond: Int64 = 1024
    public static func clampLimit(_ v: Int64) -> Int64 { v <= 0 ? 0 : max(v, minRateBytesPerSecond) }
    public static let alwaysOnInterval: UInt64 = 30
}

extension RTORLibrary {
    func meter(_ dir: RTORDirection, _ key: String) -> RTORMeter {
        if dir == .up { if let m = upMeters[key] { return m }; let m = RTORMeter(); upMeters[key] = m; return m }
        if let m = downMeters[key] { return m }; let m = RTORMeter(); downMeters[key] = m; return m
    }

    func record(_ dir: RTORDirection, _ key: String, bytes: Int, since start: Date) {
        meter(dir, key).add(Int64(bytes), seconds: Date().timeIntervalSince(start))
        rateTick &+= 1
    }

    /// The measured rate for one file in one direction.
    public func rate(_ dir: RTORDirection, _ item: RTORItem) -> RTORRate {
        var r = RTORRate()
        for k in [item.sha256, item.btmhV2].compactMap({ $0 }) {
            guard let m = (dir == .up ? upMeters[k] : downMeters[k]) else { continue }
            m.prune()
            r.bytesPerSecond += Double(m.samples.reduce(Int64(0)) { $0 + $1.1 }) / RTORTransfers.window
            r.totalBytes += m.total
            if let l = m.last { r.lastBytes = l.0; r.lastBytesPerSecond = l.1 }
        }
        return r
    }

    /// Seeding keeps a verified copy in every reachable drop point (no RMAIL announce; that stays on the Seed button).
    public func ensureSeeded() {
        for it in items {
            for drop in drops where drop.reachable {
                let dst = drop.url.appendingPathComponent("\(it.sha256.prefix(12))-\(it.name)")
                if let a = try? FileManager.default.attributesOfItem(atPath: dst.path), (a[.size] as? NSNumber)?.int64Value == it.size { continue }
                guard let d = try? Data(contentsOf: path(it)), RTORHash.sha256(d) == it.sha256 else { break }
                let t0 = Date()
                guard (try? d.write(to: dst, options: .atomic)) != nil else { continue }
                record(.up, it.sha256, bytes: d.count, since: t0)
                if let i = items.firstIndex(where: { $0.sha256 == it.sha256 }), !items[i].seededTo.contains(dst.path) { items[i].seededTo.append(dst.path); save() }
            }
        }
    }

    /// Starts the always-on loop: seed pass + re-check of queued magnets every 30 s. Safe to call more than once.
    public func startAlwaysOn() {
        guard alwaysOnTask == nil else { return }
        alwaysOnTask = Task { @MainActor [weak self] in
            while !Task.isCancelled {
                guard let self else { return }
                self.ensureSeeded()
                for m in self.leechQueue { await self.leech(m, fromQueue: true) }
                try? await Task.sleep(nanoseconds: RTORTransfers.alwaysOnInterval * 1_000_000_000)
            }
        }
    }
}
