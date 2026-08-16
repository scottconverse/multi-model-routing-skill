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
| **Selected local engine** | HTTP or native CLI | engine with the largest usable local model inventory |

Antigravity is the only route to **Gemini** and to **GPT-OSS 120B**, and
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

**All 11 models verified** with live calls on 2026-08-08 — every one exercised,
not read off `agy models`:

| Model | Round trip |
|---|---|
| `gemini-3.6-flash-low` / `-medium` / `-high` | 4–4.5 s |
| `gemini-3.5-flash-low` / `-medium` | 4 s |
| `gemini-3.5-flash-high` | 60 s (cold outlier; others were 4 s) |
| `gemini-3.1-pro-low` / `-high` | 7 s |
| `claude-sonnet-4-6` | 5 s |
| `claude-opus-4-6-thinking` | **8 s** |
| `gpt-oss-120b-medium` | 5 s |

Claude Opus 4.6 answering in 8 s **on a meter separate from Claude quota** is
the single most useful fact here when Claude usage is running tight.

The Gemini tiers are close enough in latency that the `-high`/`-medium`/`-low`
suffix should be chosen on reasoning depth, not speed — the exception was one
60 s cold start, so budget for a slow first call per model.

### Which model for which job

Run `agy models` first — this maps *tiers*, not exact IDs, because Google
renames and adds tiers over time the same way OpenAI does (see `codex.md`'s §1
for the identical caveat on that side). Apply this reasoning to whatever the
live list actually contains:

| Job | Tier | Why |
|---|---|---|
| Bulk grunt work, high volume | a Flash `-low`/`-medium` tier | Cheapest, fastest (~4 s here), and the tier Google positions for exactly this. |
| Work needing deeper reasoning, still routine | a Flash `-high` tier or Gemini Pro `-low` | One step up without paying Pro's full cost. |
| Genuinely hard reasoning, multi-step | Gemini Pro `-high` | The deepest tier Antigravity reaches on the Gemini side. |
| Claude-quality output, Claude quota tight | `claude-sonnet-4-6` or `claude-opus-4-6-thinking` | Same model family, **different meter** — the single most useful fact in this file when Claude usage is running tight. Opus-class in 8 s here. |
| Free, open-weights, no quota concern at all | `gpt-oss-120b-*` | Zero cost on any meter; the only free tier this backend reaches. |

This is a starting heuristic, not a locked mapping — it exists so a choice gets
made without re-deriving it from zero, not to replace judgment when a job's
shape is genuinely ambiguous.

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

## 3. Local tool-using agents — use the bundled harness

```bash
python scripts/local_agent.py --model <MODEL> --task "<TASK>" --cwd <DIR> \
  [--max-steps N] [--read-only] [--base-url URL] [--no-sdk]
```

This is the primary agent loop for local weights. The LM Studio SDK's
`LLM.act()` is the first lane; `--no-sdk` is a hand-rolled OpenAI
`/v1/chat/completions` tool loop that can target another compatible server via
`--base-url` or `LOCAL_AGENT_BASE_URL`. By default the tools are `read_file`,
`list_dir`, `grep`, `run_command` (unrestricted — real shell, chaining, and
redirection), and `write_file`; `--read-only` narrows to just the three read
tools. There is no command allowlist and no destructive-command block (removed
2026-08-16 by owner directive; the harness runs on the owner's own hardware
against trusted local models). Run untrusted work in a disposable `--cwd` copy
and set `LOCAL_AGENT_LOG=<file>` for a JSONL audit trail. `--max-steps` is the
hard loop budget.

Each step reports input/output tokens on stderr, followed by a total
`[receipt]`. Those per-step token receipts satisfy the skill's receipts rule.
Keep local concurrency to one loop per server unless that server has been
tested under parallel load.

### Why `codex --oss` is no longer the primary loop

Codex still exposes this route:

```bash
codex exec --oss --local-provider <ENGINE> -m <MODEL> -s read-only \
  --skip-git-repo-check --ephemeral "task"
```

