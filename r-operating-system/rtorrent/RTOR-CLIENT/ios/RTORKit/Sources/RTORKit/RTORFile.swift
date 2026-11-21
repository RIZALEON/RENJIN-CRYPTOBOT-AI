import Foundation
import CryptoKit
import UniformTypeIdentifiers

public enum RTORFileType: String, Codable, Sendable {
    case rzl, cryptoJSON = "crypto-json", cryptoPEM = "crypto-pem", rtor, torrent, magnet, file
}

public extension UTType {
    static let rtorRZL = UTType(exportedAs: "info.rizal.rzl", conformingTo: .data)
    static let rtorRTOR = UTType(exportedAs: "info.rizal.rtor", conformingTo: .json)
    static let rtorMagnetFile = UTType(exportedAs: "info.rizal.magnet", conformingTo: .plainText)
    static let rtorTorrent = UTType(importedAs: "org.bittorrent.torrent", conformingTo: .data)
    static let rtorPEM = UTType(importedAs: "info.rizal.pem", conformingTo: .text)
    /// Everything RTOR opens (the file picker also allows any file — RTOR seeds any file).
    static let rtorOpenable: [UTType] = [.rtorRZL, .rtorRTOR, .rtorMagnetFile, .rtorTorrent, .rtorPEM, .x509Certificate, .json, .data, .item]
}

/// Published RTOR-INSTALL fingerprints.
public let rtorPublishedRZL: [String: String] = [
    "RENJIN-COMPONENT.rzl": "67a8c186f45de7359db1ff2c4385dceaeeda9d4d4ace5e79a1024ddb3184f5aa",
    "RENJIN-KUBO.rzl": "04b7b1e27d2198bce73936f0e96c09ce90e96fef0d06505f03c232bce98b3a97",
]

public enum RTORHash {
    public static func sha256(_ d: Data) -> String { SHA256.hash(data: d).map { String(format: "%02x", $0) }.joined() }
    public static func sha1(_ d: Data) -> String { Insecure.SHA1.hash(data: d).map { String(format: "%02x", $0) }.joined() }
}

public struct RTORClassified {
    public var type: RTORFileType
    public var btihV1: String?
    public var btmhV2: String?
    public var detail: [String: String] = [:]
    public var verified: [RTORVerify] = []
}

enum RTORClassifier {
    static let privateBlock = try! NSRegularExpression(pattern: "-----BEGIN [A-Z ]*PRIVATE KEY-----|-----BEGIN OPENSSH PRIVATE KEY-----|-----BEGIN PGP PRIVATE KEY BLOCK-----", options: [.caseInsensitive])
    static let privateField = try! NSRegularExpression(pattern: "^(private_?key|privkey|priv|secret(_?key)?|seed(_?hex|_?phrase)?|mnemonic|xprv|wif|keystore|ciphertext|passphrase|password|signing_?key|sk|d)$", options: [.caseInsensitive])

    static func matches(_ rx: NSRegularExpression, _ s: String) -> Bool {
        rx.firstMatch(in: s, range: NSRange(s.startIndex..., in: s)) != nil
    }

    static func privateHits(_ v: Any, _ path: String, _ hits: inout [String]) {
        if let m = v as? [String: Any] {
            for (k, x) in m {
                if matches(privateField, k) {
                    if let s = x as? String, s.trimmingCharacters(in: .whitespaces).isEmpty {} else { hits.append(path + "." + k) }
                }
                privateHits(x, path + "." + k, &hits)
            }
        } else if let a = v as? [Any] {
            for (i, x) in a.enumerated() { privateHits(x, path + "[\(i)]", &hits) }
        } else if let s = v as? String, s.hasPrefix("xprv") || matches(privateBlock, s) {
            hits.append(path)
        }
    }

