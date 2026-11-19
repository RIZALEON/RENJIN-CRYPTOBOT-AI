// ThundRAdapter.swift — native-side ThundR Plugin Adapter (tpa.v1).
//
// NOTE: written-but-uncompiled. There is no Xcode on the VM this was
// written on, so this file has NOT been compiled. It is Foundation-only
// with no new dependencies; compile it inside RTHUNDR-APP (or any Swift
// target) and run the source-contract checks in tests/test_adapter.py
// (class TestSwiftContract) before trusting it.
//
// The native twin of the Python reference implementation
// (python/thundr_adapter/). Same tpa.v1 method names, same envelope shape
// as the LocalBrain.call(tool:text:done:) bridge — [String: Any] results
// with ok / via / reply|data / error / refused — so the float UI, a
// helper, or any native host can drive the adapter without a server.
//
// Pattern: NativeCommands / NativeMaintenance from RIZALEON/RTHUNDR
// src/LocalBrain.swift (branch feature/native-diagnostics):
//  - one small command registry, deterministic help routed BEFORE any
//    model load or service call;
//  - diagnostics are offline, read-only, symlink-safe GGUF inventory;
//  - proposals are NOT authorization or execution — there is no
//    apply/approve entry point that executes anything in this file.
// Refuse rules are the 7 regexes from thundr-commands.json
// (schema thundr.core.commands.v1), enforced here for every native caller.
// Wallet/signing verbs (wallet balances, casket verify, signing status,
// prompt faceid, sign this, request approval — the parser's ready reply in
// the live float, screenshot 2026-11-19) are GO-gated: the native adapter
// never runs them, it hands them back for Rizal's explicit GO —
// sufficient authorization, no biometric step required.
// Engine verbs (models, use qwen, use granite — the R:> shell quick
// commands) are answered deterministically; the native adapter records no
// engine preference and probes no relay (it has no network).
import Foundation

/// ThundR Plugin Adapter, native side. No network, no process execution,
/// no app-state access, no writes. Everything is in-process and offline.
public enum ThundRAdapter {
    public static let protocolVersion = "tpa.v1"
    public static let adapterVersion = "0.1.1"

    /// The twelve tpa.v1 methods, in protocol order.
    public static let methods: [String] = [
        "adapter.hello",
        "adapter.commands.list",
        "adapter.commands.get",
        "adapter.chat",
        "adapter.diagnostics",
        "adapter.analyze",
        "adapter.debug",
        "adapter.repair.propose",
        "adapter.repair.apply",
        "adapter.update.check",
        "adapter.update.apply",
        "adapter.visual",
    ]

    /// Methods that mutate state and therefore require an explicit GO.
    public static let goGatedMethods: Set<String> = [
        "adapter.repair.apply",
        "adapter.update.apply",
    ]

    // MARK: - Envelope (LocalBrain.call shape)

    public static func ok(via: String, data: Any? = nil, reply: String? = nil) -> [String: Any] {
        var out: [String: Any] = ["ok": true, "via": via]
        if let data { out["data"] = data }
        if let reply { out["reply"] = reply }
        return out
    }

    public static func fail(_ error: String, via: String? = nil, refused: Bool = false, reply: String? = nil) -> [String: Any] {
        var out: [String: Any] = ["ok": false, "error": error]
        if let via { out["via"] = via }
        if refused { out["refused"] = true }
        if let reply { out["reply"] = reply }
        return out
    }

    // MARK: - Refuse rules (thundr-commands.json `refuse`, verbatim)

    /// The 7 refuse rules: (ICU regex, label). Patterns are lowercase;
    /// input is lowercased before matching, as in thundr_chat.py.
    public static let refuseRules: [(pattern: String, label: String)] = [
        ("^optimize\\s+(clean|deep)\\b", "optimize clean / optimize deep (removes files)"),
        ("^eggs?\\s+install\\b", "eggs install"),
        ("^self[- ]?evolution\\b", "self-evolution"),
        ("^rebirth\\b.*\\bgo\\b", "REBIRTH … go (real run)"),
        ("^(egg\\s+apply|api/egg/apply|api/approve)\\b", "egg apply / approve endpoint"),
        ("^rscribe\\s+build\\b.*--run\\b", "rscribe build --run (real Apple build/sign)"),
        ("^17e\\s+(uninstall|delete|rm|sign|keychain|wallet)\\b", "17e uninstall/delete/rm/sign/keychain/wallet"),
    ]

    public static let refuseReply = "needs Rizal's GO. ThundR never signs, mints, seals, installs, removes files or writes the chain/wallet. Nothing was run."

