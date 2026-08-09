# Audit Lite — multi-model-routing (v0.3.5 + 2 commits)
**Date:** 2026-08-09
**Scope:** The shipped skill at `C:\Users\scott\.claude\skills\multi-model-routing`, HEAD `2efd4a4`. Focus on the surface added since v0.3.4 — `scripts/benchmarks.sh`, the `CALL_LOCAL_DIALECT` change, and the CI guards.
**Reviewer:** Claude (audit-lite)

## TL;DR

**Ship, with one thing to fix first.** The mature surface — `call_local.sh`, `install.py` — is in good shape: 36 test cases, guards that have each caught a real defect, CI across two OSes and two Python versions. But **`scripts/benchmarks.sh` shipped with zero tests**, and that gap is not theoretical: three probes of untested paths found three defects, one of which regresses a standard this repo explicitly set for itself two releases ago.

No Blockers. Nothing here risks data or history. It is a quality gap in the newest file, not a structural problem.

## Severity rollup (original)
- Blocker: 0
- Critical: 0
- Major: 3
- Minor: 1
- Nit: 0

## Resolution — 2026-08-09, same day
**All four findings fixed. Rollup now 0 / 0 / 0 / 0 / 0.**

| Finding | Status |
|---|---|
| F-001 `benchmarks.sh` untested | **Fixed** — `tests/test_benchmarks.py`, 23 checks, fixture-based so it needs no network. Wired into `PAYLOAD` and CI. |
| F-002 `--limit` traceback | **Fixed** — validated in the argument loop; `abc`, `0`, `-5`, `3.5` all rejected with `--limit must be a positive integer`. Four regression cases. |
| F-003 `--open` misleading | **Fixed** — names the real reason, states it says nothing about how open models score, and points at `--measure capabilities`. Three regression cases. |
| F-004 measures undocumented | **Fixed** — all six `--measure` values in a table in `references/benchmarks.md`, with the `--open` limitation stated. A test asserts each appears as a flag value, not merely as a substring of a filename. |

The audit's own conclusion held: writing the tests for F-001 is what forced
F-002 and F-003 into the open. One untested file produced three defects, and
the fix for all of them was the same fix.

---

## Findings

### FINDING-001 Major: `scripts/benchmarks.sh` has no test coverage at all
**Dimension:** Tests
**Evidence:** No file under `tests/` references `benchmarks.sh` (0 matches). By contrast `call_local.sh` is referenced by 2 test files and `install.py` by 1. The script is in `PAYLOAD` (`install.py:36`), so it ships to every install.
**Why it matters:** This repo's own `CONTRIBUTING.md` states *"Every bug fixed in `scripts/call_local.sh` gets a regression test in the same change."* A new shipped executable arrived exempt from that. The three findings below were all found by probing paths a test would have covered — the gap is already producing defects, not merely risking them.
**Fix path:** Add `tests/test_benchmarks.py` covering: argument validation, unknown measure, `--list`, `--model` with no match, `--open` against a measure lacking the accessibility column, and cache-hit vs refetch. Point it at a fixture directory via `BENCHMARKS_CACHE` so it needs no network — the same trick `test_call_local.py` uses with mock servers.

---

### FINDING-002 Major: `--limit <non-numeric>` leaks a Python traceback
**Dimension:** Correctness
**Evidence:**
```
$ bash scripts/benchmarks.sh --limit abc
Traceback (most recent call last):
  File "<string>", line 66, in <module>
    ...[:int(os.environ["LIMIT"])]:
ValueError: invalid literal for int() with base 10: 'abc'
```
Exit 1, and a partial table header is printed *before* the traceback, so the output is both broken and confusing.
**Why it matters:** This is a **regression of a standard this repo set deliberately.** v0.3.2 fixed exactly this class in `call_local.sh`, which now answers `call_local.sh: max_tokens must be an integer, got 'abc'`. The CHANGELOG records that as a fix. The new script reintroduced the behaviour the old one was corrected for.
**Fix path:** Validate `--limit` in the bash argument loop, matching the existing style: `case "$LIMIT" in ''|*[!0-9]*) echo "benchmarks.sh: --limit must be a positive integer, got '$LIMIT'" >&2; exit 1 ;; esac`.

