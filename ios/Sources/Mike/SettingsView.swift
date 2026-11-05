import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var store: ProviderStore
    @EnvironmentObject var models: ModelManager
    @State private var showSetup = false
    @StateObject private var google = GoogleConnector()

    /// Choosing "On this iPhone" is not the same as being able to think there.
    private var localReadiness: String {
        switch models.state {
        case .downloaded:
            return LocalInference.runtimeBundled
                ? "Model is on this phone, but it has not been proven to run on an iPhone 13: it needs about 3 GB of memory and iOS may close the app. If replies fail, switch to Groq."
                : "Model file is on this phone, but this build has no runtime, so Mike cannot think on-device yet. Switch to Groq to chat."
        default:
            return LocalInference.runtimeBundled
                ? "Not ready: no model is downloaded yet. It is a multi-GB file and unproven on an iPhone 13, so Groq is the safer choice."
                : "Not ready: this build has no on-device runtime, so downloading the model would not let Mike think. Use Groq for now."
        }
    }

    var body: some View {
        NavigationStack {
            ScrollViewReader { proxy in
            List {
                Section("Where Mike thinks") {
                    HStack {
                        Text("Current")
                        Spacer()
                        Text(store.provider?.title ?? "Not set").foregroundStyle(.secondary)
                    }
                    if store.provider == .local {
                        Text(localReadiness)
                            .font(.footnote).foregroundStyle(.orange)
                    }
                    Button("Change provider") { showSetup = true }
                    Text("Switching keeps your chats and settings. Mike never switches on its own.")
                        .font(.footnote).foregroundStyle(.secondary)
                }
                Section("Saved memory") {
                    NavigationLink("View, edit or delete") { MemoryView() }
                    Text("What Mike remembers about you, stored only on this iPhone.")
                        .font(.footnote).foregroundStyle(.secondary)
                }
                Section("Google") {
                    if google.connected {
                        Text("Connected. Mike reads inbox ids and your next events to tell you what is new.")
                            .font(.footnote).foregroundStyle(.secondary)
                        Button("Check now") { Task { await google.checkNow() } }
                        Button("Disconnect", role: .destructive) { google.disconnect() }
                    } else {
                        TextField("Your Google iOS client id", text: $google.clientID)
                            .textInputAutocapitalization(.never).autocorrectionDisabled()
                            .onSubmit { google.saveClientID(google.clientID) }
                        Toggle("Also let Mike propose calendar events and email drafts", isOn: $google.allowActions)
                        Text("Each one waits in Approvals for your tap. Mike can save a draft but never sends email. Asks Google for wider access when you connect.")
                            .font(.footnote).foregroundStyle(.secondary)
                        Button("Connect Google") { google.saveClientID(google.clientID); google.connect() }
                    }
                    if !google.status.isEmpty {
                        Text(google.status).font(.footnote).foregroundStyle(.secondary)
                    }
                    Text("By default Mike only reads. With the toggle on it can also add calendar events and save email drafts, each after your tap; it never sends email and cannot delete anything. Checks run only when iOS allows background refresh, so they can be late or skipped. In a Google project in Testing mode, access expires after 7 days and Mike asks you to reconnect.")
                        .font(.footnote).foregroundStyle(.secondary)
                        .id("googleEnd")
                }
                if store.provider == .groq {
                    Section("Groq") {
                        Text(KeychainStore.load(KeychainStore.groqKey) != nil
                             ? "Key saved in the iPhone Keychain." : "No key saved yet.")
                            .font(.footnote).foregroundStyle(.secondary)
                        Button("Remove Groq key", role: .destructive) {
                            KeychainStore.delete(KeychainStore.groqKey)
                        }
                    }
                }
                if store.provider == .backend {
                    Section("Backend") {
                        Text(UserDefaults.standard.string(forKey: "mike.baseURL") ?? "No URL set")
                            .font(.footnote).foregroundStyle(.secondary)
                        Button("Remove backend token", role: .destructive) {
                            KeychainStore.delete(KeychainStore.backendToken)
                        }
                    }
                }
                if store.provider == .local {
                    Section("On-device model") {
                        switch models.state {
                        case .notDownloaded:
                            Picker("Model build", selection: Binding(
                                get: { models.artifact },
                                set: { models.select($0) })) {
                                ForEach(ModelManager.Artifact.allCases) { a in
                                    Text(a.pickTitle).tag(a)
                                }
                            }
                            Text(models.artifact.pickBlurb)
                                .font(.footnote).foregroundStyle(.secondary)
                            if LocalInference.runtimeBundled {
                                Text("Gemma 4 E2B in LiteRT-LM format. Downloads from Hugging Face over HTTPS - no account needed, and the file is checked against the publisher's checksum after downloading. Keep Mike open while it downloads. Only download if that is OK.")
                                    .font(.footnote).foregroundStyle(.secondary)
                            } else {
                                Text("Gemma 4 E2B in LiteRT-LM format - but this build does not include the runtime, so the file cannot chat yet. Downloads from Hugging Face over HTTPS - no account needed. Only download if that is OK.")
                                    .font(.footnote).foregroundStyle(.secondary)
                            }
                            Button("Download model") { models.startDownload() }
                        case .downloading(let p):
                            ProgressView(value: p) { Text("Downloading model - \(Int(p * 100))%") }
                            Button("Cancel", role: .destructive) { models.cancelDownload() }
                        case .verifying:
                            ProgressView { Text("Checking the file against the publisher's checksum...") }
                        case .downloaded(let bytes):
                            if LocalInference.runtimeBundled {
                                Text("Gemma 4 E2B (\(models.artifact.pickTitle)) is on this phone (\(String(format: "%.1f", Double(bytes) / 1e9)) GB), checksum verified. The first reply loads the model (slow on first use), and iPhone 13 behavior is untested. If a local reply fails you get the real error, never a fake one.")
                                    .font(.footnote).foregroundStyle(.secondary)
                            } else {
                                Text("Gemma 4 E2B is on this phone (\(String(format: "%.1f", Double(bytes) / 1e9)) GB), checksum verified. This build does not include the runtime, so the file cannot chat yet.")
                                    .font(.footnote).foregroundStyle(.secondary)
                            }
                            Button("Delete model", role: .destructive) { models.deleteModel() }
                        case .failed(let why):
                            Text(why).font(.footnote).foregroundStyle(.secondary)
                            Button("Try again") { models.startDownload() }
                        }
                    }
                }
            }
            .onAppear {
                #if SIM_SETTINGS_SCROLLED
                DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
                    withAnimation { proxy.scrollTo("googleEnd", anchor: .bottom) }
                }
                #endif
            }
            }
            .navigationTitle("Settings")
            .sheet(isPresented: $showSetup) {
                OnboardingView()
                    .environmentObject(store)
                    .environmentObject(APIClient())
            }
        }
    }
}

#Preview { SettingsView().environmentObject(ProviderStore()).environmentObject(ModelManager()) }
