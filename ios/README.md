# Mike iOS app

SwiftUI client for the agent core. Tabs: Chat, Approvals, Activity (+ Stop),
plus Settings (mode, keys, Google) and a Saved memory screen.

## Layout

- `Package.swift` - SwiftPM package, swift-tools 6.0, iOS 17, library target, language mode v5
- `Sources/Mike/` - the app: `App.swift` (@main), `Models.swift`, `APIClient.swift`, `ChatView.swift`, `ApprovalsView.swift`, `ActivityView.swift`, `SettingsView.swift`, `MemoryView.swift`, `OnboardingView.swift`, provider files (`Provider.swift`, `GroqClient.swift`, `LocalInference.swift`, `ModelManager.swift`), the agent loop (`AgentLoop.swift`, `Tooling.swift`, `AgentStore.swift`, `ProactiveEngine.swift`, `BackgroundCheck.swift`) and the Google integration (`GoogleAuth.swift`, `GoogleReader.swift`, `GoogleSync.swift`, `GoogleWrite.swift`, `GoogleConnector.swift`). See `../docs/ARCHITECTURE.md` for what each file owns.
- `Info.plist`, `xtool.yml` - xtool build config (bundleID `dev.federicotaranu.mike`)

## Build (free, unsigned IPA)

GitHub Actions `macos-latest` + [xtool](https://github.com/xtool-org/xtool) 1.17.0, workflow in `.github/workflows/build-ipa.yml` (manual dispatch). Produces an unsigned IPA artifact (7-day retention). Re-sign and install with SideStore/AltStore/Sideloadly - no paid Apple account needed for the build.

Check remaining private Actions minutes before dispatching; never enable paid overage.
