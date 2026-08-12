# Local notes — machine/account-specific facts

**This is the template. Copy it to `local-notes.md` in this folder and edit
that copy.** `local-notes.md` is git-ignored and never committed — it
describes one machine and one owner's accounts, so it has no business in
version control. Keeping it out means `git status` stays clean, `git pull`
never conflicts on it, and no stray `git add -A` can publish your hardware,
your install paths, or your quota to a public repo.

```bash
cp references/local-notes.example.md references/local-notes.md
```

`local-notes.md` is the ONLY place machine- or account-specific facts live.
The main SKILL.md stays generic so the skill works on any machine; everything
true only of *this* machine or *this* owner's accounts goes in your copy, with
an as-of date on every entry.

**Reading rule:** treat any entry more than a month old as a hypothesis to
verify (ask the user or re-probe), not a fact. **Writing rule:** when you
discover a durable machine/account fact during a session (a quota situation,
a CLI path, a hardware limit), offer to record it there with today's date.

---

## Backend roster

- *(no entries yet — record each local engine's name, native discovery
  command/API, whether it is running, and the date you checked)*

## Local model inventories

- *(no entries yet — for each engine, record the reachable model count, model
  identifiers, capabilities, and which models fit in RAM/VRAM. The engine with
  the largest usable inventory should be preferred for local work.)*

## Codex / OpenAI

- *(no entries yet — run `codex doctor` for the active model and auth mode.
  Choose models by capability, not by asking the user; see
  `references/codex.md`. Record here only what you actually verify, with a
  date — especially any model that turns out NOT to be reachable.)*

## Antigravity (`agy`)

- *(no entries yet — the CLI is often NOT on PATH; on Windows look in
  `%LOCALAPPDATA%\agy\bin\agy.exe`. Record the real path here. Run
  `agy models` for the roster — it's free and first-class. Note that it
  injects a large system prompt, so record the per-call input-token cost you
  observe.)*

## Hardware

- *(no entries yet — record available RAM/VRAM here once measured, with date.
  It decides which model sizes you can actually load without thrashing)*
