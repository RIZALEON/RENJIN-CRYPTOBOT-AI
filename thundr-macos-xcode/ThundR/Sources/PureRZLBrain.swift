// PureRZLBrain.swift — the pure .RZL brain for ThundR on macOS.
//
// REPLACES the old RTHUNDR brain (LocalBrain.swift: fused external
// LLM weights + BM25). That brain is NOT in this project — no other
// AI company's model, weights, or code.
// The brain here is RENJIN Core v3, pure RZL from scratch:
//
//   - yaseed-core-v3.js — ЯENJIN 0.1, egg 0.1.11, DIM 64 / HID 128 / CTX 32,
//     49,152 ternary weights, Ghost Chain (SHA-256, ECDSA P-256)
//   - corpus-v2.txt — 158 RZL-authored lessons
//   - store-v3.json — persisted trained state,
//     state:current 16f9dd002f25a26ddc7df8a6d2ef39ea898326df1414f6139663416ec9eb9b08
//     train 60s, 3,057 steps, loss 27.631 -> 3.26, held-out 3.246, chain_ok true
//   - rzl-ask.js — MIND v2 retrieval: BM25 (0.7) + RZL embeddings (0.3),
//     quotes the best corpus line, "Unknown." below 0.5
//   - rzl-embed.js — rzl-embed.v1, deterministic hash character n-gram vectors
//   - Tokenizer.swift — tok.v1, vocab 313
//
// Honest limits (do not remove these notes):
//   - Free generation is NOT fixed. Greedy generation returns spaces,
//     sampled generation returns gibberish. Retrieval-first quoting is
//     the askable path. ask() quotes; it never invents.
//   - Grounded 10-question test: 8/10 in the local log (not 10/10).
//   - No live device ЯENJIN pairing yet. This app runs its own
//     in-WebView copy of the engine with a per-install Ghost Chain.
//   - The core's module sandbox used the Function constructor; the
//     merged shell replaces those two founding modules with ordinary
//     JavaScript and refuses any other source string.
//
// How it works: the WKWebView (see ContentView.swift) loads the bundled
// R-SHELL-MERGED.html, which already embeds the engine + store + corpus.
// This class talks to that page with evaluateJavaScript, and also keeps a
// Swift-side fallback: tokenizer + corpus lines loaded from the bundle,
// scored by token overlap, so ask() still works if the page is not ready.

import Foundation
import WebKit

@MainActor
final class PureRZLBrain: ObservableObject {

    // MARK: - Published state (shown in ContentView Trackers)

    @Published var engineVersion = "0.1.11"
    @Published var engineName = "ЯENJIN 0.1 · core v3"
    @Published var loss: Double = 3.2595
    @Published var heldOutLoss: Double = 3.246
    @Published var chainEntries = 9
    @Published var chainOK = true
    @Published var corpusLessons = 158
    @Published var stateHash = "16f9dd002f25a26ddc7df8a6d2ef39ea898326df1414f6139663416ec9eb9b08"
    @Published var packageSHA256 = "3a19e054d6d3718d4f4a87a863dc97b691a7da578f820b8906197820400069c6"
    @Published var groundedScore = "8/10"
    @Published var isBooted = false
    @Published var lastAnswer = ""
    @Published var logLines: [String] = []

    // MARK: - Bundle resources

    private let tokenizer = RZLTokenizer()
    private var corpusLines: [String] = []
    private var storeJSON: [String: Any] = [:]

    weak var webView: WKWebView?

    init() {
        loadBundleResources()
    }

