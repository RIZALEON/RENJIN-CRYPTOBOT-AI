import Foundation

/// Per-space SPACE-RID.json: { rid, space, rklowd_node, rmail_address, drop_paths (array or object of paths) }.
public struct RTORSpace: Decodable, Sendable {
    public var rid: String?
    public var space: String?
    public var rklowdNode: String?
    public var rmailAddress: String?
    public var dropPaths: [(name: String, path: String)] = []

    struct Entry: Decodable { var address: String; var kind: String? }
    enum K: String, CodingKey { case rid, space, rklowd_node, rmail_address, drop_paths }

    public init(from d: Decoder) throws {
        let c = try d.container(keyedBy: K.self)
        rid = try? c.decode(String.self, forKey: .rid)
        space = try? c.decode(String.self, forKey: .space)
        rklowdNode = try? c.decode(String.self, forKey: .rklowd_node)
        rmailAddress = try? c.decode(String.self, forKey: .rmail_address)
        if let a = try? c.decode([String].self, forKey: .drop_paths) {
            dropPaths = a.enumerated().map { ("drop\($0.offset)", $0.element) }
        } else if let o = try? c.decode([String: String].self, forKey: .drop_paths) {
            dropPaths = o.keys.sorted().map { ($0, o[$0]!) }
        } else if let o = try? c.decode([String: [String]].self, forKey: .drop_paths) {
            for k in o.keys.sorted() { for (i, p) in o[k]!.enumerated() { dropPaths.append(("\(k)\(i)", p)) } }
        } else if let e = try? c.decode([Entry].self, forKey: .drop_paths) {
            // registry form [{address, kind, role}]: only filesystem addresses are drop folders
            for (i, x) in e.enumerated() where !x.address.contains("@") && !x.address.contains("://") && x.kind != "rmail" && x.kind != "site" {
                dropPaths.append(("\(x.kind ?? "drop")\(i)", x.address))
            }
        }
    }

    public struct Drop: Identifiable, Sendable { public var id: String { name }; public var name: String; public var url: URL; public var reachable: Bool }

    /// Relative paths resolve inside the app's Documents folder (where other apps / Files can drop).
    public func drops(base: URL) -> [Drop] {
        dropPaths.map { (n, p) in
            let expanded = (p as NSString).expandingTildeInPath
            let u = expanded.hasPrefix("/") ? URL(fileURLWithPath: expanded) : base.appendingPathComponent(expanded)
            var isDir: ObjCBool = false
            let ok = FileManager.default.fileExists(atPath: u.path, isDirectory: &isDir) && isDir.boolValue
            return Drop(name: n, url: u, reachable: ok)
        }
    }

    public static func load(_ candidates: [URL]) -> RTORSpace? {
        for u in candidates {
            if let d = try? Data(contentsOf: u), let s = try? JSONDecoder().decode(RTORSpace.self, from: d), s.rid != nil || s.space != nil { return s }
        }
        return nil
    }
}
