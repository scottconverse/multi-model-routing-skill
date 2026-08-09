# Audit Lite — the fourth fix commit (`c13d63a`)
**Date:** 2026-08-09
**Scope:** `c13d63a`, which closed the three findings of the third fix-audit. Files touched: `tests/test_install.py`, `CHANGELOG.md`, plus the prior report.
**Reviewer:** Claude (audit-lite)

## TL;DR

**All three prior findings are closed**, each verified in the environment it was about — the repo runs the drift guard, a plain install skips it, and an install inside a foreign repo skips it naming that project. But the accumulated git handling now has **three unguarded call sites**, and on a machine without git the shipped suite **crashes with a traceback** instead of skipping. Git is not a requirement for using this skill, and `tests/test_install.py` already contains a helper that catches exactly this.

Ship-with-fixes. One Major, one Minor, both in `tests/test_install.py`.

## Severity rollup (original)
- Blocker: 0 | Critical: 0 | **Major: 1** | **Minor: 1** | Nit: 0

## Resolution — 2026-08-09, same day
**Both fixed, plus a third defect the fix surfaced. Rollup now 0 / 0 / 0 / 0 / 0.**

| Finding | Status |
|---|---|
| F-401 crash without git | **Fixed** — a single `git_run()` chokepoint catching `OSError`; all six git call sites route through it. Verified on Windows and on WSL with a symlink PATH containing every tool but git: all three suites now **PASS** where `install` used to die with `FileNotFoundError`. |
| F-402 skip labels duplicated as literals | **Fixed** — `DRIFT_CHECKS`, `VCS_UNINSTALL_CHECKS` and `CHECKOUT_PRUNE_CHECKS` name each check once; `check()` and `skip()` both read from them. Proven: renaming a check makes the skip label follow automatically. |
| **F-403** *(found while verifying F-401)* nine more checks vanishing silently | **Fixed** — with git absent the suite reported a clean `PASS: 13` while 11 checks were missing and only 2 were announced. One block announced its skip with a bare `print()` (invisible to the tally), and a second had **no `else` at all**. Both now call `skip()` per check. |

**The accounting balances in every environment**, which is the property that was actually missing:

```
repo     ran=25  skipped=0   total=25
no git   ran=14  skipped=11  total=25
```

**Class kills, not instance fixes** — both enforced from the parse tree, so neither can recur quietly:

- **`git is spawned only through git_run()`** — an AST walk for `subprocess.run(["git", ...])` outside `git_run`'s body. A text search would answer "does this string appear", which is not the question; only the parse tree knows where a body ends.
- **`every skip goes through skip(), never a bare print`** — an AST walk for `print("SKIP...")`, which is exactly how F-403's first block hid four checks.

**Perturbations, 3/3 as designed:** a raw git call planted outside `git_run` is caught by line number; a bare `print("  SKIP ...")` is caught by line number; renaming a check carries its skip label with it. Rounds 1 and 2 re-run clean at 5/5 and 3/3 — no regression.

**Verified after the fix:** 16 + 25 + 31 = **72 checks**, green on Windows/Python 3.13, WSL Ubuntu 26.04 / Python 3.14 / bash 5.3.9, and with git entirely absent on both platforms.

---

## Findings

### FINDING-401 Major: the shipped suite crashes on a machine without git
**Dimension:** Correctness / Runtime
**Evidence:** Measured with a PATH containing every tool **except** git — `sed`, `grep`, `curl`, `bash` and `python3` all present, so git's absence is the only variable (WSL Ubuntu 26.04, symlink shim):
```
git on the shim PATH: ABSENT
sed/grep/curl/bash:   ok/ok/ok/ok

call_local   PASS
install      CRASH (traceback)
                 FileNotFoundError: [Errno 2] No such file or directory: 'git'
benchmarks   PASS
```
Reproduced independently on Windows (`FileNotFoundError: [WinError 2]`, first raised at `tests/test_install.py:189`). Three unguarded call sites:

