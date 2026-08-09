# Cross-agent routing — Claude, Cowork, Codex, Antigravity

How the agent systems on one machine find each other and each other's models.
**Every claim here was verified by a live call on 2026-08-08; receipts noted.**

---

## 1. The fleets are different — that's the point

No single agent system reaches all these models. Routing across systems is how
you reach a model your own harness doesn't offer.

| System | CLI | Reaches |
|---|---|---|
| **Claude Code / Cowork** | `claude` | Claude tiers (Opus/Sonnet/Haiku) + any Anthropic-compatible endpoint |
| **Codex** | `codex` | 7 OpenAI models + **local models via `--oss`** |
| **Antigravity** | `agy` | **Gemini 3.6/3.5 Flash, Gemini 3.1 Pro, Claude Sonnet 4.6, Claude Opus 4.6, GPT-OSS 120B** |
| **Ollama / LM Studio** | HTTP | whatever is installed locally |

Antigravity is the only local route to **Gemini** and to **GPT-OSS 120B**, and
it's a second, separately-billed path to Claude models. If Claude quota is
tight, `agy --model claude-opus-4-6-thinking` is a different meter.

---

## 2. Antigravity (`agy`)

The CLI is **not on PATH**. It lives at:

```
C:\Users\scott\AppData\Local\agy\bin\agy.exe        (Windows)
```

A launcher also sits at `~/.gemini/antigravity-cli/bin/agentapi.bat`.

### Discovery — first-class, unlike Codex

```bash
agy models     # lists model IDs + display names
agy agents     # lists agents
```

**`agy models` is authoritative and free.** Codex has no equivalent — prefer
Antigravity's when you need to know what's available.

### Headless calls

```bash
agy -p "prompt" --model gemini-3.6-flash-low
```

*Verified: returned `ANTIGRAVITY-OK` in **4.5 s**, exit 0. Fastest backend on
this machine — faster than Codex (34 s) and faster than a cold local model.*

### Structured output — the best batch surface here

```bash
agy -p "Classify this record: ..." --model gemini-3.6-flash-low \
    --output-format json --json-schema schema.json
```

`--json-schema` **requires** `--output-format json` or `stream-json`, or it
errors out. The reply carries a parsed `structured_output` object plus a full
`usage` receipt:

```json
{"status":"SUCCESS","structured_output":{"language":"python","severity":"high"},
 "duration_seconds":2.1,
 "usage":{"input_tokens":27203,"output_tokens":360,"thinking_tokens":336,"total_tokens":27563}}
```

*Verified 2026-08-08: schema honored, 2.1 s.*

⚠️ **Note the 27,203 input tokens for a one-line prompt.** Antigravity injects
a large system prompt on every call. It's fast and structured, but not cheap
per item — for very large batches, weigh that against a local model.

### Other flags

`--effort low|medium|high` · `--mode accept-edits|plan` · `--output-format
text|json|stream-json` · `--add-dir` · `--continue` / `--conversation <id>` ·
`--sandbox` · `--print-timeout` (default 5m) · `--dangerously-skip-permissions`
(don't).

---

## 3. Codex driving local models — free, with one hard constraint

```bash
codex exec --oss --local-provider ollama -m gemma4:e4b -s read-only \
  --skip-git-repo-check --ephemeral "task"
```

*Verified: returned `CODEX-OSS-OK`, 9,479 tokens, 2 m 11 s, **zero API cost**.*

This gives you Codex's agent loop, tooling and sandboxing running on free local
weights. `--local-provider` accepts `ollama` or `lmstudio`.

**The constraint: the local model MUST support thinking.**

```
ERROR: "qwen2.5:7b" does not support thinking
```

`qwen2.5:7b` fails. `gemma4:e4b` works. Check capabilities before routing —
`GET /api/tags` on Ollama lists a `capabilities` array per model; look for
`thinking`.

**Two harmless warnings you can ignore:**
- `failed to refresh available models: missing field 'models'` — Codex expects
  `{"models":…}`; Ollama returns `{"data":…}`. Cosmetic.
- `Model metadata for <x> not found. Defaulting to fallback metadata` — expected
  for local models.

---

## 4. Claude Code against a local model — works in protocol, too slow in practice

**Don't route to this.** Documented so nobody re-derives it.

```bash
ANTHROPIC_BASE_URL=http://localhost:11434 \
ANTHROPIC_AUTH_TOKEN=local-dummy \
ANTHROPIC_MODEL=gemma4:e4b \
claude -p "..."
```

What testing established on 2026-08-08:

- **The protocol is fine.** Pointed at a logging mock, `claude -p` completed
  normally. It sends `POST /v1/messages?beta=true` with `system`, `metadata`,
  `thinking`, `context_management`, `output_config`, and `stream`.
- **Ollama accepts every one of those fields** — all returned HTTP 200 when
  tested individually.
- **But it never completes.** Two runs, `qwen2.5:7b` and `gemma4:e4b`, killed
  at 4 and 5 minutes with no output.
- **Cause: prompt-processing time.** A ~10k-token system prompt costs **41.8 s
  cold** on an 8B model (3.1 s warm, once prompt-cached). Claude Code's real
  system prompt with tool schemas is larger, and it makes 4+ calls per turn.

**Use `scripts/call_local.sh` instead** for local work — you control the prompt
size, so you don't pay a 40-second tax per call. Revisit this only with a much
faster local model or far smaller system prompt.

---

## 5. MCP is the interop bus

- **`codex mcp-server`** — Codex exposes *itself* as an MCP server over stdio.
  Any MCP client (Claude Code, Cowork, Antigravity) can drive Codex as a native
  tool instead of shelling out and scraping stdout.
- **`codex mcp`** — manages MCP servers Codex itself can reach.
- **Antigravity** reads `~/.gemini/config/mcp_config.json`. On this machine it
  is **empty** — the hook exists and is unused. Wiring `codex mcp-server` in
  there would let Antigravity drive Codex directly.

## 6. Skills are portable across harnesses

Antigravity keeps skills in `~/.gemini/config/skills/` — the same shape as
Claude's `~/.claude/skills/`. This machine already has `workflowwright` in
both.

**This skill can be installed into Antigravity the same way:**

```bash
git clone https://github.com/scottconverse/multi-model-routing-skill.git \
  ~/.gemini/config/skills/multi-model-routing
```

Antigravity also has its own plugins (`~/.gemini/config/plugins/`) — this
machine carries `chrome-devtools-plugin`, `data-agent-kit-plugin`, and
`modern-web-guidance-plugin`.

---

## 7. Picking a system

| Need | Go to | Why |
|---|---|---|
| Fastest structured batch item | **`agy` + `--json-schema`** | 2–4 s, schema-validated, receipts included |
| Free bulk work | **local via `call_local.sh`** | no quota at all |
| Free *agentic* work | **`codex --oss`** | agent loop on local weights — needs a thinking-capable model |
| Gemini, or GPT-OSS 120B | **`agy`** | only local route to them |
| Claude on a different meter | **`agy --model claude-opus-4-6-thinking`** | separate billing from your Claude quota |
| Serious code review | **`codex review -m gpt-5.6-sol`** | see [codex.md](./codex.md) |