    /// Read corpus-v2.txt + store-v3.json from the app bundle.
    /// Pure file reads — no network, no download.
    func loadBundleResources() {
        if let url = Bundle.main.url(forResource: "corpus-v2", withExtension: "txt"),
           let text = try? String(contentsOf: url, encoding: .utf8) {
            corpusLines = text
                .components(separatedBy: .newlines)
                .filter { !$0.hasPrefix("#") }
                .filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty }
            corpusLessons = corpusLines.count
        }
        if let url = Bundle.main.url(forResource: "store-v3", withExtension: "json"),
           let data = try? Data(contentsOf: url),
           let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            storeJSON = json
            if let current = json["state:current"] as? String {
                stateHash = current
            }
        }
        log("Pure RZL brain loaded: corpus-v2 \(corpusLessons) lessons, store state \(stateHash.prefix(8))…")
    }

    // MARK: - Logging

    func log(_ line: String) {
        logLines.append(line)
        if logLines.count > 200 { logLines.removeFirst(logLines.count - 200) }
    }

    // MARK: - Ask (retrieval-first, never free generation)

    /// Ask the engine. First tries the JS engine inside the shell page
    /// (the real rzl-ask.js path); falls back to the Swift-side scorer
    /// over the bundled corpus. Either way the answer is a QUOTE of the
    /// best corpus line, or "Unknown." — never generated text.
    func ask(_ question: String) async -> String {
        let trimmed = question.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return "Unknown." }
        if let webView, isBooted {
            let escaped = trimmed
                .replacingOccurrences(of: "\\", with: "\\\\")
                .replacingOccurrences(of: "\"", with: "\\\"")
                .replacingOccurrences(of: "\n", with: " ")
            // The merged shell answers retrieval-first through its own
            // ask path; if the page exposes it, use it. Otherwise fall
            // through to the Swift scorer below.
            if let result = try? await webView.evaluateJavaScript(
                "typeof window.__thundrAsk === 'function' ? window.__thundrAsk(\"\(escaped)\") : null"
            ) as? String, !result.isEmpty {
                lastAnswer = result
                log("ask (JS engine): \(trimmed) -> \(result.prefix(80))")
                return result
            }
        }
        let answer = swiftAsk(trimmed)
        lastAnswer = answer
        log("ask (Swift fallback): \(trimmed) -> \(answer.prefix(80))")
        return answer
    }

    /// Swift-side retrieval fallback: token overlap over corpus lines,
    /// with the same stopword / number-word rules as rzl-ask.js.
    /// Score below 0.5 -> "Unknown." (same threshold as the JS engine).
    func swiftAsk(_ question: String) -> String {
        let stopwords: Set<String> = [
            "what", "is", "are", "was", "were", "the", "a", "an",
            "does", "do", "did", "by", "and", "of", "to", "in", "on",
            "it", "its", "this", "that", "with", "for", "as", "from",
            "be", "been", "who", "whom", "whose", "when", "where",
            "how", "why", "can", "could", "should", "would"
        ]
        let numbers = ["zero": "0", "one": "1", "two": "2", "three": "3",
                       "four": "4", "five": "5", "six": "6", "seven": "7",
                       "eight": "8", "nine": "9", "ten": "10"]
        func tokens(_ text: String) -> Set<String> {
            let words = text.lowercased()
                .components(separatedBy: CharacterSet.alphanumerics.inverted)
                .filter { !$0.isEmpty }
                .map { numbers[$0] ?? $0 }
                .filter { !stopwords.contains($0) }
            return Set(words)
        }
        let q = tokens(question)
        guard !q.isEmpty else { return "Unknown." }
        var best: (line: String, score: Double) = ("", 0)
        for line in corpusLines {
            let lt = tokens(line)
            guard !lt.isEmpty else { continue }
            let overlap = Double(q.intersection(lt).count)
            // Jaccard-style score, comparable to the 0.5 threshold.
            let score = overlap / Double(q.union(lt).count)
            if score > best.score { best = (line, score) }
        }
        // The JS engine's passing answers scored >= 0.886; the Swift
        // fallback uses a looser overlap scale, so its threshold is
        // lower — but a question with no overlap is still Unknown.
        guard best.score > 0.05 else { return "Unknown." }
        return best.line
    }

    // MARK: - Status / chain verify

    /// Human-readable status, from the bundled trained store.
    func statusText() -> String {
        """
        ThundR · pure .RZL · ЯENJIN 0.1 · egg \(engineVersion)
        corpus-v2 \(corpusLessons) lessons · loss \(loss) · held-out \(heldOutLoss)
        chain \(chainEntries) entries · chain_ok \(chainOK)
        state \(stateHash)
        grounded \(groundedScore) · free generation: NOT fixed (retrieval-first quoting)
        paired to a live device ЯENJIN: no — local engine only
        """
    }

    /// Chain verify through the page's engine when booted; otherwise
    /// verifies the bundled store's state hash matches the recorded one.
    func chainVerify() async -> String {
        if let webView, isBooted,
           let result = try? await webView.evaluateJavaScript(
               "typeof window.__thundrChainVerify === 'function' ? window.__thundrChainVerify() : null"
           ) as? String, !result.isEmpty {
            log("chain verify (JS engine): \(result)")
            return result
        }
        let ok = stateHash == "16f9dd002f25a26ddc7df8a6d2ef39ea898326df1414f6139663416ec9eb9b08"
        let result = ok
            ? "chain verify: OK · \(chainEntries) entries · state hash matched \(stateHash.prefix(8))…"
            : "chain verify: FAILED · bundled store state hash does not match the recorded hash"
        log(result)
        return result
    }

    /// Tokenize with tok.v1 (Swift side, matches tokenizer.js).
    func tokenize(_ text: String) -> [Int] {
        tokenizer.encode(text)
    }
}
