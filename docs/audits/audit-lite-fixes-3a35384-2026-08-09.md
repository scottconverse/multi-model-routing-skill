# Audit Lite — the third fix commit (`3a35384`)
**Date:** 2026-08-09
**Scope:** `3a35384`, which closed the five findings of the second fix-audit. Files touched: `install.py` (comment only), `scripts/benchmarks.sh`, `tests/test_install.py`, `tests/test_benchmarks.py`, `references/benchmarks.md`, `docs/MANUAL.md`, `README.md`.
**Reviewer:** Claude (audit-lite)

## TL;DR

**All five prior findings are closed and each was verified by re-running its failing case.** But the F-201 fix was half a fix: it made the *no-git* case honest and left the *wrong-git* case crying wolf. Installed into a user's own git project — a documented, supported install — the shipped suite now **fails**, naming the user's own `local-notes.md` as an unaccounted file. Two Minors alongside it, one of which is a hardcoded count in the very output the fix added for legibility.

Ship-with-fixes. One Major on the primary verification path a user is told to run.

## Severity rollup (original)
- Blocker: 0 | Critical: 0 | **Major: 1** | **Minor: 2** | Nit: 0

## Resolution — 2026-08-09, same day
**All three fixed. Rollup now 0 / 0 / 0 / 0 / 0.**

| Finding | Status |
|---|---|
| F-301 spurious failure inside a foreign repo | **Fixed** — `why_not_the_repo()` compares `git rev-parse --show-toplevel` against the test's own root, so the guard tests repository *identity* rather than git *availability*. Verified in all three environments: the repo runs it (23 checks), a plain install skips it, and an install inside a user's git project skips it naming that project by path. |
| F-302 hardcoded, wrong skip count | **Fixed** — `skip()` is called once per check that did not run, naming each. The tally counts itself: `PASS: 21 install.py checks (2 skipped: ...)`, and 23 − 21 = 2 now agrees. |
| F-303 four commits, no changelog entry | **Fixed** — an `## [Unreleased]` section covering all four, so tagging `v0.3.6` is a rename rather than an archaeology exercise. |

**Perturbations, all watched behaving as designed (3/3):**

- Planting an unaccounted file in the repo still turns the guard **red** — the identity check narrowed where it runs without switching it off, which was the obvious way to "fix" this wrongly.
- Neutralising the identity check (`if top != ROOT.resolve():` → `if False:`) **reproduces the original failure** on a foreign-repo install, naming `local-notes.md` again. The check is load-bearing, not decorative.
- Restored, that same install passes with exactly 2 named skips.
- The five round-1 perturbations still hold at 5/5 — no regression.

**Verified after the fix:** 16 + 23 + 31 = **70 checks**, green on Windows/Python 3.13 and WSL Ubuntu 26.04 / Python 3.14 / bash 5.3.9, CRLF scan clean, and CI green on the parent commit.

---

## Findings

### FINDING-301 Major: the shipped suite fails spuriously when installed inside another git repository
**Dimension:** Correctness / Runtime
**Evidence:** `python3 install.py --project <a git repo>`, then run the shipped suite from the install:
```
FAIL every tracked file is shipped or explicitly excluded
  - add to PAYLOAD or NOT_SHIPPED: ['__pycache__/install.cpython-313.pyc',
                                    'references/local-notes.md']
FAIL: 1/22 - every tracked file is shipped or explicitly excluded
```
`git_files()` runs with `cwd=ROOT` and asks only whether git **succeeded**, never whether the repository it answered about is *this* one. Inside a user's project, `git ls-files --others` happily enumerates the freshly installed files against the wrong index.
**Why it matters:** `--project DIR` is documented in `install.py`'s own usage, and `tests/` ships expressly so a user can "verify their own install" (`install.py:37`). What they get is a red suite blaming `references/local-notes.md` — the file the installer just created for them, on purpose, and the one file the whole design protects. A false alarm on the verification path is worse than a silent pass: it tells the user their install is broken when it is fine, and the fix instruction ("add to PAYLOAD or NOT_SHIPPED") is meaningless to someone who is not developing this repo.

