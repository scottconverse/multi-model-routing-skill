#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Scott Converse
#
# call_local.sh — one-shot prompt against a local LLM server (Ollama, LM Studio).
#
# Tries the Anthropic-format endpoint (/v1/messages) first; if the server
# returns 404 (older builds without the Anthropic dialect), falls back to the
# OpenAI-format endpoint (/v1/chat/completions). Prints the model's reply on
# stdout and a "[receipt] in=<n> out=<n>" token-usage line on stderr — keep
# the receipt as evidence the call actually happened.
#
# Usage:
#   call_local.sh <base-url> <model> <prompt> [max_tokens]
# Examples:
#   call_local.sh http://localhost:11434 qwen2.5-coder:7b "Reply with exactly: OK" 512
#   call_local.sh http://localhost:1234  gemma-3-12b     "Summarize: ..."       2048
#
# Note: max_tokens defaults to 1024. Reasoning-style models spend hidden
# tokens before visible output, so values under ~500 can return empty text.

set -euo pipefail

BASE="${1:?usage: call_local.sh <base-url> <model> <prompt> [max_tokens]}"
MODEL="${2:?missing <model>}"
PROMPT="${3:?missing <prompt>}"
MAX_TOKENS="${4:-1024}"

BODY=$(MODEL="$MODEL" PROMPT="$PROMPT" MAX_TOKENS="$MAX_TOKENS" python3 -c '
import json, os
print(json.dumps({
    "model": os.environ["MODEL"],
    "max_tokens": int(os.environ["MAX_TOKENS"]),
    "messages": [{"role": "user", "content": os.environ["PROMPT"]}],
}))
')

do_post() {
    # $1 = path, remaining args = extra curl headers
    local path="$1" code
    shift
    code=$(curl -sS -o "$RESP_FILE" -w '%{http_code}' -X POST "$BASE$path" \
        -H 'content-type: application/json' "$@" -d "$BODY") || code="000"
    echo "${code:-000}"
}

RESP_FILE=$(mktemp)
trap 'rm -f "$RESP_FILE"' EXIT

CODE=$(do_post /v1/messages -H 'anthropic-version: 2023-06-01')
if [ "$CODE" = "404" ]; then
    CODE=$(do_post /v1/chat/completions)
fi

if [ "$CODE" != "200" ]; then
    if [ "$CODE" = "000" ]; then
        echo "call_local.sh: no server reachable at $BASE" >&2
    else
        echo "call_local.sh: HTTP $CODE from $BASE" >&2
    fi
    cat "$RESP_FILE" >&2 || true
    exit 1
fi

python3 - "$RESP_FILE" <<'PY'
import json, sys

with open(sys.argv[1]) as f:
    d = json.load(f)

if "content" in d:  # Anthropic format
    print("".join(b.get("text", "") for b in d["content"] if b.get("type") == "text"))
    u = d.get("usage", {})
    print(f"[receipt] in={u.get('input_tokens')} out={u.get('output_tokens')}", file=sys.stderr)
else:  # OpenAI format
    print(d["choices"][0]["message"]["content"])
    u = d.get("usage", {})
    print(f"[receipt] in={u.get('prompt_tokens')} out={u.get('completion_tokens')}", file=sys.stderr)
PY
