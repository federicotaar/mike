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
| `MemoryView.swift` | Saved-memory screen: list, edit, delete |
| `Models.swift` | Shared data models |
| `GoogleAuth.swift` | Google sign-in (PKCE), tokens in the Keychain |
| `GoogleReader.swift` | Read Gmail/Calendar data after sign-in |
| `GoogleSync.swift` | Background refresh of the Google data cache |
| `GoogleWrite.swift` | Opt-in, approval-gated writes (calendar events, Gmail drafts) |
| `GoogleConnector.swift` | Wires the Google pieces into the provider loop |
| `BackgroundCheck.swift` | Scheduled background refresh entry points |
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

## Desktop app (`desktop/`) - optional, preview

A native Tk chat window that embeds the same core modules directly, no
server needed:

- `__main__.py` - chat window, memory/activity/approvals popups
- `service.py` - session state: Groq key in memory only, facts, history
- `capture.py` / `smoke.py` / `clicktest.py` - CI screenshot, smoke and
  click-through checks on real widgets
- `launcher.py` - frozen entry point

## Trust boundaries

1. The phone talks only to the user-chosen provider (Groq, own backend, or
   the on-device model).
2. The core binds to 127.0.0.1 and requires a bearer token before any tunnel
   exposes it.
3. Phone memory/reminder writes wait for an approval. Google writes
   (calendar events, Gmail drafts) exist but are off unless the user opts in,
   and each one still waits for an approval; there is no send/delete path.
   Messaging, spending, public posting and new-account tools are not
   implemented. The core's
   guardrail name list is not a complete enforcement layer for future tools.
   Self-edit execution is disabled; see `SAFETY.md` for implemented limits.
