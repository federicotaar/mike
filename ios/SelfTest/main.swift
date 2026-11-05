import Foundation
import UserNotifications

var failures = 0
var lines: [String] = []
func check(_ name: String, _ cond: Bool) {
    let line = (cond ? "PASS " : "FAIL ") + name
    print(line)
    lines.append(line)
    if !cond { failures += 1 }
}

// 1. Keychain roundtrip + legacy UserDefaults migration.
// Note: an ad-hoc signed process spawned directly on the simulator has no
// keychain access group, so SecItemAdd returns errSecMissingEntitlement
// there. That is a test-environment limitation, not an app defect (real
// sideloaded builds get a real application-identifier). We probe once and
// SKIP the Keychain-dependent assertions in that case instead of faking a
// pass; the migration's UserDefaults cleanup is asserted unconditionally.
func keychainAvailable() -> Bool {
    KeychainStore.save("probe", account: "probe")
    let ok = KeychainStore.load("probe") == "probe"
    KeychainStore.delete("probe")
    return ok
}
let kcOK = keychainAvailable()
KeychainStore.delete(KeychainStore.backendToken)
UserDefaults.standard.set("legacy-secret-123", forKey: "mike.token")
KeychainStore.migrateLegacyToken()
if kcOK {
    check("migration moves token to Keychain", KeychainStore.load(KeychainStore.backendToken) == "legacy-secret-123")
    KeychainStore.save("abc", account: KeychainStore.groqKey)
    check("keychain roundtrip", KeychainStore.load(KeychainStore.groqKey) == "abc")
    check("keychain updates existing credential", KeychainStore.save("updated", account: KeychainStore.groqKey) && KeychainStore.load(KeychainStore.groqKey) == "updated")
    KeychainStore.delete(KeychainStore.groqKey)
    check("keychain delete", KeychainStore.load(KeychainStore.groqKey) == nil)
    KeychainStore.delete(KeychainStore.backendToken)
} else {
    print("SKIP keychain value checks: no keychain access group in ad-hoc sim process (device-covered)")
}
if kcOK {
    check("migration deletes UserDefaults copy after secure save", UserDefaults.standard.string(forKey: "mike.token") == nil)
} else {
    check("failed secure migration preserves legacy token", UserDefaults.standard.string(forKey: "mike.token") == "legacy-secret-123")
    UserDefaults.standard.removeObject(forKey: "mike.token")
}

// 2. Redirect policy fail-closed
func req(_ s: String) -> URLRequest { URLRequest(url: URL(string: s)!) }
check("cross-host redirect blocked", !RedirectPolicy.allowed(newRequest: req("https://evil.example.com/x"), originalHost: "api.groq.com"))
check("plain-http redirect blocked", !RedirectPolicy.allowed(newRequest: req("http://api.groq.com/x"), originalHost: "api.groq.com"))
check("same-host https redirect allowed", RedirectPolicy.allowed(newRequest: req("https://api.groq.com/v1"), originalHost: "api.groq.com"))

// 3. APIClient refuses plain HTTP before any network call
let api = APIClient()
api.baseURL = URL(string: "http://192.168.1.5:8787")
let sem = DispatchSemaphore(value: 0)
var threw = false
Task {
    do { _ = try await api.status(); } catch { threw = true }
    sem.signal()
}
_ = sem.wait(timeout: .now() + 5)
check("APIClient refuses plain http", threw)

