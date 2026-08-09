# Changelog

All notable changes to multi-model-routing are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); versioning is
[SemVer](https://semver.org/).

## [0.3.1] — 2026-08-09

Three ideas adopted after reading [Warden](https://github.com/domdoss/Warden),
a local-first personal assistant with a hybrid routing architecture. Ideas
only — that repo currently ships **no LICENSE file** despite its README naming
MIT, so no code was taken.

### Added
- **"Local" means the endpoint, not the machine.** `call_local.sh` takes a base
  URL and has no localhost assumption, so any Ollama-compatible endpoint works
  — including one on another box, which is the escape hatch for models that
  don't fit in local RAM. **Verified** against a non-localhost address.
  **Not** verified end-to-end: Ollama binds `127.0.0.1` by default and the
  serving host needs `OLLAMA_HOST=0.0.0.0`, so it's one config change on that
  box, not zero. The privacy warning is sharpened to match — the guarantee
  comes from `localhost`, not from the word "local," and a remote endpoint is a
  third-party backend for consent purposes.
- **"Delegate WHAT, never HOW."** Give a subagent the outcome and let it pick
  the route; prescribing URLs, queries or numbered steps spends tokens writing
  instructions the agent could derive and caps the result at your guess.
- **Consider routing the routing.** Deciding where work goes *is*
  classification, which is what small local models measurably do well (7B
  scored 12/12 on the batch benchmark). On a long sweep, a local model can
  pre-sort items by "needs judgment / mechanical" for free, keeping premium
  tokens for the work rather than the dispatch. Warden's core bet is a 12B
  orchestrating frontier models; our own measurement supports it.
- **`install.py --uninstall`.** Removal was previously a bare `rm -rf` in one
  section of the manual, with no tooling and no mention in the README or on the
  landing page. The uninstaller **preserves your `local-notes.md`** to
  `multi-model-routing.local-notes.backup.md` beside the install and prints the
  path — those are measured machine facts, not disposable — and it refuses to
  delete any directory without a `SKILL.md` in it, so a mistyped `--project`
  can't take out something unrelated. Works with `--list`, `--app` and
  `--project`. Removal is now documented in all three human-facing docs,
  including the point that MCP registrations live in the agent's own config and
  survive uninstalling this skill.

### Verified for this release
Full lifecycle exercised end to end in a clean directory: install → suite 7/7
from the installed copy → live calls against both Ollama (`in=40 out=8`) and
LM Studio (`in=37 out=5`) → `--uninstall --list` dry run left everything in
place → real uninstall removed the tree and preserved a hand-edited
`local-notes.md` with the edit intact.

## [0.3.0] — 2026-08-09

Proof release. The routing advice was sound but the skill had never been
watched doing its own job, and several commands it recommended had never been
run. Both fixed, and running them found real defects in the advice itself.

### Added
- **End-to-end proof the skill works.** A real batch — 12 log files classified
  as auth failure / other error / clean, with a known correct answer for each —
  routed local-first through `call_local.sh`, one call at a time:
  **12/12 correct, 27 s, $0, 12 receipts.**
  Set against the earlier audit result (same model class, ~1 of 10 findings
  real), this measures both halves of the routing rule instead of asserting
  them: a small local model is exact on mechanical work and inventive on
  judgment calls. That gap is the entire argument for the ladder, and it is now
  on the landing page and in the manual.
- **Claude Code → Codex over MCP**, so a Claude session can hand work to Codex
  as a native tool: `claude mcp add codex --scope user -- <abs path> mcp-server`.
  Verified `✔ Connected`. All three bridge directions now proven.
- The skill installed into Antigravity's own skills directory. Routing advice
  only helps the session that can read it.

### Fixed
- **`--output-schema` blocks forever without a stdin redirect.** The docs
  recommended it without mentioning that `codex exec` stops at
  `Reading additional input from stdin…` when run non-interactively. Every
  example now carries `< /dev/null`. Verified working with it.
- **Resolved the "Unverified" note left in `references/codex.md`.** Codex
  Desktop plugins *do* reach `codex exec` runs — a schema-constrained run
  reported 13 tools including document, spreadsheet, presentation and PDF
  authoring. `exec` is not a bare text endpoint.

### Fixed — defects found by finally running `codex review`
- **A false claim was on the landing page.** "A tool server registered once is
  reachable from whichever agent you route to" is wrong. MCP registration is
  **per-agent**: `~/.codex/config.toml`, `~/.gemini/config/mcp_config.json` and
  `~/.claude.json` are separate registries, and adding a server to one does
  nothing for the others. Corrected in four places.
- **The canonical `codex review` call in the docs did not work.** `review`
  rejects `-m` outright, has no `-s/--sandbox`, and its free-text prompt is
  mutually exclusive with `--commit`. It reviews a **diff**, not arbitrary
  files — for a single file, `codex exec` is the right tool. All three traps
  documented.
- The Chrome DevTools example uses `npx`, which on Windows is the same class of
  `.cmd` shim that section warns about. It works, but the tension is now called
  out with the fix if a registration ever silently yields no tools.

### Added — repo conventions
- **`install.py`** — installs into Claude Code and/or Antigravity, auto-detects
  both, `--list` for a dry run, `--project` for a single project, and refuses
  to overwrite an existing `local-notes.md`.
- **CI** (`.github/workflows/test.yml`) — the suite on **Ubuntu and Windows**
  (every defect this repo has shipped was Windows-specific), plus shellcheck,
  an executable-bit check, a CRLF check, a guard that `local-notes.md` is never
  tracked, a check that every referenced `references/*.md` exists, and both a
  dry-run and a real-install test for `install.py`.
- **`CONTRIBUTING.md`** — the evidence rule, argued from the four defects this
  repo shipped by breaking it.
- **`docs/DISCUSSIONS_SEED.md`** — six open questions from building this.

### Verified while closing out
- `qwen2.5-coder-14b-instruct` (8.99 GB) works — 25.9 s including load.
- **`google/gemma-4-26b-a4b` (17.99 GB) does not load at 17.5 GB free.** It
  thrashed and hit the 300 s timeout having received zero bytes. Half a
  gigabyte short cost six minutes — a model that "almost fits" does not fit.
  This is also the v0.1.0 timeout fix earning its place in real use.
- `agy agents` returns an empty list with exit 0 — no agents configured, not an
  error.

### Changed
- **New rule: ask small local models for constrained plain text, not JSON
  schema.** Measured on one model and prompt — a one-word answer scored 12/12
  on the classification batch, while Ollama's native `format` schema got 1 of 3
  wrong, and adding a free-text string field made it degenerate into a
  600-token repeat loop. Schema-forcing costs accuracy at that size. For
  structured output, route to `agy --json-schema` or `codex --output-schema`.
- The manual and landing page now document the MCP bridges. They previously
  contained zero mentions of MCP — every bridge lived only in `references/`,
  so no human-facing page described the feature at all.
- **All four documents brought into sync for the release.** An audit found the
  README never mentioned MCP, `agy`, or any of the three reference files, and
  neither the manual nor the landing page mentioned `install.py` at all. The
  README now leads with the measured 12/12-vs-1-of-10 result, and every
  document lists the same install paths and the same file inventory.

## [0.2.0] — 2026-08-08

Cross-agent release. The skill knew about four backends and one way to call
each. It now covers five backends on three separate meters, picks models by
capability instead of asking the user, and documents the routes between agent
systems. **Every path below was verified by a live call before shipping.**

### Added
- **Antigravity (`agy`) as a first-class backend.** Reaches Gemini 3.6/3.5
  Flash, Gemini 3.1 Pro, Claude Sonnet 4.6, Claude Opus 4.6 and GPT-OSS 120B —
  the only local route to Gemini and GPT-OSS, and a second path to Claude
  models on a meter separate from Claude quota. Verified: headless reply in
  4.5 s; schema-validated `structured_output` with a token receipt in 2.1 s.
  Caveat recorded: it injects ~27k input tokens per call.
- **`references/codex.md`** — model selection by capability, the full CLI
  surface (`review`, `mcp-server`, `mcp`, `doctor`, `plugin`, `apply`, `fork`,
  `sandbox`), and the flags that matter (`--output-schema`, `-o`, `--json`,
  `--oss`, `-i`, `-s`, `-p`).
- **`references/cross-agent.md`** — how the agent systems find each other and
  each other's models, including MCP as the interop bus (`codex mcp-server`
  exposes Codex to any MCP client) and the fact that skills are portable
  between `~/.claude/skills/` and `~/.gemini/config/skills/`.
- **`codex exec --oss --local-provider ollama|lmstudio`** documented — Codex's
  agent loop on free local weights. Verified at zero API cost. **Hard
  constraint found by testing: the local model must support thinking**
  (`qwen2.5:7b` fails, `gemma4:e4b` works).
- `agy models` and `codex doctor` added to the discovery table as the real
  probes.
- **Agents driving agents over MCP, verified end to end.** `codex mcp-server`
  exposes Codex as an MCP server (protocol `2025-06-18`, tools `codex` and
  `codex-reply`), confirmed by a raw stdio handshake. Wiring it into a client's
  MCP config lets that client call Codex natively; a live Antigravity → MCP →
  Codex → reply run completed in 17.9 s. Documented with the gotcha that cost
  the time: register the **absolute path to the real executable**, never the
  PATH shim, because `.cmd` wrappers fail to spawn under stdio MCP.
- Recorded that a call through a bridge spends the **callee's** quota —
  Antigravity → Codex bills Codex. Useful when one meter is tight, but it
  should be a deliberate choice, and the skill now says to name the meter.
- **All 11 Antigravity models exercised with live calls**, not taken from a
  list: the three `gemini-3.6-flash` tiers and two of the `3.5` tiers at ~4 s,
  `gemini-3.5-flash-high` at 60 s (a cold outlier worth budgeting for), both
  `gemini-3.1-pro` tiers at 7 s, `claude-sonnet-4-6` 5 s,
  `claude-opus-4-6-thinking` 8 s, `gpt-oss-120b-medium` 5 s.
- **The reverse bridge, also verified: `codex mcp add`.** Registering Chrome
  DevTools MCP with Codex exposed 20+ browser-automation tools to it in a live
  run. A tool server built for one agent ecosystem is reusable by another, so
  choosing a backend on cost or capability doesn't cost you your tooling.
  Both directions now proven on real hardware: Antigravity→Codex (17.9 s) and
  Codex→Chrome DevTools (21.8 s).

### Changed
- **Model choice is now the agent's decision, made on capability.** The old
  text said "pick the model by quota… ask the user which one has quota,"
  turning a capability decision into an availability question the user had to
  answer. Now: bulk work → `gpt-5.6-luna`; images or long inputs →
  `gpt-5.4-mini`; fast interactive edits → `gpt-5.3-codex-spark`; review,
  audits and long agentic runs → `gpt-5.6-sol`. The user is consulted only if a
  call actually fails on quota.
- Two published traps recorded, because both reverse the obvious choice: Terra
  is a false economy for long agentic runs (~2.7x Sol's output tokens for fewer
  completions), and Luna's long-context recall collapses to ~41% versus Sol's
  ~91%.
- `models_cache.json` demoted to low-trust — it goes stale and fails the CLI's
  own loader. Task creation is the only authority.
- Documented that a wrong model ID returns `400 … not supported with a ChatGPT
  account`, which reads like "no access" but means "no such model" — the exact
  trap that produced a false "sol/terra/luna unavailable" conclusion here.

### Notes
- **Calling local models works; *running on* one doesn't.** These get
  conflated, so the docs now separate them explicitly. An agent calling a local
  model through `scripts/call_local.sh` is the skill's core path and is proven
  repeatedly with receipts — real classifications and real prose tasks on both
  backends, not just smoke replies. Only the second case below failed.
- **Claude Code *running on* a local model: tested, does not work in practice.**
  The protocol is fine — a logging mock proved `claude -p` completes, and
  Ollama accepts every field it sends. But ~10k tokens of system prompt costs
  41.8 s cold on an 8B model, and Claude Code sends more than that plus 4+
  calls per turn; two runs never finished in 5 minutes. Recorded as a negative
  result so nobody re-derives it. Use `scripts/call_local.sh` for local work.

## [0.1.0] — 2026-08-08

First public release. The skill, the local-call script, a regression suite,
and full docs.

### Added
- **`SKILL.md`** — the routing policy: cost and privacy ladder (local → Codex →
  Haiku → premium Claude), lazy backend probing with smoke tests, model
  selection rules that respect available RAM, and the discipline rules
  (receipts, escalate-don't-loop, capped local concurrency).
- **`scripts/call_local.sh`** — one-shot prompt against a local LLM server.
  Anthropic-format first, automatic fallback to OpenAI-format, token-usage
  receipt on stderr as evidence the call happened.
- **`tests/test_call_local.py`** — offline suite covering both dialects and
  every failure mode below. Needs no real Ollama or LM Studio; runs in ~6 s.
- **`docs/MANUAL.md`** and **`docs/index.html`** — user manual and landing page.
- **`references/local-notes.example.md`** — template for machine-specific facts.

### Fixed
Six defects found by an adversarial audit that routed the review across a
local 7B model, Codex, and Claude. Each was reproduced against a purpose-built
mock server before being fixed, and each now has a regression test.

- **No request timeout.** A server that accepted the connection then stalled
  hung the script forever — the worst case for a tool whose job is batch
  sweeps, since one wedged backend would hang the entire run. Now bounded by
  `CALL_LOCAL_TIMEOUT` (300 s) and `CALL_LOCAL_CONNECT_TIMEOUT` (5 s).
- **Empty replies reported as success.** A reasoning model that spent its
  budget on hidden tokens returned exit 0 with empty stdout, so a batch caller
  would record `""` as a valid answer. Now exit 2, with the receipt still
  emitted.
- **Fallback too narrow.** Only HTTP 404 triggered the OpenAI fallback, so a
  server answering an unknown path with 405 hard-failed even though it spoke
  the other dialect fine. Now falls back on 404, 405 and 501.
- **`null` content printed as `"None"`.** OpenAI-shaped tool-call and filtered
  responses have `content: null`; the literal string `None` was being printed
  as if it were the model's answer. Now treated as empty.
- **Error bodies misdiagnosed.** An HTTP 200 carrying an error payload died
  with `KeyError: 'choices'`, blaming the wrong dialect. Now names the actual
  server error.
- **Test skip reported as failure.** The no-POSIX-bash path exited 1, so a
  machine that simply can't run the script showed a failed build. Now exits 0.
  Test subprocess calls also gained a timeout, so a hang in the script can't
  hang the suite.

### Changed
- **`references/local-notes.md` is no longer tracked.** It was committed and
  then expected to diverge locally forever, which bought nothing and cost
  three things: a permanently dirty `git status`, a file `git pull` could
  conflict on, and one stray `git add -A` between a machine's hardware and
  account details and a public repo. It is now git-ignored, with
  `local-notes.example.md` shipped as the template.
- **Windows support.** The suite invokes the script through a resolved Git
  Bash rather than assuming `bash` on `PATH` (which is the WSL shim, unable to
  resolve `C:/` paths or reach Windows-side localhost servers). Added
  `.gitattributes` pinning the working tree to LF, since a Windows clone with
  `core.autocrlf=true` produced a CRLF `call_local.sh` that bash rejects.
- **Documented that the script enforces nothing "local."** It posts to
  whatever base URL it is given, so the privacy guarantee is the caller's to
  keep. Stated plainly rather than implied.
