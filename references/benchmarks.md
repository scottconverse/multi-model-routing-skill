# Grounding tier assignments in benchmarks

Which model belongs in which tier is a claim about capability. Claims in this
repo are backed by evidence, and a number someone typed into prose six months
ago is not evidence — it's a fossil.

**Reference of record: [Epoch AI's Benchmarking Hub](https://epoch.ai/benchmarks).**
A non-profit research institute, publishing under
**[CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/) — free to use,
distribute and reproduce with attribution.** No account, no API key, no
redistribution restriction. Consult it when assigning a model to a tier, when
an assignment looks wrong, or when an unfamiliar model appears in a roster.

Don't re-derive rankings from a web search — that's how stale numbers get
laundered into confident prose.

### Why this source and not a gated one

Benchmark scores are **published facts**. The labs and academic groups that ran
MMLU, GPQA, SWE-bench, Terminal-Bench and the rest published them; aggregators
collect them. A composite index built on top is the aggregator's own derived
work and theirs to license — but the underlying results are not proprietary,
and paying for access to facts someone else measured is a choice, not a
requirement.

Epoch AI publishes both the collected results **and** its own composite (the
Epoch Capabilities Index) under CC-BY. So numbers from here **may be quoted in
this repo** with the citation below. That is the practical difference: an
Artificial Analysis free-tier key forbids redistribution, so anything pulled
from it can never appear in shipped docs.

**Required attribution** (include it wherever these numbers appear):

> Epoch AI, 'AI Benchmarking Hub'. Published online at epoch.ai.
> Retrieved from https://epoch.ai/benchmarks

---

## 0. Get the data — one command, no key

```bash
curl -sSL -o benchmark_data.zip https://epoch.ai/data/benchmark_data.zip
unzip -o benchmark_data.zip
```

*Verified 2026-08-09 from this machine:* HTTP 200, ~452 KB, **75+ benchmark
CSVs**, updated that same day. A Python client also exists
(`pip install epochai`) if relationships between entities matter more than flat
files.

### The flags

Every flag `scripts/benchmarks.sh` accepts. `--help` prints the same list; a
test asserts these two stay in step, because `--limit` shipped documented in
neither for a release.

| Flag | Effect |
|---|---|
| `--measure NAME` | which benchmark to rank on (table below); default `capabilities` |
| `--model NAME` | only models whose name contains NAME, case-insensitive |
| `--open` | open-weights models only — **`capabilities` only**, see below |
| `--limit N` | how many rows to print, positive integer; default 25 |
| `--refresh` | force a refetch now, ignoring cache age |
| `--list` | which measures exist and which are cached, then exit |

Two environment variables: `BENCHMARKS_CACHE` (default
`~/.cache/multi-model-routing/benchmarks`) and `BENCHMARKS_MAX_AGE_DAYS`
(default 7 — how stale the cache may get before a run refetches). `--refresh`
is the manual override for the second; you rarely need it, since a run older
than the max age refetches on its own.

### The `--measure` values

`scripts/benchmarks.sh --list` prints these; they are named here so you can
reach for one without running it first.

| `--measure` | Backing file | `--open` supported? |
|---|---|---|
| `capabilities` *(default)* | `epoch_capabilities_index.csv` | **yes** |
| `coding` | `swe_bench_verified.csv` | no |
| `terminal` | `terminalbench_external.csv` | no |
| `aider` | `aider_polyglot_external.csv` | no |
| `agentic` | `os_world_external.csv` | no |
| `reasoning` | `gpqa_diamond.csv` | no |

⚠️ **`--open` only works with `capabilities`.** Only that file carries a
`Model accessibility` column; the per-benchmark files don't record open versus
closed. Asking for `--open` on the others is refused with an explanation rather
than an empty list — an empty list would read as "no open model scores here,"
which is false. To compare open and closed on a specific benchmark, filter by
name with `--model` against a model you already know the licence of.

### The files that matter for routing

| File | Use |
|---|---|
| `epoch_capabilities_index.csv` | **the headline composite (ECI)** — 815 model rows, the default comparison |
| `swe_bench_verified.csv`, `deepswe_external.csv`, `terminalbench_external.csv`, `aider_polyglot_external.csv` | coding |
| `os_world_external.csv`, `osworld_2_external.csv`, `the_agent_company_external.csv`, `apex_agents_external.csv` | agentic / tool use |
| `gpqa_diamond.csv`, `mmlu_external.csv`, `hle_external.csv`, `live_bench_external.csv` | general reasoning |

`epoch_capabilities_index.csv` carries **`Model accessibility`**, which marks
open weights versus API-only — the column that makes local-versus-cloud a
direct comparison rather than a guess.

### Measured 2026-08-09, one scale, cloud and local together

| Model | ECI | Access |
|---|---|---|
| `gpt-5.6-sol` | 161.65 | API |
| `claude-opus-5` | 161.02 | API |
| `gpt-5.6-terra` | 158.96 | API |
| `gpt-5.6-luna` | 156.13 | API |
| `claude-sonnet-5` | 155.53 | API |
| `gemini-3.6-flash` | 153.98 | API |
| **`deepseek-v4-flash`** | **152.53** | **open weights** |
| **`deepseek-v4-pro`** | **149.07** | **open weights** |
| `gpt-5.4-mini` | 148.91 | API |
| **`gemma-4-31b-it`** | **142.28** | **open weights** |
| **`gpt-oss-120b`** | **140.48** | **open weights** |

Two things fall out of that immediately, and neither was visible before:

- **`deepseek-v4-flash` (open weights, 152.53) outscores `gpt-5.4-mini`
  (148.91)** — a paid tier this skill routes to. On capability alone, a model
  you could run yourself beats one you're paying for.
- **`gpt-oss-120b` (140.48)** is reachable free through Antigravity
  (`cross-agent.md`), so a 120B open model is already one command away.

Neither is a routing instruction on its own — RAM, speed and the measured
results in `local-backends.md` still decide. But this is the comparison the
skill was missing.

### ⚠️ "Open weights" means downloadable, NOT runnable here

This is the trap in reading the `--open` list top-down. The highest-scoring
open model on that list is **`kimi-k3` (157.01)**, and its requirements are:

| | |
|---|---|
| Parameters | 2.8 trillion, sparse MoE (896 experts, 16 active) |
| Full weights | 1.56 TB |
| Quantized (MXFP4) download | ~594 GB |
| Minimum to serve | **8× H200 on one node**, or 8 nodes of 8× H100 at full precision |

Against 25.8 GB of RAM on this machine, that is not a close call. **Open
weights is a licence fact, not a hardware fact.** The two get conflated
constantly and the leaderboard does nothing to separate them.

**So there are three different questions, and only the first is about the
score:**

1. *Is it good?* — the benchmark data answers this.
2. *Can I run it?* — parameter count and quantized file size against free RAM.
   See the measured ceiling in `local-backends.md`: a 17.99 GB model failed to
   load with 17.5 GB free. The realistic local ceiling here is well under that.
3. *Can I reach it another way?* — a big open model is usually served by
   API providers (OpenRouter lists `moonshotai/kimi-k3`), and Antigravity
   already gives free access to `gpt-oss-120b`. That is still worth having —
   often cheaper than a proprietary tier at similar capability — but it is
   **not local and not private**, so the privacy half of the routing rule
   applies exactly as it does to Codex.

**Rule of thumb:** filter the `--open` list by what fits before treating it as
a shortlist. A frontier open model you cannot host is an API option with better
licensing, not a local one.

⚠️ **One discrepancy to verify before relying on it:** Epoch's
`Model accessibility` column marks `kimi-k3` as *"Open weights
(non-commercial)"*, while the release reporting describes Apache 2.0 weights on
Hugging Face. Those cannot both be right. Check the actual model card before
making a licensing decision on it — this is a good reminder that a metadata
column is a summary, not the licence.

---

## 1. Which measure for which job

| Job | Epoch AI file | Artificial Analysis equivalent |
|---|---|---|
| general capability, default sort | `epoch_capabilities_index.csv` (ECI) | Intelligence Index |
| code work | `swe_bench_verified.csv`, `deepswe_external.csv`, `terminalbench_external.csv` | Coding Agent Index |
| tool use, multi-step loops | `os_world_external.csv`, `the_agent_company_external.csv` | Agentic Index |

A model topping the general composite is not automatically right for an agentic
loop. Match the measure to the job — and prefer the raw benchmark to a
composite when the job is narrow, since a composite averages away exactly the
thing you care about.

## 2. Artificial Analysis — the gated alternative

Use Epoch AI first. Artificial Analysis is a reasonable cross-check when you
want a second opinion on a specific model, and its free API works — but its
terms make it the weaker default for this repo.

```bash
curl -H "x-api-key: $AA_API_KEY" \
  https://artificialanalysis.ai/api/v2/language/models/free
```

| | |
|---|---|
| Base URL | `https://artificialanalysis.ai/api/v2` |
| Auth | `x-api-key` header (no OAuth, no bearer exchange) |
| Free tier | **100 requests / 24h**, fixed window, shared per organization |
| Free tier returns | model identity, **headline indices**, median performance, input/output token pricing |
| Key fields | `artificial_analysis_intelligence_index`, `artificial_analysis_coding_index`, `artificial_analysis_agentic_index`, `intelligence_index_version` |
| Rate headers | `X-RateLimit-Remaining`, `X-RateLimit-Reset`, `Retry-After` on 429 |

*Verified 2026-08-09 from this machine:* the endpoint is live and reachable —
no key returns `{"error":"API key is required"}`, a bad key returns
`{"error":"Invalid API key."}`, both HTTP 401. **A key is the only blocker.**

**Getting a key** is an account signup on the Artificial Analysis Insights
Platform, then generate one from the API key page. That is the owner's to do —
an agent must not create accounts. Store it as `AA_API_KEY` in the environment,
never in this repo.

Docs: <https://artificialanalysis.ai/data-api/docs>

### ⚠️ Licence constraint — read before publishing any number

The free tier is **internal use only, no redistribution, and commercial use is
prohibited.** Attribution to Artificial Analysis is required on every tier.

For this repo that means a hard line:

- **Using the indices to decide routing is fine** — that is internal use.
- **Publishing a table of API-sourced scores into this public MIT repo is
  redistribution and is not permitted on the free tier.** Keep pulled numbers
  in `local-notes.md` (git-ignored) or in the session, not in shipped docs.
- Capability *claims* sourced from public articles and vendor posts are a
  different thing and may be cited with attribution — that is what
  `references/codex.md` does. Don't blur the two.
- Redistribution needs a Pro or Commercial tier. If that changes, revisit this.

### Ready-made integrations

Rather than hand-rolling a client:

- **`davidhariri/artificial-analysis-mcp`** — unofficial MCP server, MIT,
  actively maintained. Wiring it in means the indices become tool calls, the
  same shape as the Codex bridge in `cross-agent.md`.
- **`aneym/artificial-analysis-cli`** — Rust CLI, MIT, if a shell call suits
  better than an MCP server.

Both are third-party and unaudited; read before trusting, and remember the key
they consume is a production secret.

## 3. Query it, don't read it

Prefer a query over the web page: the page is JavaScript-rendered, so a plain
fetch returns methodology prose and no numbers.

**The OpenRouter MCP exposes the Artificial Analysis indices directly.** Two
tools, both server-side so you never post-process a full dump:

```
list-benchmarks   source=artificial-analysis  [task_type=coding|intelligence|agentic]
                  -> intelligence, coding and agentic index scores

list-models       sort=intelligence-high-to-low | coding-high-to-low | agentic-high-to-low
                  min_intelligence_index=  min_coding_index=  min_agentic_index=
                  min_tool_success_rate=   (0-1)
                  -> the same indices as filters, alongside price and context
```

⚠️ A plain `list-models` dump does **not** return the index columns. Use the
sorts, the `min_*_index` filters, or `get-model`.

⚠️ **Check the connector first.** `claude mcp list` should show the OpenRouter
MCP as `✔ Connected`; as of 2026-08-09 on this machine it reported
`! Needs authentication`, which makes every query above silently unavailable.
If it needs auth, say so and fall back to asking the user rather than guessing
at rankings.

## 4. Why this matters more here than in most skills

**Artificial Analysis scores open-weights models on the same indices as
proprietary ones.** That is the piece a routing skill actually needs: it puts
the models on this machine and the models behind an API on **one scale**.

The owner's working comparison set spans exactly that range — the Claude 5
family, the GPT-5.6 trio, Gemini 3.6 Flash, and open weights including
`gemma-4-31b`, `gemma-4-26b-a4b`, `qwen3-6-27b` and `deepseek-v4-pro`. Several
of those are installed locally (see `local-notes.md`), so "is the local model
good enough for this job, or does it need to go up a tier?" stops being a
judgment call and becomes a comparison.

Use it that way:

- **Before routing a job class to local**, check where the installed model sits
  on the relevant index against the cloud model you'd otherwise use. A small
  gap on Coding for mechanical work means local is free and fine.
- **When a local model disappoints**, check whether the index predicted it. If
  it did, escalate the tier rather than re-prompting.
- **When picking what to pull**, sort open weights by the index that matches
  the job and check it fits in RAM (`local-backends.md`).

## Fallbacks

If there is no key, or the daily quota is spent, say so — do not substitute a
guess. Options, in order:

1. **Epoch AI's ZIP** — no key, CC-BY, one curl. This should almost never fail.
2. **Ask the owner.** He maintains a working comparison set.
3. **The OpenRouter MCP** (`list-benchmarks source=artificial-analysis`), when
   its connector is authenticated.
4. **Aggregators** — `llm-stats.com`, `benchlm.ai`, Vellum's leaderboard. Several
   source from Artificial Analysis themselves, so treat them as the same claim
   relayed, not independent confirmation.

What is NOT acceptable: scraping the site to work around the API, or reciting a
remembered ranking as though it were looked up. The page is
JavaScript-rendered, so a plain fetch returns methodology prose and no numbers —
if a number appears without a call behind it, it was invented.

## 5. Rules

- **Cite the source, the index and the date** when a tier assignment rests on it. "Chosen
  on Coding Agent Index, checked 2026-08-09" ages honestly; "it's better at
  code" does not.
- **Re-check before trusting a stale assignment.** This field moves monthly.
  An assignment older than a month is a hypothesis.
- **Benchmarks rank, they don't decide.** A measured result on *this* machine
  beats a leaderboard every time — the local 7B that scored 12/12 on
  classification and ~1 of 10 on code review is the standing example. Use the
  index to choose what to try; use a receipt to decide what to keep.
- **Never invent a score.** If the connector is down and the page won't render,
  say the number is unavailable and ask. A fabricated index is worse than none,
  because it looks like evidence.