// 5. Groq chat-model selection: classifiers/guards/audio never picked,
// even when they sort first in the account's model list (the v0.2.5 bug).
let mockList = [
    "llama-guard-3-8b", "llama-prompt-guard-2-86m", "whisper-large-v3",
    "llama-3.1-8b-instant", "llama-3.3-70b-versatile", "openai/gpt-oss-120b",
    "qwen/qwen3-32b", "mixtral-8x7b-32768", "gemma2-9b-it",
    "deepseek-r1-distill-llama-70b", "llama-3.2-3b-preview"
]
let resolved = GroqClient.resolveChatModel(from: mockList)
check("classifier never selected from 11-model list", resolved == "llama-3.3-70b-versatile")
check("unknown future id never selected", GroqClient.resolveChatModel(from: ["acme/future-llama-9b"]) == nil)
check("resolved model is on the allowlist", GroqClient.supportedChatModels.contains(resolved ?? ""))
let onlyClassifiers = ["llama-guard-3-8b", "whisper-large-v3"]
check("unsupported-only list returns nil, never a guess", GroqClient.resolveChatModel(from: onlyClassifiers) == nil)
// 6. A bad stored pick from an older build is ignored on the next send
UserDefaults.standard.set("llama-guard-3-8b", forKey: "mike.groqModel")
UserDefaults.standard.set(mockList, forKey: "mike.groqModels")
check("stale bad model self-heals from stored list", GroqClient.resolveChatModel() == "llama-3.3-70b-versatile")
UserDefaults.standard.removeObject(forKey: "mike.groqModel")
UserDefaults.standard.removeObject(forKey: "mike.groqModels")

// 4. Provider choice persists and reloads
UserDefaults.standard.removeObject(forKey: "mike.provider")
check("fresh store has no provider", ProviderStore().provider == nil)
let store = ProviderStore()
store.select(.groq)
check("provider persisted", UserDefaults.standard.string(forKey: "mike.provider") == "groq")
check("reloaded provider", ProviderStore().provider == .groq)
UserDefaults.standard.removeObject(forKey: "mike.provider")


// 7. Tool calling: argument validation, approval gating, loop bounds
let tmp = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
try? FileManager.default.createDirectory(at: tmp, withIntermediateDirectories: true)
let agentStore = AgentStore(directory: tmp)
func mkCall(_ name: String, _ args: String) -> Tooling.ToolCall {
    Tooling.ToolCall(id: "call_1", type: "function", function: .init(name: name, arguments: args))
}
check("unknown tool rejected", (try? Tooling.validatedArgs(mkCall("delete_everything", "{}"))) == nil)
check("empty remember rejected", (try? Tooling.validatedArgs(mkCall("remember", "{\"text\":\"\"}"))) == nil)
check("valid remember accepted", (try? Tooling.validatedArgs(mkCall("remember", "{\"text\":\"Fred likes espressos\"}"))) != nil)
check("past reminder rejected", (try? Tooling.validatedArgs(mkCall("schedule_reminder", "{\"text\":\"x\",\"at\":\"2020-01-01T10:00:00+02:00\"}"))) == nil)
check("garbage date rejected", (try? Tooling.validatedArgs(mkCall("schedule_reminder", "{\"text\":\"x\",\"at\":\"tomorrow-ish\"}"))) == nil)
let futureISO = ISO8601DateFormatter().string(from: Date().addingTimeInterval(30 * 24 * 3600))
check("future reminder accepted", (try? Tooling.validatedArgs(mkCall("schedule_reminder", "{\"text\":\"x\",\"at\":\"\(futureISO)\"}"))) != nil)
check("over-one-year reminder rejected", (try? Tooling.validatedArgs(mkCall("schedule_reminder", "{\"text\":\"x\",\"at\":\"2100-01-01T10:00:00+02:00\"}"))) == nil)
check("broken JSON rejected", (try? Tooling.validatedArgs(mkCall("recall", "not json"))) == nil)

// Write tools never execute without approval
let before = agentStore.memory.count
let res = Tooling.run(mkCall("remember", "{\"text\":\"Fred likes espressos\"}"), store: agentStore)
check("write tool returns queued-for-approval message", res.contains("approval"))
check("write tool queued one approval", agentStore.approvals.filter { $0.status == .pending }.count == 1)
check("write NOT executed before approval", agentStore.memory.count == before)
let queued = agentStore.approvals[0]
// Denial path
if let denied = agentStore.resolve(queued.id, approved: false) {
    check("denied approval marked denied", denied.status == .denied)
} else { check("denial resolves pending approval", false) }
check("denied write still not executed", agentStore.memory.isEmpty)
// Approval path executes exactly the stored action
let res2 = Tooling.run(mkCall("remember", "{\"text\":\"Fred likes espressos\"}"), store: agentStore)
_ = res2
let queued2 = agentStore.approvals[0]
if let approved = agentStore.resolve(queued2.id, approved: true) {
    Tooling.executeApproved(approved, store: agentStore)
}
check("approved remember executed", agentStore.memory.first == "Fred likes espressos")
// Read-only recall runs immediately
let recallRes = Tooling.run(mkCall("recall", "{\"query\":\"espresso\"}"), store: agentStore)
check("recall finds approved memory", recallRes.contains("espressos"))
check("recall of unknown term is honest", Tooling.run(mkCall("recall", "{\"query\":\"zzz-nothing\"}"), store: agentStore).contains("Nothing"))
// get_current_time runs immediately
check("get_current_time runs read-only", Tooling.run(mkCall("get_current_time", "{}"), store: agentStore).contains("Current device time"))
// Bad args never crash the loop - model gets a rejection string
check("bad args return rejection text", Tooling.run(mkCall("remember", "{}"), store: agentStore).contains("rejected"))

