#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Scott Converse
#
# call_local.sh — one-shot prompt against a local LLM server (Ollama, LM Studio).
#
# Tries the Anthropic-format endpoint (/v1/messages) first; if the server says
# it does not serve that endpoint (404/405/501), falls back to the OpenAI-format
# endpoint (/v1/chat/completions). Prints the model's reply on stdout and a
# "[receipt] in=<n> out=<n>" token-usage line on stderr — keep the receipt as
# evidence the call actually happened.
#
# Usage:
#   call_local.sh <base-url> <model> <prompt|-|file:PATH> [max_tokens]
#
# The prompt may be given three ways. Use `-` or `file:PATH` for anything large:
# a literal argument has to fit in the OS argv limit, which a real batch input
# will exceed (curl reports "Argument list too long" past ~32k on Windows, and
# a .cmd shim caps the whole command line near 8k).
#
# Examples:
#   call_local.sh http://localhost:11434 qwen2.5-coder:7b "Reply with exactly: OK" 512
#   call_local.sh http://localhost:1234  gemma-3-12b     file:prompt.txt            2048
#   cat big.log | call_local.sh http://localhost:11434 qwen2.5:7b - 2048
#
# Exit codes:
#   0  reply on stdout
#   1  transport, HTTP, or parse failure (details on stderr)
#   2  server replied 200 but the visible text was empty — see below
#
# Note: max_tokens defaults to 1024. Reasoning-style models spend hidden
# tokens before visible output, so values under ~500 can come back with
# nothing visible. That is reported as a failure (exit 2), never as an empty
# success — a batch caller must not record "" as a valid answer.
#
# Timeouts: CALL_LOCAL_CONNECT_TIMEOUT (default 5s) to establish the
# connection and CALL_LOCAL_TIMEOUT (default 300s) for the whole call. A
# server that accepts the connection and then stalls will not hang this script
# forever. Raise CALL_LOCAL_TIMEOUT for genuinely long generations.
#
# Privacy: this sends <prompt> to whatever <base-url> you give it. The name
# says "local" but nothing here enforces it — point it at a remote host and
# your prompt goes to that host. Keep it on localhost for private material.

set -euo pipefail

BASE="${1:?usage: call_local.sh <base-url> <model> <prompt|-|file:PATH> [max_tokens]}"
MODEL="${2:?missing <model>}"
PROMPT_ARG="${3:?missing <prompt> (use - for stdin, or file:PATH)}"
MAX_TOKENS="${4:-1024}"

CONNECT_TIMEOUT="${CALL_LOCAL_CONNECT_TIMEOUT:-5}"
TIMEOUT="${CALL_LOCAL_TIMEOUT:-300}"

RESP_FILE=$(mktemp)
PROMPT_FILE=$(mktemp)
BODY_FILE=$(mktemp)
trap 'rm -f "$RESP_FILE" "$PROMPT_FILE" "$BODY_FILE"' EXIT

# Get the prompt onto disk without it ever passing through argv or the
# environment. Both have hard ceilings that a batch caller hits with a real
# input: on Windows curl refuses a body over ~32k with "Argument list too
# long", and a .cmd shim caps the whole command line at ~8k. Reading a file or
# stdin has no such limit.
# NOTE: the file sigil is `file:PATH`, deliberately NOT `@PATH`. Git Bash on
# Windows expands a leading @ as a *response file* before the script ever runs:
# `@p.txt` containing "alpha beta gamma" arrives as three separate arguments,
# which silently shifts every later argument. Verified 2026-08-09.
case "$PROMPT_ARG" in
    -)  cat > "$PROMPT_FILE" ;;                        # prompt on stdin
    file:*)
        src="${PROMPT_ARG#file:}"
        [ -f "$src" ] || { echo "call_local.sh: no such prompt file: $src" >&2; exit 1; }
        cat "$src" > "$PROMPT_FILE" ;;
    *)  printf '%s' "$PROMPT_ARG" > "$PROMPT_FILE" ;;  # literal, as before
esac

MODEL="$MODEL" MAX_TOKENS="$MAX_TOKENS" \
PROMPT_FILE="$PROMPT_FILE" BODY_FILE="$BODY_FILE" python3 -c '
import json, os, sys

raw = os.environ["MAX_TOKENS"]
try:
    max_tokens = int(raw)
except ValueError:
    sys.exit("call_local.sh: max_tokens must be an integer, got %r" % raw)

with open(os.environ["PROMPT_FILE"], encoding="utf-8") as f:
    prompt = f.read()

with open(os.environ["BODY_FILE"], "w", encoding="utf-8") as f:
    json.dump({
        "model": os.environ["MODEL"],
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }, f)
'

