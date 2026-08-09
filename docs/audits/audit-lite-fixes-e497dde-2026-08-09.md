# Audit Lite — the fix commit (`e497dde`)
**Date:** 2026-08-09
**Scope:** `e497dde`, which closed the four findings from the first audit-lite pass. Files touched: `scripts/benchmarks.sh`, `tests/test_benchmarks.py` (new), `install.py`, `references/benchmarks.md`, `.github/workflows/test.yml`, and the audit report's relocation to `docs/audits/`.
**Reviewer:** Claude (audit-lite)

## TL;DR

**The four original findings are genuinely fixed** — verified by running each failing case. But the fix commit introduced **four new defects of its own**, one of which is the third occurrence of a bug class this session has already fixed twice. `--help` is currently broken and documents a variable that does nothing.

No Blockers. Ship-with-fixes: none of this risks data, but `--help` is a user-facing surface that is wrong right now.

## Severity rollup (original)
- Blocker: 0 | Critical: 0 | Major: 2 | Minor: 2 | Nit: 0

## Resolution — 2026-08-09, same day
**All four fixed. Rollup now 0 / 0 / 0 / 0 / 0.**

| Finding | Status |
|---|---|
| F-101 dated filename in `NOT_SHIPPED` | **Fixed** — entries may now end in `/` to exclude a directory; `docs/audits/` replaces the dated file. `install.is_excluded()` is shared with the drift test so the guard and the list cannot disagree. A test asserts no exclusion names a file inside a nested directory, and a second file dropped into `docs/audits/` is proven not to break the guard. |
| F-102 `--help` broken | **Fixed** — delimited by `# Usage:` / `# --- end usage ---` markers instead of a hardcoded line range, so edits above or below cannot shift it. `--limit` added to the usage block. |
| F-103 wrong cache variable | **Fixed** — `BENCHMARKS_CACHE`, with a test asserting the real name appears and the wrong one does not. |
| F-104 vacuous `--help` test | **Fixed** — four assertions: exits 0, documents **every** flag the parser accepts, leaks no shell syntax, names the real cache variable. Flags are extracted from the script's own `case` labels, so a new flag cannot ship undocumented. |

**Two things the fix pass caught in itself**, both of the same shape the audit named:

- The flag extraction first split on `esac` and silently captured only **three of six** flags — the `--limit` branch contains a nested `case/esac`. Found by printing what the extraction actually returned rather than trusting a green tick. Now slices to the end of the `while` loop and asserts `len(accepted) >= 6`.
- Each new assertion was verified to **fail on purpose** — removing `--limit`, then `--open`, from the help text produced a red run naming that exact flag. A check not watched failing is a check not known to work.

---

## Findings

### FINDING-101 Major: `NOT_SHIPPED` hardcodes a dated filename — the by-name bug, third occurrence
**Dimension:** Correctness
**Evidence:** `install.py` lists `"docs/audits/audit-lite-multi-model-routing-2026-08-09.md"` as a literal entry. Dropping a second report in that directory immediately fails the drift guard:
```
FAIL every tracked file is shipped or explicitly excluded
  add to PAYLOAD or NOT_SHIPPED: ['docs/audits/audit-lite-something-2026-09-01.md']
```
**Why it matters:** This is **the same class of defect the same session fixed twice** — the exec-bit guard and shellcheck both enumerated `scripts/call_local.sh` by name and went blind when a second script arrived. Both were rewritten to `git ls-files 'scripts/*.sh'`. Then this commit — whose own message says *"fixing the class, not the instance"* — hardcoded a **dated filename**, guaranteeing a failure on the next audit. Every future audit forces an unrelated edit to `install.py`, which is exactly the maintenance tax the drift guard exists to remove.
**Fix path:** Exclude the directory, not the file. Support a trailing `/` in `NOT_SHIPPED` entries and add `docs/audits/`, matching how `.gitignore` handles the same problem. Add a test: create two files under `docs/audits/` and assert the guard stays green.

---

