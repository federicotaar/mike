import Foundation
import CryptoKit

/// One background/foreground check. Network and storage are injected so the
/// selftest drives it with fixtures. It never logs tokens or item contents,
/// stores only short hashes of ids, and only ever speaks: it cannot act on
/// Google.
enum GoogleSync {
    struct Outcome: Equatable {
        enum Status: Equatable { case notConnected, ok, needsReconsent, failed(String) }
        var status: Status
        var message: String?
    }

    struct Store {
        var seen: () -> [String]
        var setSeen: ([String]) -> Void
        var lastCheck: () -> Int?
        var setLastCheck: (Int) -> Void
        var reconsentSent: () -> Bool
        var setReconsentSent: (Bool) -> Void
    }

    static func hash(_ id: String) -> String {
        SHA256.hash(data: Data(id.utf8)).prefix(8).map { String(format: "%02x", $0) }.joined()
    }

    /// Mirror of mike-watch/src/briefing.js so both sides say the same thing.
    static func briefing(newMail: Int, events: [GoogleReader.Event], tz: TimeZone = TimeZone(identifier: "Europe/Rome")!) -> String? {
        if newMail == 0 && events.isEmpty { return nil }
        var parts: [String] = []
        if newMail > 0 { parts.append("\(newMail) new email\(newMail == 1 ? "" : "s")") }
        if let next = events.first {
            let f = DateFormatter(); f.dateFormat = "HH:mm"; f.timeZone = tz
            parts.append("\(events.count) event\(events.count == 1 ? "" : "s") soon (next: \(next.title) at \(f.string(from: next.start)))")
        }
        return parts.joined(separator: "; ") + "."
    }

    static let reconsentText = "Google sign-in expired. Open Mike to reconnect."

    static func run(clientID: String, refreshToken: String?, store: Store, now: Date,
                    send: (URLRequest) async throws -> (Int, Data)) async -> Outcome {
        guard let refreshToken else { return Outcome(status: .notConnected, message: nil) }
        do {
            let (ts, tb) = try await send(GoogleAuth.refreshRequest(clientID: clientID, refreshToken: refreshToken))
            switch GoogleAuth.parseToken(status: ts, body: tb) {
            case .needsReconsent:
                if store.reconsentSent() { return Outcome(status: .needsReconsent, message: nil) }
                store.setReconsentSent(true)
                return Outcome(status: .needsReconsent, message: reconsentText)
            case .failed(let why):
                return Outcome(status: .failed(why), message: nil)
            case .ok(let token, _, _):
                store.setReconsentSent(false)
                let nowSec = Int(now.timeIntervalSince1970)
                let last = store.lastCheck() ?? (nowSec - 3600)
                func get(_ url: URL) async throws -> (Int, Data) {
                    var r = URLRequest(url: url)
                    r.setValue("Bearer \(token)", forHTTPHeaderField: "authorization")
                    return try await send(r)
                }
                let (ms, mb) = try await get(GoogleReader.gmailListURL(sinceEpoch: last))
                let (cs, cb) = try await get(GoogleReader.calendarURL(from: now, to: now.addingTimeInterval(7200)))
                guard ms == 200, cs == 200 else { return Outcome(status: .failed("http_\(ms)_\(cs)"), message: nil) }
                let mailIDs = GoogleReader.parseGmailIDs(mb)
                let events = GoogleReader.parseEvents(cb)
                let seen = Set(store.seen())
                let mailHashes = mailIDs.map { hash($0) }
                let evHashes = events.map { hash("ev:" + $0.id) }
                let freshMail = mailHashes.filter { !seen.contains($0) }.count
                let freshEvents = zip(events, evHashes).filter { !seen.contains($0.1) }.map { $0.0 }
                let keep = Array((mailHashes + evHashes + store.seen().filter { !(mailHashes + evHashes).contains($0) }).prefix(200))
                store.setSeen(keep)
                store.setLastCheck(nowSec)
                return Outcome(status: .ok, message: briefing(newMail: freshMail, events: freshEvents))
            }
        } catch {
            return Outcome(status: .failed("network"), message: nil)
        }
    }
}