    static func classify(name: String, data: Data, sha: String) throws -> RTORClassified {
        let ext = (name as NSString).pathExtension.lowercased()
        let text = String(decoding: data.prefix(4 << 20), as: UTF8.self)
        if matches(privateBlock, text) { throw RTORError.refused("contains a private key block; RTOR never stores or moves keys") }
        var c = RTORClassified(type: .file)
        switch ext {
        case "rzl":
            c.type = .rzl
            for (n, h) in rtorPublishedRZL where n == (name as NSString).lastPathComponent || h == sha {
                c.verified.append(RTORVerify(method: "published RTOR-INSTALL table", ok: h == sha, detail: n))
            }
        case "torrent":
            let t = try RTORTorrent.parse(data)
            c.type = .torrent; c.btihV1 = t.infoV1
            if t.metaVersion == 2 { c.btmhV2 = t.infoV2 }
            c.detail = ["torrent_name": t.name ?? "", "torrent_length": String(t.length ?? 0), "meta_version": String(t.metaVersion)]
        case "rtor", "json":
            guard let j = try? JSONSerialization.jsonObject(with: data) else {
                if ext == "json" { throw RTORError.refused("not valid JSON") }
                c.type = .rtor; break
            }
            var hits: [String] = []
            privateHits(j, "$", &hits)
            if !hits.isEmpty { throw RTORError.refused("private-key fields present (\(hits.joined(separator: ", "))); only public exports are accepted") }
            c.type = ext == "rtor" ? .rtor : .cryptoJSON
            if let m = j as? [String: Any] {
                c.detail["fields"] = m.keys.sorted().prefix(40).joined(separator: ",")
                if let mg = m["magnet"] as? String, let mi = try? RTORMagnet(parsing: mg) { c.detail["magnet"] = mi.raw }
            }
        case "magnet":
            let mi = try RTORMagnet(parsing: text)
            c.type = .magnet; c.detail["magnet"] = mi.raw
        case "pem", "crt", "cer":
            if ext == "pem" || text.contains("-----BEGIN") {
                guard text.contains("-----BEGIN CERTIFICATE-----") || text.contains("-----BEGIN PUBLIC KEY-----") else {
                    throw RTORError.refused("only public certificates / public keys are accepted")
                }
            }
            c.type = .cryptoPEM
        default:
            c.type = text.lowercased().hasPrefix("magnet:?") ? .magnet : .file
        }
        return c
    }
}

/// Minimal bencode reader: enough to compute a .torrent's infohash and read name/length.
public enum RTORTorrent {
    public struct Meta { public var name: String?; public var length: Int64?; public var infoV1: String; public var infoV2: String; public var metaVersion: Int }

    static func skip(_ b: [UInt8], _ i: Int) throws -> Int {
        guard i < b.count else { throw RTORError.io("bencode: eof") }
        switch b[i] {
        case UInt8(ascii: "i"):
            guard let e = b[i...].firstIndex(of: UInt8(ascii: "e")) else { throw RTORError.io("bencode: int") }
            return e + 1
        case UInt8(ascii: "l"), UInt8(ascii: "d"):
            var j = i + 1
            while j < b.count && b[j] != UInt8(ascii: "e") { j = try skip(b, j) }
            return j + 1
        case UInt8(ascii: "0")...UInt8(ascii: "9"):
            let (_, end) = try str(b, i)
            return end
        default: throw RTORError.io("bencode: bad byte")
        }
    }

    static func str(_ b: [UInt8], _ i: Int) throws -> ([UInt8], Int) {
        guard let c = b[i...].firstIndex(of: UInt8(ascii: ":")), let n = Int(String(decoding: b[i..<c], as: UTF8.self)), c + 1 + n <= b.count else {
            throw RTORError.io("bencode: string")
        }
        return (Array(b[(c + 1)..<(c + 1 + n)]), c + 1 + n)
    }

    public static func parse(_ data: Data) throws -> Meta {
        let b = [UInt8](data)
        guard b.first == UInt8(ascii: "d") else { throw RTORError.refused("not a bencoded torrent") }
        var i = 1
        var meta: Meta?
        while i < b.count && b[i] != UInt8(ascii: "e") {
            let (k, j) = try str(b, i)
            let end = try skip(b, j)
            if String(decoding: k, as: UTF8.self) == "info" {
                let raw = Data(b[j..<end])
                var m = Meta(name: nil, length: nil, infoV1: RTORHash.sha1(raw), infoV2: RTORHash.sha256(raw), metaVersion: 1)
                var x = j + 1
                while x < end - 1 && b[x] != UInt8(ascii: "e") {
                    let (ik, y) = try str(b, x)
                    let ye = try skip(b, y)
                    let v = Array(b[y..<ye])
                    switch String(decoding: ik, as: UTF8.self) {
                    case "name": if let r = try? str(v, 0) { m.name = String(decoding: r.0, as: UTF8.self) }
                    case "length": m.length = Int64(String(decoding: v.dropFirst().dropLast(), as: UTF8.self))
                    case "meta version": m.metaVersion = Int(String(decoding: v.dropFirst().dropLast(), as: UTF8.self)) ?? 1
                    default: break
                    }
                    x = ye
                }
                meta = m
            }
            i = end
        }
        guard let m = meta else { throw RTORError.refused("torrent has no info dictionary") }
        return m
    }
}
