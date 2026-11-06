# Setup

## iPhone app

1. Download `Mike-iPhone.ipa` from
   [Releases](https://github.com/federicotaar/mike/releases).
2. Sideload with SideInstaller, Sideloadly or AltStore (update over the old
   install; settings carry over).
3. With a free Apple ID the signature expires after 7 days - re-sign weekly.
4. On first launch, pick where thinking happens:
   - **Groq API** - paste your own key (stored in the Keychain)
   - **Your own backend** - HTTPS URL + access token
   - **On this iPhone** - on-device model (in integration; the app says so
     honestly until it works)

## Agent core on your own machine

```bash
git clone https://github.com/federicotaar/mike.git
cd mike
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
[ -f .env ] || cp .env.example .env
```

Edit `.env`:

| Variable | Purpose | Required |
| --- | --- | --- |
| `MIKE_TOKEN` | Bearer token the app uses | Yes, before any tunnel |
| `GROQ_API_KEY` | Groq key for chat replies | Only after you approve it |
| `GROQ_MODEL` | Model override | No (default `openai/gpt-oss-120b`) |
| `MIKE_GROQ_TIMEOUT` | Seconds before a model call gives up | No (default `60`) |
| `MIKE_DIGEST_MINUTES` | Minutes between approvals-digest checks | No (default `15`, minimum 1) |
| `NTFY_TOPIC` | ntfy.sh topic for push | No |
| `DB_PATH` | SQLite location | No (default `./mike.db`) |
| `HOST` / `PORT` | Used by `python -m agent.main` | No (default `127.0.0.1:8787`); `run.sh` explicitly binds loopback |
| `AGENT_NAME` | Name Mike uses for itself | No |
| `APPROVAL_REQUIRED` | Enforce approvals | No (default true - keep it) |

Run and check:

```bash
python3 -m pytest tests        # expect all green
./run.sh                       # serves on 127.0.0.1:8787
./check.sh                     # prints 401 without token, JSON with token
```

Point the app's "Your own backend" mode at the HTTPS URL of your tunnel.