| Line | Call | Added in |
|---|---|---|
| 189 | `git ls-files "*.py"` (cp437 scan) | `3a35384` |
| 251 | `git rev-parse --show-toplevel` | `c13d63a` |
| 262 | `git ls-files` | `3a35384` |

`subprocess.run` raises `FileNotFoundError` when the executable does not exist — it never reaches a return code, so every one of these return-code checks is unreachable in that case.
**Why it matters:** Nothing about this skill needs git. `install.py` is pure Python, `call_local.sh` and `benchmarks.sh` shell out to curl and python3. A user installs the skill, runs the suite they are told verifies their install, and gets a Python traceback about `CreateProcess`. The other two suites handle it correctly and pass.

The sharper point: **`tests/test_install.py:44` already defines `have_git()`, which exists solely to catch this**, and all three new call sites were written without it — added *while fixing git-related findings*, in the file that holds the guard.
**Fix path:** One chokepoint, not three fixes. A `git_run(*args)` helper that catches `OSError` and returns `None`, with every git call routed through it. Then kill the class rather than the instance: a static assertion that no raw `subprocess.run(["git"` survives outside that helper, enumerated from the file's own source — so a fourth call site cannot be added unguarded.

---

### FINDING-402 Minor: the skip loop hardcodes check names, duplicating them as string literals
**Dimension:** Tests
**Evidence:** `tests/test_install.py` announces skips from a literal tuple:
```python
for missed in ("every tracked file is shipped or explicitly excluded",
               "a second file in docs/audits/ does not break the guard"):
```
The same two strings appear again as the `name` argument of the `check()` calls in the branch below. Renaming either check leaves the skip announcing a name that no longer exists anywhere.
**Why it matters:** Low blast radius — a misleading string in skip output, not a wrong verdict. But it is the **by-name habit, fifth occurrence** (exec-bit guard, shellcheck, `NOT_SHIPPED`, the cp437 scan, now this), and it was introduced *in the commit that removed a hardcoded count for being exactly this class*. Worth fixing on principle: the habit is the defect, and each instance left standing is a vote for it.
**Fix path:** Name the two checks once, in a module-level tuple, and read both the `skip()` calls and the `check()` calls from it.

---

## What's working

- **All three prior findings verified closed in the environments they concern**, not by inspection: repo runs the guard (23 checks), plain install skips with 2 named skips, foreign-repo install skips naming the offending project by path, and 23 − 21 = 2 now agrees with the tally.
- **The identity check was proven load-bearing, not decorative.** Neutralising it (`if top != ROOT.resolve():` → `if False:`) reproduces the original foreign-repo failure; planting an unaccounted file in the repo still turns the guard red. It narrowed *where* the guard runs without switching it off — the obvious way to get this wrong.
- **`## [Unreleased]` is accurate**, checked line by line against `git log v0.3.5..HEAD`: all four commits are represented, and the flag/error-message/skip-output changes it claims are the ones that actually shipped.
- **The other two suites handle a missing git correctly** — `test_call_local.py` and `test_benchmarks.py` both use `shutil.which("git")`, which returns `None` rather than raising, and both pass cleanly without it. The right pattern was already in the repo, twice.

## Watch items

1. **A blunt measurement nearly produced two false findings.** The first pass at this ran the suites with `PATH` stripped to `System32`, which removes `sed`, `grep` and `curl` along with git; `call_local` and `benchmarks` "failed" for reasons that had nothing to do with git. Isolating the single variable turned two findings into zero. An environment test that changes more than one thing measures nothing.
2. **Every git call site added in the last two commits was unguarded**, in a file that has had `have_git()` since before either. Guards get written and then not used — worth a chokepoint anywhere a subprocess is spawned conditionally.

## Escalation recommendation

**No escalation needed.** Two findings, one file, both with concrete fixes; the Major is a helper function and a static check.
