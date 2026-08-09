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

- *(no entries yet — record which of Ollama / LM Studio / Codex are installed
  here, whether their servers are running, and the date you checked)*

## Ollama

- *(no entries yet — binary path, and which models are installed)*

## LM Studio

- *(no entries yet — the `lms` CLI is commonly at `~/.lmstudio/bin/lms`
  (`lms.exe` on Windows) and is often NOT on PATH, so record the real path.
  Note which models are downloaded and which actually fit in RAM)*

## Codex / OpenAI quota

- *(no entries yet — quota is per-account and the CLI won't report it without
  spending a call, so record what you learn here with a date, and pass the
  model explicitly every time: `-c model="<model>"`)*

## Hardware

- *(no entries yet — record available RAM/VRAM here once measured, with date.
  It decides which model sizes you can actually load without thrashing)*