    /// Returns the matched rule label, or nil when the text is allowed.
    public static func refuseCheck(_ text: String) -> String? {
        let lowered = text.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        for rule in refuseRules {
            guard let rx = try? NSRegularExpression(pattern: rule.pattern) else { continue }
            let range = NSRange(lowered.startIndex..<lowered.endIndex, in: lowered)
            if rx.firstMatch(in: lowered, range: range) != nil { return rule.label }
        }
        return nil
    }

    // MARK: - GO-gated wallet/signing verbs (live /rmint/request)

    /// The sensitive subset of the A2 LocalBrain liveCmd regex: wallet and
    /// signing verbs map to the LIVE flow, and bot/agent input cannot
    /// request, confirm, or send on it. Not forbidden — needs Rizal's
    /// explicit GO for that exact action (sufficient authorization;
    /// no biometric step required).
    public static let goGatedPattern = "^/?(wallet|rwallet|signing|sign this|sign egg|egg-sign|prompt faceid|faceid|request approval|approve|mint|request mint|request sign|casket\\s+(verify|approve|sign))\\b"

    /// Returns the matched verb, or nil when the text is not a gated verb.
    public static func goGatedCheck(_ text: String) -> String? {
        let lowered = text.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard let rx = try? NSRegularExpression(pattern: goGatedPattern) else { return nil }
        let range = NSRange(lowered.startIndex..<lowered.endIndex, in: lowered)
        guard let match = rx.firstMatch(in: lowered, range: range),
              let verbRange = Range(match.range, in: lowered) else { return nil }
        return String(lowered[verbRange])
    }

    public static func goGatedReply(verb: String) -> String {
        "GO-gated: \(verb) touches the live wallet/signing flow (/rmint/request). The adapter never runs it — bot/agent input cannot request, confirm, or send on that flow. Nothing was run. To proceed, type the verb in the ThundR R:> shell yourself, or get Rizal's explicit GO for that exact action. Rizal's GO is sufficient authorization — no biometric step is required."
    }

    // MARK: - Deterministic help (routed BEFORE any model/service call)

    public static var help: String {
        let entries = methods.enumerated().map { index, method in
            let gated = goGatedMethods.contains(method) ? " — GO-gated" : ""
            return "\(index + 1). \(method)\(gated)"
        }
        return "ThundR Plugin Adapter \(adapterVersion) (\(protocolVersion)) — \(methods.count) methods, offline, loopback-only:\n"
            + entries.joined(separator: "\n")
            + "\nRepair and update apply need Rizal's explicit GO. Refused patterns are never run."
    }

    /// The MODELS panel (R:> shell quick command). The native adapter has
    /// no network, so it names both engines and says where liveness is
    /// reported — the float status bar for Qwen, the Python adapter's
    /// diagnostics for the Granite relay on :4983 — instead of probing.
    public static var modelsText: String {
        "MODELS\n"
        + "• Qwen 1.7B (in-process llama.cpp fallback)  [liveness: the float status bar]\n"
        + "• Granite 4.2 3B (SANDISK relay :4983)  [liveness: the Python adapter's diagnostics — this file has no network]\n"
        + "\nCommands: use qwen · use granite · models"
    }

    // MARK: - Dispatch (LocalBrain.call shape: tool + text -> [String: Any])

