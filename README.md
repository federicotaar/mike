<div align="center">

# Mike

<img src="mike-logo.png" alt="Mike logo" width="180">

**A personal AI assistant for phone and desktop. Open source, with clear controls and honest limits.**

![status](https://img.shields.io/badge/status-v0.4.4--preview.1%20early-orange)
![license](https://img.shields.io/badge/license-MIT-lightgrey)
![cost](https://img.shields.io/badge/app-0%E2%82%AC%20free%20forever-brightgreen)

</div>

---

Mike combines an iOS app with a portable Python agent core. Ubuntu, Windows
and macOS desktop clients are in early preview: the first packages
(`desktop-v0.1.0-preview.1` on the Releases page) ship a native chat window
with session-only Groq keys, saved facts and pause controls, still unsigned
and under smoke testing.
The iPhone app remains available as a sideloadable IPA.
On first launch it asks one question: **where should Mike's thinking happen?**
You pick, and you can change your mind later in Settings - your chats and
settings stay, and Mike never switches on its own.

| Mode | What it means | Current implementation status |
| --- | --- | --- |
| **Groq API** | Chat replies from Groq's API, direct from the phone. You paste your own key into the app, privately. | **Chat implemented, in device testing.** The key is stored in the iPhone Keychain and used only in requests the app makes to api.groq.com. If Groq returns an error (for example a spent quota) Mike shows it - it never switches providers on its own. Time, recall, approved memory storage and reminder tools are implemented. Physical-device testing is still needed. |
| **Your own backend** | Connect to a Mike core you run yourself (HTTPS URL + access token). | **Implemented; latest changes under test.** HTTPS is required; the token is stored in the Keychain. Approvals and Activity screens read from your core. |
| **On this iPhone** | A small on-device model (candidate: Gemma 4 E2B, which has documented tool calling). | **Experimental.** The runtime and checksum-verified model download are integrated; earlier simulator smoke testing generated replies. Physical iPhone 13 memory usage and speed remain unverified. No download starts before you choose it. |

The app is free, forever. If you use a third-party provider key, that
account's terms and any costs are between you and them - Mike never changes
providers, upgrades plans, or spends anything on its own.

## Platform availability

| Platform | Available now | In progress |
| --- | --- | --- |
| iPhone | Sideloadable iOS app; Groq, own-backend and experimental local modes | Physical-device verification of the latest changes |
| Ubuntu | Python core and desktop preview from source | Reviewed desktop package |
| Windows | Python core and desktop preview from source | Reviewed Windows executable |
| macOS | Python core and desktop preview from source | Reviewed macOS package |

Desktop package status will be updated only after builds and smoke tests pass.
No released desktop download is implied by this table. See [desktop preview setup and limits](docs/desktop.md).

## What iOS does and doesn't allow

Design boundaries Mike is built around - these are platform rules, and most
of them are **planned work, not shipped features**:

- Chat works whenever you open the app (Groq or your backend).
- iOS can deliver **scheduled local notifications** when the app is closed; Mike implements approved reminders and a greeting on reopen. Earlier simulator checks passed; physical-device testing remains needed.
- iOS grants **short background windows** at times the system chooses; using them for checks is planned, not in this build.
- **Not implemented:** an always-running agent. Force-quitting stops app execution until reopen; already scheduled system notifications can still be delivered. An on-device model changes where thinking happens, not when iOS allows it.

## Install the iPhone app

No App Store, no paid Apple account:

1. Download `Mike-iPhone.ipa` from [Releases](https://github.com/federicotaar/mike/releases).
2. Sideload it with a tool like SideInstaller, Sideloadly or AltStore.
3. With a free Apple ID the signature expires after 7 days - re-sign weekly (Apple's rule, not ours).

## The agent core (optional backend)

What exists today: a FastAPI core with a chat endpoint, an approvals queue,
an activity log, SQLite memory with search and export, a scheduled
approvals-digest job, a test suite, and guardrails
(`agent/guardrails.py`).

Planned, not built yet: the self-improvement loop below.

```bash
set -euo pipefail
git clone https://github.com/federicotaar/mike.git
cd mike
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
[ -f .env ] || cp .env.example .env   # existing .env is never overwritten
# set MIKE_TOKEN in .env now; GROQ_API_KEY later, once approved
python3 -m pytest tests
DB_PATH=./mike.db uvicorn agent.api:app --host 127.0.0.1 --port 8787
```

This binds to 127.0.0.1 only. Every endpoint requires
`Authorization: Bearer $MIKE_TOKEN` once the token is set - set it BEFORE any
tunnel or port forward exposes the core. Then point the app's "Your own
backend" mode at its HTTPS URL.

## What "self-improving" means here (planned)

1. **It learns you.** Corrections and approvals become memory rows it reads back next time. (Exists in the core.)
2. **It will propose improvements to its own code - once it is safe.** The plan: draft a change on a git branch, run tests inside a networkless throwaway container, show you the diff, apply only with your yes. Until that isolated container exists, self-edit execution is DISABLED on purpose: model-generated code never runs.
3. **It stays in its lane.** Messaging anyone, spending, posting, or new permissions always require your approval. Guardrails live in `agent/guardrails.py`, which the self-edit loop is forbidden to touch.

## Privacy

- Keys and tokens live in the iPhone Keychain, not in logs, the repo, or chats. Builds before v0.2 kept the backend token in UserDefaults; v0.2 moves it to the Keychain and deletes the old copy on first launch.
- No analytics, no tracking, no third-party servers except the provider you chose yourself.

## Screenshots

Automated simulator captures of the v0.2 UI (fresh-install states, no backend
connected, no key entered):

- [Setup screen](https://github.com/federicotaar/mike/releases/download/sim-evidence/ONBOARDING.png)
- [Chat (Groq mode selected)](https://github.com/federicotaar/mike/releases/download/sim-evidence/CHAT.png)
- [Chat with on-device mode selected, honestly unavailable](https://github.com/federicotaar/mike/releases/download/sim-evidence/LOCALCHAT.png)
- [Settings](https://github.com/federicotaar/mike/releases/download/sim-evidence/SETTINGS.png)
- [Approvals](https://github.com/federicotaar/mike/releases/download/sim-evidence/APPROVALS.png)
- [Activity](https://github.com/federicotaar/mike/releases/download/sim-evidence/ACTIVITY.png)

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - how the app and the core fit together
- [Setup](docs/SETUP.md) - install the app, run the core
- [Core API](docs/API.md) - every endpoint the app uses
- [Safety model](docs/SAFETY.md) - the rules Mike cannot break
- [Testing](docs/TESTING.md) - what is tested and how
- [Roadmap](docs/ROADMAP.md) - planned work, honestly labeled
- [Changelog](CHANGELOG.md)

## License

MIT. See [LICENSE](LICENSE).
