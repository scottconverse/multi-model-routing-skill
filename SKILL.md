---
name: multi-model-routing
description: >-
  Use this skill any time a request repeats one operation across many items:
  summarizing all the logs or documents in a folder, reformatting every file
  in a directory, tagging or classifying hundreds of rows, reviews, or
  records, sweeping a codebase for TODOs, or generating dozens-to-hundreds of
  test records. Phrases like "every file", "all of them", a folder path, or a
  count ("30 logs", "200 reviews") are the signal -- this is the required way
  to execute batch work, not an optional optimization, so invoke it before
  reading any files or writing any code. Also use it whenever another model
  or agent system enters the picture: Ollama, LM Studio, OpenCode Zen,
  Antigravity, Codex/GPT, Gemini, or any non-Claude model -- reaching a model
  your own harness does not offer, offloading work to save Claude quota, or
  asking what model backends this machine has. Do not use for single-item
  analysis, architecture or design, security review, or prose writing.
---

# Multi-Model Routing

You have up to six model backends, on four separate meters. Use them
deliberately so the owner's Claude usage goes to work that actually needs
Claude:

1. **Ollama** (local) — free, private, no quota.
2. **LM Studio** (local) — free, private, no quota.
3. **OpenCode Zen** (cloud) — **free, no API key, no account.** 61 models
   advertised, 8+ of them free-tier. Costs nothing on any meter, which is why
   it sits above Codex.
4. **Codex CLI** — OpenAI models, billed to the owner's ChatGPT account.
   Also runs its agent loop on *local* models for free (`--oss`).
5. **Antigravity** (`agy`) — Gemini 3.6/3.5 Flash, Gemini 3.1 Pro, Claude
   Sonnet 4.6, Claude Opus 4.6, GPT-OSS 120B. A separate meter from Claude.
6. **Claude subagents** (Agent tool) — billed to the owner's Claude usage.

**No single system reaches every model.** Antigravity is the only local route
to Gemini and GPT-OSS, and a second, separately-billed path to Claude models.
Codex is the only route to the GPT-5.x fleet. Routing *across* systems is how
you reach a model your own harness doesn't offer — read
`references/cross-agent.md` before assuming a model is unavailable.

## Before anything else: read the local notes

Read `references/local-notes.md` in this skill folder. It holds
machine/account-specific facts (which Codex model has quota, where CLIs live)
that deliberately do NOT belong in this generic file. Every entry carries an
as-of date — treat anything more than a month old as a hypothesis to verify,
not a fact.

That file is git-ignored — it describes one machine, so it stays out of
version control. On a fresh clone it won't exist yet: copy
`references/local-notes.example.md` to `references/local-notes.md` and fill it
in as you learn things. If it's missing, say so and carry on; it is not a
blocker.

## Routing rule

Two axes, cost and privacy. **Cost is the one that decides most calls.**

- **Cost, cheapest meter first:**
  1. **Local** (Ollama, LM Studio) — free and private. Grunt work starts here.
  2. **OpenCode Zen** — free, no key. When no local model fits, this costs
     nothing, so it comes before anything metered. Its free tier includes
     models that outscore paid tiers further down this list.
  3. **Codex** — spends ChatGPT quota, roughly 10k+ tokens even for a trivial
     prompt. Real money; don't loop it carelessly.
  4. **Antigravity** — a separate meter again, and the only route to Gemini
     and GPT-OSS.
  5. **Claude Haiku** for bulk work that must stay on Claude; **premium
     Claude** (yourself, Opus-class subagents) reserved for core reasoning,
     architecture, security-sensitive work, and final review.

