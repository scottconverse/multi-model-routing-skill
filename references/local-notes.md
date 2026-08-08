# Local notes — machine/account-specific facts

This file is the ONLY place machine- or account-specific facts live. The main
SKILL.md stays generic so the skill works on any machine; everything that is
true only of *this* machine or *this* owner's accounts goes here, with an
as-of date on every entry.

**Reading rule:** treat any entry more than a month old as a hypothesis to
verify (ask the user or re-probe), not a fact. **Writing rule:** when you
discover a durable machine/account fact during a session (a quota situation,
a CLI path, a hardware limit), offer to record it here with today's date.

This file is expected to diverge per machine if you use the skill on more
than one computer — that's fine, it's local, not synced content. Consider
adding it to `.gitignore` in your own fork if you don't want per-machine
facts committed to shared history.

---

## Codex / OpenAI quota

- *(no entries yet — quota is per-account and the CLI won't report it without
  spending a call, so record what you learn here with a date, and pass the
  model explicitly every time: `-c model="<model>"`)*

## CLI locations

- *(as of 2026-08)* `lms` (LM Studio CLI) lives at `~/.lmstudio/bin/lms` and
  may not be on PATH.

## Hardware

- *(no entries yet — record available RAM/VRAM here once measured, with date)*