    /// Route one adapter call. `method` must be a tpa.v1 method name;
    /// `text` is the free-text argument (chat line, command id, path).
    /// `resources` is the app bundle resource URL for diagnostics.
    /// The completion runs on the calling thread; wrap in DispatchQueue
    /// when calling from the float bridge, as LocalBrain.call does.
    public static func call(method: String, text: String, resources: URL?, done: @escaping ([String: Any]) -> Void) {
        let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        let low = t.lowercased()

        // Refuse enforcement first, for every method that carries text.
        if method == "adapter.chat", let rule = refuseCheck(t) {
            var res = fail("refused", via: "adapter.chat/refuse", refused: true, reply: refuseReply)
            res["rule"] = rule
            return done(res)
        }

        // GO-gated wallet/signing verbs — never forwarded to any executor.
        if method == "adapter.chat", let verb = goGatedCheck(t) {
            var res: [String: Any] = ["ok": false, "via": "adapter.chat/go-gated", "go_gated": true, "error": "go-gated", "reply": goGatedReply(verb: verb)]
            res["verb"] = verb
            return done(res)
        }

        switch method {
        case "adapter.hello":
            return done(ok(via: "adapter", data: [
                "adapter": "ThundR Plugin Adapter",
                "adapter_version": adapterVersion,
                "protocol": protocolVersion,
                "methods": methods,
                "go_gated": Array(goGatedMethods).sorted(),
                "transport": "in-process (native)",
                "offline": true,
            ]))
        case "adapter.chat":
            // Deterministic help before any model load or service call.
            if ["help", "commands", "functions", "?"].contains(low) {
                return done(ok(via: "adapter.chat/native-help", reply: help))
            }
            // Engine verbs (R:> shell quick commands), deterministic.
            if ["models", "list models", "model"].contains(low) {
                return done(ok(via: "adapter.chat/models", reply: modelsText))
            }
            if ["use qwen", "engine qwen"].contains(low) {
                return done(ok(via: "adapter.chat/engine", reply: "Active engine → Qwen 1.7B (preferred).\nThe native adapter records no preference — type `use qwen` in the R:> shell to switch the app, or use the Python adapter's chat."))
            }
            if ["use granite", "engine granite"].contains(low) {
                return done(ok(via: "adapter.chat/engine", reply: "Active engine → Granite 4.2 3B (preferred).\nThe native adapter records no preference and probes no relay — type `use granite` in the R:> shell to switch the app, or use the Python adapter's chat."))
            }
            // No live brain in the native adapter: the in-process engine
            // answers through LocalBrain.call, not through this file.
            // Never fake a brain reply here.
            return done(ok(via: "adapter.chat/offline", reply: "No live ThundR brain is reachable from the native adapter. Ask the in-process LocalBrain, or type help for the adapter methods."))
        case "adapter.diagnostics":
            return done(ok(via: "adapter.diagnostics", reply: diagnostics(resources: resources)))
        case "adapter.repair.propose":
            return done(ok(via: "adapter.repair", reply: "REPAIR PROPOSAL — NOT EXECUTED. Scope: this app package only. Review diagnostics, identify a reviewed replacement artifact, verify its provenance and offline regression tests, then request explicit human approval through a supported installer. This adapter cannot approve or apply repairs."))
        case "adapter.update.check":
            return done(ok(via: "adapter.update", reply: "UPDATE CHECK — read-only. Compare the bundled registry stamp against the canonical registry (thundr-build.json content_sha256). No download or installation has occurred."))
        case "adapter.repair.apply", "adapter.update.apply":
            return done(fail("refused", via: "adapter", refused: true, reply: "REFUSED: no maintenance execution or approval capability is granted in the native adapter. Use diagnostics, repair proposal or update check; a proposal is not an installed repair/update."))
        case "adapter.commands.list", "adapter.commands.get", "adapter.analyze", "adapter.debug", "adapter.visual":
            return done(fail("not available natively: \(method) runs through the Python adapter (loopback server or CLI) against the registry on disk.", via: "adapter"))
        default:
            return done(fail("unknown method: \(method)", via: "adapter"))
        }
    }

    // MARK: - Diagnostics (NativeMaintenance shape)

    /// Offline, read-only GGUF inventory of the bundle's model directory.
    /// Counts regular .gguf files only; never follows symbolic links.
    /// Availability only: inference is NOT TESTED here.
    public static func diagnostics(resources: URL?) -> String {
        guard let resources else {
            return "DIAGNOSTICS · offline read-only\nResources unavailable. Model inference NOT TESTED. Maintenance execution NOT GRANTED."
        }
        let fm = FileManager.default
        let model = resources.appendingPathComponent("model", isDirectory: true)
        let keys: Set<URLResourceKey> = [.isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey]
        let directoryIsLink = (try? model.resourceValues(forKeys: [.isSymbolicLinkKey]).isSymbolicLink) == true
        let entries = directoryIsLink ? [] : ((try? fm.contentsOfDirectory(at: model, includingPropertiesForKeys: Array(keys))) ?? [])
        var count = 0
        var bytes = 0
        var names: [String] = []
        for entry in entries where entry.pathExtension.lowercased() == "gguf" {
            guard let values = try? entry.resourceValues(forKeys: keys),
                  values.isRegularFile == true, values.isSymbolicLink != true else { continue }
            count += 1
            bytes += values.fileSize ?? 0
            names.append(entry.lastPathComponent)
        }
        return "DIAGNOSTICS · offline read-only\nRegular bundled GGUF files: \(count); bytes: \(bytes).\n\(names.isEmpty ? "No models found." : "Models: " + names.joined(separator: ", ") + ".")\nGranite relay :4983 liveness is checked by the Python adapter (diagnostics), not here — this file has no network.\nAvailability only: package authenticity, template compatibility and inference NOT TESTED.\nNative adapter: in-process diagnostics and proposal rendering supported.\nMaintenance execution NOT GRANTED; no approval/apply handler."
    }
}
