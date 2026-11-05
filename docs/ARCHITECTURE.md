# Architecture

Mike has two parts that can work together or apart.

## iPhone app (`ios/`)

SwiftUI app, iOS 17+, built for iPhone 13 and newer.

| File | Responsibility |
| --- | --- |
| `App.swift` | App entry, tab shell, onboarding gate |
| `OnboardingView.swift` | First-launch choice of thinking mode |
| `ChatView.swift` | Chat UI, keyboard handling, glass input bar |
| `SettingsView.swift` | Mode switching, key/token entry, model downloads |
| `ApprovalsView.swift` | The approval inbox: every sensitive action waits here |
| `ActivityView.swift` | The activity log the agent cannot hide from |
| `Provider.swift` | The three thinking modes behind one interface |
| `GroqClient.swift` | Direct Groq API calls with the user's own key |
| `APIClient.swift` | Talks to a self-hosted core over HTTPS + bearer token |
| `LocalInference.swift` | On-device model runtime (Gemma 4 E2B candidate) |
| `ModelManager.swift` | Model download, CPU/GPU artifacts, storage |
| `AgentLoop.swift` | Tool-calling loop on top of a provider |
| `Tooling.swift` | Tools Mike can call (time, memory, reminders) |
| `AgentStore.swift` | On-phone persistence for chats, memory, approvals |
| `ProactiveEngine.swift` | Scheduled-notification proactivity |
| `RuntimeSmoke.swift` | In-app smoke checks used by CI |

Secrets (Groq key, backend token) live in the iPhone Keychain. Nothing is
sent anywhere except the provider the user picked.

## Agent core (`agent/`) - optional

A small FastAPI service for running Mike on the user's own machine:

- `api.py` - HTTP API the app talks to (see `docs/API.md`)
- `brain.py` - one approved inference provider, fail closed
- `memory.py` - SQLite: memories, approvals, activity, paused flag
- `guardrails.py` - actions that always need a human yes
- `selfedit.py` - the self-improvement loop, DISABLED until isolation exists
- `scheduler.py` - registers proactive jobs (one so far: the approvals digest)
- `proactive.py` - jobs that speak only when they have something real to say
- `notify.py` - ntfy push notifications
- `config.py` - `.env`-driven settings; secrets never come from the repo

## Trust boundaries

1. The phone talks only to the user-chosen provider (Groq, own backend, or
   the on-device model).
2. The core binds to 127.0.0.1 and requires a bearer token before any tunnel
   exposes it.
3. Phone memory/reminder writes wait for an approval. Messaging, spending,
   public posting and new-account tools are not implemented. The core's
   guardrail name list is not a complete enforcement layer for future tools.
   Self-edit execution is disabled; see `SAFETY.md` for implemented limits.