### FINDING-102 Major: `--help` is broken — it prints shell code and omits a flag
**Dimension:** UX / Docs
**Evidence:** `scripts/benchmarks.sh:60` uses a hardcoded line range: `sed -n '5,28p' "$0"`. The header grew when the `--limit` validation and comments were added, so the range now overruns it. Actual tail of `--help`:
```
Cache: $CALL_LOCAL_CACHE or ~/.cache/multi-model-routing/benchmarks
Staleness: BENCHMARKS_MAX_AGE_DAYS (default 7)

set -euo pipefail
```
It also omits `--limit` entirely — the very flag this commit added validation for. Flag coverage in `--help`: `--measure` ✓, `--model` ✓, `--open` ✓, `--refresh` ✓, `--list` ✓, **`--limit` ✗**.
**Why it matters:** `--help` is the first thing a user or agent runs on an unfamiliar script. Leaking `set -euo pipefail` reads as a broken tool, and the one flag with new validation is invisible — so a user hits "must be a positive integer" for a flag help never mentioned.
**Fix path:** Stop counting lines. Delimit the usage block explicitly — e.g. `sed -n '/^# Usage:/,/^# Staleness:/p'` — so edits above or below cannot shift it. Add `--limit N` to the usage list. Then assert in the test that `--help` contains every flag the argument parser accepts and contains no shell syntax.

---

### FINDING-103 Minor: `--help` documents an environment variable that does nothing
**Dimension:** Docs
**Evidence:** The header says `Cache: $CALL_LOCAL_CACHE or ~/.cache/...`, but the script reads `BENCHMARKS_CACHE` (`scripts/benchmarks.sh:31`). Demonstrated:
```
CALL_LOCAL_CACHE=$T benchmarks.sh  -> 0 files in $T   (ignored)
BENCHMARKS_CACHE=$T benchmarks.sh  -> 76 files in $T  (works)
```
A copy-paste from `call_local.sh`'s variable naming.
**Why it matters:** Silently ignored configuration is worse than undocumented configuration — the user sets it, sees no error, and concludes the cache can't be relocated. Low blast radius (one line, one variable), hence Minor.
**Fix path:** Correct the header to `BENCHMARKS_CACHE`. Cover it in the `--help` test once FINDING-102's assertion is tightened.

---

### FINDING-104 Minor: the `--help` test passes while `--help` is broken
**Dimension:** Tests
**Evidence:** `tests/test_benchmarks.py`:
```python
check("--help prints usage, not the file header verbatim",
      r.returncode == 0 and "--open" in r.stdout, ...)
```
`--open` does appear — inside the usage block — so the assertion is satisfied while the output simultaneously leaks `set -euo pipefail` and omits `--limit`.
**Why it matters:** A test whose name claims more than its assertion checks is worse than no test: it converts an unverified area into an apparently verified one. This is the same shape as the doc-coverage check in the previous commit, which passed on substrings inside CSV filenames until it was tightened — so the pattern is recurring, not isolated.
**Fix path:** Assert the negative as well as the positive: every accepted flag appears, and no shell syntax (`set -`, `esac`, `fi`) appears. Naming a test for what it *checks* rather than what it *hopes* would have surfaced this.

---

## What's working

- **The four original findings are genuinely closed**, each verified by re-running its failing case: `--limit abc|0|-5|3.5` now returns `--limit must be a positive integer`; `--measure coding --open` explains that the file carries no accessibility data and points at `capabilities`; all six `--measure` values are in a table; `tests/test_benchmarks.py` exists with 23 checks.
- **The new test suite is well-constructed where it counts.** Fixture-driven via `BENCHMARKS_CACHE`, so it never touches the network or the real cache — the same isolation discipline as the mock servers in `test_call_local.py`. The fixture deliberately includes a file *with* an accessibility column and one *without*, which is the asymmetry that produced FINDING-003.
- **The doc-coverage check was tightened correctly.** Moving from a substring search to `| \`{measure}\`` closed a real vacuous-pass that would otherwise have matched `terminalbench_external.csv`. The lesson was applied — just not to the `--help` test written in the same file.
- **The drift guard earned its place again**, catching the audit report sitting unaccounted in the repo root minutes after it was created.
- **Cross-platform verification held**: all three suites pass on Ubuntu 26.04 / Python 3.14 via WSL and across four CI jobs.

## Watch items

1. **The by-name pattern has now recurred three times** (exec bit, shellcheck, `NOT_SHIPPED`). It is a habit, not an accident — worth a standing rule that any exclusion list entry must be a pattern or a directory, never a literal filename.
2. **Two vacuous-pass tests in two consecutive commits** (doc substring, `--help`). Both were caught by review rather than by the suite. A test whose assertion is weaker than its name is a systematic risk in a repo that leans this hard on its tests.

## Escalation recommendation

**No escalation needed.** Four findings, all local to two files, all with concrete fixes. The recurrence patterns in Watch items are worth a rule, not an `audit-team` run.

Worth stating plainly: **the fix commit for an audit introduced four new defects, in a repo with 59 tests and five CI jobs.** Nothing here was caught by automation — all four came from manually exercising the changed surface. That is the argument for auditing fixes, not just features.