- **Privacy — state it honestly.** Only the local backends keep data on the
  machine. **Everything else is somebody's cloud, including Claude itself**:
  this conversation already goes to Anthropic, Codex goes to OpenAI,
  Antigravity to Google, Zen to OpenCode and its upstream provider. A rule
  phrased as "never send to a third-party cloud" would forbid the harness you
  are running in, so don't pretend to follow one.

  The real distinction is **account-bound versus anonymous**. Codex,
  Antigravity and Claude run under the owner's own accounts, with terms and a
  relationship attached. Zen's free tier is anonymous — no key, no account, no
  data-handling commitment tied to him, and no controllable quota.

  So: for genuinely sensitive material — secrets, credentials, private client
  code, anything he has said not to share — use **local models only**, and ask
  first if you are unsure. For ordinary work, all of these are already in play
  every day; pick on cost.

- **Open source first.** Where an open-weights model can do the job, prefer it
  — over a paid API model, and when choosing what to pull. This is the owner's
  standing preference and it is not only about cost: open weights keep data on
  the machine when run locally, cost nothing per call, and cannot be deprecated
  out from under you. It is also no longer a capability sacrifice — on the open
  data (`scripts/benchmarks.sh --open`), leading open-weights models score
  *above* several paid tiers this skill routes to. Check before assuming the
  paid option is better.

  ⚠️ **"Open weights" means downloadable, not runnable.** Before treating a
  high-scoring open model as a local option, check its size against free RAM.
  The top open model on that list is 2.8T parameters and needs 8× H200 — it is
  an API option with better licensing, not something this machine will host.
  Three separate questions: is it good (the data), can I run it (size vs RAM,
  see `references/local-backends.md`), and can I reach it another way (API
  providers, or Antigravity's free `gpt-oss-120b`). A big open model reached
  over an API is **not private** — the privacy rule applies to it exactly as it
  does to Codex.

Local model output is raw material: it never ships unreviewed. You (or a
Claude subagent) review before it counts.

**Tier assignments are claims about capability — ground them.** Run
`scripts/benchmarks.sh` rather than recalling a ranking. It pulls Epoch AI's
open benchmark data (CC-BY, no account, no API key), refetches itself when the
cache is over a week old, and marks open-weights versus API-only, so local and
cloud sit on one scale:

```bash
scripts/benchmarks.sh --open              # best open-weights models
scripts/benchmarks.sh --measure coding    # code work specifically
scripts/benchmarks.sh --model deepseek    # one family
```

A measured result on this machine still outranks a leaderboard — use the data
to pick what to *try*, and a receipt to decide what to *keep*. **Never invent a
score:** the data is one curl away, so a number without a call behind it has no
excuse. Details, other measures, and the attribution CC-BY requires are in
`references/benchmarks.md`.

## Discover lazily, prove before claiming

Do NOT run a discovery sweep just because this skill loaded. Probe a backend
the first time you're about to route real work at it, probe only the backends
you're considering, and cache the result for the rest of the session.

| Backend | Probe | Healthy looks like |
|---|---|---|
| Ollama | `GET http://localhost:11434/api/tags` | JSON list of models + `capabilities` |
| LM Studio | `GET http://localhost:1234/v1/models` | JSON list of models |
| OpenCode Zen | `GET https://opencode.ai/zen/v1/models` | JSON list, no key sent |
| Codex CLI | `codex doctor` | active model, auth mode, install health |
| Antigravity | `agy models` | model IDs + display names |
| Claude subagents | always available (Agent tool) | — |

`agy` is usually **not on PATH** — on Windows it's at
`%LOCALAPPDATA%\agy\bin\agy.exe`. Record the real path in local-notes.
`codex doctor` beats `--version` + `login status`: one call, and it reports the
configured model too.

A backend counts as **available** only after it has returned a one-word smoke
reply in this session (`scripts/call_local.sh <base-url> <model> "Reply with
exactly: OK" 512` for local backends). The probe and the smoke test are one
step, not two. Report the resulting roster to the user as a single line.

If a local server isn't responding but its CLI exists, you may start it
(`ollama serve` in the background; `lms server start` — check local-notes for
where `lms` lives). **Sandbox guard:** some sessions (e.g. a cloud-hosted
Cowork or Claude Code environment) run in a container where `localhost` is
not the user's actual machine. If you start a server and it reports an empty
model list but the user says they have models installed, you almost
certainly started a fresh instance inside a sandbox that isn't their real
machine — stop, tell the user, and do not pull models to "fix" it. If you're
unsure whether this session runs locally or in a cloud sandbox, say so rather
than assuming.

**A missing backend is a one-line ask, never a blocker.** Say what's missing
and how to enable it ("Codex CLI isn't installed — install the Codex app or
`npm i -g @openai/codex` and log in, and I'll use it next time"), then keep
working with whatever IS available.

## How to call each backend

### Local (Ollama / LM Studio) — use the bundled script

`scripts/call_local.sh <base-url> <model> <prompt> [max_tokens]` sends an
Anthropic-format request to `<base-url>/v1/messages` and automatically falls
back to OpenAI-format `/v1/chat/completions` if that 404s (older builds).
It prints the reply on stdout and a `[receipt]` token-usage line on stderr —
keep that receipt; it backs any claim that the backend did work.

**Read `references/local-backends.md`** for what these backends verifiably do:
tool support, vision, embeddings, prompt caching, and the RAM rules. Two things
worth knowing up front — **tool support is a property of the model, not the
server** (a coder-tuned model may have no tool training at all), and
**embeddings are nearly free** and excellent for deduping or clustering a batch
before you spend model calls on it.

- Ollama base URL: `http://localhost:11434`. List installed models:
  `GET /api/tags` or `ollama list`. Pull new: `ollama pull <model>` (see
  model choice rules below first).
- **The endpoint does not have to be this machine.** `call_local.sh` takes a
  base URL, so any Ollama-compatible endpoint works — a beefier box on the LAN
  can serve a model that won't fit in local RAM. Ask the user for the URL; do
  not scan the network for one. ⚠️ A remote endpoint is **not private**: the
  privacy guarantee comes from `localhost`, not from the word "local." Treat a
  non-localhost URL exactly like a third-party cloud backend and get an
  explicit OK before sending anything sensitive.
- LM Studio base URL: `http://localhost:1234`. Loaded models:
  `GET /v1/models`; everything downloaded: `lms ls`; load:
  `lms load <model-key> -c <context>`; download: `lms get <search>`.
- Reasoning-style local models spend hidden "thinking" tokens before visible
  output — a small `max_tokens` can return empty text. Always give at least a
  few hundred; the script defaults to 1024.
- **Concurrency: keep local calls to 1–2 at a time.** Local servers serialize
  or thrash under parallel load, especially when requests force model swaps.
- **Ask a small local model for constrained plain text, NOT JSON schema.**
  Measured on the same model and prompt: a one-word answer scored **12/12** on
  a real classification batch, while Ollama's native `format` schema got **1 of
  3 wrong**, and adding a free-text string field to the schema made it
  degenerate into a 600-token repeat loop. Schema-forcing costs accuracy at
  this size. Want structured output? Either parse the one-word replies
  yourself, or route to a tier that handles schemas well — `agy
  --json-schema` or `codex --output-schema`.

### OpenCode Zen — free cloud, same script

The bundled script reaches it too; it is an OpenAI-dialect endpoint, so state
the dialect rather than letting `auto` probe:

```bash
CALL_LOCAL_DIALECT=openai scripts/call_local.sh \
  https://opencode.ai/zen deepseek-v4-flash-free "your prompt" 1024
```

- **No API key and no account.** `GET /v1/models` lists 61 models; the ones
  ending `-free` cost nothing. *Verified 2026-08-09 from this machine:* a
  one-word reply in **9.1 s**, `[receipt] in=88 out=21`, no credentials sent.
- **State the dialect.** `auto` probes `/v1/messages` first and Zen serves that
  path only for paid Claude models, answering 401/400 for free ones — a 400 is
  usually a genuine bad request, so the fallback deliberately does not retry on
  it. `CALL_LOCAL_DIALECT=openai` skips the wrong guess entirely.
- **Use it when no local model fits and the work is not sensitive.** It is free,
  so it beats spending ChatGPT or Claude quota. On the open benchmark data
  `deepseek-v4-flash-free` scores **152.53**, above `gpt-5.4-mini` at 148.91 —
  a paid tier further down this ladder. Check with `scripts/benchmarks.sh`
  rather than trusting that number's freshness.
- **Anonymous means unaccountable.** No key means no terms tied to the owner
  and no controllable quota. Fine for ordinary work; for secrets, credentials
  or private client code, stay local.

### Codex CLI

```bash
codex exec -m <MODEL> -s read-only --skip-git-repo-check "task"
```

**Read `references/codex.md` before routing work here.** It holds the model
capability table, two cost traps that reverse the obvious choice, the
discovery rules, and the rest of the CLI surface.

- **Choosing the model is YOUR call, made on capability — not a quota question
  you put to the user.** These models have distinct, published strengths:
  bulk grunt work → `gpt-5.6-luna` (or `gpt-5.4-mini` when the batch has images
  or long inputs); fast interactive code edits → `gpt-5.3-codex-spark`; review,
  audits and long agentic runs → `gpt-5.6-sol`. Ask the user only if a call
  actually fails on quota.
- **Get the ID exactly right.** A wrong model ID returns `400 … not supported
  with a ChatGPT account`, which reads like "no access" but means "no such
  model." Don't generalize one rejection into "that tier is unavailable."
- **`codex review` is purpose-built for reviews** — prefer it over hand-rolling
  a review prompt through `exec`.
- **`--output-schema <FILE>`** gives schema-validated JSON instead of prose to
  parse. Use it for batch work.
- **`--oss --local-provider ollama|lmstudio`** runs Codex's own agent loop
  against a local model — Codex's tooling and sandboxing at zero API cost.
- **Keep `-s read-only` for questions and reviews.** The default is
  workspace-write with approval=never — it WILL edit files without asking.
- Multi-turn: `codex exec resume --last "follow-up"`.

### Antigravity (`agy`)

```bash
agy -p "task" --model gemini-3.6-flash-low
agy -p "task" --model <M> --output-format json --json-schema schema.json
```

**The best structured-batch surface on this machine** — verified 2.1 s for a
schema-validated classification, with a token receipt in the same JSON.
`--json-schema` requires `--output-format json`, or it errors.

- `agy models` lists what's available — free, first-class, no equivalent in
  Codex. Use it instead of guessing.
- Reaches models nothing else here does: **Gemini** and **GPT-OSS 120B**, plus
  Claude Sonnet/Opus 4.6 on a **separate meter from Claude quota**.
- ⚠️ It injects a large system prompt — ~27k input tokens even for a one-line
  request. Fast and structured, but not cheap per item; for very large batches
  weigh it against a local model.
- Details and flags: `references/cross-agent.md`.

### Agents driving agents (MCP)

`codex mcp-server` makes Codex an MCP server over stdio, so any MCP client —
Claude Code, Cowork, Antigravity — can call Codex as a native tool instead of
shelling out and scraping stdout. It exposes `codex` (run a session) and
`codex-reply` (continue a thread).

Register it in the client's MCP config with the **absolute path to the real
executable**, not a PATH shim — `.cmd` wrappers commonly fail to spawn under
stdio MCP. Recipe and a verified end-to-end run are in
`references/cross-agent.md`.

**A call through a bridge spends the *callee's* quota.** Routing Antigravity →
Codex bills Codex, not Antigravity. That's useful when one meter is tight —
but be deliberate, and say which meter you're spending.

### Claude subagents

Pass `model: "haiku" | "sonnet" | "opus"` on the Agent call; use whatever
models this session exposes. Mechanical bulk work that must stay on Claude
goes to Haiku. Cap every fan-out, track your agents, never fire-and-forget.

**Delegate WHAT, never HOW.** Give a subagent the outcome and let it choose the
route. Don't hand it the URL to fetch, the search query to run, or a numbered
procedure — that spends your tokens writing instructions the agent could
derive, and it caps the result at your guess rather than its investigation. A
brief should be self-contained and state the goal, the constraints, and what
"done" looks like. If you find yourself writing step 3, you're doing the work
twice.

**Consider routing the routing.** Deciding *where* work goes is classification,
and classification is exactly what small local models do well — a 7B scored
12/12 on the batch benchmark in `references/local-backends.md`. On a long
sweep, having a local model pre-sort items by "needs judgment / mechanical"
costs nothing and keeps premium tokens for the work itself rather than the
dispatch. Review its split before acting on it, same as any local output.

**You drive local models constantly — that's this whole skill.** Use
`scripts/call_local.sh`. It works, it's fast, and it produces receipts.

The one thing that does NOT work is *replacing your own inference backend* with
a local server — running Claude Code itself on local weights via
`ANTHROPIC_BASE_URL`, rather than calling out to them. That path is
protocol-compatible (local servers accept every field Claude Code sends) but
impractical: a large system prompt costs ~42 s of prompt processing per call on
a small model, and Claude Code makes several calls per turn. Two attempts never
finished in 5 minutes. Calling local models = yes. Being one = no. Full
findings in `references/cross-agent.md`.

## Choose the BEST local model, not just the loaded one

1. **Inventory first:** prefer an installed model that fits — zero download.
2. **If nothing installed fits** (vision, stronger coding, longer context):
   pick the best current open model for the job. **Check Artificial Analysis
   rather than reasoning from memory** — it scores open-weights models on the
   same indices as proprietary ones, so a local model and the cloud model you'd
   otherwise use are directly comparable. Query it via the OpenRouter MCP
   (`list-benchmarks source=artificial-analysis`, or `list-models` with
   `sort=coding-high-to-low` / `min_coding_index=`); the web page is
   JavaScript-rendered and a plain fetch returns no numbers. Method, caveats
   and rules in `references/benchmarks.md`.
3. **Respect the hardware:** check available RAM/VRAM before choosing a size.
   A model that barely fits will thrash; prefer a quantization with headroom.
4. **Confirm before big downloads:** a multi-GB pull writes to the user's
   disk — say what, from where, how big, and get an OK. Small pulls on an
   already-approved plan can proceed.
5. **Smoke-test after loading** before routing real work at it.

Rough fit guide (verify against current reality): general/summarization →
mid-size instruct model; code grunt work → a coder-tuned variant; vision → a
VL model; long-context sweeps → whatever holds the largest stable context on
this hardware.

## What counts as grunt work (route local-first)

Log/JSON triage, file summarization sweeps, test-data generation, format
conversion, classification/tagging, first-draft docstrings, commit-message
drafts, bulk renaming plans, extracting TODOs — anything high-volume,
low-stakes, and mechanically checkable.

**Never route to local models or Codex without review:** architecture
decisions, security-sensitive code, anything that ships unreviewed, final
audit verdicts, judgment calls the owner will rely on.

## Discipline

- **Escalate instead of looping.** If a backend's output fails your review
  twice on the same piece of work, escalate one tier (local → Codex or Haiku
  → premium Claude). Do not burn a third attempt at the same tier.
- **Receipts.** Any claim that a backend did work is backed by evidence of
  the actual call — reply text or the `[receipt]` usage line.
- **Report plain-English, TL;DR first.** What happened, then the roster.
- **Clean up only what you started.** Stop servers/processes you launched if
  the user won't need them; leave anything that was already running alone.
- **Missing pieces are one-line asks, not blockers.**
