// ThundRPluginAdapter.swift — integrated plugin adapter for ThundR.
// Neo-only: add to the RTHUNDR (or RCODE) Xcode target on MacBook Neo.
// Written on a VM with no Xcode toolchain — source for Neo, static-checked
// only, NOT compiled here. Do not claim Xcode was run on this file.
//
// Purpose: let ThundR (RTHUNDR.app / THUNDR-FLOAT) talk to all bots and
// AI — certainly Muse — for communication, diagnostics, analysis,
// debugging, repairs, updates, and coding + visual integrations.
//
// Pattern: extends the proven RCODE adapter (RCodeHostBridge.swift).
// The Swift side injects thundr-plugin-bridge.js at document start,
// sets globalThis.YASEED_HOST, and answers bridge calls through
// WKScriptMessageHandlerWithReply. The JS side registers the
// 'thundr-plugin' through the RENJIN core's own registerPlugin()
// (selftest -> device-signed descriptor -> plugin.register chain entry).
//
// LAW (standing, GHOSTMACHINE ghostkey):
//   - Bots never sign. Keys never leave the device.
//   - Every mint / sign / pay needs one unlock on a hard device.
//   - Decider approval before anything changes a device, installs,
//     rebuilds, or spends. Repairs and updates are propose-first.
//   - Allowlist only. Unknown methods are refused, never faked.
//   - Never erase: no uninstall, no wipe of app data, transcripts,
//     manuscripts, or the CHALKBOARD. Refuse app source without the
//     neverErase flag.
//   - This bridge carries public identifiers and messages only —
//     never key material, never signatures on the model's behalf.
//   - Install / re-sign / rebuild requests go to Яloader (RVPNRelay
//     :47800), never through this bridge directly. This adapter can
//     ask for a rebuild and report its result; it cannot run Xcode.

import WebKit

/// One adapter message. Mirrors rzl.link.v1 (see thundr-plugin-bridge.js).
/// In-process (WKWebView) the envelope travels as plain JSON; between
/// devices it is a signed rzl.link.v1 cmd/report (Ed25519, exp <= 24h).
struct ThundRPluginMessage: Codable {
    var schema: String          // "rzl.link.v1"
    var type: String            // "cmd" | "report"
    var from: String            // ЯID, e.g. "ЯID-0001-3QQS"
    var kind: String            // "talk" | "analyze" | "retrieve" | "repair" | "watch"
    var plugin: String          // "thundr-plugin"
    var pluginVersion: String   // "0.1.0"
    var capability: String      // diagnostics | analysis | debug | repair | update | code | visual | communicate
    var method: String
    var args: [String: String]
    var nonce: String
    var approved: Bool          // Decider approval carried with the request; false = propose only
}

final class ThundRPluginAdapter: NSObject, WKScriptMessageHandlerWithReply {

    /// Public ЯID this device answers for (never a key).
    var publicYaId: String?

    /// Whether the owner / Decider has approved this adapter's
    /// allowlist on this device. Nothing state-changing runs before
    /// this is set by the host app (e.g. after a Face ID unlock).
    var deciderApproved: Bool = false

    /// Methods the native side agrees to serve. Anything else is refused.
    /// - communicate / diagnostics / analysis are read-only and may run
    ///   without Decider approval.
    /// - debug may capture logs (read-only) without approval.
    /// - repair / update / code-write / visual-write REQUIRE approval:
    ///   without it they return a proposal, never an execution.
    var allowedMethods: Set<String> = [
        // communicate
        "talk", "ask", "report",
        // diagnostics
        "diagnostics.status", "diagnostics.chain", "diagnostics.plugins",
        "diagnostics.hostInfo", "diagnostics.modelInventory",
        // analysis
        "analysis.code", "analysis.corpus", "analysis.purity",
        // debug (read-only capture)
        "debug.capture",
        // repair / update / code / visual — propose-first, approval-gated
        "repair.propose", "repair.apply",
        "update.request", "update.check",
        "code.read", "code.write",
        "visual.layout", "visual.asset",
        // RbotLoadR / Яloader — ask + report only, never run Xcode here
        "rloader.status", "rloader.rebuild.request", "rloader.resign.status",
        // identity
        "getYaId", "hostInfo"
    ]