# Echoes "<http_code> <curl_exit>". curl's exit status has to ride along in
# stdout: the caller reads this through a command substitution, so a global
# set in here would not survive the subshell.
do_post() {
    local path="$1" code rc=0
    shift
    # --data-binary @FILE, never -d "$BODY": passing the body as an argument is
    # what hits the OS argv ceiling on a large prompt.
    code=$(curl -sS -o "$RESP_FILE" -w '%{http_code}' \
        --connect-timeout "$CONNECT_TIMEOUT" --max-time "$TIMEOUT" \
        -X POST "$BASE$path" -H 'content-type: application/json' "$@" \
        --data-binary "@$BODY_FILE") || rc=$?
    echo "${code:-000} $rc"
}

# CALL_LOCAL_DIALECT: auto (default) | anthropic | openai
#
# `auto` probes /v1/messages then falls back. That is right for a local server,
# which either serves a dialect or doesn't. It is wrong for a GATEWAY, where the
# dialect depends on the MODEL: OpenCode Zen serves /v1/messages only for paid
# Claude models and answers 401/400 for everything else, while its free models
# work fine on /v1/chat/completions. Falling back on 400 generally is not the
# answer -- a 400 is usually a genuine bad request and retrying would hide it.
# So the caller states the dialect when it knows.
DIALECT="${CALL_LOCAL_DIALECT:-auto}"

case "$DIALECT" in
    openai)
        read -r CODE CURL_RC <<<"$(do_post /v1/chat/completions)"
        ;;
    anthropic)
        read -r CODE CURL_RC <<<"$(do_post /v1/messages -H 'anthropic-version: 2023-06-01')"
        ;;
    auto)
        read -r CODE CURL_RC <<<"$(do_post /v1/messages -H 'anthropic-version: 2023-06-01')"
        # 404, 405 and 501 all mean "this server doesn't serve that endpoint" —
        # try the OpenAI dialect before giving up. Matching only 404 would
        # strand us on servers that answer an unknown path with 405. Anything
        # else is a genuine failure and retrying would just obscure it.
        case "$CODE" in
            404|405|501) read -r CODE CURL_RC <<<"$(do_post /v1/chat/completions)" ;;
        esac
        ;;
    *)
        echo "call_local.sh: CALL_LOCAL_DIALECT must be auto, anthropic or openai" >&2
        exit 1
        ;;
esac

if [ "$CODE" != "200" ]; then
    case "$CURL_RC" in
        28)  echo "call_local.sh: timed out after ${TIMEOUT}s talking to $BASE (raise CALL_LOCAL_TIMEOUT)" >&2 ;;
        6|7) echo "call_local.sh: no server reachable at $BASE" >&2 ;;
        0)   echo "call_local.sh: HTTP $CODE from $BASE" >&2 ;;
        *)   echo "call_local.sh: curl failed (exit $CURL_RC) talking to $BASE" >&2 ;;
    esac
    cat "$RESP_FILE" >&2 || true
    exit 1
fi

python3 - "$RESP_FILE" <<'PY'
import json, sys

with open(sys.argv[1]) as f:
    try:
        d = json.load(f)
    except json.JSONDecodeError as e:
        sys.exit(f"call_local.sh: HTTP 200 but the body is not JSON ({e})")

if not isinstance(d, dict):
    sys.exit(f"call_local.sh: unexpected JSON top level: {type(d).__name__}")

# A 200 can still carry an error body. Say so plainly rather than dying on a
# missing key further down and blaming the wrong dialect.
if "content" not in d and "choices" not in d:
    err = d.get("error")
    if err is not None:
        msg = err.get("message") if isinstance(err, dict) else err
        sys.exit(f"call_local.sh: server returned an error: {msg}")
    sys.exit(f"call_local.sh: unrecognized response shape (keys: {', '.join(sorted(d))})")

if "content" in d:  # Anthropic format
    blocks = d["content"] if isinstance(d["content"], list) else []
    text = "".join(b.get("text", "") for b in blocks
                   if isinstance(b, dict) and b.get("type") == "text")
    u = d.get("usage", {})
    receipt = f"[receipt] in={u.get('input_tokens')} out={u.get('output_tokens')}"
else:  # OpenAI format
    try:
        # content is None on tool-call and filtered responses; treat as empty
        # rather than printing the string "None" as if it were the answer.
        text = d["choices"][0]["message"]["content"] or ""
    except (IndexError, KeyError, TypeError) as e:
        sys.exit(f"call_local.sh: malformed OpenAI-format response ({e})")
    u = d.get("usage", {})
    receipt = f"[receipt] in={u.get('prompt_tokens')} out={u.get('completion_tokens')}"

# Receipt first, so it survives even when the reply itself turns out empty.
print(receipt, file=sys.stderr)

if not text.strip():
    # ASCII only: cmd.exe defaults to cp437, which has no em dash, and a
    # UnicodeEncodeError here would replace a clear diagnostic with a traceback.
    print("call_local.sh: server replied 200 but the visible text was empty - "
          "raise max_tokens (reasoning models spend hidden tokens first)",
          file=sys.stderr)
    sys.exit(2)

print(text)
PY
