import Foundation
import BackgroundTasks
import UserNotifications

/// Opportunistic background check. iOS decides when (or whether) this runs:
/// it is not a schedule and not a guarantee. Nothing is delivered while the
/// phone is off or iOS skips the task. When it does run it only reads, then
/// posts one local notification if something is new.
enum BackgroundCheck {
    static let taskID = "dev.federicotaranu.mike.refresh"
    enum Keys {
        static let seen = "mike.google.seen"
        static let last = "mike.google.last"
        static let reconsent = "mike.google.reconsent"
    }

    static func register() {
        BGTaskScheduler.shared.register(forTaskWithIdentifier: taskID, using: nil) { task in
            schedule()  // always queue the next one first
            let work = Task {
                let msg = await runOnce()
                if let msg { await notify(msg) }
                task.setTaskCompleted(success: true)
            }
            task.expirationHandler = { work.cancel() }
        }
    }

    static func schedule() {
        let req = BGAppRefreshTaskRequest(identifier: taskID)
        req.earliestBeginDate = Date(timeIntervalSinceNow: 30 * 60)
        try? BGTaskScheduler.shared.submit(req)
    }

    static var store: GoogleSync.Store {
        let d = UserDefaults.standard
        return GoogleSync.Store(
            seen: { d.stringArray(forKey: Keys.seen) ?? [] },
            setSeen: { d.set($0, forKey: Keys.seen) },
            lastCheck: { d.object(forKey: Keys.last) as? Int },
            setLastCheck: { d.set($0, forKey: Keys.last) },
            reconsentSent: { d.bool(forKey: Keys.reconsent) },
            setReconsentSent: { d.set($0, forKey: Keys.reconsent) })
    }

    /// Returns the message to say, or nil. Never throws, never logs contents.
    static func runOnce() async -> String? {
        let clientID = UserDefaults.standard.string(forKey: GoogleConnector.clientIDKey) ?? ""
        let out = await GoogleSync.run(clientID: clientID, refreshToken: KeychainStore.load(GoogleAuth.refreshAccount),
                                       store: store, now: Date()) { req in
            let (data, resp) = try await URLSession.shared.data(for: req)
            return ((resp as? HTTPURLResponse)?.statusCode ?? 0, data)
        }
        return out.message
    }

    static func notify(_ text: String) async {
        let c = UNMutableNotificationContent()
        c.title = "Mike"
        c.body = text
        let r = UNNotificationRequest(identifier: "mike.google.\(UUID().uuidString)", content: c, trigger: nil)
        try? await UNUserNotificationCenter.current().add(r)
    }
}