// 10. Queue survives a restart (fresh store, same directory)
let agentStore2 = AgentStore(directory: tmp)
check("memory survives restart", agentStore2.memory.first == "Fred likes espressos")
check("approvals survive restart", agentStore2.approvals.count == agentStore.approvals.count)
check("activity log survived restart", !agentStore2.activity.isEmpty)
// 11. An approval can only be resolved once
let again = agentStore2.resolve(queued2.id, approved: true)
check("already-resolved approval cannot execute twice", again == nil)
let deniedAgain = agentStore2.resolve(queued.id, approved: true)
check("denied approval cannot later be approved", deniedAgain == nil)

// 8. Groq tool_calls response parses (content may be null)
let mockResp = """
{"choices":[{"message":{"role":"assistant","content":null,"tool_calls":[{"id":"call_9","type":"function","function":{"name":"get_current_time","arguments":"{}"}}]}}]}
"""
let parsed = try? JSONDecoder().decode(Tooling.ToolChatResponse.self, from: Data(mockResp.utf8))
check("tool_calls response parses", parsed?.choices.first?.message.tool_calls?.first?.function.name == "get_current_time")
check("null content tolerated", parsed?.choices.first?.message.content == nil)

// 9. Model download source is fixed, https, Hugging Face only
check("model url is huggingface https litertlm", ModelManager.modelURL.scheme == "https" && ModelManager.modelURL.host == "huggingface.co" && ModelManager.modelURL.path.hasSuffix(".litertlm"))
check("model size constant matches the verified artifact", ModelManager.expectedBytes == 2_008_432_640)

// 9b. Both published artifacts are pinned to the publisher's LFS hashes, and
// the user's artifact choice is explicit (default stays GPU, cpu is opt-in).
let gpuA = ModelManager.Artifact.gpu
let cpuA = ModelManager.Artifact.cpu
check("gpu artifact pins publisher sha256", gpuA.sha256 == "a53a59001894c58e6bdb5b9b227709f91a2e3e556baa7d85acf9c55402ba5cf5")
check("cpu artifact pins publisher sha256", cpuA.sha256 == "181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c")
check("cpu artifact size matches publisher", cpuA.expectedBytes == 2_588_147_712)
check("cpu artifact url is huggingface https litertlm", cpuA.url.scheme == "https" && cpuA.url.host == "huggingface.co" && cpuA.url.path.hasSuffix(".litertlm"))
check("backend follows artifact not guesswork", gpuA.usesCPU == false && cpuA.usesCPU == true)
let mm = ModelManager()
check("artifact default is the shipped gpu build", mm.artifact == .gpu)
mm.select(.cpu)
check("explicit artifact choice is honored", mm.artifact == .cpu)
mm.select(.gpu)
check("artifact choice can switch back", mm.artifact == .gpu)

// 12. Notification scheduling math is real: the calendar trigger's next
// fire date equals the scheduled date (no permission needed to verify this;
// the actual permission prompt and delivery only exist on device, where
// failures are logged to Activity).
let notifTarget = Date().addingTimeInterval(3600)
let comps = Calendar.current.dateComponents([.year, .month, .day, .hour, .minute, .second], from: notifTarget)
let trig = UNCalendarNotificationTrigger(dateMatching: comps, repeats: false)
if let next = trig.nextTriggerDate() {
    check("notification trigger fires at the scheduled time", abs(next.timeIntervalSince(notifTarget)) < 2)
} else {
    check("notification trigger produced a fire date", false)
}

