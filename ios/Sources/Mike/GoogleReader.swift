import Foundation

/// Read-only Gmail and Calendar requests plus parsers. Gmail is asked for ids
/// only (inbox, bounded), so subjects, senders and bodies are never downloaded.
enum GoogleReader {
    struct Event: Equatable { let id: String; let title: String; let start: Date }

    static func gmailListURL(sinceEpoch: Int, max: Int = 20) -> URL {
        var c = URLComponents(string: "https://gmail.googleapis.com/gmail/v1/users/me/messages")!
        c.queryItems = [.init(name: "q", value: "in:inbox after:\(sinceEpoch)"),
                        .init(name: "maxResults", value: String(min(max, 50)))]
        return c.url!
    }

    static func calendarURL(from: Date, to: Date) -> URL {
        let f = ISO8601DateFormatter()
        var c = URLComponents(string: "https://www.googleapis.com/calendar/v3/calendars/primary/events")!
        c.queryItems = [.init(name: "timeMin", value: f.string(from: from)),
                        .init(name: "timeMax", value: f.string(from: to)),
                        .init(name: "singleEvents", value: "true"),
                        .init(name: "orderBy", value: "startTime"),
                        .init(name: "maxResults", value: "10")]
        return c.url!
    }

    static func parseGmailIDs(_ body: Data) -> [String] {
        let obj = (try? JSONSerialization.jsonObject(with: body)) as? [String: Any]
        return ((obj?["messages"] as? [[String: Any]]) ?? []).compactMap { $0["id"] as? String }
    }

    /// Skips cancelled and all-day events (no dateTime).
    static func parseEvents(_ body: Data) -> [Event] {
        let obj = (try? JSONSerialization.jsonObject(with: body)) as? [String: Any]
        let f1 = ISO8601DateFormatter()
        let f2 = ISO8601DateFormatter()
        f2.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return ((obj?["items"] as? [[String: Any]]) ?? []).compactMap { e in
            if (e["status"] as? String) == "cancelled" { return nil }
            guard let id = e["id"] as? String,
                  let start = e["start"] as? [String: Any],
                  let s = start["dateTime"] as? String,
                  let d = f1.date(from: s) ?? f2.date(from: s) else { return nil }
            return Event(id: id, title: (e["summary"] as? String) ?? "(no title)", start: d)
        }
    }
}
