// ContentView.swift — ThundR for macOS, main window.
//
// Layout: sidebar (ThundR identity + live Trackers + plugin status) and
// the R:> Shell in a WKWebView, with a prompt bar at the bottom.
// The shell is the bundled R-SHELL-MERGED.html — the merged RENJIN
// Core v3 shell (Trackers + trained engine + corpus-v2 retrieval).
// No network: the webview loads only from the app bundle, and the
// App Sandbox has no outgoing network except loopback 127.0.0.1:4873
// (rvm-out, if present). See ThundR.entitlements.

import SwiftUI
import WebKit

struct ContentView: View {
    @EnvironmentObject var brain: PureRZLBrain
    @State private var prompt = ""
    @State private var answer = ""
    @State private var isAsking = false
    @State private var selectedShell = ShellChoice.merged
    @FocusState private var promptFocused: Bool

    enum ShellChoice: String, CaseIterable, Identifiable {
        case merged = "R-SHELL-MERGED.html"
        case neo = "RSHELL-RENJIN.html"
        var id: String { rawValue }
        var label: String {
            switch self {
            case .merged: return "Merged shell (Trackers)"
            case .neo: return "Neo one-file shell"
            }
        }
    }

    var body: some View {
        HSplitView {
            // MARK: Sidebar
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 10) {
                    Image("ThundR")
                        .resizable()
                        .frame(width: 48, height: 48)
                        .clipShape(Circle())
                    VStack(alignment: .leading, spacing: 2) {
                        Text("ThundR")
                            .font(.title2).bold()
                        Text("pure .RZL · ЯENJIN 0.1")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
                .padding(.top, 8)

                Divider()

                Text("TRACKERS")
                    .font(.caption).bold()
                    .foregroundStyle(.secondary)
                TrackerRow(label: "Corpus-v2", value: "\(brain.corpusLessons) lessons")
                TrackerRow(label: "Loss", value: "27.631 → \(brain.loss)")
                TrackerRow(label: "Held-out", value: String(brain.heldOutLoss))
                TrackerRow(label: "Chain", value: "\(brain.chainEntries) entries · ok \(brain.chainOK)")
                TrackerRow(label: "Grounded", value: brain.groundedScore)
                TrackerRow(label: "Free generation", value: "NOT fixed")
                TrackerRow(label: "State", value: String(brain.stateHash.prefix(16)) + "…")
                    .help(brain.stateHash)

                Divider()

                Text("PLUGIN")
                    .font(.caption).bold()
                    .foregroundStyle(.secondary)
                Text("thundr-plugin v0.1.0 · rzl.thundr.plugin.v1")
                    .font(.caption)
                Text("Muse ↔ RENJIN ↔ ThundR ↔ all bots")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text("Repairs / updates: propose-first. Bots never sign.")
                    .font(.caption)
                    .foregroundStyle(.secondary)

                Divider()

                Text("SHELL")
                    .font(.caption).bold()
                    .foregroundStyle(.secondary)
                Picker("Shell", selection: $selectedShell) {
                    ForEach(ShellChoice.allCases) { choice in
                        Text(choice.label).tag(choice)
                    }
                }
                .pickerStyle(.radioGroup)
                .font(.caption)

                Button("Chain Verify") {
                    Task {
                        answer = await brain.chainVerify()
                    }
                }
                .buttonStyle(.bordered)

                Spacer()

                Text("Offline-first. No cloud, no LLM weights, no eval.")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
            .padding()
            .frame(minWidth: 240, idealWidth: 280)

            // MARK: Shell + prompt
            VStack(spacing: 0) {
                ShellWebView(shellFile: selectedShell.rawValue, brain: brain)
                    .frame(minWidth: 480, minHeight: 400)

                Divider()

                VStack(alignment: .leading, spacing: 8) {
                    if !answer.isEmpty {
                        Text(answer)
                            .font(.body)
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(8)
                            .background(Color(nsColor: .textBackgroundColor))
                            .cornerRadius(6)
                    }
                    HStack {
                        Text("R:\\>")
                            .font(.body.monospaced())
                            .foregroundStyle(.green)
                        TextField("Ask the engine (retrieval-first quoting)…", text: $prompt)
                            .textFieldStyle(.plain)
                            .focused($promptFocused)
                            .onSubmit { submitPrompt() }
                        Button("Ask") { submitPrompt() }
                            .disabled(isAsking || prompt.trimmingCharacters(in: .whitespaces).isEmpty)
                            .buttonStyle(.borderedProminent)
                    }
                    .padding(8)
                    .background(Color(nsColor: .controlBackgroundColor))
                }
                .padding(8)
            }
        }
        .frame(minWidth: 800, minHeight: 560)
        .onReceive(NotificationCenter.default.publisher(for: .thundRFocusPrompt)) { _ in
            promptFocused = true
        }
    }

    private func submitPrompt() {
        let question = prompt
        guard !question.trimmingCharacters(in: .whitespaces).isEmpty else { return }
        prompt = ""
        isAsking = true
        Task {
            answer = await brain.ask(question)
            isAsking = false
        }
    }
}

struct TrackerRow: View {
    var label: String
    var value: String
    var body: some View {
        HStack {
            Text(label).font(.caption).foregroundStyle(.secondary)
            Spacer()
            Text(value).font(.caption).monospaced()
        }
    }
}

// MARK: - WKWebView wrapper

/// Hosts the bundled R:> Shell HTML. Loads from the app bundle only.
/// Injects thundr-plugin-bridge.js at document start and registers the
/// ThundRPluginAdapter as the "thundrHost" message handler, so the
/// shell's JS can call native methods (see ThundRPluginAdapter.swift).
/// The core engine JS lives inside the shell page itself; this wrapper
/// does not fetch, download, or evaluate any remote code.
struct ShellWebView: NSViewRepresentable {
    var shellFile: String
    var brain: PureRZLBrain

