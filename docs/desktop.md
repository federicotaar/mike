# Mike desktop preview

The desktop client is a real chat window for Ubuntu, Windows and macOS.
It is an early preview, not a port of every iPhone feature.

## Current features

- Chat through your own Groq key. Enter it in the masked field at each launch.
- The key stays in process memory. It is not saved to settings, SQLite or logs.
- Add and permanently delete facts with the Memory window. Facts are included
  in chat requests sent to Groq, so only save facts you want that provider to see.
- Pause/resume blocks new chat requests. It cannot recall a request already sent.
- No automatic fallback provider and no automatic paid-plan upgrades.

Not implemented: local inference, reminder tools, conversation persistence,
background monitoring, OS integrations, automatic updates or iPhone sync.
Groq account terms still apply. A quota or account error stops the request.

## Run from source

Use Python 3.11. Ubuntu also needs `python3-tk` (Tk is included in the standard
Windows and python.org macOS Python installers).

```sh
python -m pip install -r requirements.txt
python -m desktop
```

The desktop client creates `mike.db` in the current user's application-data folder:

- Ubuntu: `$XDG_DATA_HOME/Mike`, or `~/.local/share/Mike`.
- Windows: `%LOCALAPPDATA%/Mike`.
- macOS: `~/Library/Application Support/Mike`.

The database stores manually saved facts, the paused flag and a minimal activity
record. Chat text and API keys are not written by the desktop client. Uninstalling
an app package does not delete this folder. Back it up or remove it yourself when
wanted; there is no automatic data deletion during an update.

## Preview packages

The `desktop-preview` GitHub workflow builds on each target OS. It runs service
tests and opens the native window for a bounded GUI smoke test before packaging.
Artifacts are kept for review, not automatically published as stable releases.

- Ubuntu: `Mike-Ubuntu-amd64.deb`, built on Ubuntu 22.04.
- Windows: `Mike-Windows.zip` contains `Mike/Mike.exe` plus required libraries.
  Keep the folder together; the executable is not a standalone single file.
- macOS: `Mike-macOS.zip` contains `Mike.app`; runner architecture determines
  which Macs the preview supports. It is not a universal binary.

These previews are unsigned. No Windows signing certificate or Apple Developer
notarization is configured. Do not treat successful packaging as a guarantee on
every computer. Native runner GUI smoke is not a live authenticated Groq chat test.

For local packaging, install `pyinstaller` and run `python packaging/build_desktop.py`.
