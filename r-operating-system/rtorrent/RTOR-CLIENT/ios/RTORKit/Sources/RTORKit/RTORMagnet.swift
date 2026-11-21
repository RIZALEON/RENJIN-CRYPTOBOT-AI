import Foundation

/// A parsed magnet: link. Handles urn:btih 40-hex / base32 (BitTorrent v1), 64-hex (the RENJIN records' form),
/// urn:btmh:1220… (BitTorrent v2) and urn:sha256.
public struct RTORMagnet: Codable, Equatable, Sendable {
    public var raw: String
    public var btihV1: String?
    public var btih64: String?
    public var btmhV2: String?
    public var sha256: String?
    public var name: String?
    public var size: Int64?
    public var trackers: [String] = []
    public var sources: [String] = []
    public var problems: [String] = []

    /// The recorded RENJIN Core v3 magnet (records/RTOR-GHOSTCHAIN-TRANSPONDER.md). Use as-is; never rebuild it.
    public static let renjinCoreV3 = "magnet:?xt=urn:btih:3a19e054d6d3718d4f4a87a863dc97b691a7da578f820b8906197820400069c6&xt=urn:sha256:16f9dd002f25a26ddc7df8a6d2ef39ea898326df1414f6139663416ec9eb9b08&dn=RENJIN-CORE-V3.rzl&tr=https://rizal.pw/rtrackr"

    /// RGHOSTCHAIN.rzl (RIZALEON/RENJIN-CRYPTOBOT-AI r-operating-system/rtorrent/UBUNTU-RTOR-GHOSTCHAIN.md @97279b80).
    public static let rghostchainSHA256 = "92d1572a642aa073efa1979000e7705126e8924fbf94403b6617f65a45e81e37"
    public static let rghostchainRaw = "https://raw.githubusercontent.com/RIZALEON/RENJIN-CRYPTOBOT-AI/main/r-operating-system/rtorrent/RGHOSTCHAIN.rzl"
    public static let rghostchainPages = "https://rizaleon.github.io/RENJIN-CRYPTOBOT-AI/r-operating-system/rtorrent/RGHOSTCHAIN.rzl"
    public static let rghostchain = "magnet:?xt=urn:btih:92d1572a642aa073efa1979000e7705126e8924fbf94403b6617f65a45e81e37&dn=RGHOSTCHAIN.rzl&tr=https://rizal.pw/rtrackr"
    /// The same magnet plus the two exact-source links, so a one-tap leech can fetch it (still SHA-256 gated).
    public static var rghostchainLeech: String {
        let enc: (String) -> String = { $0.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? $0 }
        return rghostchain + "&ws=" + enc(rghostchainRaw) + "&as=" + enc(rghostchainPages)
    }

    public var hashes: [String] { [sha256, btih64, btmhV2].compactMap { $0 } }

    static func isHex(_ s: String, _ n: Int) -> Bool { s.count == n && s.allSatisfy { $0.isHexDigit } }

    public init(parsing s: String) throws {
        raw = s.trimmingCharacters(in: .whitespacesAndNewlines)
        guard raw.lowercased().hasPrefix("magnet:?") else { throw RTORError.notMagnet }
        let query = String(raw.dropFirst("magnet:?".count))
        for pair in query.split(separator: "&") {
            let kv = pair.split(separator: "=", maxSplits: 1).map(String.init)
            guard kv.count == 2 else { continue }
            let key = kv[0].split(separator: ".").first.map(String.init) ?? kv[0]
            let v = kv[1].replacingOccurrences(of: "+", with: " ").removingPercentEncoding ?? kv[1]
            let lv = v.lowercased()
            switch key {
            case "xt":
                if lv.hasPrefix("urn:btih:") {
                    let h = String(v.dropFirst(9))
                    if Self.isHex(h, 40) { btihV1 = h.lowercased() }
                    else if h.count == 32, h.uppercased().allSatisfy({ "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567".contains($0) }) { btihV1 = "b32:" + h.uppercased() }
                    else if Self.isHex(h, 64) { btih64 = h.lowercased() }
                    else { problems.append("btih not 40-hex, base32 or 64-hex") }
                } else if lv.hasPrefix("urn:btmh:") {
                    let h = String(lv.dropFirst(9))
                    if h.hasPrefix("1220"), Self.isHex(String(h.dropFirst(4)), 64) { btmhV2 = String(h.dropFirst(4)) }
                    else { problems.append("btmh not a sha2-256 multihash") }
                } else if lv.hasPrefix("urn:sha256:") {
                    let h = String(lv.dropFirst(11))
                    if Self.isHex(h, 64) { sha256 = h } else { problems.append("sha256 not 64-hex") }
                }
            case "dn": name = v
            case "xl": size = Int64(v)
            case "tr": trackers.append(v)
            case "xs", "as", "ws": sources.append(v)
            default: break
            }
        }
        if btihV1 == nil && btih64 == nil && btmhV2 == nil && sha256 == nil { throw RTORError.noHash }
    }

    /// Magnet for a library file: urn:sha256 (+ v1/v2 infohash for torrents), name, size, RTRACKR tracker.
    public static func forFile(sha256: String, name: String, size: Int64, btihV1: String? = nil, btmhV2: String? = nil) -> String {
        var s = "magnet:?xt=urn:sha256:\(sha256)"
        if let b = btihV1 { s += "&xt=urn:btih:\(b)" }
        if let b = btmhV2 { s += "&xt=urn:btmh:1220\(b)" }
        let dn = name.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? name
        return s + "&dn=\(dn)&xl=\(size)&tr=https://rizal.pw/rtrackr"
    }
}

public enum RTORError: LocalizedError {
    case notMagnet, noHash, refused(String), notFound(String), io(String)
    public var errorDescription: String? {
        switch self {
        case .notMagnet: return "not a magnet: link"
        case .noHash: return "magnet has no usable xt hash"
        case .refused(let s): return "refused: " + s
        case .notFound(let s): return s
        case .io(let s): return s
        }
    }
}
