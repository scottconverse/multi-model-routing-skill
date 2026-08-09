#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Scott Converse
#
# benchmarks.sh - rank models on open benchmark data, cloud and local on one scale.
#
# Data: Epoch AI's Benchmarking Hub, CC-BY 4.0 (free to use, distribute and
# reproduce with attribution). No account and no API key.
#   Epoch AI, 'AI Benchmarking Hub'. Published online at epoch.ai.
#   Retrieved from https://epoch.ai/benchmarks
#
# The point of this script is FRESHNESS. A number pasted into a document is a
# fossil the moment a model ships; this refetches whenever the cache is older
# than MAX_AGE_DAYS, so a routing decision is made against current data instead
# of whatever someone typed months ago.
#
# Usage:
#   benchmarks.sh                      # top 25 by the headline composite
#   benchmarks.sh --open               # open-weights models only
#   benchmarks.sh --measure coding     # coding benchmarks instead
#   benchmarks.sh --model deepseek     # everything matching a name
#   benchmarks.sh --refresh            # force a refetch
#   benchmarks.sh --list               # which measures are available
#
# Cache: $CALL_LOCAL_CACHE or ~/.cache/multi-model-routing/benchmarks
# Staleness: BENCHMARKS_MAX_AGE_DAYS (default 7)

set -euo pipefail

URL="https://epoch.ai/data/benchmark_data.zip"
CACHE="${BENCHMARKS_CACHE:-$HOME/.cache/multi-model-routing/benchmarks}"
MAX_AGE_DAYS="${BENCHMARKS_MAX_AGE_DAYS:-7}"

MEASURE="capabilities"
LIMIT=25
OPEN_ONLY=0
MODEL_FILTER=""
REFRESH=0
LIST=0

while [ $# -gt 0 ]; do
    case "$1" in
        --measure) MEASURE="${2:?--measure needs a value}"; shift 2 ;;
        --model)   MODEL_FILTER="${2:?--model needs a value}"; shift 2 ;;
        --limit)
            LIMIT="${2:?--limit needs a value}"
            # Validate here, not in the python below. Leaving it to int() gave a
            # raw ValueError traceback -- the exact failure call_local.sh was
            # corrected for in v0.3.2. A shipped script should never answer a
            # bad argument with a stack trace.
            case "$LIMIT" in
                ''|*[!0-9]*|0)
                    echo "benchmarks.sh: --limit must be a positive integer, got '$LIMIT'" >&2
                    exit 1 ;;
            esac
            shift 2 ;;
        --open)    OPEN_ONLY=1; shift ;;
        --refresh) REFRESH=1; shift ;;
        --list)    LIST=1; shift ;;
        -h|--help) sed -n '5,28p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "benchmarks.sh: unknown argument: $1" >&2; exit 1 ;;
    esac
done

mkdir -p "$CACHE"
STAMP="$CACHE/.fetched"

need_fetch=0
if [ "$REFRESH" = "1" ] || [ ! -f "$STAMP" ]; then
    need_fetch=1
