# multi-model-routing

**[Website](https://scottconverse.github.io/multi-model-routing-skill/) ·
[Manual](./docs/MANUAL.md) · [SKILL.md](./SKILL.md) ·
[Changelog](./CHANGELOG.md)**

A [Claude Code](https://claude.com/claude-code) / Claude Cowork / Antigravity
skill that routes batch and mechanical work across whatever model backends are
actually available on the machine — local LLMs (Ollama, LM Studio), the Codex
CLI (OpenAI models), Antigravity (`agy`: Gemini, GPT-OSS 120B, Claude 4.6), and
Claude itself — instead of defaulting everything to premium Claude usage.

Grunt work (log triage, bulk tagging, format conversion, first-draft
docstrings, test-data generation, TODO sweeps — anything high-volume and
mechanically checkable) goes local-first, then Codex, then Claude's own
Haiku tier, with premium Claude reserved for architecture, security-sensitive
work, and final review. Local output never ships unreviewed. Full routing
rule, discovery protocol, and per-backend call instructions are in
[`SKILL.md`](./SKILL.md).

## Why the "never unreviewed" rule is load-bearing

Same 7B local model, same machine, same day:

| Job | Result | Cost | Time |
|---|---|---|---|
| Classify 12 log files (known answers) | **12/12 correct** | $0 | 27 s |
| Adversarial review of a bash script | **~1 of 10 findings real** | $0 | 72 s |

Exact on mechanical work, inventive on judgment. That gap is the whole reason
the ladder exists — a small local model isn't "worse AI" you tolerate to save
money, it's a tool with one sharp edge and one blunt one.

## Agents can drive each other

MCP is the common bus, and all three directions are verified on real hardware:
Claude Code → Codex, Antigravity → Codex, and Codex → Chrome DevTools. So a
Claude session can hand work to Codex as a native tool rather than shelling
out. **Registration is per-agent, not global** — each harness keeps its own
config. See [`references/cross-agent.md`](./references/cross-agent.md).

## Install

**Easiest — the installer.** It auto-detects Claude Code and Antigravity,
installs into each, and creates your notes file from the template without ever
overwriting an existing one:

```bash
git clone https://github.com/scottconverse/multi-model-routing-skill.git
cd multi-model-routing-skill
python3 install.py            # --list to preview, --app claude|antigravity,
                              # --project DIR for a single project
```

### Or install by hand

Skills are auto-discovered from two locations:

- **Personal, all projects on this machine:** clone directly into
  `~/.claude/skills/multi-model-routing` (the folder name must match
  `multi-model-routing` — that's what `SKILL.md`'s `name:` field expects,
  independent of what this repo happens to be called on GitHub).

  ```bash
  git clone https://github.com/scottconverse/multi-model-routing-skill.git \
    ~/.claude/skills/multi-model-routing
  ```

- **One project only:** clone into that project's `.claude/skills/multi-model-routing`
  instead. Most people want the personal install above — it's what makes the
  skill "general," applying across every project you touch on that machine.

Then create your machine's notes file, which the skill reads on startup:

```bash
cp references/local-notes.example.md references/local-notes.md
```

That copy is git-ignored on purpose. It records your hardware, install paths
and quota state — facts about one machine that have no business in version
control — so `git status` stays clean and no stray commit can publish them.

To use it on a second machine, repeat the clone and the copy there. There's no
sync mechanism beyond git — `git pull` inside the installed folder picks up
updates, and your `local-notes.md` is untouched by it.

## Uninstall

```bash
python3 install.py --uninstall          # add --list to preview
```

Your `local-notes.md` is preserved beside where the skill was, and the path is
printed — those are your measured machine facts, not disposable. Repeat
uninstalls get numbered backups; an existing one is never overwritten.

**It refuses to delete a git checkout.** If you installed by cloning, the
install *is* your working copy, and removing it would take your repository
history with it. Uninstall stops and says so. It also refuses any directory
without a `SKILL.md`, so a mistyped `--project` can't destroy something else.

Every install ships its own `install.py`, so you can uninstall from the install
itself. Any MCP servers you registered live in the agent's own config and are
unaffected.

## Model choice is looked up, not guessed

```bash
scripts/benchmarks.sh --open        # best open-weights models
scripts/benchmarks.sh --measure coding
scripts/benchmarks.sh --model deepseek --limit 10
```

`--help` lists every flag; `references/benchmarks.md` has the full table.

Rankings come from [Epoch AI's Benchmarking Hub](https://epoch.ai/benchmarks) —
a non-profit publishing under **CC-BY 4.0**, no account and no API key. The
script caches and **refetches when the data is over a week old**, so the skill
never carries rankings that rot.

It scores open-weights models on the same scale as proprietary ones, which is
the comparison a routing skill needs. ⚠️ But **open weights means downloadable,
not runnable** — the top open model is 2.8T parameters and needs 8× H200. Check
size against free RAM before treating a high score as a local option.

## Large prompts

`scripts/call_local.sh` takes the prompt three ways — a literal argument, `-`
for stdin, or `file:PATH`:

```bash
cat big.log | scripts/call_local.sh http://localhost:11434 qwen2.5:7b - 2048
```

`CALL_LOCAL_DIALECT=auto|anthropic|openai` picks the API dialect. `auto` probes
Anthropic then falls back — right for a local server, wrong for a gateway where
the dialect depends on the model, so state it when you know.

Use `-` or `file:` for real inputs. A literal prompt must fit in the OS
argument limit, and a batch input won't: it fails loudly (`Argument list too
long`, or `The command line is too long.` through a `.cmd` shim) rather than
truncating. The sigil is `file:` and not `@` because Git Bash on Windows
expands a leading `@` as a response file, silently splitting the file's
contents into separate arguments.

## "Local" doesn't have to mean this machine

`scripts/call_local.sh` takes a base URL and has no localhost assumption, so
any Ollama-compatible endpoint works — including a beefier box on the LAN
serving a model that won't fit in your RAM. The serving host needs
`OLLAMA_HOST=0.0.0.0` (Ollama binds `127.0.0.1` by default).

⚠️ A remote endpoint is **not private**. The privacy property comes from
`localhost`, not from the word "local" — treat any non-localhost URL like a
third-party cloud backend.

## What's in here

```
SKILL.md                    the skill itself — read this first
scripts/call_local.sh       calls a local Ollama/LM Studio server, with
                             Anthropic/OpenAI dialect fallback and a
                             stderr "receipt" line for evidence
references/codex.md         Codex: model selection BY CAPABILITY (not by
                             asking the user), the full CLI surface, and two
                             cost traps that reverse the obvious choice
references/cross-agent.md   how Claude Code, Codex and Antigravity find each
                             other and each other's models; the MCP bridges,
                             all verified end to end
references/benchmarks.md   grounding tier assignments in Artificial Analysis
                             indices, and how to QUERY them rather than
                             recall them
references/local-backends.md  what Ollama and LM Studio verifiably do — tools,
                             vision, embeddings, prompt caching, RAM limits
references/local-notes.example.md
                            template for machine/account-specific facts
                             (quota, CLI paths), kept OUT of SKILL.md so the
                             skill stays portable. Copy it to
                             references/local-notes.md and edit that copy —
                             which is git-ignored and never committed
tests/test_call_local.py    offline smoke test for call_local.sh (spins up
                             mock HTTP servers, no real Ollama/LM Studio
                             needed) — run with `python3 tests/test_call_local.py`
docs/MANUAL.md              the user manual — install, routing rule, every
                             backend, troubleshooting, honest limits, FAQ
docs/index.html             the landing page, published via GitHub Pages
CHANGELOG.md                what changed, and why
install.py                  installs the skill into Claude Code and/or
                             Antigravity; --list for a dry run
CONTRIBUTING.md             the evidence rule: claims are backed by a run
docs/DISCUSSIONS_SEED.md    six open questions from building this
.github/workflows/test.yml  CI: the suite on Ubuntu AND Windows, shellcheck,
                             LF/exec-bit checks, and a guard that the private
                             notes file is never committed
```

## Requirements

`bash`, `curl`, `python3` (stdlib only, no pip installs) for the bundled
script. The skill itself works with whatever subset of Ollama / LM Studio /
Codex CLI / Claude is actually installed — nothing here requires all four.

## License

MIT — see [LICENSE](./LICENSE).
