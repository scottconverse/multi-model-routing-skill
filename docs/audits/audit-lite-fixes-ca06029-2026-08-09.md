# Audit Lite — the second fix commit (`ca06029`)
**Date:** 2026-08-09
**Scope:** `ca06029`, which closed the four findings of the previous fix-audit. Files touched: `install.py`, `scripts/benchmarks.sh`, `tests/test_install.py`, `tests/test_benchmarks.py`, plus the prior report's move into `docs/audits/`.
**Reviewer:** Claude (audit-lite)

## TL;DR

**The four prior findings are genuinely closed** — `--help` is clean and complete, the cache variable is right, the flag-coverage test is real, and `NOT_SHIPPED` uses a directory pattern. But the commit leaves **five new defects**, and the two worst are both guards that are green because of where they run: the payload drift guard **cannot run where it ships** (outside a checkout `git ls-files` exits 128, the unchecked result becomes an empty list, and the check prints `ok` having verified nothing), and the cp437 guard checks `install.py` **by name**, so the test harness's own em dashes went unnoticed and crash the suite on the exact run that has bad news.

Ship-with-fixes. No data risk, but three Majors, all in the tests-and-docs layer this repo leans on hardest.

## Severity rollup (original)
- Blocker: 0 | Critical: 0 | **Major: 3** | **Minor: 2** | Nit: 0

## Resolution — 2026-08-09, same day
**All five fixed. Rollup now 0 / 0 / 0 / 0 / 0.**

| Finding | Status |
|---|---|
| F-201 drift guard green while blind | **Fixed** — `git_files()` returns `None` on a non-zero exit instead of letting empty stdout mean "nothing unaccounted". Outside a checkout the guard now prints `SKIP payload drift guard (3 checks) - not a git checkout`, and the tally reads `PASS: 21 install.py checks (1 skipped: ...)`. Verified in a real install with a junk file planted in `references/`: previously `ok`, now an explicit skip. |
| F-202 `--limit`/`--refresh` documented nowhere | **Fixed** — a full flag table in `references/benchmarks.md`, both flags in `docs/MANUAL.md`, `--model` in `README.md`. Enforced: the same parser-derived flag list that guards `--help` now guards both doc surfaces. |
| F-203 date-fossil guard only fired at depth ≥2 | **Fixed** — asserts no `NOT_SHIPPED` entry matches `\d{4}-\d{2}-\d{2}`, at any depth. The depth check stays; they are complementary. |
| F-204 missing-value errors leaked bash internals | **Fixed** — a `need_value` helper in the house voice. `benchmarks.sh --measure` now prints `benchmarks.sh: --measure needs a value`, no `line 45:`, no bare `2:`. One test per flag, asserting the message and the absence of `line `. |
| F-205 cp437 crash in the harness, by-name guard | **Fixed** — four em dashes replaced with ASCII; the guard now enumerates `git ls-files '*.py'`, falling back to an `rglob` walk where git is absent, so it covers all 4 shipped `.py` files instead of `install.py` alone. |

**One thing this fix pass caught in itself**, the same shape as ever:

- The new "reference doc documents every flag" assertion was **vacuous on arrival**. Deleting the `--limit` row from the table left it GREEN, because the sentence introducing the table also names `--limit` — a plain substring match. Prose about a flag is not documentation of a flag. Now anchored to each surface's real shape (`| \`--limit` for the table, `benchmarks.sh --limit` for the manual). This is the **fifth** vacuous-pass in this repo and the first written *while fixing* a vacuous-pass finding.
- All five new assertions were then **watched failing on purpose** — 5/5 red under deliberate perturbation, each reverted atomically. The first run scored 4/5 and named the bad one.

**Verified after the fix:** 16 + 23 + 31 = **70 checks**, green on Windows/Python 3.13 and on WSL Ubuntu 26.04 / Python 3.14 / bash 5.3.9, plus a clean CRLF scan and the three missing-value paths exercised on real bash.

---

## Findings

### FINDING-201 Major: the payload drift guard passes vacuously wherever git is absent — including every installed copy
**Dimension:** Tests
**Evidence:** `tests/test_install.py:193-208` runs `git ls-files` and never inspects the return code. Run from a real install (`python3 install.py --project ...`, no `.git` anywhere):
```
$ git ls-files
fatal: not a git repository (or any of the parent directories): .git
  rc=128  stdout-was-empty

  tracked=0  untracked=0  unaccounted=[]
  -> guard verdict: ok (VACUOUS)  while references/totally-unaccounted-for.md
     is sitting right there: True
```
The suite reports `PASS: 21 install.py checks` — against **22** in the repo. The `docs/audits/` probe at `tests/test_install.py:224` is wrapped in `if audits.is_dir():`, and `docs/audits/` is `NOT_SHIPPED`, so in an install that check silently evaporates. Nothing tells the reader a check disappeared.
**Why it matters:** `tests/` is in `PAYLOAD` precisely so a user can "verify their own install" (`install.py:37`). What they get is a green suite where the two checks about install completeness are the ones that stopped running. CI cannot catch this — every job starts with `actions/checkout@v4`, so the guard is only ever exercised in the one environment where it works.

