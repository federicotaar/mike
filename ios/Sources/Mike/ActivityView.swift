import SwiftUI

struct ActivityView: View {
    @EnvironmentObject var api: APIClient
    @EnvironmentObject var store: ProviderStore
    @EnvironmentObject var agent: AgentStore
    @State private var remote: [ActivityEntry] = []
    @State private var showStopConfirm = false
    @State private var loadFailed = false
    @State private var paused: Bool?
    @State private var controlError: String?
    @State private var changingState = false

    var body: some View {
        NavigationStack {
            Group {
                if store.provider == .backend {
                    backendList
                } else {
                    localList
                }
            }
            .navigationTitle("Activity")
            .refreshable { if store.provider == .backend { await reload() } }
            .task { if store.provider == .backend { await reload() } }
            .toolbar {
                if store.provider == .backend {
                    ToolbarItem(placement: .topBarTrailing) {
                        if paused == true {
                            Button("Resume") { changePausedState(false) }
                                .disabled(changingState)
                        } else {
                            Button("Stop", role: .destructive) { showStopConfirm = true }
                                .disabled(changingState)
                        }
                    }
                }
            }
            .alert("Couldn't change backend state", isPresented: Binding(
                get: { controlError != nil }, set: { if !$0 { controlError = nil } })) {
                Button("OK", role: .cancel) { controlError = nil }
            } message: { Text(controlError ?? "") }
            .confirmationDialog("Stop Mike?", isPresented: $showStopConfirm, titleVisibility: .visible) {
                Button("Stop Mike", role: .destructive) {
                    changePausedState(true)
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("Pause chat on your backend until you resume it. This does not cancel phone reminders or pause other providers.")
            }
        }
    }

    @ViewBuilder private var localList: some View {
        if agent.activity.isEmpty {
            ContentUnavailableView("No activity yet", systemImage: "list.bullet.rectangle",
                description: Text("This is the real on-device log - empty because Mike hasn't done anything yet, not because something failed to load. Tool runs, approvals and downloads land here."))
        } else {
            List {
                ForEach(agent.activity) { entry in
                    VStack(alignment: .leading, spacing: 2) {
                        Text(entry.summary)
                        Text(entry.kind.uppercased())
                            .font(.caption2).foregroundStyle(.secondary)
                    }
                }
            }
        }
    }

    @ViewBuilder private var backendList: some View {
        if loadFailed && remote.isEmpty {
            ContentUnavailableView("Can't reach your backend", systemImage: "exclamationmark.triangle",
                description: Text("The backend you set isn't answering. Pull to retry once it is up."))
        } else {
            List {
                ForEach(remote) { entry in
                    VStack(alignment: .leading, spacing: 2) {
                        Text(entry.summary)
                        Text(entry.kind.uppercased())
                            .font(.caption2).foregroundStyle(.secondary)
                    }
                }
            }
        }
    }

    private func changePausedState(_ shouldPause: Bool) {
        guard !changingState else { return }
        changingState = true
        Task {
            defer { changingState = false }
            do {
                if shouldPause { try await api.stopMike() }
                else { try await api.startMike() }
                await reload()
            } catch {
                controlError = "The request failed. Check your backend URL, token and connection, then try again."
            }
        }
    }

    private func reload() async {
        do {
            remote = try await api.activity()
            paused = try await api.status().paused
            loadFailed = false
        } catch {
            loadFailed = true
        }
    }
}

#Preview { ActivityView().environmentObject(APIClient()).environmentObject(ProviderStore()).environmentObject(AgentStore()) }
