# multi-model-routing

**[Website](https://scottconverse.github.io/multi-model-routing-skill/) ·
[Manual](./docs/MANUAL.md) · [SKILL.md](./SKILL.md) ·
[Changelog](./CHANGELOG.md)**

A [Claude Code](https://claude.com/claude-code) / Claude Cowork skill that
routes batch and mechanical work across whatever model backends are actually
available on the machine — local LLMs (Ollama, LM Studio), the Codex CLI
(OpenAI models), and Claude itself — instead of defaulting everything to
premium Claude usage.

Grunt work (log triage, bulk tagging, format conversion, first-draft
docstrings, test-data generation, TODO sweeps — anything high-volume and
mechanically checkable) goes local-first, then Codex, then Claude's own
Haiku tier, with premium Claude reserved for architecture, security-sensitive
work, and final review. Local output never ships unreviewed. Full routing
rule, discovery protocol, and per-backend call instructions are in
[`SKILL.md`](./SKILL.md).

## Install

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

## What's in here

```
SKILL.md                    the skill itself — read this first
scripts/call_local.sh       calls a local Ollama/LM Studio server, with
                             Anthropic/OpenAI dialect fallback and a
                             stderr "receipt" line for evidence
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
```

## Requirements

`bash`, `curl`, `python3` (stdlib only, no pip installs) for the bundled
script. The skill itself works with whatever subset of Ollama / LM Studio /
Codex CLI / Claude is actually installed — nothing here requires all four.

## License

MIT — see [LICENSE](./LICENSE).
