---
name: multi-model-routing
description: >-
  Use this skill any time a request means repeating one operation across many
  items, whatever the domain: summarizing all the logs or documents in a
  folder, converting or reformatting every file in a directory,
  tagging/classifying hundreds of rows, reviews, or records, sweeping a
  codebase to collect TODOs or comments, or generating dozens-to-hundreds of
  fake/test records. Phrases like "every file", "all of them", a folder path,
  or a count ("30 logs", "200 reviews", "500 records") are the signal — this
  is the required way to execute batch work, not an optional optimization, so
  invoke it before reading any files or writing any code. Also use it
  whenever another model enters the picture: getting a second opinion from
  Codex/GPT or any non-Claude model, using Ollama or LM Studio, offloading
  work to save Claude quota, or asking what model backends this machine has.
  Do not use for single-item analysis, architecture or design, security
  review, or prose writing.
---

# Multi-Model Routing

You have up to four model backends. Use them deliberately so the owner's
Claude usage goes to work that actually needs Claude:

1. **Ollama** (local) — free, private, no quota.
2. **LM Studio** (local) — free, private, no quota.
3. **Codex CLI** — OpenAI models, billed to the owner's ChatGPT account.
4. **Claude subagents** (Agent tool) — billed to the owner's Claude usage.

## Before anything else: read the local notes

Read `references/local-notes.md` in this skill folder. It holds
machine/account-specific facts (which Codex model has quota, where CLIs live)
that deliberately do NOT belong in this generic file. Every entry carries an
as-of date — treat anything more than a month old as a hypothesis to verify,
not a fact.

## Routing rule

Two axes, cost and privacy:

- **Cost:** grunt work goes to **local models first**. If no local backend
  fits, escalate to **Codex** — spending ChatGPT quota before Claude quota is
  the owner's stated preference, not a law of nature; a Codex run still costs
  them real quota (~10k+ tokens even for a trivial prompt), so don't loop it
  carelessly. Bulk work that must stay on Claude goes to **Haiku**. Reserve
  premium Claude (yourself, Opus-class subagents) for core reasoning,
  architecture, security-sensitive work, and final review.
- **Privacy:** local models keep everything on the machine. Codex ships the
  content to OpenAI. Do not send sensitive or private code/data to a
  third-party cloud backend without an explicit OK from the user — for that
  material it's local models or Claude.

Local model output is raw material: it never ships unreviewed. You (or a
Claude subagent) review before it counts.

## Discover lazily, prove before claiming

Do NOT run a discovery sweep just because this skill loaded. Probe a backend
the first time you're about to route real work at it, probe only the backends
you're considering, and cache the result for the rest of the session.

| Backend | Probe | Healthy looks like |
|---|---|---|
| Ollama | `GET http://localhost:11434/api/tags` | JSON list of models |
| LM Studio | `GET http://localhost:1234/v1/models` | JSON list of models |
| Codex CLI | `codex --version` then `codex login status` | version + "Logged in" |
| Claude subagents | always available (Agent tool) | — |

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

- Ollama base URL: `http://localhost:11434`. List installed models:
  `GET /api/tags` or `ollama list`. Pull new: `ollama pull <model>` (see
  model choice rules below first).
- LM Studio base URL: `http://localhost:1234`. Loaded models:
  `GET /v1/models`; everything downloaded: `lms ls`; load:
  `lms load <model-key> -c <context>`; download: `lms get <search>`.
- Reasoning-style local models spend hidden "thinking" tokens before visible
  output — a small `max_tokens` can return empty text. Always give at least a
  few hundred; the script defaults to 1024.
- **Concurrency: keep local calls to 1–2 at a time.** Local servers serialize
  or thrash under parallel load, especially when requests force model swaps.

### Codex CLI

```bash
codex exec --skip-git-repo-check -c model="<MODEL>" -c sandbox_mode="read-only" "task"
```

- **Pick the model by quota, not habit.** Check local-notes for the current
  quota situation; if the note is stale or absent, ask the user which OpenAI
  model has quota. Pass it explicitly with `-c model=...` every time.
- **Keep `sandbox_mode="read-only"` for questions and reviews.** Codex's
  default is workspace-write with approval=never — it WILL edit files without
  asking if you drop the flag. Drop it only when you intend Codex to edit.
- Multi-turn: `codex exec resume --last "follow-up"`.

### Claude subagents

Pass `model: "haiku" | "sonnet" | "opus"` on the Agent call; use whatever
models this session exposes. Mechanical bulk work that must stay on Claude
goes to Haiku. Cap every fan-out, track your agents, never fire-and-forget.

## Choose the BEST local model, not just the loaded one

1. **Inventory first:** prefer an installed model that fits — zero download.
2. **If nothing installed fits** (vision, stronger coding, longer context):
   pick the best current open model for the job. If you don't confidently
   know what's current, research it on the web — the local-model landscape
   moves monthly; don't trust stale training knowledge.
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
