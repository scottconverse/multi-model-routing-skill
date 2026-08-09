# Grounding tier assignments in benchmarks

Which model belongs in which tier is a claim about capability. Claims in this
repo are backed by evidence, and a number someone typed into prose six months
ago is not evidence — it's a fossil.

**Reference of record: [Artificial Analysis](https://artificialanalysis.ai/).**
Consult it when assigning a model to a tier, when a tier assignment looks
wrong, or when a model you haven't seen before appears in a roster. Don't
re-derive rankings from a web search — that's how stale numbers get laundered
into confident prose.

---

## 1. The three indices, and which one to use

| Index | What it measures | Use it for |
|---|---|---|
| **Intelligence Index** | composite across ~9 evals | general capability, the default sort |
| **Coding Agent Index** | pass@1 across DeepSWE, Terminal-Bench, SWE-Atlas-QnA | code work — the one that matters most here |
| **Agentic Index** | tool use, planning, autonomy | anything running a multi-step loop |

A model that tops Intelligence is not automatically the right pick for an
agentic loop. Match the index to the job.

## 2. The official Data API — the path that actually works

**There is a free public API, and it returns exactly what routing needs.**

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

## Fallbacks if the API is unavailable

If there is no key, or the daily quota is spent, say so — do not substitute a
guess. Options, in order:

1. **Ask the owner.** He maintains a working comparison set and can read the
   numbers off the page in seconds.
2. **The OpenRouter MCP** (`list-benchmarks source=artificial-analysis`) carries
   the same indices second-hand, when its connector is authenticated.
3. **Aggregators** — `llm-stats.com`, `benchlm.ai`, Vellum's leaderboard. Several
   of these source from Artificial Analysis themselves, so treat them as the
   same claim relayed, not as independent confirmation.

What is NOT acceptable: scraping the site to work around the API, or reciting a
remembered ranking as though it were looked up. The page is
JavaScript-rendered, so a plain fetch returns methodology prose and no numbers —
if a number appears without a call behind it, it was invented.

## 5. Rules

- **Cite the index and the date** when a tier assignment rests on it. "Chosen
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
