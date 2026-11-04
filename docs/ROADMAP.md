# Roadmap

What Mike does not do yet, in the order it is planned. Nothing on this list
is claimed as working anywhere else in the repo.

## Next

- **Real proactive jobs in the core.** `agent/scheduler.py` starts but
  registers zero jobs. First candidates: a morning briefing and a
  quota-remaining check, each only when it has something genuinely useful
  to say.
- **Physical-device verification of the on-device model.** Gemma 4 E2B
  generates replies in the simulator; memory and speed on a real iPhone 13
  decide whether on-device mode ships as default.
- **Per-day quota tracking** so `/status` can report a real
  `quotaRemainingToday` instead of `null`.

## Then

- **Memory and tools in Groq mode.** Approvals/activity already work
  against a self-hosted core; wiring them into direct-Groq mode is planned.
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