This is the **fourth** vacuous-pass in this repo (doc substring in CSV filenames, the `--help` assertion, the 3-of-6 flag extraction, now this) and the first where the test is green *because* its input vanished rather than because its assertion was weak.
**Fix path:** Capture the `git ls-files` result and branch on it. If `returncode != 0`, the environment is not a checkout: `print("  SKIP payload drift guard (not a git checkout)")` and skip, the way the suite already handles `have_git()` at line 68. Never let an empty stdout stand in for "nothing unaccounted". Then make skips visible: track them alongside `results` and print `PASS: N checks (M skipped)` so 21-vs-22 is legible instead of silent.

---

### FINDING-202 Major: `--limit` and `--refresh` exist and are in `--help`, but appear on no documentation surface
**Dimension:** Docs
**Evidence:** Flag coverage across every surface, measured:
```
references/benchmarks.md   --open --measure --model [MISSING:--limit] [MISSING:--refresh] --list
docs/MANUAL.md             --open --measure --model [MISSING:--limit] [MISSING:--refresh] --list
README.md                  --open --measure [MISSING:--model] [MISSING:--limit] [MISSING:--refresh] --list
SKILL.md                   --open --measure --model [MISSING:--limit] [MISSING:--refresh] [MISSING:--list]
docs/index.html            [MISSING:--open] ... --list
```
`--limit` is the flag the **previous** commit added validation for and this commit added to `--help` — and it still reaches no reader. `references/benchmarks.md` is the file the skill tells the agent to load, so the agent driving this script cannot learn the flag exists.
**Why it matters:** Doc drift on changed behaviour is a Major by this repo's own guardrail, and this is its **fifth** occurrence (0.3.0, 0.3.2, 0.3.4, 0.3.5, now). The pattern holds because the existing doc-coverage test checks `--measure` *values* (`tests/test_benchmarks.py:190`) and no test checks *flags* at all. `--help` completeness is enforced against the parser; documentation completeness is not.
**Fix path:** Add `--limit` and `--refresh` to `references/benchmarks.md` and `docs/MANUAL.md`, and `--model` to `README.md`. Then close the class: extend the flag extraction already in `tests/test_benchmarks.py:161-166` to assert every accepted flag appears in `references/benchmarks.md`, the same way it already asserts they appear in `--help`. `docs/index.html` is a marketing page, not a reference — exempt it explicitly rather than leaving it ambiguous.

---

### FINDING-203 Minor: the "no exclusion names a file" guard only fires two directories deep
**Dimension:** Tests
**Evidence:** `tests/test_install.py:216-217` requires `e.count("/") >= 2`. Measured against candidate entries:
```
docs/audits/audit-2026-09-01.md   guard flags it: True
docs/audit-2026-09-01.md          guard flags it: False
audit-2026-09-01.md               guard flags it: False
```
**Why it matters:** The guard was written to kill the by-name habit — a dated filename in `NOT_SHIPPED` — and it catches only the exact shape that was there when it was written. Put the next audit report at `docs/` instead of `docs/audits/` and the fossil returns unchallenged. The depth threshold is also arbitrary: `CHANGELOG.md` and `.gitignore` are legitimate literal names at depth 0, which is why the author reached for depth, but depth is a proxy for the wrong property.
**Fix path:** Test for what actually makes an entry a fossil rather than for how deep it sits: assert no `NOT_SHIPPED` entry matches `\d{4}-\d{2}-\d{2}`. That covers every depth and every directory, and leaves the legitimate literal names alone. Keep the depth check as well if desired — they are complementary, not redundant.

---

