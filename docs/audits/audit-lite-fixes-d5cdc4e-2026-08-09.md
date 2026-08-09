# Audit Lite — the fifth fix commit (`d5cdc4e`)
**Date:** 2026-08-09
**Scope:** `d5cdc4e`, which closed the three findings of the fourth fix-audit. Files touched: `tests/test_install.py`, `CHANGELOG.md`, plus the prior report.
**Reviewer:** Claude (audit-lite)

## TL;DR

**All three prior findings are closed and the central property now holds**: `ran + skipped` is 25 in every environment, with git and without it, on both platforms. Nothing here breaks at runtime. What remains is three Minors — a guard narrower than its own name, a wrong number in the changelog, and (outside this diff) a CI check that cannot fail.

Ship. No Blockers, no Criticals, no Majors — the first clean-of-Majors round in this sequence.

## Severity rollup (original)
- Blocker: 0 | Critical: 0 | Major: 0 | **Minor: 3** | Nit: 0

## Resolution — 2026-08-09, same day
**All three fixed. Rollup now 0 / 0 / 0 / 0 / 0.**

| Finding | Status |
|---|---|
| F-501 guard narrower than its name | **Fixed** — matches any `subprocess.<attr>` whose first argument is a list starting with `"git"`, and names the entry point in the failure detail. Proven against all four: `run`, `check_output`, `Popen`, `check_call` — 4/4 red, where 3 of 4 previously sailed through. |
| F-502 "six call sites", actually eight | **Fixed** — corrected in `CHANGELOG.md`. The `d5cdc4e` commit message is immutable history and stays as written. |
| F-503 CI CRLF check cannot fail | **Fixed** — checks `git ls-files --eol` for any `i/crlf`, which is what a clone actually receives, and prints the tracked-file count so a vacuous pass is visible. The working-tree grep is kept underneath it for anything generated during a run rather than checked out. Verified locally: `index is LF-clean (28 tracked files)`. |

Also normalised `CHANGELOG.md` back to LF in the working tree — `git ls-files --eol` had it as `i/lf w/crlf`, written by Python's `write_text` on Windows. Third occurrence this session; written with `newline="\n"` now. All 28 tracked files are `w/lf` (or `w/none`).

**Verified after the fix:** 16 + 25 + 31 = **72 checks** green; round-1/2/3 perturbation harnesses re-run clean at 5/5, 3/3 and 3/3.

---

## Findings

### FINDING-501 Minor: the AST guard is narrower than its own name
**Dimension:** Tests
**Evidence:** The check is named *"git is spawned only through `git_run()`"*, but it matches `subprocess.run` alone. Run against three plausible ways to spawn git:
```
subprocess.run(["git", "status"])              caught: True
subprocess.check_output(["git", "status"])     caught: False
subprocess.Popen(["git", "status"])            caught: False
```
**Why it matters:** `check_output` is the *natural* choice for exactly the read-only queries this file makes — `ls-files`, `rev-parse` — so the most likely future call site is the one that evades the guard. It also raises `FileNotFoundError` identically, so it reintroduces F-401 exactly.

This is the same shape the guard was written to end: **the check encodes the instance it was built against, not the property.** The property is "spawns git", not "calls `subprocess.run`".
**Fix path:** Match any `subprocess.<attr>` call whose first argument is a list beginning with `"git"`, rather than `run` specifically. Verify by planting a `check_output` and a `Popen` call and watching both go red.

---

### FINDING-502 Minor: the changelog and commit message both say six git call sites; there are eight
**Dimension:** Docs
**Evidence:** `CHANGELOG.md` states "spawned git at six call sites without a guard". Counted from the source:
```
line  67  git_run("--version")             line 231  git_run("ls-files", "*.py")
line 124  git_run("init", "-q")            line 292  git_run("rev-parse", ...)
line 125  git_run("add", "-A")             line 304  git_run("ls-files", *args)
line 126  git_run("-c", ..., "commit")     line 189  git_run("init", "-q")
```
Eight call sites, not six.
**Why it matters:** Small, but this changelog is the artefact a reader trusts to describe what happened, and the number is checkable in ten seconds. A repo that argues this hard about evidence should not carry a figure that was estimated rather than counted. Low blast radius — one word in one line — hence Minor.
**Fix path:** Correct to eight in `CHANGELOG.md`. The commit message for `d5cdc4e` is immutable history and stays as it is; the changelog is the surface a reader actually consults.

---

### FINDING-503 Minor: the CI "no CRLF" check cannot fail
**Dimension:** Tests
**Scope note:** This sits **outside the audited diff** — it is pre-existing, in `.github/workflows/test.yml`. Surfaced while verifying line endings after this commit wrote `CHANGELOG.md` from Python. Reported because it is a guard that provides no protection, not because the audit widened.
**Evidence:** `.gitattributes` is `* text=auto eol=lf`, applying to every path. CI greps the **working tree** of a fresh checkout:
```yaml
if grep -rlIU $'\r' --exclude-dir=.git . ; then ... exit 1
```
Every text file is normalised to LF by that checkout *by definition*, and `grep -I` skips the binary files that could still hold CRLF. Measured on a fresh clone of this repo:
```
CI grep on a fresh checkout: finds nothing (as it always will)
index EOL states present:   i/lf i/none
committed blobs containing CRLF: 0 of 28
```
**Why it matters:** It is the **sixth** vacuous check in this repo, and it is checking the one place the answer is guaranteed in advance. The property it cares about — that a POSIX clone gets LF — is genuinely enforced by `.gitattributes`, so nothing is left unprotected; the defect is the false assurance and a CI step that can never earn its place.

Worth noting what a correct version would have caught right now: `git ls-files --eol` reports `CHANGELOG.md` as `i/lf w/crlf` — index clean, working tree CRLF, written by Python's `write_text` on Windows. Harmless for markdown, invisible to the current check, and precisely the state a real guard should be able to describe.
**Fix path:** Check the index, which is what a clone actually receives, rather than a working tree that has already been normalised: fail on any `i/crlf` in `git ls-files --eol`. That can fire, and it tests the thing that matters.

---

## What's working

- **The property that was missing now holds and is measured.** `ran + skipped` = 25 in the repo, 14 + 11 with git absent, on Windows and on WSL. A check can no longer disappear without saying so.
- **`git_run()` is a real chokepoint, not a wrapper someone might use.** All eight call sites go through it, and the AST guard means a ninth cannot be added by hand without failing — proven by planting a raw call and watching it named by line number.
- **`skip()` enforcement was aimed at the right target.** The bare-`print("SKIP...")` form is what hid four checks; an AST walk for that exact shape is a class kill, and it went red on a planted example.
- **The name tuples closed the by-name habit properly this time.** Renaming a check was verified to carry its skip label automatically — the first time in this sequence that a fix for that habit was proven rather than asserted.
- **`test_call_local.py` and `test_benchmarks.py` needed no changes at all** — both already used `shutil.which("git")`, which returns `None` instead of raising. The correct pattern was in the repo twice while the third file got it wrong.

## Watch items

1. **Guards keep being narrower than their names.** `subprocess.run` for "spawns git" (F-501), depth for "dated filename", substring for "documented". Three different instances of encoding the example instead of the property, and the first two were themselves fixes for that habit. The name of a check is a claim; it is worth reading each one back as a specification and asking what else satisfies it.
2. **Python's `write_text` on Windows keeps reintroducing CRLF.** Third occurrence this session. `newline="\n"` costs nothing and this repo pins LF everywhere.

## Escalation recommendation

**No escalation needed.** Three Minors, no Majors, no runtime risk. Two are one-line corrections and the third is a four-line CI change.
