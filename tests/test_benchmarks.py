# SPDX-License-Identifier: MIT
"""Tests for scripts/benchmarks.sh.

Runs entirely against a FIXTURE cache via BENCHMARKS_CACHE, so it needs no
network and never touches the real cache or epoch.ai. Every case here exists
because the 2026-08-09 audit found a defect on an untested path.

Run: python3 tests/test_benchmarks.py
"""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = (ROOT / "scripts" / "benchmarks.sh").as_posix()


def find_bash():
    """Same resolution as test_call_local.py: on Windows `bash` is the WSL shim,
    which cannot resolve C:/ paths. Prefer Git Bash."""
    if sys.platform != "win32":
        return "bash"
    found = shutil.which("bash")
    if found and "system32" not in found.lower() and "windowsapps" not in found.lower():
        return found
    git = shutil.which("git")
    if git:
        cand = pathlib.Path(git).resolve().parent.parent / "bin" / "bash.exe"
        if cand.is_file():
            return str(cand)
    for cand in (r"C:\Program Files\Git\bin\bash.exe",
                 r"C:\Program Files (x86)\Git\bin\bash.exe"):
        if pathlib.Path(cand).is_file():
            return cand
    print("SKIP: no Git Bash found; benchmarks.sh needs a POSIX bash on Windows")
    sys.exit(0)


BASH = find_bash()

# A file WITH accessibility (like the real capabilities index) and one WITHOUT
# (like the real swe_bench_verified) -- that asymmetry is what FINDING-003 was.
CAPABILITIES = """Model version,ECI Score,Model accessibility,Organization
open-big_high,160.0,Open weights (unrestricted),TestOrg
open-big_low,160.0,Open weights (unrestricted),TestOrg
closed-top,161.0,API access,TestOrg
open-small,140.0,Open weights (non-commercial),TestOrg
closed-mid,150.0,API access,TestOrg
no-score,,API access,TestOrg
"""

CODING = """Model version,mean_score,Organization
closed-top,0.83,TestOrg
open-big,0.79,TestOrg
"""


def make_cache():
    d = pathlib.Path(tempfile.mkdtemp())
    (d / "epoch_capabilities_index.csv").write_text(CAPABILITIES, encoding="utf-8")
    (d / "swe_bench_verified.csv").write_text(CODING, encoding="utf-8")
    (d / ".fetched").write_text("fixture\n", encoding="utf-8")   # fresh -> no refetch
    return d


def run(*args, cache=None, timeout=120):
    env = {**os.environ, "BENCHMARKS_CACHE": str(cache)}
    return subprocess.run([BASH, SCRIPT, *args], capture_output=True, text=True,
                          timeout=timeout, env=env)


results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f"  — {detail}" if detail and not cond else ""))


CACHE = make_cache()

# --- it reads the cache and ranks correctly, without hitting the network -----
r = run("--limit", "3", cache=CACHE)
check("ranks from the cache without a refetch", r.returncode == 0 and "closed-top" in r.stdout,
      f"rc={r.returncode} {r.stderr[:150]}")
check("does not refetch when the cache is fresh", "fetching" not in r.stderr, r.stderr[:120])
check("highest score is listed first",
      r.stdout.find("closed-top") < r.stdout.find("open-big"), r.stdout[:200])
check("rows with no score are skipped", "no-score" not in r.stdout)
check("effort suffixes collapse to one row per model",
      r.stdout.count("open-big") == 1, f"counted {r.stdout.count('open-big')}")
check("prints the CC-BY attribution every run", "Epoch AI" in r.stdout, r.stdout[-150:])

# --- FINDING-002: a bad --limit must not leak a traceback -------------------
for bad in ("abc", "0", "-5", "3.5"):
    r = run("--limit", bad, cache=CACHE)
    ok = (r.returncode == 1
          and "must be a positive integer" in r.stderr
          and "Traceback" not in (r.stdout + r.stderr))
    check(f"--limit {bad!r} is rejected cleanly, no traceback", ok,
          f"rc={r.returncode} err={r.stderr[:120]}")

# --- FINDING-003: --open on a measure with no accessibility column ----------
r = run("--measure", "coding", "--open", cache=CACHE)
check("--open without accessibility data explains itself",
      r.returncode != 0 and "not available for measure" in r.stderr,
      f"rc={r.returncode} err={r.stderr[:160]}")
check("--open failure does NOT claim nothing matched",
      "nothing matched" not in r.stderr.lower(), r.stderr[:160])
check("--open failure names a measure that does work",
      "capabilities" in r.stderr, r.stderr[:160])

# --- --open works where the column exists ----------------------------------
r = run("--open", cache=CACHE)
check("--open returns only open-weights models",
      r.returncode == 0 and "open-big" in r.stdout and "closed-top" not in r.stdout,
      r.stdout[:200])

# --- other argument handling ------------------------------------------------
r = run("--measure", "nonsense", cache=CACHE)
check("unknown --measure is rejected with a hint",
      r.returncode != 0 and "unknown measure" in r.stderr and "--list" in r.stderr,
      r.stderr[:150])

r = run("--model", "open-small", cache=CACHE)
check("--model filters to matching names",
      r.returncode == 0 and "open-small" in r.stdout and "closed-top" not in r.stdout,
      r.stdout[:200])

r = run("--model", "zzz-no-such-model", cache=CACHE)
check("--model with no match says so without a traceback",
      r.returncode != 0 and "Traceback" not in (r.stdout + r.stderr), r.stderr[:150])

r = run("--bogus-flag", cache=CACHE)
check("an unknown flag is rejected", r.returncode == 1 and "unknown argument" in r.stderr,
      r.stderr[:150])

r = run("--list", cache=CACHE)
check("--list names every supported measure",
      all(m in r.stdout for m in ("capabilities", "coding", "terminal",
                                  "aider", "agentic", "reasoning")), r.stdout[:250])

r = run("--help", cache=CACHE)
check("--help prints usage, not the file header verbatim",
      r.returncode == 0 and "--open" in r.stdout, r.stdout[:200])

# --- a measure whose file is absent from the cache --------------------------
r = run("--measure", "terminal", cache=CACHE)
check("a missing measure file is reported, not a traceback",
      r.returncode != 0 and "Traceback" not in (r.stdout + r.stderr)
      and "not in the cache" in r.stderr, r.stderr[:160])

# --- every measure the script advertises must be documented -----------------
docs = (ROOT / "references" / "benchmarks.md").read_text(encoding="utf-8")
# Look for each value in a `--measure` table cell, not just anywhere in the
# file: "terminal" and "capabilities" also appear inside CSV filenames, so a
# bare substring search passes while the flag stays undocumented.
undocumented = [m for m in ("capabilities", "coding", "terminal", "aider",
                            "agentic", "reasoning") if f"| `{m}`" not in docs]
check("every supported --measure value is documented as a flag value",
      not undocumented, f"undocumented: {undocumented}")
check("the --open limitation is documented",
      "--open` only works with `capabilities`" in docs
      or "--open** only works with `capabilities`" in docs
      or "only works with `capabilities`" in docs)

shutil.rmtree(CACHE, ignore_errors=True)

print()
bad = [n for n, ok in results if not ok]
if bad:
    print(f"FAIL: {len(bad)}/{len(results)} — {'; '.join(bad)}")
    sys.exit(1)
print(f"PASS: {len(results)} benchmarks.sh checks")
