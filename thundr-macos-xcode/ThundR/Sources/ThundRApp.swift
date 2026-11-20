// ThundRApp.swift — ThundR for macOS, pure .RZL.
// SwiftUI app entry point. No external dependencies, no Swift packages.
// The brain is RENJIN Core v3 (pure RZL JS in WKWebView) — no other
// company's model, no LLM weights, no cloud, no eval.
// Written on a VM with no Xcode toolchain — NOT compiled here.
// Open ThundR.xcodeproj in Xcode on MacBook Neo and build (see README.md).

import SwiftUI

@main
struct ThundRApp: App {
    @StateObject private var brain = PureRZLBrain()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(brain)
        }
        .windowStyle(.titleBar)
        .commands {
            CommandGroup(replacing: .newItem) {}
            CommandMenu("ThundR") {
                Button("Ask the Engine…") {
                    NotificationCenter.default.post(
                        name: .thundRFocusPrompt, object: nil)
                }
                .keyboardShortcut("l", modifiers: [.command])
                Button("Chain Verify") {
                    Task { await brain.chainVerify() }
                }
                .keyboardShortcut("v", modifiers: [.command, .shift])
            }
        }
    }
}

extension Notification.Name {
    static let thundRFocusPrompt = Notification.Name("thundRFocusPrompt")
}
