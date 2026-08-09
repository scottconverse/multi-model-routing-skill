# Codex CLI — capabilities, model selection, and full surface

Read this before routing work to Codex. `SKILL.md` says *when* to use Codex;
this says *which model* and *which command*.

---

## 1. Pick the model by capability, not by quota

**Choosing a model is a capability decision you make, not an availability
question you escalate to the user.** These models have published, distinct
strengths — use them. Only ask the user if a call actually fails on quota.

| Task | Model | Why |
|---|---|---|
| **Bulk grunt work** — tagging, classifying, field extraction, ticket/log summaries, short routine drafts | `gpt-5.6-luna` | Purpose-built for high-volume, well-defined, rule-clear jobs. Cheapest and fastest. This is literally its design brief and it maps exactly onto what this skill calls grunt work. |
| **Bulk work needing images or a big context** | `gpt-5.4-mini` | 400k context, vision, strong agentic reliability, very cheap. Use over Luna when the batch involves images or long inputs. |
| **Fast interactive code edits** — targeted changes, refining logic or UI, contextual questions about a codebase | `gpt-5.3-codex-spark` | Real-time coding model, 1000+ tok/s. Built for near-instant iterate-while-you-watch loops. |
| **Serious code review, audits, long agentic runs** | `gpt-5.6-sol` | Flagship. Leads the Coding Agent Index; best long-horizon completion *and* the fewest tokens to get there. |
| **Balanced one-shot work**, not long-horizon | `gpt-5.6-terra` | GPT-5.5-level quality at roughly half the cost — but see the trap below. |
| Prior generation | `gpt-5.5`, `gpt-5.4` | No reason to prefer these over Terra/Sol unless reproducing older behavior. |

### Two traps worth knowing

**Terra is a false economy for long agentic runs.** It is cheaper per token,
but on long-horizon coding it passed 40.7% of tasks at ~55,600 output tokens
each, against Sol's 63.7% at ~21,000. That's ~2.7x the tokens for fewer
completions — Sol is *cheaper in total* and better. Cheaper-per-token is not
cheaper. Prefer Sol for anything agentic and multi-step.

**Luna's long-context recall collapses.** ~41% versus ~91% for Sol and ~90%
for Terra. Superb for high-volume well-defined items; do not point it at large
codebases, multi-document synthesis, or anything needing recall across a big
context. Keep Luna's inputs small and self-contained.

**Spark is a latency model, not a depth model.** Text-only, 128k context,
optimized for interactive iteration. It will complete a long unattended job,
but it is off-label for one — reach for Sol there.

### Pairing rule

When Codex both writes and reviews, use **different lineages**: let Spark or
Terra implement and `gpt-5.6-sol` review. A model reviewing its own output
shares its blind spots.

---

## 2. Model discovery — what's authoritative

**Task creation is the only authority.** A model either accepts a request or
returns a clean validation error. Everything else on disk is a cache that can
be stale or wrong.

| Source | Value | Trust |
|---|---|---|
| Actually running a task | definitive | **authoritative** |
| `codex doctor` | active model, auth mode, MCP count, install health | high — reflects live config |
| `~/.codex/config.toml` | the configured default (`model = …`) | high, but it's a *default*, not a capability list |
| `~/.codex/models_cache.json` | server-fetched list + etag | **low — known to go stale and to fail the CLI's own loader (`missing field 'base_instructions'`)**. Read it for candidate IDs, never as proof of availability. |

**Get the IDs exactly right.** A wrong ID returns
`400 invalid_request: model not supported with a ChatGPT account` — which
reads like "no access" but means "no such model." That exact mistake produced
a false "sol/terra/luna unavailable" conclusion here on 2026-08-08; the real
IDs are `gpt-5.6-*`, not `gpt-5.3-codex-*`, and all seven work fine.

A rejection costs **zero tokens** (rejected at validation). A success costs
real quota — roughly 10k+ even for a trivial prompt. So probing an ID you
believe is wrong is free; probing broadly is not.

---

## 3. Commands beyond `exec`

| Command | Use it for |
|---|---|
| `codex exec` | the general non-interactive workhorse |
| `codex review` | **purpose-built non-interactive code review** — prefer over hand-rolling a review prompt through `exec` |
| `codex mcp-server` | run Codex **as an MCP server over stdio** — the native integration path, instead of shelling out and scraping stdout |
| `codex mcp` | manage external MCP servers Codex itself can reach |
| `codex doctor` | diagnose install, config, auth, runtime — also the cheapest discovery probe |
| `codex plugin list` | what plugins are installed and enabled |
| `codex apply` | apply the agent's last diff as `git apply` |
| `codex resume --last` / `codex fork` | continue or branch a previous session |
| `codex sandbox` | run a command inside Codex's sandbox |

## 4. `codex exec` flags that matter here

| Flag | Why it matters |
|---|---|
| `-m, --model <MODEL>` | first-class model selection — prefer over `-c model=…` |
| `--output-schema <FILE>` | **JSON Schema for the final response.** For batch routing this is the difference between parseable results and regex-ing prose. ⚠️ **Redirect stdin (`< /dev/null`)** or `exec` blocks on `Reading additional input from stdin…` and never returns. Verified working with the redirect. |
| `-o, --output-last-message <FILE>` | write the final message to a file — clean capture, no stdout scraping |
| `--json` | streaming JSON events |
| `--oss --local-provider ollama\|lmstudio` | **run Codex's agent loop against a local model.** Codex's tooling and sandboxing, zero API cost. A whole routing tier in one flag. |
| `-i, --image <FILE>...` | vision input (Sol, Terra, Luna, 5.4, 5.4-mini — *not* Spark) |
| `-s, --sandbox <MODE>` | **keep `read-only` for questions and reviews.** Default is workspace-write with approval=never — it *will* edit files. |
| `-C, --cd <DIR>` / `--add-dir` | scope which directories are visible |
| `-p, --profile <NAME>` | layer `$CODEX_HOME/<name>.config.toml` over the base config |
| `--ephemeral` | don't persist the session |
| `--skip-git-repo-check` | needed outside a git repo |

### Canonical calls

```bash
# review — use the purpose-built command
codex review -m gpt-5.6-sol -s read-only "Audit for correctness and security"

# batch item with structured output -- note the stdin redirect, it is required
codex exec -m gpt-5.6-luna -s read-only --skip-git-repo-check \
  --output-schema schema.json -o out.json "Classify this record: ..." < /dev/null

# Codex's agent loop against a free local model
codex exec --oss --local-provider ollama -s read-only "..."
```

---

## 5. Codex Desktop plugins

`codex plugin list` shows what's enabled. A typical install carries
`computer-use`, `browser`, `chrome`, `github`, `documents`, `spreadsheets`,
`presentations`, `pdf`, `sites`, `visualize`, `template-creator`, plus any
personal marketplace plugins.

**Verified 2026-08-08: they DO reach `codex exec` runs**, not just the Desktop
app. A schema-constrained `codex exec` run reported 13 tools available
including document, spreadsheet, presentation and PDF authoring. (Tool count
is the model's own report of its toolset, but it matches `codex plugin list`.)
So `exec` is not a bare text endpoint — it carries the plugin surface with it.

---

## Sources

Model capability claims come from published benchmarks and OpenAI's own
documentation, not from this machine:
Artificial Analysis Coding Agent Index and Intelligence Index, Terminal-Bench
2.1, SWE-Bench Pro, BrowseComp, OSWorld 2.0, and OpenAI's model announcements.
Re-check them — this landscape moves monthly, and a stale capability claim is
worse than none.
