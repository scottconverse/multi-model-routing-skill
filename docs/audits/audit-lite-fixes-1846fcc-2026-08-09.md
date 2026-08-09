# Audit Lite — the eighth fix commit (`1846fcc`)
**Date:** 2026-08-09
**Scope:** `1846fcc` — the round-6 report, plus a one-string typo fix in the first report of the sequence. Two files, both documentation.
**Reviewer:** Claude (audit-lite)

## TL;DR

Nothing found. Every number the round-6 report asserted was re-derived against **the commit it audited** rather than against the tree as it stands now, which is where a stale-figure error would have hidden. The typo fix targets a file that exists and leaves the surrounding recommendation correct. CI green.

**Ship. Second consecutive clean round.**

## Severity rollup
- Blocker: 0 | Critical: 0 | Major: 0 | Minor: 0 | Nit: 0

**0 / 0 / 0 / 0 / 0**

---

## Findings

None.

## What was checked

**Correctness / UX / Runtime — N/A by scope.** Two markdown files; no executable path touched. The full battery was re-run anyway one commit earlier and CI is green on this one.

**Docs:**

| Claim | Verified how | Result |
|---|---|---|
| "29 files `i/lf w/lf`, one `i/none w/none`" | counted from `git ls-tree -r d48c190` — 30 tracked, minus `docs/.nojekyll` | **accurate** for the audited commit (the tree now holds 31, which is why it had to be checked against `d48c190` and not against `HEAD`) |
| the typo target `tests/test_benchmarks.py` | file exists; the corrected sentence now names the suite that was actually built | **accurate** |
| "first clean round of this sequence" | rollups to date: 5, 3, 3, 3, 2, 0 | **accurate** |
| regression battery figures | re-run in full at the previous commit across both platforms, with and without git | **accurate** |

**Deliberately not raised as findings**, with the reasoning, since two of them look like defects to an automated scan:

- **`tests/test_benchmarks.sh.py` still appears once in the repo** — in the round-6 report, quoting the typo in the sentence that labels it a typo and records the fix. A quotation of an error inside its own correction is not the error. Any future reference-scan will flag it; it is a false positive by construction, the same shape as the `docs/audits-old/x.md` case already documented.
- **The "29 files" figure was inferred rather than measured when written** (30 total minus the one `i/none`). It turned out correct, verified above — so there is no defect in the artefact. Recorded as a watch item, not a finding: the process is worth tightening, the output was right, and calling a correct statement a defect would be padding.

## Watch items

1. **Stale figures need checking against the commit they describe, not against `HEAD`.** The "29 files" claim reads as wrong today (the tree holds 31) and is right for `d48c190`. Historical documents age by design; verification has to age with them.
2. **Two documented false-positive shapes now exist for reference scans** — path-like strings used as test data in prose, and errors quoted inside their own corrections. Worth remembering before chasing either a third time.
3. **Changelog completeness is still the one invariant held by intention rather than a check.** Carried forward unanswered for the third round, deliberately: a weak completeness test would be the seventh vacuous check in this repo.

## Escalation recommendation

**No escalation needed.**

---

## Sequence summary

Eight audits, each on the fix commit produced by the previous one:

| Round | Commit | Blocker | Critical | Major | Minor | Nit |
|---|---|---|---|---|---|---|
| 1 | `ca06029` | 0 | 0 | 3 | 2 | 0 |
| 2 | `3a35384` | 0 | 0 | 1 | 2 | 0 |
| 3 | `c13d63a` | 0 | 0 | 1 | 2 | 0 |
| 4 | `d5cdc4e` | 0 | 0 | 0 | 3 | 0 |
| 5 | `a18d97c` | 0 | 0 | 0 | 2 | 0 |
| 6 | `d48c190` | 0 | 0 | 0 | 0 | 0 |
| 7 | `1846fcc` | 0 | 0 | 0 | 0 | 0 |

Majors stop after round 3; findings reach zero at round 6 and stay there. **17 findings across the sequence, all fixed, each verified by re-running its failing case.**

The two defect classes that account for most of them:

- **A guard narrower than its own name** — six occurrences. By-name enumeration (exec bit, shellcheck, `NOT_SHIPPED`, the cp437 scan), then depth instead of datedness, substring instead of structure, and `subprocess.run` instead of "spawns git". Each check encoded the example it was written against rather than the property it claimed. **Reading a check's name back as a specification and asking what else satisfies it** is what caught the last three.
- **A check that is green because of where it runs** — the payload drift guard could not run where it ships and reported `ok` on empty input; the CI CRLF check ran only where the answer was already guaranteed. **Where does this run, and where does it ship?** is now the standing question.

The single practice that did the most work: **watching every new assertion fail on purpose.** It caught a vacuous assertion in the same pass that wrote it (round 1 scored 4/5 and named its own bad one), and it is the reason the guards added later are known to fire rather than assumed to.
