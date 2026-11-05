import SwiftUI

/// Saved memory on this phone: see it, correct it, delete it. Nothing here
/// leaves the device.
struct MemoryView: View {
    @EnvironmentObject var agent: AgentStore
    @State private var editingIndex: Int?
    @State private var draft = ""
    @State private var showEditor = false

    var body: some View {
        Group {
            if agent.memory.isEmpty {
                ContentUnavailableView("Nothing saved yet",
                    systemImage: "brain",
                    description: Text("When you approve something for Mike to remember, it shows up here. You can correct or delete it any time."))
            } else {
                List {
                    ForEach(Array(agent.memory.enumerated()), id: \.offset) { index, text in
                        Text(text)
                            .swipeActions(edge: .trailing) {
                                Button(role: .destructive) { agent.forgetMemory(at: index) } label: {
                                    Label("Delete", systemImage: "trash")
                                }
                                Button { beginEdit(index) } label: {
                                    Label("Edit", systemImage: "pencil")
                                }.tint(.blue)
                            }
                            .accessibilityHint("Swipe left to edit or delete")
                    }
                    Section {
                        Text("Stored only on this iPhone. Swipe a row left to edit or delete it.")
                            .font(.footnote).foregroundStyle(.secondary)
                    }
                }
            }
        }
        .navigationTitle("Saved memory")
        .alert("Edit memory", isPresented: $showEditor) {
            TextField("Memory", text: $draft)
            Button("Save") {
                if let i = editingIndex { agent.correctMemory(at: i, to: draft) }
            }
            Button("Cancel", role: .cancel) {}
        }
        #if SIM_MEMORY_FIXTURE
        .onAppear {
            // Screenshot fixture only: compiled out of every device build.
            if agent.memory.isEmpty {
                agent.remember("[Sample] Likes short answers")
                agent.remember("[Sample] Lives in Modena")
            }
        }
        #endif
    }

    private func beginEdit(_ index: Int) {
        guard agent.memory.indices.contains(index) else { return }
        editingIndex = index
        draft = agent.memory[index]
        showEditor = true
    }
}
