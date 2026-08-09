# Contributing

Small repo, one hard rule: **claims in this repo are backed by a run.**

## The evidence rule

Every capability claim in `SKILL.md`, `README.md`, `docs/`, or `references/`
must come from a command someone actually executed — not from a `--help` page,
not from a vendor doc, not from memory. If you can't run it, mark it
**Unverified** in the text and say what would settle it.

This isn't ceremony. Every defect this repo has shipped came from skipping it:

- The handoff said the test suite passed. It passed on Linux. On Windows it
  failed three different ways.
- `--output-schema` was documented for a week before anyone ran it; it blocks
  forever without `< /dev/null`.
- `codex review -m …` was in the docs as the canonical call. `review` rejects
  `-m` outright.
- "A tool server registered once is reachable from whichever agent you route
  to" was published on the landing page. MCP registration is per-agent; the
  claim was simply false.

Negative results are contributions. "I tried X, here's the timing, it doesn't
work in practice" saves the next person an afternoon — see the
`ANTHROPIC_BASE_URL` section in `references/cross-agent.md`.

## Running the tests

```bash
python3 tests/test_call_local.py
```

No real Ollama or LM Studio needed — it spins up mock servers on 127.0.0.1.
It should pass on Linux, macOS and Windows. On Windows it needs Git Bash;
without a POSIX bash it prints `SKIP:` and exits 0 rather than failing.

Every bug fixed in `scripts/call_local.sh` gets a regression test in the same
change. The suite exists because six real defects were found by an audit, and
each one is now a case in it.

## What must not change

- **`references/local-notes.md` is git-ignored and stays that way.** It holds
  one machine's hardware, install paths and account state. Edit
  `local-notes.example.md` if you're changing the template.
- **LF line endings.** `.gitattributes` pins the working tree. A CRLF
  `call_local.sh` is rejected outright by bash, and Windows clones default to
  `core.autocrlf=true`.
- **`scripts/call_local.sh` keeps its executable bit** (mode `100755`).
- **Printed strings stay ASCII.** `cmd.exe` defaults to cp437, which has no em
  dash; one in a `print()` raised `UnicodeEncodeError` *mid-install*, after
  files had been copied. cp1252 hides this because that codepage does have the
  character — so "it looked fine on my machine" proves nothing here.

  **The rule is "printed strings are ASCII", not "files are ASCII."** Comments
  never reach a stream and are exempt; seven non-ASCII characters live in
  comments today and should stay there. Don't widen the check to whole files —
  it would fail for a reason that cannot affect anyone, and a test that cries
  wolf gets disabled. The check in `tests/test_install.py` scopes itself to
  lines that print, on purpose.

CI enforces all three, plus shellcheck and a check that every `references/*.md`
mentioned in the docs actually exists.

## Style

Match what's there. `SKILL.md` is written *to an agent* and is loaded into
context on every trigger — keep it tight and put depth in `references/`, which
load on demand. `docs/MANUAL.md` is written *to a human* and can be long.

Prefer a measured number to an adjective. "~42 s of prompt processing per call"
beats "slow."
