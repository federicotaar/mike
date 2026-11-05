# Changelog

All notable changes to Mike are documented here. Versions follow the
`VERSION` file at the repo root; iPhone releases ship as `Mike-iPhone.ipa`
on the [Releases page](https://github.com/federicotaar/mike/releases).

## [Unreleased]

### Added
- Core: `/status` reports `requestsSentToday` and `localDailyCap`; an optional
  local cap (`MIKE_LOCAL_DAILY_CAP`, default off) can stop chat. The provider's
  own quota stays `null` because it cannot be read.
- Core: approvals digest job pushes to your ntfy topic when approvals are
  waiting. Silent while paused, no repeats until the pending set changes.
- Core: `DELETE /memories/{id}`, approval history, activity pruning.

## [0.4.3] - 2026-10-26

### Fixed
- Release workflow: version now comes from the `VERSION` file and existing
  releases are guarded against overwrite (v0.4.2 was previously replaced).
- Local notification scheduling uses a longer, more reliable delay, with a
  retry when the permission dialog appears.

### Added
- Approvals and Activity screens read real on-phone data.
- Keyboard dismissal (tap outside, drag down) in chat, covered by UI tests.
- On-device model runtime (Gemma 4 E2B candidate) generates replies in the
  simulator; physical-device performance still unverified.

## [0.3.0] - 2026-10-25

### Added
- Groq chat with tool calling (time, memory, reminders via the Approvals inbox).
- First-launch setup screen with the three thinking modes: Groq API key,
  your own backend, or on this iPhone.

## [0.2.8] - 2026-10-25

### Changed
- Backend token moved from UserDefaults into the iPhone Keychain; the old
  copy is deleted on first launch after updating.

## [0.2.5] - 2026-10-25

### Added
- "Your own backend" mode over HTTPS with an access token.

## [0.1.4] - 2026-10-25

### Added
- First installable iPhone build: chat shell, settings, and the MIT-licensed
  repo with a professional README.
