# SPDX-License-Identifier: MIT
"""Tests for scripts/codex_models.sh.

Runs entirely against a FIXTURE cache via CODEX_MODELS_CACHE, so it needs no
real Codex install and never touches ~/.codex. Every case here exists because
this script's first real run, against the real cache, crashed twice before
shipping -- an f-string escaping bug, then a second bug introduced while
fixing the first (single-quoted Python string literals breaking the OUTER
bash single-quoted block they live inside). Both were caught by running the
script for real, not by reading it. These tests exist so the next change to
this file gets the same treatment automatically.

Run: python3 tests/test_codex_models.py
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = (ROOT / "scripts" / "codex_models.sh").as_posix()


def find_bash():
    """Same resolution as test_call_local.py and test_benchmarks.py: on
    Windows `bash` is the WSL shim, which cannot resolve C:/ paths."""
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
    print("SKIP: no Git Bash found; codex_models.sh needs a POSIX bash on Windows")
    sys.exit(0)


BASH = find_bash()

# Real shape, trimmed to two models -- one rich (matches gpt-5.6-sol from the
# live cache), one sparse (missing optional fields, to prove those don't crash
# the script). A fixture with fields OMITTED is the whole point: the live
# cache has 33 fields per model and this script must not assume all of them
# are present.
FIXTURE = {
    "fetched_at": None,   # filled in per-test so freshness is controllable
    "etag": "W/\"test-etag\"",
    "client_version": "0.145.0",
    "models": [
        {
            "slug": "gpt-5.6-sol",
            "display_name": "GPT-5.6-Sol",
            "description": "Latest frontier agentic coding model.",
            "default_reasoning_level": "low",
            "supported_reasoning_levels": [
                {"effort": "low", "description": "Fast"},
                {"effort": "high", "description": "Deep"},
            ],
            "context_window": 272000,
        },
        {
            # Sparse on purpose: no description, no reasoning levels, no
            # context window. A real cache entry can look like this.
            "slug": "codex-auto-review",
            "display_name": "Codex Auto Review",
        },
    ],
}


def make_cache(age_days=0.0, models=None):
    d = tempfile.mkdtemp()
    cache = pathlib.Path(d) / "models_cache.json"
    data = dict(FIXTURE)
    if models is not None:
        data["models"] = models
    fetched = datetime.now(timezone.utc) - timedelta(days=age_days)
    data["fetched_at"] = fetched.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    cache.write_text(json.dumps(data), encoding="utf-8")
    return cache


def run(*args, cache, env_extra=None, timeout=60):
    env = {**os.environ, "CODEX_MODELS_CACHE": str(cache)}
    if env_extra:
        env.update(env_extra)
    return subprocess.run([BASH, SCRIPT, *args], capture_output=True, text=True,
                          timeout=timeout, env=env)


results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f"  - {detail}" if detail and not cond else ""))


# --- the fixture itself must actually exercise a sparse entry --------------
# If every fixture field is present, a script that blindly does m["field"]
# instead of m.get("field") would still pass. Assert the sparse entry stays
# sparse so this suite cannot go vacuous by accident.
check("fixture's second model is genuinely sparse (no description)",
      "description" not in FIXTURE["models"][1])

# --- default output: both a rich and a sparse entry, no traceback ----------
cache = make_cache()
r = run(cache=cache)
check("default output exits 0", r.returncode == 0, f"rc={r.returncode} {r.stderr[:150]}")
check("lists the rich model", "gpt-5.6-sol" in r.stdout)
check("lists the sparse model without crashing on missing fields",
      "codex-auto-review" in r.stdout and "Traceback" not in r.stderr)
check("prints cache age", "day(s) old" in r.stdout)
shutil.rmtree(cache.parent, ignore_errors=True)

# --- --model on the rich entry: every optional field rendered --------------
cache = make_cache()
r = run("--model", "gpt-5.6-sol", cache=cache)
check("--model exits 0", r.returncode == 0, r.stderr[:150])
check("--model shows the description",
      "Latest frontier agentic coding model" in r.stdout)
check("--model shows reasoning levels", "low, high" in r.stdout)
check("--model shows context window", "272,000" in r.stdout)
shutil.rmtree(cache.parent, ignore_errors=True)

# --- --model on the SPARSE entry: must not crash on absent fields ----------
# This is the exact shape of bug that shipped twice: code that assumes a
# field exists because the one model tested against (by hand) happened to
# have it.
cache = make_cache()
r = run("--model", "codex-auto-review", cache=cache)
ok = (r.returncode == 0 and "codex-auto-review" in r.stdout
      and "Traceback" not in (r.stdout + r.stderr))
check("--model on a sparse entry (no description/levels/context) does not crash",
      ok, f"rc={r.returncode} {r.stderr[:200]}")
shutil.rmtree(cache.parent, ignore_errors=True)

# --- --model with no match: clean error, names what IS known ---------------
cache = make_cache()
r = run("--model", "totally-fake-model", cache=cache)
check("unknown --model fails cleanly, no traceback",
      r.returncode == 1 and "Traceback" not in (r.stdout + r.stderr),
      f"rc={r.returncode} {r.stderr[:150]}")
check("unknown --model names the real slugs",
      "gpt-5.6-sol" in r.stderr and "codex-auto-review" in r.stderr, r.stderr[:200])
shutil.rmtree(cache.parent, ignore_errors=True)

# --- --model with no value ---------------------------------------------------
cache = make_cache()
r = run("--model", cache=cache)
check("--model with no value is rejected in the script's own voice",
      r.returncode == 1 and "codex_models.sh: --model needs a value" in r.stderr
      and "Traceback" not in (r.stdout + r.stderr), r.stderr[:150])
shutil.rmtree(cache.parent, ignore_errors=True)

# --- --list: slugs only, one per line, nothing else -------------------------
cache = make_cache()
r = run("--list", cache=cache)
lines = [l for l in r.stdout.splitlines() if l.strip()]
check("--list prints exactly the slugs, nothing decorative",
      r.returncode == 0 and set(lines) == {"gpt-5.6-sol", "codex-auto-review"},
      f"{lines}")
shutil.rmtree(cache.parent, ignore_errors=True)

# --- --json: valid, parseable JSON, and the ORIGINAL data round-trips ------
cache = make_cache()
r = run("--json", cache=cache)
check("--json exits 0", r.returncode == 0, r.stderr[:150])
try:
    parsed = json.loads(r.stdout)
    check("--json round-trips the model count", len(parsed.get("models", [])) == 2)
except json.JSONDecodeError as e:
    check("--json output is valid JSON", False, str(e))
shutil.rmtree(cache.parent, ignore_errors=True)

# --- --json piped into something that closes the pipe early -----------------
# codex_models.sh shipped its first version with a BrokenPipeError traceback
# on exactly this -- the single most common real use of --json is piping it
# into head/jq/grep, all of which close the pipe once satisfied.
cache = make_cache()
proc = subprocess.run(
    f'"{BASH}" "{SCRIPT}" --json | head -c 50', shell=True, capture_output=True,
    text=True, timeout=60, env={**os.environ, "CODEX_MODELS_CACHE": str(cache)})
check("--json piped into a pipe that closes early produces no traceback",
      "Traceback" not in (proc.stdout + proc.stderr) and "BrokenPipeError" not in proc.stderr,
      proc.stderr[:200])
shutil.rmtree(cache.parent, ignore_errors=True)

# --- staleness: fresh cache says nothing alarming, old cache flags itself ---
cache = make_cache(age_days=1.0)
r = run(cache=cache)
check("a 1-day-old cache is not flagged stale (default max age 7)",
      "stale" not in r.stdout.lower())
shutil.rmtree(cache.parent, ignore_errors=True)

cache = make_cache(age_days=10.0)
r = run(cache=cache)
check("a 10-day-old cache is flagged stale", "stale" in r.stdout.lower(), r.stdout[-200:])
check("the stale message points at a real exec call, not codex doctor",
      "codex exec" in r.stdout and "codex doctor" not in r.stdout.lower().split("stale")[-1],
      r.stdout[-250:])
shutil.rmtree(cache.parent, ignore_errors=True)

cache = make_cache(age_days=3.0)
r = run(cache=cache, env_extra={"CODEX_MODELS_MAX_AGE_DAYS": "2"})
check("CODEX_MODELS_MAX_AGE_DAYS is honored", "stale" in r.stdout.lower(), r.stdout[-200:])
shutil.rmtree(cache.parent, ignore_errors=True)

# --- missing cache: clean, actionable error, no traceback -------------------
missing = pathlib.Path(tempfile.mkdtemp()) / "nope.json"
r = run(cache=missing)
ok = (r.returncode == 1 and "Traceback" not in (r.stdout + r.stderr)
      and "codex exec" in r.stderr)
check("a missing cache explains itself and points at a real fix, no traceback",
      ok, f"rc={r.returncode} {r.stderr[:250]}")
check("the missing-cache message does NOT claim codex doctor helps",
      "doctor does NOT populate" in r.stderr or "doctor" not in r.stderr.lower(),
      r.stderr[:250])
shutil.rmtree(missing.parent, ignore_errors=True)

# --- malformed JSON: clean error naming the file, no traceback --------------
bad = pathlib.Path(tempfile.mkdtemp()) / "models_cache.json"
bad.write_text("{not valid json", encoding="utf-8")
r = run(cache=bad)
check("malformed JSON fails cleanly, no traceback",
      r.returncode == 1 and "Traceback" not in (r.stdout + r.stderr)
      and "not valid JSON" in r.stderr, r.stderr[:200])
shutil.rmtree(bad.parent, ignore_errors=True)

# --- empty models array: clean error, not an empty silent success ----------
cache = make_cache(models=[])
r = run(cache=cache)
check("an empty models array is reported, not silently treated as zero results",
      r.returncode == 1 and "no models array" in r.stderr, r.stderr[:200])
shutil.rmtree(cache.parent, ignore_errors=True)

# --- --help is complete AND clean, same discipline as benchmarks.sh --------
cache = make_cache()
r = run("--help", cache=cache)
check("--help exits 0", r.returncode == 0, r.stderr[:150])
script_src = (ROOT / "scripts" / "codex_models.sh").read_text(encoding="utf-8")
parser = script_src.split("while [ $# -gt 0 ]", 1)[-1].split("\ndone", 1)[0]
accepted = sorted({tok for tok in re.findall(r"(--[a-z-]+)\s*[)|]", parser)
                   if tok not in ("--help",)})
assert len(accepted) >= 3, f"flag extraction looks broken: {accepted}"
missing_from_help = [f for f in accepted if f not in r.stdout]
check("--help documents every flag the parser accepts", not missing_from_help,
      f"accepted={accepted} missing={missing_from_help}")
leaked = [tok for tok in ("set -euo", "esac", "shift 2", '"$0"', "exit 0")
          if tok in r.stdout]
check("--help leaks no shell syntax", not leaked, f"leaked: {leaked}")
shutil.rmtree(cache.parent, ignore_errors=True)

# --- an unknown flag is rejected, not silently ignored -----------------------
cache = make_cache()
r = run("--bogus-flag", cache=cache)
check("an unknown flag is rejected",
      r.returncode == 1 and "unknown argument" in r.stderr, r.stderr[:150])
shutil.rmtree(cache.parent, ignore_errors=True)

print()
bad_checks = [n for n, ok in results if not ok]
if bad_checks:
    print(f"FAIL: {len(bad_checks)}/{len(results)} - {'; '.join(bad_checks)}")
    sys.exit(1)
print(f"PASS: {len(results)} codex_models.sh checks")