### FINDING-204 Minor: missing-value errors leak bash internals and a line number
**Dimension:** UX
**Evidence:** `scripts/benchmarks.sh:45-48` uses `${2:?...}`. Observed:
```
$ benchmarks.sh --measure
scripts/benchmarks.sh: line 45: 2: --measure needs a value      (rc=1)
$ benchmarks.sh --model
scripts/benchmarks.sh: line 46: 2: --model needs a value        (rc=1)
$ benchmarks.sh --limit
scripts/benchmarks.sh: line 48: 2: --limit needs a value        (rc=1)
```
Compare the deliberate style two lines below: `benchmarks.sh: --limit must be a positive integer, got 'abc'`.
**Why it matters:** The bare `2:` is a positional-parameter reference no user can act on, and the embedded line number is the same species of fossil that `--help`'s hardcoded `sed -n '5,28p'` just was — it drifts silently with every edit above it. Three reachable argument paths, no test covers any of them, so the format is free to change without anyone noticing.
**Fix path:** Replace the parameter-expansion form with an explicit guard matching the house style, e.g. `[ $# -ge 2 ] || { echo "benchmarks.sh: --measure needs a value" >&2; exit 1; }`. Add one test per flag asserting rc=1, the flag name in stderr, and no `line ` prefix.

---

### FINDING-205 Major: the test harness crashes on cp437 — but only when a test fails
**Dimension:** Tests / Runtime
**Evidence:** `tests/test_install.py:56` and `:259`, and `tests/test_benchmarks.py:81` and `:204`, print an em dash. In every case it sits in the **failure** branch:
```python
print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f"  — {detail}" if detail and not cond else ""))
...
print(f"FAIL: {len(bad)}/{len(results)} — {'; '.join(bad)}")
```
Forced through cp437, which is cmd.exe's historic default codepage:
```
UnicodeEncodeError: 'charmap' codec can't encode character '—'
  in position 19: character maps to <undefined>
```
A passing run is clean; a failing run dies with a traceback instead of naming the failed check. Scan across the suites: `test_install.py` 2 lines, `test_benchmarks.py` 2 lines, `test_call_local.py` 0.
**Why it matters:** This is the **same defect the repo already fixed in `install.py`** — an em dash in a printed string that cp1252 hides and cp437 does not. It survived because the guard that enforces the rule reads exactly one file:
```python
src = (ROOT / "install.py").read_text(encoding="utf-8")
```
That is the **by-name guard class, fourth occurrence** — after the exec-bit check, shellcheck, and `NOT_SHIPPED`. The blast pattern is identical each time: the guard is written for the file that had the bug, a second file arrives, and the guard goes blind. Here it means a user on cmd.exe who runs the shipped suite and hits a real failure gets a traceback about character encoding instead of the name of what broke — the worst possible moment to lose the message.
**Fix path:** Two parts. (1) Replace the four em dashes with ASCII `-`. (2) Kill the class: enumerate the files to scan from the repo rather than naming one — `git ls-files '*.py'`, falling back to `PAYLOAD`'s `.py` entries when git is unavailable — and assert cp437-safety across all of them. Verify by re-inserting an em dash and watching the guard name the offending file.

---

## What's working

- **All four prior findings are genuinely closed**, each re-verified by running its failing case: `--help` now emits exactly the usage block, ends at `Staleness:`, leaks no `set -euo pipefail`, and lists all six flags including `--limit`; the header names `BENCHMARKS_CACHE`, the variable the script actually reads.
- **`is_excluded()` is the right shape.** Sharing one matcher between `install.py` and the drift test removes the possibility that the guard and the list disagree, and the trailing-slash convention borrows from `.gitignore` rather than inventing a syntax. Prefix matching behaves correctly at boundaries: `docs/audits-old/x.md` is **not** swallowed by the `docs/audits/` entry (verified).
- **The `--help` marker delimiters are a genuine class fix.** `/^# Usage:/,/^# --- end usage ---/` cannot drift when the header grows, which is what broke the line-range version.
- **The flag-coverage test earns its keep** — extracting from the script's own `case` labels rather than a hand-kept list means a seventh flag cannot ship undocumented in `--help`. Slicing to the end of the `while` loop instead of the first `esac` correctly handles the nested `case` in the `--limit` branch.
- **The self-caught defects in the prior pass were real work.** Printing what the flag extraction actually returned, and watching each new assertion fail on purpose, is what turned a 3-of-6 silent gap into a caught one.

## Watch items

1. **Guards keep being green in the one environment that matters least.** The exec-bit guard, shellcheck, and now the drift guard were all written where CI runs and not where the artifact lands. Worth a standing question on every new check: *where does this run, and where does it ship?*
2. **Documentation completeness has no automated floor.** Five releases of drift, five manual catches. Every other invariant in this repo is a test; this one is a habit.

## Escalation recommendation

**No escalation needed.** Four findings across two files, all local, all with concrete fixes. The recurrence patterns are a case for two more assertions, not for `audit-team`.

Worth stating plainly, as last time: **the fix commit for an audit again introduced four defects** — and the most serious is a guard that reports success by having nothing to inspect. Two consecutive fix commits have done this. The lesson is not "audit harder", it is that a check must be run in the environment it ships to before it is believed.