---

### FINDING-003 Major: `--open` reports "nothing matched" when the data simply lacks the column
**Dimension:** Correctness / UX
**Evidence:** `swe_bench_verified.csv` has no `Model accessibility` column (confirmed: 0 matches in its header). So:
```
$ bash scripts/benchmarks.sh --measure coding --open
benchmarks.sh: nothing matched
```
**Why it matters:** The message is *technically* true and *practically* misleading. A user asking "which open models are best at coding?" is told nothing matched, and the reasonable inference — "no open-weights model scores on coding" — is false. The data just doesn't carry accessibility for that file. This is the skill's headline use case (open-source-first, cloud-vs-local on one scale) failing quietly in the exact place a user would look.
**Fix path:** Detect a missing accessibility column and say so explicitly: *"`--open` is unavailable for measure 'coding': `swe_bench_verified.csv` carries no accessibility data. Use `--measure capabilities` for open/closed filtering, or drop `--open`."* Also document which measures support `--open` — currently only `capabilities` does.

---

### FINDING-004 Minor: documented `--measure` values are incomplete
**Dimension:** Docs
**Evidence:** The script supports six measures (`capabilities, coding, terminal, aider, agentic, reasoning` via `--list`). Docs mention only `coding` — `SKILL.md`, `README.md`, `docs/MANUAL.md` and `references/benchmarks.md` show `--measure coding` and no others. `terminal`, `aider`, `agentic` and `reasoning` are undiscoverable without running `--list`.
**Why it matters:** Low harm — `--list` exists and works. But the agent reads these docs to decide what it can ask for, and won't reach for a measure it has never seen named.
**Fix path:** Add the six-value list to `references/benchmarks.md` beside the existing file table, and mention `--list` in `SKILL.md`.

---

## What's working

- **`call_local.sh` is genuinely well-tested.** 16 cases covering both dialects, empty replies, error bodies served as 200, null content, stall timeouts, >200 KB prompts via stdin and `file:`, and all four `CALL_LOCAL_DIALECT` paths. Every case traces to a real defect rather than a hypothetical.
- **The guards have each earned their place, and they generalize.** The exec-bit and shellcheck checks were rewritten from by-name to `git ls-files 'scripts/*.sh'` after `benchmarks.sh` shipped `100644` — fixing the *class*, not the instance. The payload drift guard reads both tracked and untracked files after a new reference doc slipped past it.
- **The destructive paths are properly defended.** Uninstall refuses a VCS checkout, refuses a directory with no `SKILL.md`, and never overwrites a notes backup. All three verified against the real checkout: 22 tracked files before and after.
- **CI matches the real failure surface.** Two OSes × two Python versions, after a 3.12-only API passed locally and died on 3.11.
- **Evidence discipline is real.** The CHANGELOG records corrections against the reports that prompted them (the argv finding "did not reproduce as reported"), and distinguishes measured from inferred (the POSIX `rmtree` behaviour was re-labelled once actually run under WSL).

## Watch items

1. **`SKILL.md` is 339 lines / 17.9 KB and loads on every trigger**, against 1,235 lines in `references/` that load on demand. The split is deliberate and documented, but the hot-path file has grown ~40% across the last three releases. Worth a pass to move detail down.
2. **The free-tier OpenCode Zen path is documented but not in the routing ladder.** That is a deliberate open decision, not drift — but an undecided item in shipped docs invites someone to assume either answer.
3. **`benchmarks.sh` depends on a third-party file layout.** If Epoch renames a CSV, the `MEASURES` map breaks with `not in the cache; try --refresh`, which misdirects toward a refetch that won't help.

## Escalation recommendation

**No escalation needed.** Three Majors, all confined to one new file, all with local fixes. Nothing architectural, no Blockers or Criticals, and the mature surface holds up. Fix FINDING-001 (tests) and the other three fall out of writing them.

If `audit-team` were run later, the useful scope would be the SKILL.md-vs-references split and whether the routing rule still reads coherently after five releases of additions — a design question this pass deliberately did not open.
