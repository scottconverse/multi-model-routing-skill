#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Scott Converse
#
# codex_models.sh - the model roster Codex CLI itself currently believes in.
#
# Codex maintains ~/.codex/models_cache.json as part of its own normal
# operation -- an etag-conditional fetch, refreshed whenever a real `codex
# exec` (or interactive) call runs. This script only READS that file; it does
# not fetch anything itself, and it does not shell out to Codex. That keeps it
# honest about what it actually knows versus what Codex knows.
#
# Verified 2026-08-10 on this machine: `codex doctor` does NOT touch the
# cache's mtime. A real `codex exec` call does. So "the cache looks stale" is
# fixed by one real exec call, not by re-running doctor -- a claim this script
# would have gotten wrong without testing both paths first.
#
# Usage:
#   codex_models.sh                    # every model, slug + name + description
#   codex_models.sh --model gpt-5.6-sol   # one model, full detail
#   codex_models.sh --json             # the raw cache, unmodified
#   codex_models.sh --list             # slugs only, one per line
#
# Cache: $CODEX_MODELS_CACHE (test override) or
#        $CODEX_HOME/models_cache.json, defaulting to ~/.codex
# Staleness: CODEX_MODELS_MAX_AGE_DAYS (default 7) -- advisory only. This
# script cannot refresh the cache; it can only say how old it is.
# --- end usage ---

set -euo pipefail

CACHE="${CODEX_MODELS_CACHE:-${CODEX_HOME:-$HOME/.codex}/models_cache.json}"
MAX_AGE_DAYS="${CODEX_MODELS_MAX_AGE_DAYS:-7}"

MODEL_FILTER=""
AS_JSON=0
LIST_ONLY=0

while [ $# -gt 0 ]; do
    case "$1" in
        --model)
            [ -n "${2-}" ] || { echo "codex_models.sh: --model needs a value" >&2; exit 1; }
            MODEL_FILTER="$2"; shift 2 ;;
        --json) AS_JSON=1; shift ;;
        --list) LIST_ONLY=1; shift ;;
        -h|--help)
            sed -n '/^# Usage:/,/^# --- end usage ---/p' "$0" \
              | grep -v '^# --- end usage ---' \
              | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) echo "codex_models.sh: unknown argument: $1" >&2; exit 1 ;;
    esac
done

if [ ! -f "$CACHE" ]; then
    echo "codex_models.sh: no cache at $CACHE" >&2
    echo "  Codex writes this itself on a real call. Run one real command," >&2
    echo "  e.g.: codex exec --skip-git-repo-check -c sandbox_mode=\"read-only\" \"hi\"" >&2
    echo "  codex doctor does NOT populate this file -- verified; it checks" >&2
    echo "  install health only, never touches the model cache." >&2
    exit 1
fi

CACHE="$CACHE" MODEL_FILTER="$MODEL_FILTER" AS_JSON="$AS_JSON" LIST_ONLY="$LIST_ONLY" \
MAX_AGE_DAYS="$MAX_AGE_DAYS" python3 -c '
import json, os, sys, time

path = os.environ["CACHE"]
try:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
except json.JSONDecodeError as e:
    sys.exit(f"codex_models.sh: {path} is not valid JSON ({e}) -- "
             f"Codex may be mid-write; try again in a moment")
except OSError as e:
    sys.exit(f"codex_models.sh: cannot read {path}: {e}")

if os.environ["AS_JSON"] == "1":
    # --json exists to be piped into jq/head/grep. Closing that pipe early
    # (`codex_models.sh --json | head`) is the normal case, not an error --
    # without this, Python raises BrokenPipeError and prints a traceback for
    # entirely expected behavior. The standard fix: on SIGPIPE, exit quietly,
    # and redirect stdout to devnull first so the interpreter shutdown does
    # not then try to flush the already-closed pipe and raise a second time.
    try:
        print(json.dumps(data, indent=2))
        sys.stdout.flush()
    except BrokenPipeError:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        sys.exit(0)
    sys.exit(0)

models = data.get("models", [])
if not models:
    sys.exit(f"codex_models.sh: {path} has no models array -- "
             f"unexpected cache shape, not a Codex file this script recognizes")

fetched_at = data.get("fetched_at")
age_days = None
if fetched_at:
    try:
        # Codex writes fetched_at with a trailing Z and NANOSECOND fractional
        # seconds (9 digits) -- confirmed against the real cache on this
        # machine: "2026-08-10T14:52:54.104013800Z". datetime.fromisoformat
        # happens to truncate that to microseconds on this interpreter, but
        # that is version-specific leniency this project has already been
        # burned by trusting once (shutil.rmtree(onexc=) worked on 3.13, died
        # on the CI 3.11 job). Normalize the fractional part to at most 6
        # digits so parsing does not depend on which Python runs it.
        import re
        from datetime import datetime, timezone
        ts = fetched_at.replace("Z", "+00:00")
        ts = re.sub(r"\.(\d{1,6})\d*([+-]\d{2}:\d{2})$",
                    lambda m: f".{m.group(1)}{m.group(2)}", ts)
        fetched = datetime.fromisoformat(ts)
        age_days = (datetime.now(timezone.utc) - fetched).total_seconds() / 86400
    except ValueError:
        pass

filt = os.environ["MODEL_FILTER"]
if filt:
    models = [m for m in models if m.get("slug") == filt]
    if not models:
        known = ", ".join(m.get("slug", "?") for m in data.get("models", []))
        sys.exit(f"codex_models.sh: no model {filt!r} in the cache. "
                 f"Known: {known}")

if os.environ["LIST_ONLY"] == "1":
    for m in models:
        print(m.get("slug", ""))
    sys.exit(0)

if filt:
    m = models[0]
    slug = m.get("slug", "")
    name = m.get("display_name", "")
    desc = m.get("description", "")
    print(f"  {slug}  ({name})")
    print(f"  {desc}")
    levels = m.get("supported_reasoning_levels", [])
    if levels:
        names = ", ".join(l.get("effort", "?") for l in levels)
        default_level = m.get("default_reasoning_level", "?")
        print(f"  reasoning levels: {names}  (default: {default_level})")
    ctx = m.get("context_window")
    if ctx:
        print(f"  context window: {ctx:,}")
else:
    print("  " + "slug".ljust(24) + "display name".ljust(24) + "description")
    print("  " + "-" * 90)
    for m in models:
        slug = m.get("slug", "")
        name = m.get("display_name", "")
        desc = (m.get("description") or "")[:44]
        print(f"  {slug:<24}{name:<24}{desc}")

print()
if age_days is not None:
    stale = " (stale -- Codex has not refreshed this in a while; run a real " \
            "codex exec call to update it)" if age_days > int(os.environ["MAX_AGE_DAYS"]) else ""
    print(f"  cache from Codex itself, {age_days:.1f} day(s) old{stale}")
else:
    print("  cache from Codex itself, age unknown (no fetched_at field)")
'
