# Audit Lite — the sixth fix commit (`a18d97c`)
**Date:** 2026-08-09
**Scope:** `a18d97c`, which closed the three Minors of the fifth fix-audit. Files touched: `tests/test_install.py`, `.github/workflows/test.yml`, `CHANGELOG.md`, plus the prior report.
**Reviewer:** Claude (audit-lite)

## TL;DR

**Both code changes are correct and both were proven to fire**, which is the bar the previous round set: the widened spawn guard catches all four `subprocess` entry points, and the new index-based CRLF check was verified against a repo whose index genuinely stores CRLF. CI is green on the rewritten workflow step. Nothing is broken at runtime.

The two findings are both documentation, and both are self-inflicted: an explanation in the round-4 report that this round's experiment disproves, and the `[Unreleased]` changelog section — added one commit ago *specifically to prevent drift* — which has already drifted.

Ship. No Blockers, Criticals or Majors.

## Severity rollup (original)
- Blocker: 0 | Critical: 0 | Major: 0 | **Minor: 2** | Nit: 0

## Resolution — 2026-08-09, same day
**Both fixed. Rollup now 0 / 0 / 0 / 0 / 0.**

| Finding | Status |
|---|---|
| F-601 wrong mechanism in the round-4 report | **Fixed** — the sentence now names the real reason (`text=auto` with no `-text` exception), and a marked **Correction** block records what the experiment showed: the old grep *does* catch a `-text` path, which is why the fix kept it underneath the index check rather than replacing it. |
| F-602 `[Unreleased]` drifted within one commit | **Fixed** — both missing entries added. Coverage re-checked mechanically: CRLF CI rewrite ✓, widened spawn guard ✓, eight call sites ✓. |

**Verified after the fix:** 16 + 25 + 31 = **72 checks** green; `CHANGELOG.md` written with `newline="\n"`, 0 CRLF pairs.

---

## Findings

### FINDING-601 Minor: the round-4 report states a mechanism this round disproves
**Dimension:** Docs
**Evidence:** `docs/audits/audit-lite-fixes-d5cdc4e-2026-08-09.md` explains why the old CRLF check could not fire:

> "…and `grep -I` skips the binary files that could still hold CRLF."

Measured, by building a repo whose index genuinely stores CRLF (a path marked `-text`) and running both checks against a fresh clone:
```
i/crlf  w/crlf  attr/-text   bad.sh

--- OLD check (working-tree grep) ---
./bad.sh
    -> WOULD FAIL (caught it)

--- NEW check (index) ---
    CRLF stored in the index for: bad.sh
    -> FAILS (caught it)
```
The old grep **caught it**. The escape route the report named is not the one that mattered.
**Why it matters:** The verdict was right — the old check cannot fire *in this repo* — but for a different reason than stated: `.gitattributes` is `* text=auto eol=lf` with **no `-text` exception anywhere** (verified), so no text file escapes normalisation. The report as written also implies the old check was worthless, when it demonstrably catches the most likely real regression: someone adding a `-text` path. A shipped audit report is a record other people reason from, and this one asserts a mechanism that a ten-line experiment contradicts.
**Fix path:** Correct the sentence in the round-4 report to name the real reason (`text=auto` with no exceptions), and record that the old grep does catch the `-text` case — which is why it was kept underneath the new check rather than replaced by it.

---

### FINDING-602 Minor: `[Unreleased]` drifted within one commit of being created
**Dimension:** Docs
**Evidence:** The section added in `c13d63a` opens: *"Kept current from here on… tagging should be a rename of this heading, not an archaeology exercise."* Checked against what `a18d97c` actually changed:
```
the CRLF CI check rewrite        NOT MENTIONED
the widened spawn guard          not described (only the pre-widening guard, from d5cdc4e)
eight call sites (F-502)         covered
```
The correction that *prompted* the commit is in; neither code change is.
**Why it matters:** Doc drift, sixth occurrence in this repo and the first inside the mechanism built to prevent it. Low blast radius — no user is misled about behaviour, since both changes are internal to CI and the test harness — but an `[Unreleased]` section that is only sometimes current is worse than none: it invites the reader to trust it as complete at tag time, which is exactly the failure it was added to stop.
**Fix path:** Add both entries. Longer term this wants the same treatment as every other invariant here — a check rather than an intention — but a changelog-completeness test is a genuinely hard thing to write well, and inventing a weak one would be the seventh vacuous check. Recorded as a watch item instead.

---

## What's working

- **Both new guards were proven able to fire, not assumed to be.** The spawn guard: 4/4 entry points caught (`run`, `check_output`, `Popen`, `check_call`) where 3 of 4 previously escaped. The CRLF check: verified against a purpose-built repo with `i/crlf` in its index — the exact test the *old* check never got, which is why it survived vacuous for a release.
- **CI is green on the rewritten workflow step** (`a18d97c`, `test` — success), so the `awk` over `git ls-files --eol` runs correctly on Ubuntu, not just here.
- **Keeping the working-tree grep underneath the index check was the right call** — this round's experiment shows the two catch overlapping but not identical sets, and the combination is strictly stronger than either.
- **Runtime paths re-exercised end to end:** `--list` creates 0 files, install produces 16, uninstall leaves exactly 1 (the preserved notes backup). Installed copies report 23 checks + 2 named skips = 25, matching the repo in both a plain directory and inside a foreign git repo.
- **Line endings are clean across the whole tree**: 28 files `i/lf w/lf`, one `i/none w/none` (`docs/.nojekyll`, an empty file).

## Watch items

1. **Changelog completeness is the last invariant here held by intention rather than by a check.** Every other one — payload drift, flag documentation, cp437 safety, git spawning, skip accounting — is enforced. This one drifted within a single commit of being created, which is fair evidence that intention is not enough. Worth solving properly rather than quickly.
2. **An audit report is a shipped artefact and inherits the same evidence bar as code.** F-601 is the first finding in this sequence against a report rather than against the repo; the claim was plausible, unmeasured, and wrong.

## Escalation recommendation

**No escalation needed.** Two Minors, both documentation, both one-paragraph corrections.