// 13. Proactive dedup: unchanged signals stay silent, new signals speak
let suite = UserDefaults(suiteName: "mike-selftest-proactive")!
suite.removePersistentDomain(forName: "mike-selftest-proactive")
let d1 = ProactiveEngine.signalDigest(approvalIDs: ["a1"], reminderIDs: ["r1"])
check("digest deterministic for same signals", d1 == ProactiveEngine.signalDigest(approvalIDs: ["a1"], reminderIDs: ["r1"]))
check("digest order-independent", ProactiveEngine.signalDigest(approvalIDs: ["b", "a"], reminderIDs: ["2", "1"]) == ProactiveEngine.signalDigest(approvalIDs: ["a", "b"], reminderIDs: ["1", "2"]))
check("new approval changes digest", d1 != ProactiveEngine.signalDigest(approvalIDs: ["a1", "a2"], reminderIDs: ["r1"]))
check("no signals means silence", ProactiveEngine.shouldSpeak(currentDigest: ProactiveEngine.signalDigest(approvalIDs: [], reminderIDs: []), defaults: suite) == false)
check("first sight of signals speaks", ProactiveEngine.shouldSpeak(currentDigest: d1, defaults: suite) == true)
ProactiveEngine.markSpoken(d1, defaults: suite)
check("relaunch with unchanged signals stays silent", ProactiveEngine.shouldSpeak(currentDigest: d1, defaults: suite) == false)
let d2 = ProactiveEngine.signalDigest(approvalIDs: ["a1"], reminderIDs: ["r1", "r2"])
check("new reminder speaks again", ProactiveEngine.shouldSpeak(currentDigest: d2, defaults: suite) == true)

// Backend timestamps are Unix seconds, not Apple's 2001 reference date.
let unixFixture = Data("[{\"id\":\"1\",\"kind\":\"chat\",\"summary\":\"hello\",\"time\":1700000000}]".utf8)
if let entries = try? APIClient.responseDecoder().decode([ActivityEntry].self, from: unixFixture) {
    check("backend activity date uses Unix epoch", abs(entries[0].time.timeIntervalSince1970 - 1700000000) < 0.01)
} else { check("backend activity fixture decodes", false) }

// Persistent lists are newest-first and must retain the newest 200 rows.
let retentionDir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
try? FileManager.default.createDirectory(at: retentionDir, withIntermediateDirectories: true)
let retentionStore = AgentStore(directory: retentionDir)
for index in 0..<205 {
    retentionStore.log("test", "entry-\(index)")
    retentionStore.remember("memory-\(index)")
}
let reopenedStore = AgentStore(directory: retentionDir)
check("relaunch retains newest activity", reopenedStore.activity.first?.summary == "entry-204")
check("relaunch retains newest memory", reopenedStore.memory.first == "memory-204")
check("persisted activity is bounded", reopenedStore.activity.count == 200)
check("persisted memory is bounded", reopenedStore.memory.count == 200)
try? FileManager.default.removeItem(at: retentionDir)
let approvalFixture = Data("[{\"id\":\"1\",\"summary\":\"review\",\"detail\":\"test\",\"createdAt\":1700000000,\"status\":\"pending\"}]".utf8)
if let approvals = try? APIClient.responseDecoder().decode([Approval].self, from: approvalFixture) {
    check("backend approval date uses Unix epoch", abs(approvals[0].createdAt.timeIntervalSince1970 - 1700000000) < 0.01)
} else { check("backend approval fixture decodes", false) }

// A reminder approved after its target time must not roll into next year.
let stale = agentStore.queueApproval(tool: "schedule_reminder", title: "expired", detail: "test",
    argumentsJSON: "{\"text\":\"expired\",\"at\":\"2020-01-01T10:00:00Z\"}")
if let approval = agentStore.resolve(stale.id, approved: true) {
    Tooling.executeApproved(approval, store: agentStore)
}
check("expired approved reminder is rejected", agentStore.activity.first?.summary.contains("has passed") == true)