    /// Read-only methods (no approval needed). Everything else is
    /// propose-first and needs deciderApproved == true to execute.
    var readOnlyMethods: Set<String> = [
        "talk", "ask", "report",
        "diagnostics.status", "diagnostics.chain", "diagnostics.plugins",
        "diagnostics.hostInfo", "diagnostics.modelInventory",
        "analysis.code", "analysis.corpus", "analysis.purity",
        "debug.capture",
        "repair.propose",
        "update.check",
        "code.read",
        "rloader.status", "rloader.resign.status",
        "getYaId", "hostInfo"
    ]

    /// Attach to a webview configuration BEFORE the webview is created.
    func attach(to config: WKWebViewConfiguration, bridgeJS: String) {
        let userScript = WKUserScript(
            source: bridgeJS + "\n;ThundRPluginBridge.install();",
            injectionTime: .atDocumentStart,
            forMainFrameOnly: true)
        config.userContentController.addUserScript(userScript)
        config.userContentController.addScriptMessageHandler(
            self, contentWorld: .page, name: "thundrHost")
    }

    func userContentController(_ controller: WKUserContentController,
                               didReceive message: WKScriptMessage,
                               replyHandler: @escaping (Any?, String?) -> Void) {
        guard let body = message.body as? [String: Any],
              let method = body["method"] as? String else {
            replyHandler(nil, "bad message: expected {method, args}")
            return
        }
        guard allowedMethods.contains(method) else {
            replyHandler(nil, "refused: method not allowed over the ThundR plugin bridge: \(method)")
            return
        }
        // State-changing methods need Decider approval; without it they
        // may only propose. The JS side enforces the same rule, so a
        // proposal is returned, never a silent execution.
        if !readOnlyMethods.contains(method) && !deciderApproved {
            if method == "repair.apply" || method == "code.write" ||
               method == "update.request" || method == "visual.asset" ||
               method == "rloader.rebuild.request" {
                replyHandler(["proposed": true, "method": method,
                              "note": "Decider approval required — proposal recorded, nothing executed"],
                             nil)
                return
            }
            replyHandler(nil, "refused: Decider approval required for \(method)")
            return
        }
        switch method {
        case "getYaId":
            replyHandler(["yaId": publicYaId ?? ""], nil)
        case "hostInfo":
            replyHandler(["hostId": "thundr-native",
                          "platform": ProcessInfo.processInfo.operatingSystemVersionString,
                          "deciderApproved": deciderApproved], nil)
        case "diagnostics.status":
            replyHandler(["status": "ok", "hostId": "thundr-native",
                          "note": "live values are filled by the host app on Neo"], nil)
        case "rloader.status":
            // Яloader state is read from the Neo services, never invented here.
            replyHandler(["rloader": "unknown-on-this-host",
                          "note": "Яloader status lives on Neo (RVPNRelay :47800); this build reports, it does not run Xcode"], nil)
        default:
            // All other allowlisted methods are served by the host app on
            // Neo (diagnostics / analysis / debug capture / proposals).
            // This skeleton routes them to the host; it does not invent
            // results. A host that has not implemented a method returns
            // the refusal below instead of a fake value.
            replyHandler(nil, "not implemented on this host yet: \(method) — implement in the RTHUNDR target on Neo")
        }
    }
}

// JS-side call shape: WKScriptMessageHandlerWithReply makes
// messageHandlers.thundrHost.postMessage({method, args}) return a Promise.
// thundr-plugin-bridge.js wraps that as bridge.call(method, args).
