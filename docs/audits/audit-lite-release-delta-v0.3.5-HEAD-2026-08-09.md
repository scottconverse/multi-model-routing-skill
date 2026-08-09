# Audit Lite — the whole release delta, `v0.3.5..HEAD`
**Date:** 2026-08-09
**Scope:** the **accumulated** state of all ten commits since `v0.3.5`, not a single diff. Run because the sequence's two clean rounds both landed on documentation-only commits (`code-files=0`), and because `tests/test_install.py` was rewritten across five of the ten commits and its final state had never been reviewed as a whole.
**Reviewer:** Claude (audit-lite)

## TL;DR

The accumulated state is sound — no dead code, no unused imports, no leftover TODOs, no version drift, docs consistent, 72 checks green on every surface. **One finding**, and it is one that per-commit review structurally could not catch: a guard whose *file* scope was widened in round 2 while its *pattern* scope was never questioned, and which no later diff touched.

Ship. The finding is latent, not live — nothing in the repo currently uses an evading form.

## Severity rollup (original)
- Blocker: 0 | Critical: 0 | Major: 0 | **Minor: 1** | Nit: 0

## Resolution — 2026-08-09, same day
**Fixed. Rollup now 0 / 0 / 0 / 0 / 0.**

---

## Findings

### FINDING-801 Minor: the cp437 guard checks four hardcoded call patterns, not "printed strings"
**Dimension:** Tests
**Evidence:** The check is named *"printed strings are cp437-safe across all N shipped .py files"*. It scanned only lines containing one of a literal tuple:
```python
PRINTS = ("print(", "actions.append(", "sys.exit(", "return dest, [")
```
Measured against other ways a string reaches a stream:
```
print("caf—")                CAUGHT
sys.stderr.write("caf—")     EVADES
sys.stdout.write("caf—")     EVADES
raise SystemExit("caf—")     EVADES
logging.warning("caf—")      EVADES
```
**Why it matters:** No live exposure — none of the evading forms is used in any shipped `.py` today (verified). But this is the **seventh** occurrence of a guard narrower than its own name, and the mechanism is the specific one whole-delta review exists to catch: in round 2 the guard's *file* scope was correctly widened from `install.py`-by-name to every shipped `.py`, and nobody asked whether the *pattern* scope was right. No commit afterwards touched that line, so no per-commit audit ever looked at it again.

Two of the evading forms are exactly what this codebase would reach for next: `sys.stderr.write` for a diagnostic, `raise SystemExit("message")` for a fatal — and `install.py` already uses `sys.exit("...")`, one keystroke away from the form that evades.
**Fix path:** Stop enumerating call patterns. Parse the file and check **every non-docstring string literal**: docstrings are the deliberate exemption (documentation, never streamed), and comments are invisible to the parser, so they drop out for free rather than via a `startswith("#")` that a trailing comment defeats. Verify it produces no false positives across the shipped files before adopting, then watch each evading form go red.

**Fixed:** implemented as `offending_literals()`. Verified no false positives across all four shipped `.py` files, then perturbed — **6/6 as designed**: all five output forms now caught (where four previously evaded), and a docstring containing an em dash correctly stays exempt.

---

## What was checked, and what came back clean

| Check across the whole delta | Result |
|---|---|
| dead code after five rewrites of `test_install.py` | **none** — no unused imports, no unread module-level names, in any of the four `.py` files |
| leftover `TODO` / `FIXME` / `XXX` | **none** in any `.py`, `.sh` or `.yml` |
| version-string drift across `SKILL.md`, `README.md`, `docs/MANUAL.md`, `install.py` | **none** — no version literals live in those surfaces at all, so there is nothing to drift; versions live only in `CHANGELOG.md` and git tags |
| `SKILL.md` vs the actual script | consistent — it shows three example invocations and does not claim to be a flag reference, which is why it is deliberately exempt from the flag-completeness test |
| line endings | 30 files `i/lf w/lf`, one `i/none w/none` (`docs/.nojekyll`, empty) |
| every referenced `tests/test_*.py` path exists | yes, after the round-6 typo fix |
| full battery | 16 + 25 + 31 = **72** green on Windows/py3.13, WSL Ubuntu 26.04/py3.14/bash 5.3.9, and with git absent on both |
| perturbation harnesses r1–r4 | 5/5, 3/3, 3/3, 4/4 — no regression |
| installs: plain, and inside a foreign git repo | 23 + 2 named skips = 25, both |

## Watch items

1. **Per-commit auditing has a structural blind spot** and this round is the proof: a line touched in commit *N* and never touched again is reviewed exactly once, in the context of that change alone. F-801 survived five subsequent audits because no diff contained it. Worth one whole-state pass before any tag, not just per-commit passes.
2. **Changelog completeness is still the one invariant held by intention rather than a check** — carried unanswered for the fourth round, deliberately.

## Escalation recommendation

**No escalation needed.** One Minor, latent, fixed and proven. The whole-delta pass that found it is itself the escalation that was warranted, and it has now been run.