// Memory management: delete and correct by index, with bounds and blank guards.
let editDir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
try? FileManager.default.createDirectory(at: editDir, withIntermediateDirectories: true)
let editStore = AgentStore(directory: editDir)
editStore.remember("lives in Rome")
editStore.remember("likes tea")
check("correct memory replaces text", editStore.correctMemory(at: 1, to: "  lives in Modena ") && editStore.memory[1] == "lives in Modena")
check("blank correction is refused", editStore.correctMemory(at: 0, to: "   ") == false && editStore.memory[0] == "likes tea")
check("out-of-range correction is refused", editStore.correctMemory(at: 9, to: "x") == false)
check("delete memory removes it", editStore.forgetMemory(at: 0) && editStore.memory == ["lives in Modena"])
check("out-of-range delete is refused", editStore.forgetMemory(at: 5) == false && editStore.memory.count == 1)
check("memory edits are logged", editStore.activity.first?.summary == "Deleted a saved memory")
let editReopened = AgentStore(directory: editDir)
check("memory edits survive relaunch", editReopened.memory == ["lives in Modena"])
try? FileManager.default.removeItem(at: editDir)

// Google (on-device, read-only): PKCE, URLs, callback safety, sync flow.
let rfc: [UInt8] = [116,24,223,180,151,153,224,37,79,250,96,125,216,173,187,186,22,212,37,77,105,214,191,240,91,88,5,88,83,132,141,121]
let pk = GoogleAuth.pkcePair(randomBytes: rfc)
check("PKCE verifier matches RFC 7636", pk.verifier == "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk")
check("PKCE challenge matches RFC 7636", pk.challenge == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")
check("scopes are read-only", GoogleAuth.scopes.allSatisfy { $0.hasSuffix(".readonly") })
check("redirect scheme is the reversed client id", GoogleAuth.redirectURI(clientID: "123-abc.apps.googleusercontent.com") == "com.googleusercontent.apps.123-abc:/oauth2redirect")
check("non-Google client id is rejected", GoogleAuth.redirectURI(clientID: "evil.example.com") == nil)
let au = GoogleAuth.authURL(clientID: "123-abc.apps.googleusercontent.com", state: "st", challenge: "ch")
let auItems = URLComponents(url: au!, resolvingAgainstBaseURL: false)!.queryItems!
func q(_ k: String) -> String? { auItems.first { $0.name == k }?.value }
check("auth URL: offline + S256 + state", q("access_type") == "offline" && q("code_challenge_method") == "S256" && q("state") == "st")
check("auth URL asks for read-only scopes only", q("scope") == GoogleAuth.scopes.joined(separator: " "))
check("callback with wrong state is dropped", GoogleAuth.parseCallback(URL(string: "com.googleusercontent.apps.1:/oauth2redirect?code=x&state=other")!, expectedState: "st") == .failure(.stateMismatch))
check("callback with error is denied", GoogleAuth.parseCallback(URL(string: "com.googleusercontent.apps.1:/oauth2redirect?error=access_denied&state=st")!, expectedState: "st") == .failure(.denied))
check("good callback yields the code", GoogleAuth.parseCallback(URL(string: "com.googleusercontent.apps.1:/oauth2redirect?code=abc&state=st")!, expectedState: "st") == .success("abc"))
let tokBody = Data("{\"access_token\":\"AT\",\"scope\":\"https://www.googleapis.com/auth/gmail.readonly\"}".utf8)
check("token parse reports missing scope", GoogleAuth.parseToken(status: 200, body: tokBody) == .ok(accessToken: "AT", refreshToken: nil, missingScopes: ["https://www.googleapis.com/auth/calendar.readonly"]))
check("invalid_grant means reconsent", GoogleAuth.parseToken(status: 400, body: Data("{\"error\":\"invalid_grant\"}".utf8)) == .needsReconsent)
let rr = GoogleAuth.refreshRequest(clientID: "c", refreshToken: "RT+/=")
check("refresh body is form-encoded and sends no secret", String(data: rr.httpBody!, encoding: .utf8) == "client_id=c&grant_type=refresh_token&refresh_token=RT%2B%2F%3D")
check("gmail URL asks for inbox ids only, bounded", GoogleReader.gmailListURL(sinceEpoch: 100, max: 999).absoluteString.contains("maxResults=50") && GoogleReader.gmailListURL(sinceEpoch: 100).absoluteString.contains("in:inbox"))
let evJSON = Data("{\"items\":[{\"id\":\"e1\",\"summary\":\"Dentist\",\"start\":{\"dateTime\":\"2026-11-05T18:30:00Z\"}},{\"id\":\"e2\",\"status\":\"cancelled\",\"start\":{\"dateTime\":\"2026-11-05T19:00:00Z\"}},{\"id\":\"e3\",\"start\":{\"date\":\"2026-11-06\"}}]}".utf8)
check("events parser skips cancelled and all-day", GoogleReader.parseEvents(evJSON).map { $0.id } == ["e1"])

final class MemStore {
    var seen: [String] = []; var last: Int? = nil; var reconsent = false
    var store: GoogleSync.Store {
        GoogleSync.Store(seen: { self.seen }, setSeen: { self.seen = $0 }, lastCheck: { self.last },
                         setLastCheck: { self.last = $0 }, reconsentSent: { self.reconsent }, setReconsentSent: { self.reconsent = $0 })
    }
}
func fakeSend(token: (Int, String), mail: String, cal: String) -> (URLRequest) async throws -> (Int, Data) {
    return { r in
        let u = r.url!.absoluteString
        if u.contains("oauth2.googleapis.com") { return (token.0, Data(token.1.utf8)) }
        if u.contains("gmail") { return (200, Data(mail.utf8)) }
        return (200, Data(cal.utf8))
    }
}
let okTok = (200, "{\"access_token\":\"AT\",\"scope\":\"https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/calendar.readonly\"}")
let sNow = Date(timeIntervalSince1970: 1_800_000_000)
let sync1 = MemStore()
var o1: GoogleSync.Outcome?
var o2: GoogleSync.Outcome?
var o3: GoogleSync.Outcome?
var o4: GoogleSync.Outcome?
let semG = DispatchSemaphore(value: 0)
Task {
    let send = fakeSend(token: okTok, mail: "{\"messages\":[{\"id\":\"m1\"}]}", cal: "{\"items\":[]}")
    o1 = await GoogleSync.run(clientID: "c", refreshToken: "RT", store: sync1.store, now: sNow, send: send)
    o2 = await GoogleSync.run(clientID: "c", refreshToken: "RT", store: sync1.store, now: sNow.addingTimeInterval(60), send: send)
    o3 = await GoogleSync.run(clientID: "c", refreshToken: nil, store: sync1.store, now: sNow, send: send)
    let dead = fakeSend(token: (400, "{\"error\":\"invalid_grant\"}"), mail: "", cal: "")
    let a = await GoogleSync.run(clientID: "c", refreshToken: "RT", store: sync1.store, now: sNow, send: dead)
    let b = await GoogleSync.run(clientID: "c", refreshToken: "RT", store: sync1.store, now: sNow, send: dead)
    o4 = a; _ = b
    o3 = GoogleSync.Outcome(status: o3!.status, message: b.message == nil ? "quiet" : "spoke")
    semG.signal()
}
_ = semG.wait(timeout: .now() + 10)
check("first check announces the new mail", o1?.message == "1 new email.")
check("second check with same mail stays silent", o2?.status == .ok && o2?.message == nil)
check("not connected does nothing", o3?.status == .notConnected)
check("invalid_grant tells the user to reconnect once", o4?.message == GoogleSync.reconsentText && o3?.message == "quiet")
check("stored dedupe keeps hashes, not ids", !sync1.seen.contains("m1") && sync1.seen.allSatisfy { $0.count == 16 })

let verdict = failures == 0 ? "ALL PASS" : "\(failures) FAILURES"
print(verdict)
lines.append(verdict)
let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
try? lines.joined(separator: "\n").write(to: docs.appendingPathComponent("result.txt"), atomically: true, encoding: .utf8)
exit(failures == 0 ? 0 : 1)
