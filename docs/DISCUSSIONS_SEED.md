# Discussions seed

Starter topics for GitHub Discussions on this repo. Each is a real open
question from building it, not a marketing prompt.

---

## 1. Where exactly does a local model stop being useful?

Measured on one machine, one 7B-class model, one day:

| Task | Result |
|---|---|
| Classify 12 log files (known answers) | **12/12 correct**, 27 s, $0 |
| Adversarial code review of a bash script | **~1 of 10 findings real** |

Same model. The gap is enormous and it's the whole basis of the routing rule.
But "mechanical vs. judgment" is a fuzzy line. Where does *your* local model
fall over? Summarization? Extraction with ambiguity? Multi-step reasoning over
a small context?

## 2. Why does JSON schema make small models worse?

Constrained plain text scored 12/12. Ollama's native `format` schema on the
same model and prompt got 1 of 3 wrong, and adding a free-text `string` field
sent it into a 600-token repeat loop.

Is this a llama.cpp grammar-constraint artifact, a model-size effect, or a
prompt-shape problem? Does it reproduce on your hardware and models? If it's
general, "don't schema-force small models" belongs in a lot more skills than
this one.

## 3. Is running an agent harness on local weights ever practical?

Pointing Claude Code at a local server via `ANTHROPIC_BASE_URL` is
protocol-compatible — the local servers accept every field it sends — but it
never completed here. A ~10k-token system prompt costs **41.8 s cold** on an 8B
model (3.1 s warm, prompt-cached), and the harness makes several calls per
turn.

What's the actual threshold? A 30B on a GPU with a warm prompt cache? Or is a
full agent harness structurally the wrong shape for local inference, and
one-shot calls the right pattern?

## 4. Per-agent MCP config is friction — should it be?

Codex, Antigravity and Claude Code each keep their own MCP registry
(`~/.codex/config.toml`, `~/.gemini/config/mcp_config.json`, `~/.claude.json`).
Adding a server to one does nothing for the others. Three agents, three
registrations, three chances to drift.

Should there be a shared registry, or is per-agent isolation the correct
security posture? What do people do today — a script that writes all three?

## 5. What belongs in a skill vs. a reference file?

`SKILL.md` loads into context every time the skill triggers, so length there is
a tax on every session. Depth lives in `references/*.md`, loaded on demand.

That split is a guess. Where do you draw the line? Has anyone measured whether
agents reliably *follow* a pointer to a reference file, or do they mostly work
from whatever's already in context?

## 6. Which model for which job, and how would we know?

This repo routes bulk work to `gpt-5.6-luna`, interactive edits to
`gpt-5.3-codex-spark`, and reviews to `gpt-5.6-sol`, largely from published
benchmarks plus a little local testing. Two findings reversed the obvious
choice: Terra burns ~2.7x Sol's output tokens on long agentic runs for *fewer*
completions, and Luna's long-context recall collapses to ~41%.

What's a cheap, repeatable way to validate routing choices per machine, rather
than trusting a leaderboard from three months ago?
