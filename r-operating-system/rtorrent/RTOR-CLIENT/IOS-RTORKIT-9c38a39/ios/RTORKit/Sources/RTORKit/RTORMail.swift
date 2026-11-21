import Foundation
import Combine

/// RMAIL v2 outbox over relay_8797 (same message shape as rsocial-rmail.js). Never signs or mints; verified:false.
/// Undelivered mail stays queued and is retried on flush().
@MainActor
public final class RTORMail: ObservableObject {
    public struct Msg: Codable, Hashable, Sendable {
        var v = 2, kind = "rmail", id: String, to: String, to_addr: String, from = "rtor-client", from_addr = "rtor-client"
        var from_device: String, text: String, origin = "RTORKit/0.2.3", ts: Int64, verified = false, rtor_type: String
    }
    public struct Item: Codable, Hashable, Sendable { public var msg: Msg; public var sent: Date?; public var lastError: String? }

    @Published public private(set) var items: [Item] = []
    public var relays: [String] = ["send=http://127.0.0.1:8797/send", "drop=http://192.168.0.113:8797/rscale/rmail/drop"]
    let file: URL

    init(outbox: URL) {
        file = outbox
        if let d = try? Data(contentsOf: file), let i = try? JSONDecoder().decode([Item].self, from: d) { items = i }
    }

    public var pending: Int { items.filter { $0.sent == nil }.count }

    func save() { if let d = try? JSONEncoder().encode(items) { try? d.write(to: file, options: .atomic) } }

    public func queue(to: String, text: String, type: String) {
        let id = String(Int64(Date().timeIntervalSince1970 * 1000), radix: 36) + String(UInt32.random(in: 0...UInt32.max), radix: 36)
        let dev = ProcessInfo.processInfo.hostName
        items.append(Item(msg: Msg(id: id, to: to, to_addr: to, from_device: "rtor-ios-" + dev, text: String(text.prefix(4000)), ts: Int64(Date().timeIntervalSince1970 * 1000), rtor_type: type)))
        save()
        Task { await flush() }
    }

    public func flush() async {
        for i in items.indices where items[i].sent == nil {
            var errs: [String] = []
            for r in relays {
                let parts = r.split(separator: "=", maxSplits: 1).map(String.init)
                let (mode, url) = parts.count == 2 && !parts[0].contains("/") ? (parts[0], parts[1]) : ("drop", r)
                guard let u = URL(string: url), let msg = try? JSONEncoder().encode(items[i].msg) else { continue }
                var body = msg
                if mode == "send" {
                    let box = "rmail-" + String(items[i].msg.to_addr.map { $0.isLetter || $0.isNumber || $0 == "_" || $0 == "-" ? $0 : "_" }.prefix(64))
                    body = (try? JSONSerialization.data(withJSONObject: ["to": box, "from": items[i].msg.from_addr, "type": "rmail", "body": String(decoding: msg, as: UTF8.self)])) ?? msg
                }
                var req = URLRequest(url: u, timeoutInterval: 5); req.httpMethod = "POST"; req.httpBody = body
                req.setValue("text/plain", forHTTPHeaderField: "Content-Type")
                do {
                    let (d, resp) = try await URLSession.shared.data(for: req)
                    let ok = ((resp as? HTTPURLResponse)?.statusCode ?? 0) / 100 == 2
                    if ok, let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any], j["ok"] as? Bool == true, j["id"] != nil {
                        items[i].sent = Date(); items[i].lastError = nil; break
                    }
                    errs.append("\(url): bad-ack")
                } catch { errs.append("\(url): \(error.localizedDescription)") }
            }
            if items[i].sent == nil { items[i].lastError = errs.joined(separator: " | ") }
        }
        save()
    }
}
