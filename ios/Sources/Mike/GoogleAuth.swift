import Foundation
import CryptoKit

/// Google sign-in for Mike, on the iPhone itself: no server, no client secret.
/// An iOS-type OAuth client is a public client, so the flow is PKCE only. The
/// refresh token is kept in the Keychain, never in UserDefaults or logs.
/// Scopes are read-only on purpose: Mike can look, not send or edit. Anything
/// that changes Google data would have to go through the approvals queue and
/// is not part of this file.
enum GoogleAuth {
    static let scopes = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/calendar.readonly",
    ]
    static let refreshAccount = "google-refresh-token"

    static func base64URL(_ data: Data) -> String {
        data.base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }

    /// PKCE pair from 32 random bytes (injectable so the RFC 7636 vector is testable).
    static func pkcePair(randomBytes: [UInt8]) -> (verifier: String, challenge: String) {
        let verifier = base64URL(Data(randomBytes))
        let challenge = base64URL(Data(SHA256.hash(data: Data(verifier.utf8))))
        return (verifier, challenge)
    }

    static func randomBytes(_ n: Int = 32) -> [UInt8] {
        var g = SystemRandomNumberGenerator()
        return (0..<n).map { _ in UInt8.random(in: 0...255, using: &g) }
    }

    /// iOS clients redirect to the reversed client id, e.g.
    /// "123-abc.apps.googleusercontent.com" -> "com.googleusercontent.apps.123-abc:/oauth2redirect".
    static func redirectScheme(clientID: String) -> String? {
        let suffix = ".apps.googleusercontent.com"
        guard clientID.hasSuffix(suffix), clientID.count > suffix.count else { return nil }
        let prefix = String(clientID.dropLast(suffix.count))
        guard prefix.allSatisfy({ $0.isLetter || $0.isNumber || $0 == "-" || $0 == "_" }) else { return nil }
        return "com.googleusercontent.apps.\(prefix)"
    }

    static func redirectURI(clientID: String) -> String? {
        redirectScheme(clientID: clientID).map { $0 + ":/oauth2redirect" }
    }

    static func authURL(clientID: String, state: String, challenge: String) -> URL? {
        guard let redirect = redirectURI(clientID: clientID) else { return nil }
        var c = URLComponents(string: "https://accounts.google.com/o/oauth2/v2/auth")!
        c.queryItems = [
            .init(name: "client_id", value: clientID),
            .init(name: "redirect_uri", value: redirect),
            .init(name: "response_type", value: "code"),
            .init(name: "scope", value: scopes.joined(separator: " ")),
            .init(name: "access_type", value: "offline"),
            .init(name: "prompt", value: "consent"),
            .init(name: "state", value: state),
            .init(name: "code_challenge", value: challenge),
            .init(name: "code_challenge_method", value: "S256"),
        ]
        return c.url
    }

    enum CallbackError: Error, Equatable { case denied, stateMismatch, noCode }

    /// Reads the redirect back from the browser. The state must match what we
    /// sent, otherwise the response is not ours and is dropped.
    static func parseCallback(_ url: URL, expectedState: String) -> Result<String, CallbackError> {
        let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []
        func v(_ k: String) -> String? { items.first { $0.name == k }?.value }
        if v("error") != nil { return .failure(.denied) }
        guard v("state") == expectedState else { return .failure(.stateMismatch) }
        guard let code = v("code"), !code.isEmpty else { return .failure(.noCode) }
        return .success(code)
    }

    static func tokenRequest(clientID: String, code: String, verifier: String) -> URLRequest? {
        guard let redirect = redirectURI(clientID: clientID) else { return nil }
        return form("https://oauth2.googleapis.com/token", [
            "client_id": clientID, "code": code, "code_verifier": verifier,
            "grant_type": "authorization_code", "redirect_uri": redirect])
    }

    static func refreshRequest(clientID: String, refreshToken: String) -> URLRequest {
        form("https://oauth2.googleapis.com/token", [
            "client_id": clientID, "grant_type": "refresh_token", "refresh_token": refreshToken])!
    }

    private static func form(_ url: String, _ fields: [String: String]) -> URLRequest? {
        guard let u = URL(string: url) else { return nil }
        var r = URLRequest(url: u)
        r.httpMethod = "POST"
        r.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "content-type")
        var allowed = CharacterSet.alphanumerics
        allowed.insert(charactersIn: "-._~")
        r.httpBody = fields.sorted { $0.key < $1.key }.map {
            "\($0.key)=\($0.value.addingPercentEncoding(withAllowedCharacters: allowed) ?? "")"
        }.joined(separator: "&").data(using: .utf8)
        return r
    }

    enum TokenResult: Equatable {
        case ok(accessToken: String, refreshToken: String?, missingScopes: [String])
        case needsReconsent       // invalid_grant: revoked, or the 7-day Testing expiry
        case failed(String)
    }

    static func parseToken(status: Int, body: Data) -> TokenResult {
        let obj = (try? JSONSerialization.jsonObject(with: body)) as? [String: Any] ?? [:]
        if status == 200, let at = obj["access_token"] as? String {
            let granted = ((obj["scope"] as? String) ?? "").split(separator: " ").map(String.init)
            return .ok(accessToken: at, refreshToken: obj["refresh_token"] as? String,
                       missingScopes: scopes.filter { !granted.contains($0) })
        }
        let err = (obj["error"] as? String) ?? "http_\(status)"
        return err == "invalid_grant" ? .needsReconsent : .failed(err)
    }
}
