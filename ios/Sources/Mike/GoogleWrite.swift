import Foundation

/// The "doing things" half of Google, kept narrow and approval-gated.
/// Mike may only: (1) create a calendar event, (2) save a Gmail DRAFT.
/// There is deliberately no send, delete, or edit-existing path here: a draft
/// sits in Gmail for the owner to read and send themselves. Every action is
/// queued in Approvals first and only runs after a tap.
/// Needs the wider scopes below, which the owner grants separately.
enum GoogleWrite {
    static let writeScopes = [
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/gmail.compose",
    ]
    static let enabledKey = "mike.google.write"
    static var enabled: Bool { UserDefaults.standard.bool(forKey: enabledKey) }

    struct EventSpec: Equatable { let title: String; let start: Date; let end: Date }
    struct DraftSpec: Equatable { let to: String; let subject: String; let body: String }

    static func validEmail(_ s: String) -> Bool {
        let parts = s.split(separator: "@", omittingEmptySubsequences: false)
        guard parts.count == 2, !parts[0].isEmpty, parts[1].contains("."), s.count <= 254 else { return false }
        return !s.contains { $0.isWhitespace || $0 == "," || $0 == ";" || $0 == "<" || $0 == ">" }
    }

    static func eventSpec(_ args: [String: Any], now: Date = Date()) -> EventSpec? {
        guard let t = (args["title"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines),
              !t.isEmpty, t.count <= 200,
              let s = args["start"] as? String, let start = Tooling.parseDate(s),
              let e = args["end"] as? String, let end = Tooling.parseDate(e),
              start > now.addingTimeInterval(60), end > start,
              end.timeIntervalSince(start) <= 24 * 3600,
              start < now.addingTimeInterval(366 * 24 * 3600) else { return nil }
        return EventSpec(title: t, start: start, end: end)
    }

    static func draftSpec(_ args: [String: Any]) -> DraftSpec? {
        guard let to = (args["to"] as? String)?.trimmingCharacters(in: .whitespaces), validEmail(to),
              let subject = args["subject"] as? String, !subject.isEmpty, subject.count <= 200,
              !subject.contains("\r"), !subject.contains("\n"),
              let body = args["body"] as? String, !body.isEmpty, body.count <= 5000 else { return nil }
        return DraftSpec(to: to, subject: subject, body: body)
    }

    static func eventRequest(_ spec: EventSpec, token: String) -> URLRequest {
        var r = URLRequest(url: URL(string: "https://www.googleapis.com/calendar/v3/calendars/primary/events")!)
        r.httpMethod = "POST"
        r.setValue("Bearer \(token)", forHTTPHeaderField: "authorization")
        r.setValue("application/json", forHTTPHeaderField: "content-type")
        let f = ISO8601DateFormatter()
        let body: [String: Any] = ["summary": spec.title,
            "start": ["dateTime": f.string(from: spec.start)], "end": ["dateTime": f.string(from: spec.end)]]
        r.httpBody = try? JSONSerialization.data(withJSONObject: body)
        return r
    }

    static func rfc822(_ d: DraftSpec) -> String {
        let subjectB64 = Data(d.subject.utf8).base64EncodedString()
        return "To: \(d.to)\r\nSubject: =?UTF-8?B?\(subjectB64)?=\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n\(d.body)"
    }

    /// Always the drafts endpoint. Never /messages/send.
    static func draftRequest(_ d: DraftSpec, token: String) -> URLRequest {
        var r = URLRequest(url: URL(string: "https://gmail.googleapis.com/gmail/v1/users/me/drafts")!)
        r.httpMethod = "POST"
        r.setValue("Bearer \(token)", forHTTPHeaderField: "authorization")
        r.setValue("application/json", forHTTPHeaderField: "content-type")
        let raw = GoogleAuth.base64URL(Data(rfc822(d).utf8))
        r.httpBody = try? JSONSerialization.data(withJSONObject: ["message": ["raw": raw]])
        return r
    }

    /// Runs one approved action. Returns an honest one-line result for the log.
    static func perform(tool: String, args: [String: Any], clientID: String, refreshToken: String?,
                        send: (URLRequest) async throws -> (Int, Data)) async -> String {
        
        guard let refreshToken else { return "Google is not connected; nothing was done." }
        do {
            let (ts, tb) = try await send(GoogleAuth.refreshRequest(clientID: clientID, refreshToken: refreshToken))
            guard case .ok(let token, _, _) = GoogleAuth.parseToken(status: ts, body: tb) else {
                return "Google sign-in needs renewing; nothing was done."
            }
            switch tool {
            case "create_calendar_event":
                guard let spec = eventSpec(args) else { return "The event details are no longer valid; nothing was created." }
                let (s, _) = try await send(eventRequest(spec, token: token))
                return s == 200 ? "Calendar event created: \"\(spec.title)\"." : "Google refused the event (http \(s)); nothing was created."
            case "draft_email":
                guard let spec = draftSpec(args) else { return "The draft details are invalid; nothing was saved." }
                let (s, _) = try await send(draftRequest(spec, token: token))
                return s == 200 ? "Draft saved in Gmail to \(spec.to). Not sent - you send it yourself." : "Google refused the draft (http \(s)); nothing was saved."
            default:
                return "Unknown Google action; nothing was done."
            }
        } catch {
            return "Network problem; nothing was done."
        }
    }
}
