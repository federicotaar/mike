import Foundation
import SwiftUI
import AuthenticationServices
import UserNotifications

/// Connects Mike to the owner's own Google account, on this iPhone only.
/// The owner supplies their own OAuth client id (a public identifier, not a
/// secret) from their own Google Cloud project. Nothing is created, chosen or
/// stored for them elsewhere. Read-only scopes; Disconnect deletes the token
/// from the Keychain.
@MainActor
final class GoogleConnector: NSObject, ObservableObject, ASWebAuthenticationPresentationContextProviding {
    static let clientIDKey = "mike.google.clientID"
    @Published var clientID: String = UserDefaults.standard.string(forKey: GoogleConnector.clientIDKey) ?? ""
    @Published var status: String = ""
    @Published var allowActions: Bool = GoogleWrite.enabled
    @Published var connected: Bool = KeychainStore.load(GoogleAuth.refreshAccount) != nil
    private var session: ASWebAuthenticationSession?

    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
            .flatMap { $0.windows }.first { $0.isKeyWindow } ?? ASPresentationAnchor()
    }

    func saveClientID(_ id: String) {
        clientID = id.trimmingCharacters(in: .whitespacesAndNewlines)
        UserDefaults.standard.set(clientID, forKey: GoogleConnector.clientIDKey)
    }

    func connect() {
        guard let scheme = GoogleAuth.redirectScheme(clientID: clientID) else {
            status = "That does not look like a Google iOS client id (it ends in .apps.googleusercontent.com)."
            return
        }
        let pk = GoogleAuth.pkcePair(randomBytes: GoogleAuth.randomBytes())
        let state = GoogleAuth.base64URL(Data(GoogleAuth.randomBytes(16)))
        guard let url = GoogleAuth.authURL(clientID: clientID, state: state, challenge: pk.challenge, write: allowActions) else { return }
        let wantsWrite = allowActions
        let s = ASWebAuthenticationSession(url: url, callbackURLScheme: scheme) { [weak self] cb, err in
            Task { @MainActor in
                guard let self else { return }
                guard let cb, err == nil else { self.status = "Sign-in cancelled."; return }
                switch GoogleAuth.parseCallback(cb, expectedState: state) {
                case .failure: self.status = "Google did not grant access."
                case .success(let code): await self.exchange(code: code, verifier: pk.verifier, write: wantsWrite)
                }
            }
        }
        s.presentationContextProvider = self
        s.prefersEphemeralWebBrowserSession = false
        session = s
        s.start()
    }

    private func exchange(code: String, verifier: String, write: Bool) async {
        guard let req = GoogleAuth.tokenRequest(clientID: clientID, code: code, verifier: verifier),
              let (data, resp) = try? await URLSession.shared.data(for: req),
              let http = resp as? HTTPURLResponse else { status = "Could not reach Google."; return }
        switch GoogleAuth.parseToken(status: http.statusCode, body: data, requested: write ? GoogleAuth.scopes + GoogleWrite.writeScopes : GoogleAuth.scopes) {
        case .ok(_, let refresh, let missing):
            guard missing.isEmpty else { status = "Access was only partly granted. Tick both boxes and try again."; return }
            guard let refresh, KeychainStore.save(refresh, account: GoogleAuth.refreshAccount) else {
                status = "Google gave no refresh token, or the Keychain refused it."; return }
            connected = true
            UserDefaults.standard.set(write, forKey: GoogleWrite.enabledKey)
            status = write ? "Connected. Mike can read, and propose calendar events and email drafts that wait for your approval. It cannot send email." : "Connected. Mike can read your inbox ids and next events, nothing else."
            BackgroundCheck.schedule()
        case .needsReconsent: status = "Google rejected the sign-in. Try again."
        case .failed(let why): status = "Google error: \(why)"
        }
    }

    func disconnect() {
        KeychainStore.delete(GoogleAuth.refreshAccount)
        UserDefaults.standard.removeObject(forKey: BackgroundCheck.Keys.seen)
        connected = false
        allowActions = false
        UserDefaults.standard.set(false, forKey: GoogleWrite.enabledKey)
        status = "Disconnected. The token is deleted from this iPhone. You can also revoke Mike at myaccount.google.com/permissions."
    }

    func checkNow() async {
        let message = await BackgroundCheck.runOnce()
        status = message ?? "Checked. Nothing new."
    }
}