It has worked with some version/model combinations, but it is
**known-fragile**. Verified 2026-08-15 against LM Studio and a Qwen model:
Codex's message layout placed a system message after the conversation began,
the model's Jinja chat template rejected it with `System message must be at
the beginning`, and the agent loop never ran. This is a compatibility trap,
not a task failure and not something repeated retries fix.

Other combinations can also reject a model that lacks a capability Codex
expects, for example:

```
ERROR: "qwen2.5:7b" does not support thinking
```

Treat `codex --oss` as an optional compatibility probe after Codex, server, or
chat-template changes. Use `local_agent.py` for real local tool-loop work.

**Two harmless warnings you can ignore:**
- `failed to refresh available models: missing field 'models'` — Codex expects
  `{"models":…}` while another compatible endpoint returns `{"data":…}`.
  Cosmetic.
- `Model metadata for <x> not found. Defaulting to fallback metadata` — expected
  for local models.

---

## 4. Claude *calling* local models works. Claude *running on* one doesn't.

Keep these apart — they get conflated constantly.

| | Works? |
|---|---|
| Claude **calls** a local model (`scripts/call_local.sh` one-shot or `scripts/local_agent.py` tool loop) | ✅ **Yes — this is the skill's core path.** Both lanes produce token receipts. |
| Claude Code **runs on** a local model (`ANTHROPIC_BASE_URL`) — replacing its own inference backend | ❌ No, in practice |

Everything below concerns only the second row. Documented so nobody re-derives
it — and so nobody reads it as "Claude can't use local models," which is false.

```bash
ANTHROPIC_BASE_URL=http://localhost:PORT \
ANTHROPIC_AUTH_TOKEN=local-dummy \
ANTHROPIC_MODEL=<MODEL> \
claude -p "..."
```

What testing established on 2026-08-08:

- **The protocol is fine.** Pointed at a logging mock, `claude -p` completed
  normally. It sends `POST /v1/messages?beta=true` with `system`, `metadata`,
  `thinking`, `context_management`, `output_config`, and `stream`.
- **The tested compatible local endpoint accepted every one of those fields** —
  all returned HTTP 200 when tested individually.
- **But it never completes.** Two runs, `qwen2.5:7b` and `gemma4:e4b`, killed
  at 4 and 5 minutes with no output.
- **Cause: prompt-processing time.** A ~10k-token system prompt costs **41.8 s
  cold** on an 8B model (3.1 s warm, once prompt-cached). Claude Code's real
  system prompt with tool schemas is larger, and it makes 4+ calls per turn.

**Use `scripts/call_local.sh` instead** for one-shot local work, or
`scripts/local_agent.py` when the task needs tools. You control the prompt and
loop budget in both cases. Revisit inference-backend replacement only with a
much faster local model or far smaller system prompt.

---

## 5. MCP is the interop bus — verified working

**`codex mcp-server`** makes Codex an MCP server over stdio, so any MCP client
(Claude Code, Cowork, Antigravity) can drive Codex as a native tool instead of
shelling out and scraping stdout.

*Verified by raw stdio handshake 2026-08-08:* protocol `2025-06-18`, serverInfo
`codex-mcp-server` v0.145.0, exposing two tools — **`codex`** (run a session)
and **`codex-reply`** (continue a thread by id).

### Wiring Antigravity → Codex

Antigravity reads `~/.gemini/config/mcp_config.json`, using the standard
`mcpServers` shape (same as its own plugins):

```json
{
  "mcpServers": {
    "codex": {
      "command": "<absolute path to codex.exe>",
      "args": ["mcp-server"],
      "env": {}
    }
  }
}
```

**Use the absolute path to the real executable, not the `codex` shim.** On
Windows the PATH entry is a `.cmd` wrapper, which stdio MCP clients frequently
fail to spawn. The real binary lives under
`…\npm\node_modules\@openai\codex\node_modules\@openai\codex-win32-x64\vendor\x86_64-pc-windows-msvc\bin\codex.exe`.

*Verified end-to-end 2026-08-08:* after writing that config, Antigravity
reported `codex` and `codex-reply` among its MCP tools, and a live run —
Antigravity → MCP → Codex → reply — returned in **17.9 s**. The bridge works;
it isn't theoretical.

Note that a tool call through the bridge spends **Codex** quota, not
Antigravity's. Routing through MCP changes which meter you're on — that's a
feature, but be deliberate about it.

### Wiring the reverse direction: Codex → another ecosystem's tools

`codex mcp` manages the servers Codex itself reaches:

```bash
codex mcp list                       # what Codex can already reach
codex mcp add <name> -- <command>    # stdio server
codex mcp add <name> --url <URL> --bearer-token-env-var <VAR>   # HTTP server
codex mcp get <name> / remove <name>
```

*Verified 2026-08-08:* adding Antigravity's Chrome DevTools MCP server to
Codex —

```bash
codex mcp add chrome-devtools -- npx -y chrome-devtools-mcp@latest
```

⚠️ Note the tension with the shim warning above: on Windows `npx` *is* a `.cmd`
wrapper. It worked here — Codex spawns it fine — but if a registration using
`npx` silently produces no tools, that's the first thing to replace with an
absolute path to `node` plus the package's entry script.

— made **20+ browser-automation tools** visible to Codex in a live run
(`click`, `type_text`, `fill`, `take_screenshot`, `list_network_requests`,
`list_console_messages`, `performance_stop_trace`, `new_page`, `emulate`, …),
confirmed in 21.8 s. A tool server built for one agent ecosystem is reusable by
another; MCP is the common denominator.

### Claude Code → Codex

```bash
claude mcp add codex --scope user -- "<absolute path to codex.exe>" mcp-server
```

*Verified 2026-08-08:* `claude mcp list` reports `codex … ✔ Connected`. This is
the most useful direction day to day — it lets a Claude session hand work to
Codex as a native tool rather than shelling out and parsing stdout.

**All three directions are proven on this machine:**

| Direction | Mechanism | Evidence |
|---|---|---|
| Claude Code → Codex | `claude mcp add` | `✔ Connected` |
| Antigravity → Codex | `~/.gemini/config/mcp_config.json` | live call returned in 17.9 s |
| Codex → Chrome DevTools | `codex mcp add` | 20+ tools listed in 21.8 s |

⚠️ **MCP registration is per-agent, not global.** Adding a server to Codex does
NOT make it appear in Antigravity or Claude Code. Each keeps its own config —
`~/.codex/config.toml`, `~/.gemini/config/mcp_config.json`, `~/.claude.json` —
and each must be wired separately. There is no shared registry.

What you do get is reuse of the server *itself*: the same MCP binary serves
every client, so the second and third registrations are a one-line command
rather than new work. Budget one registration per agent you actually route to,
and never assume a tool is present just because another agent has it — check
first, or the call fails at runtime.

## 6. Skills are portable across harnesses

All three harnesses use the same one-directory-per-skill shape, just in
different places:

| Harness | Skills directory |
|---|---|
| Claude Code / Cowork | `~/.claude/skills/` |
| Codex | `~/.codex/skills/` (its own bundled skills sit under `.system/`) |
| Antigravity | `~/.gemini/config/skills/` |

Codex additionally reads `agents/openai.yaml` inside a skill, for its display
name and whether it may self-invoke. A skill without one still loads there, but
carries no metadata and will not fire unless the user names it explicitly.

⚠️ **Never assume a skill is installed because it is installed somewhere.**
Each harness keeps its own copy and they drift — check the directory before
relying on it. This file used to assert that `workflowwright` was already
present in two harnesses "on this machine". It was in none of them, and the
claim shipped to every other machine as fact.

`install.py` handles all three:

```bash
python3 install.py                 # auto-detect and install everywhere found
python3 install.py --app codex     # or one at a time
```

Install it in every harness you use. Routing advice only helps in the session
that can read it — a skill that lives in one agent can't tell the others what
they're allowed to route where.

Antigravity also has its own plugins, separate from skills, in
`~/.gemini/config/plugins/`. Which plugins a machine carries — and whether that
directory exists at all — varies per install, so list it rather than assuming:
an earlier version of this file named three by hand, and none of them were
present on the next machine it was read on.

---

## 7. Picking a system

| Need | Go to | Why |
|---|---|---|
| Fastest structured batch item | **`agy` + `--json-schema`** | 2–4 s, schema-validated, receipts included |
| Free bulk work | **local via `call_local.sh`** | one-shot path, no quota at all |
| Free *agentic* work | **local via `local_agent.py`** | bounded tool loop with per-step receipts |
| Gemini, or GPT-OSS 120B | **`agy`** | only local route to them |
| Claude on a different meter | **`agy --model claude-opus-4-6-thinking`** | separate billing from your Claude quota |
| Serious code review | **`codex review -m gpt-5.6-sol`** | see [codex.md](./codex.md) |