The payload drift guard is a **repo-development** check. It has no business running in an install at all — the previous behaviour hid that by accident (empty stdout looked like success), and correcting the return code exposed it.
**Fix path:** Test identity, not availability. `git rev-parse --show-toplevel` and compare the resolved path to `ROOT`; run the guard only when they match, and skip with a reason that distinguishes "not a checkout" from "inside a different repository". Verify by installing into a git project and confirming a clean skip.

---

### FINDING-302 Minor: the new skip label hardcodes a count, and the count is wrong
**Dimension:** Tests
**Evidence:** `tests/test_install.py` prints `SKIP payload drift guard (3 checks)`. Measured:
```
in the repo:   PASS: 23 install.py checks
in an install: PASS: 21 install.py checks (1 skipped: payload drift guard (3 checks))
-> checks actually lost: 2     label claims: 3
```
**Why it matters:** The skip machinery exists *because* a silently-vanishing check is indistinguishable from a passing one. Announcing the wrong number puts a false figure where the fix put honesty — and a hardcoded literal count is the same fossil class as the dated filename and the `sed -n '5,28p'` line range, one commit after a report about that class.
**Fix path:** Stop carrying a number. Call `skip()` once per check that did not run, naming each, so the tally counts itself and cannot drift.

---

### FINDING-303 Minor: four commits past the last tag, nothing in the changelog
**Dimension:** Docs
**Evidence:** `CHANGELOG.md` opens with "All notable changes to multi-model-routing are documented here" and its newest section is `## [0.3.5] — 2026-08-09`. `git log --oneline v0.3.5..HEAD` lists four commits, all with observable behaviour changes: a CI Python matrix, three rounds of audit fixes, new documented flags, a changed error-message format, new skip output.
**Why it matters:** Not a convention breach on its own — this repo writes changelog entries at tag time. It is a **risk** one, and a well-evidenced one: reconstructing four commits from messages at tag time is precisely how the docs fell behind at 0.3.0, 0.3.2, 0.3.4 and 0.3.5. With a `v0.3.6` tag pending, the reconstruction is imminent.
**Fix path:** Add an `## [Unreleased]` section now and keep it current, so tagging becomes a rename rather than an archaeology exercise.

---

## What's working

- **All five prior findings verified closed by re-running the failing case**, not by inspection: the drift guard now prints an explicit `SKIP` where it used to print `ok` while blind; the cp437 guard covers 4 shipped `.py` files and names file and line when one regresses; `--limit`/`--refresh` reach both doc surfaces; `--measure` with no value answers `benchmarks.sh: --measure needs a value` with no `line 45:` and no bare `2:`; a dated exclusion entry is rejected at any depth.
- **The perturbation harness is the strongest thing in this commit.** Five deliberate breakages, each applied, tested and reverted atomically, repo left byte-identical. It caught a vacuous assertion *in the same pass that wrote it* — the reference-doc flag check stayed green when the `--limit` table row was deleted, because prose above the table also names `--limit`. Nothing else in this repo has ever caught a defect that fast.
- **`need_value()` is the right shape.** `"${2-}"` keeps `set -u` from firing before the check, and the single `-n` test covers unset and explicitly-empty in one place. Verified on bash 5.3.9 under Ubuntu 26.04, not just Git Bash.
- **The flag extraction survived a parser refactor untouched** — still exactly the six real flags, no artefacts picked up from the new `need_value --measure "${2-}"` call sites.
- **Doc anchors are structural now, not substring.** `| \`--limit` for a table row, `benchmarks.sh --limit` for a runnable example — each surface asserted in the shape it actually uses.

## Watch items

1. **Correcting a silent failure exposes what it was hiding.** F-201's empty-stdout bug masked F-301 completely; the honest return code surfaced it immediately. Worth expecting on the next "this check never really ran" fix.
2. **Guards written for the repo keep shipping to installs.** Third variant of the same question — *where does this run, and where does it ship?* The drift guard, the `docs/audits/` probe, and now the repo-identity check are all repo-development machinery living inside a user-facing test file.

## Escalation recommendation

**No escalation needed.** Three findings, two files, all local with concrete fixes. The Major is a one-line identity check, not an architectural problem.