    func makeCoordinator() -> Coordinator {
        Coordinator(brain: brain)
    }

    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        // No JavaScript opening windows, no remote content.
        config.preferences.javaScriptCanOpenWindowsAutomatically = false

        // Inject the ThundR plugin bridge at document start.
        let adapter = ThundRPluginAdapter()
        context.coordinator.adapter = adapter
        if let bridgeURL = Bundle.main.url(forResource: "thundr-plugin-bridge", withExtension: "js"),
           let bridgeJS = try? String(contentsOf: bridgeURL, encoding: .utf8) {
            adapter.attach(to: config, bridgeJS: bridgeJS)
        }

        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = context.coordinator
        context.coordinator.webView = webView
        brain.webView = webView
        loadShell(into: webView)
        return webView
    }

    func updateNSView(_ nsView: WKWebView, context: Context) {
        // Reload only when the chosen shell file changed.
        if context.coordinator.loadedShell != shellFile {
            loadShell(into: nsView)
        }
    }

    private func loadShell(into webView: WKWebView) {
        guard let url = Bundle.main.url(forResource: shellFile, withExtension: nil) else {
            brain.log("shell file not found in bundle: \(shellFile)")
            return
        }
        // loadFileURL with read access to the bundle Resources folder,
        // so the shell's relative assets (if any) resolve locally.
        let resources = Bundle.main.resourceURL!
        webView.loadFileURL(url, allowingReadAccessTo: resources)
    }

    final class Coordinator: NSObject, WKNavigationDelegate {
        let brain: PureRZLBrain
        var adapter: ThundRPluginAdapter?
        var webView: WKWebView?
        var loadedShell: String?

        init(brain: PureRZLBrain) {
            self.brain = brain
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            brain.isBooted = true
            if let url = webView.url?.lastPathComponent {
                loadedShell = url
            }
            brain.log("shell loaded: \(webView.url?.lastPathComponent ?? "?") — engine booting from embedded store")
        }

        func webView(_ webView: WKWebView,
                     decidePolicyFor navigationAction: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            // Offline-first: never navigate away from the bundled shell.
            // External links are refused here; the shell is self-contained.
            if navigationAction.navigationType == .linkActivated {
                decisionHandler(.cancel)
                brain.log("refused external navigation: \(navigationAction.request.url?.absoluteString ?? "?")")
                return
            }
            decisionHandler(.allow)
        }
    }
}
