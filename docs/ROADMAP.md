# Roadmap

What Mike does not do yet, in the order it is planned. Nothing on this list
is claimed as working anywhere else in the repo.

## Next

- **More proactive jobs in the core.** One job exists: the approvals digest
  (pushes to your own ntfy topic when approvals are waiting, silent while
  paused, no repeats until the pending set changes). A morning briefing is
  the next candidate, only when it has something genuinely useful to say.
- **Physical-device verification of the on-device model.** Gemma 4 E2B
  generates replies in the simulator; memory and speed on a real iPhone 13
  decide whether on-device mode ships as default.
- **Provider quota.** `/status` keeps `quotaRemainingToday` as `null` because
  Groq's remaining free quota is not readable from the core. Only a
  local count (`requestsSentToday`) and an optional user-set cap exist.

## Then

- **Memory sync with the optional backend.** The phone has a Saved memory
  screen (edit, delete; built and compiled in CI, simulator screenshot only,
  swipe gestures and a physical iPhone not yet tested). Sync with the separate
  optional backend remains unbuilt.
- **Isolated self-improvement.** Draft change on a branch, tests in a
  networkless throwaway container, user reviews the diff, merge only with
  an explicit yes. Disabled until the container exists (see
  `docs/SAFETY.md`).
- **UI polish.** Instagram-style navigation and a rounded glass text bar,
  from the user's reference designs.

## Explicitly not planned

- Always-on background operation (iOS does not allow it).
- Paid providers or automatic fallback to one.
- Cloud sync of memory: it stays on the device and the user's own core.
