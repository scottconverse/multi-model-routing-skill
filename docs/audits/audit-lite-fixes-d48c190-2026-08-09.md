# Audit Lite — the seventh fix commit (`d48c190`)
**Date:** 2026-08-09
**Scope:** `d48c190`, which closed the two documentation findings of the sixth fix-audit. Files touched: `CHANGELOG.md`, `docs/audits/audit-lite-fixes-d5cdc4e-2026-08-09.md` (correction block), `docs/audits/audit-lite-fixes-a18d97c-2026-08-09.md` (new report).
**Reviewer:** Claude (audit-lite)

## TL;DR

Documentation-only commit, no code. Every factual claim in it was re-derived independently and **all of them hold** — including the one the previous round flagged as asserted-but-unmeasured, which is now measured and correct. Full verification sweep is green on both platforms, with and without git.

**Ship. First clean round of this sequence.**

## Severity rollup
- Blocker: 0 | Critical: 0 | Major: 0 | Minor: 0 | Nit: 0

**0 / 0 / 0 / 0 / 0**

---

## Findings

None. The claims that could be falsified were tested rather than read.

## What was checked

**Correctness / Runtime — N/A by scope.** No code changed. The runtime paths were re-exercised anyway as a regression check (below) and are unaffected.

**Docs — every checkable claim re-derived:**

| Claim in the commit | Verified how | Result |
|---|---|---|
| "4 of 4 entry points caught, where 3 of 4 escaped" — flagged last round as asserted, not measured | ran both guard predicates against `run`, `check_output`, `Popen`, `check_call` | **holds** — old caught only `run`; new catches all four |
| the old grep *does* catch a `-text` path with CRLF | purpose-built repo with `i/crlf` in the index, fresh clone, both checks run | **holds** — this is what F-601 corrected |
| `.gitattributes` has no `-text` exception | read it: one line, `* text=auto eol=lf` | **holds** |
| `[Unreleased]` now covers `a18d97c` | mechanical substring check for all three topics | **holds** — CRLF rewrite ✓, widened guard ✓, eight call sites ✓ |
| `CHANGELOG.md` is LF | byte count | **holds** — 0 CRLF pairs |

**Tests — no test changed; the whole battery re-run as regression:**
```
Windows      call_local PASS   install 25   benchmarks 31
WSL 26.04    call_local PASS   install 25   benchmarks 31      (py3.14, bash 5.3.9)
git absent   call_local PASS   install 14 + 11 skipped = 25    benchmarks PASS
installs     plain 23 + 2 skipped     foreign-repo 23 + 2 skipped
perturbation r1 5/5   r2 3/3   r3 3/3   r4 4/4
```
Line endings across the tree: 29 files `i/lf w/lf`, one `i/none w/none` (`docs/.nojekyll`, empty).

## Watch items

1. **One defect exists outside this diff and is disclosed rather than counted.** `docs/audits/audit-lite-multi-model-routing-2026-08-09.md:41` recommends adding `tests/test_benchmarks.sh.py` — a typo for `tests/test_benchmarks.py`. It is in the *first* report of this sequence, untouched by `d48c190`, so it is not a finding against this commit. Fixed as housekeeping and disclosed here; counting it against a diff that does not contain it would misreport where the defect is.
2. **A cross-reference scan over the reports produced one false positive**, worth recording so the next reader does not chase it: `docs/audits-old/x.md` in the `ca06029` report is *hypothetical test data* used to show prefix-matching does not over-reach, not a reference to a file. Path-shaped strings in prose are not always references.
3. **Changelog completeness remains the last invariant held by intention, not by a check** — carried forward from the previous round, deliberately unanswered rather than answered with a weak test.

## Escalation recommendation

**No escalation needed.** Nothing found in scope.