else
    # Portable age check: no `find -mtime` reliance, no GNU date assumptions.
    age_days=$(python3 -c "
import os, time, sys
try:
    print(int((time.time() - os.path.getmtime(sys.argv[1])) // 86400))
except OSError:
    print(9999)
" "$STAMP")
    [ "$age_days" -ge "$MAX_AGE_DAYS" ] && need_fetch=1
fi

if [ "$need_fetch" = "1" ]; then
    echo "benchmarks.sh: fetching current data from epoch.ai ..." >&2
    tmp="$CACHE/.download.zip"
    if curl -sSL --connect-timeout 10 --max-time 180 -o "$tmp" "$URL"; then
        if (cd "$CACHE" && unzip -o -q "$tmp"); then
            date > "$STAMP"
            rm -f "$tmp"
        else
            echo "benchmarks.sh: downloaded file is not a readable zip" >&2
            rm -f "$tmp"; [ -f "$CACHE/epoch_capabilities_index.csv" ] || exit 1
            echo "benchmarks.sh: continuing with the previous cache" >&2
        fi
    else
        # Offline is not fatal if we already have data -- say so and carry on.
        if [ -f "$CACHE/epoch_capabilities_index.csv" ]; then
            echo "benchmarks.sh: fetch failed; using cached data (may be stale)" >&2
        else
            echo "benchmarks.sh: fetch failed and no cache present" >&2
            exit 1
        fi
    fi
fi

CACHE="$CACHE" MEASURE="$MEASURE" LIMIT="$LIMIT" OPEN_ONLY="$OPEN_ONLY" \
MODEL_FILTER="$MODEL_FILTER" LIST="$LIST" python3 -c '
import csv, os, sys, glob, time

cache = os.environ["CACHE"]

MEASURES = {
    "capabilities": ("epoch_capabilities_index.csv", "ECI Score"),
    "coding":       ("swe_bench_verified.csv",       "mean_score"),
    "terminal":     ("terminalbench_external.csv",   "mean_score"),
    "aider":        ("aider_polyglot_external.csv",  "mean_score"),
    "agentic":      ("os_world_external.csv",        "mean_score"),
    "reasoning":    ("gpqa_diamond.csv",             "mean_score"),
}

if os.environ["LIST"] == "1":
    print("measures:")
    for k, (fn, _) in MEASURES.items():
        mark = "ok " if os.path.isfile(os.path.join(cache, fn)) else "-- "
        print(f"  {mark} {k:<14} {fn}")
    n_csv = len(glob.glob(os.path.join(cache, "*.csv")))
    print()
    print("  " + str(n_csv) + " benchmark files cached")
    sys.exit(0)

measure = os.environ["MEASURE"]
if measure not in MEASURES:
    sys.exit(f"benchmarks.sh: unknown measure {measure!r}; try --list")

fn, col = MEASURES[measure]
path = os.path.join(cache, fn)
if not os.path.isfile(path):
    sys.exit(f"benchmarks.sh: {fn} not in the cache; try --refresh")

rows = list(csv.DictReader(open(path, encoding="utf-8")))
if col not in (rows[0] if rows else {}):
    col = next((c for c in rows[0] if "score" in c.lower()), col)

name_col = "Model version" if "Model version" in rows[0] else list(rows[0])[0]
acc_col  = "Model accessibility" if "Model accessibility" in rows[0] else None

filt = os.environ["MODEL_FILTER"].lower()
open_only = os.environ["OPEN_ONLY"] == "1"

# --open needs an accessibility column, and only some files carry one. Saying
# "nothing matched" here would be true and useless: the reader concludes no
# open model scores on this measure, which is false -- the data simply does not
# record open vs closed. Name the real reason and point at a measure that works.
if open_only and acc_col is None:
    sys.exit(f"benchmarks.sh: --open is not available for measure {measure!r}: "
             f"{fn} carries no accessibility data, so open and closed models "
             f"cannot be told apart here.\n"
             f"  This says nothing about how open models score on it.\n"
             f"  Use --measure capabilities for open/closed filtering, "
             f"or drop --open.")

best = {}
for r in rows:
    try:
        score = float(r[col])
    except (TypeError, ValueError):
        continue
    # Epoch suffixes reasoning-effort variants (…_high, …_max); collapse them.
    name = r[name_col].rsplit("_", 1)[0]
    acc = (r.get(acc_col) or "") if acc_col else ""
    if filt and filt not in name.lower():
        continue
    if open_only and "open" not in acc.lower():
        continue
    if name not in best or score > best[name][0]:
        best[name] = (score, acc)

if not best:
    sys.exit("benchmarks.sh: nothing matched")

print(f"  {measure}  ({fn})")
print("  " + "model".ljust(44) + "score".rjust(9) + "   access")
print("  " + "-" * 78)
for name, (score, acc) in sorted(best.items(), key=lambda kv: -kv[1][0])[:int(os.environ["LIMIT"])]:
    tag = "OPEN" if "open" in acc.lower() else ("api" if acc else "")
    print(f"  {name[:43]:<44}{score:>9.2f}   {tag}")

stamp = os.path.join(cache, ".fetched")
age = int((time.time() - os.path.getmtime(stamp)) // 86400) if os.path.isfile(stamp) else -1
print()
print("  data cached " + str(age) + " day(s) ago - Epoch AI, AI Benchmarking Hub,"
      " epoch.ai (CC-BY 4.0)")
'
