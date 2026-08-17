# Changelog

All notable changes to multi-model-routing are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); versioning is
[SemVer](https://semver.org/).

## [Unreleased]

Kept current from here on. Reconstructing several commits' worth of changes at
tag time is how the docs fell behind at 0.3.0, 0.3.2, 0.3.4 and 0.3.5; tagging
should be a rename of this heading, not an archaeology exercise.

### Security
- **The `--cwd` path boundary is restored by default (audit fix, 2026-08-16).**
  `local_agent.py`'s `ConfinedCwd.resolve()` had been left resolving any
  absolute or `../`-relative path unchanged since the 2026-08-16 guard removal,
  so e.g. `write_file("../../ESCAPED.txt")` wrote outside `--cwd` for every
  tool, read or write. By default a path that resolves outside `--cwd` is now
  refused with a `ToolError` (visible to the model, and now logged — see
  below), never a crash. `--allow-outside-cwd` opts back into the old
  unbounded resolution for the cases that actually want it.

### Fixed
- **`LOCAL_AGENT_LOG` now covers the default lane.** `_audit_log` was wired
  only into `run_raw_loop`; `run_sdk_loop` — the default lane whenever the LM
  Studio SDK is available — never wrote a single audit line, and both loops'
  unknown-tool and malformed-tool-call branches returned before logging. Every
  tool call is now logged on both lanes, including rejected and malformed
  calls (the injection evidence), by wrapping each tool implementation and
  hooking the SDK's `handle_invalid_tool_request` callback.
- **`write_file` round-trips content byte-exact.** It wrote with Python's
  default text-mode newline translation, so LF content came back CRLF on
  Windows. It now opens with `newline=""` so the bytes it's given are the bytes
  it writes. Its return string also now reports the resolved path instead of
  the caller's possibly-relative one.
- **The `grep` pure-Python fallback no longer dies on an out-of-root path.**
  `f.relative_to(confined.root)` raised an uncaught `ValueError` for any file
  outside `confined.root`, killing the whole run — the live path on any
  machine without `rg` on PATH. It now catches that and skips the file; the
  path boundary above makes this rare by default, but `--allow-outside-cwd`
  and symlinks can still reach it.

### Changed
- **Guard status (owner directive, 2026-08-16).** The command guards stay
  removed by owner directive; the `--cwd` path boundary stays enforced by
  default, since an unbounded filesystem escape is out of scope for the guard
  removal.

## [0.3.11] - 2026-08-16

### Changed
- **Local is now the mandatory default for real work, not just grunt work
  (owner directive, 2026-08-16).** The routing rule requires every task to start
  on a local model; escalating to a paid meter requires a stated, positive
  reason (a capability the local roster provably lacks, security-sensitive/
  ships-unreviewed work, or a local attempt that failed review twice). "Feels
  hard" and "no local model was tried" are not reasons. The frontier brain
  directs, plans, reviews, and audits the fleet — it does not do the bulk.
- **Local model work now has two explicit lanes.** `scripts/call_local.sh`
  remains the cheap one-shot path. New `scripts/local_agent.py` is the primary
  tool-using local agent loop, with LM Studio SDK `LLM.act()` first and a
  provider-neutral OpenAI chat-completions loop as the stdlib fallback.
- **`codex --oss` is demoted to a known-fragile compatibility probe.** A live
  LM Studio/Qwen run on 2026-08-15 failed before the loop began because Codex
  inserted a system message after conversation start and the model's Jinja
  template requires the system message first. The bundled harness avoids that
  message-layout trap.
- **Local engine selection is now provider-neutral.** The skill discovers the
  local engines available on the machine, counts their reachable and usable
  model inventories, and chooses the engine with the largest roster before
  selecting a task-fit model. It no longer assumes a particular local LLM
  engine.

### Added
- **`scripts/local_agent.py`** — a local agent harness with `read_file`,
  `list_dir`, `grep`, `run_command` (unrestricted — real shell, chaining, and
  redirection), and `write_file`; `--read-only` narrows it to the three read
  tools for analysis runs that provably cannot modify anything; `--max-steps`;
  Qwen reasoning-sentinel cleanup; per-step and total token receipts; and an
  optional `LOCAL_AGENT_LOG` JSONL audit trail of every tool call. It
  self-bootstraps `scripts/.venv-local-agent` for the LM Studio SDK, while
  `--no-sdk` needs only Python's standard library. Base URL and bearer token
  are configurable by flag or environment for compatible local servers.
- **Offline coverage for the raw agent loop.** The mock-server test proves a
  two-round tool call, tool-result replay, receipt totals, reasoning cleanup,
  UTF-8 output, API-key forwarding, custom-endpoint routing, and step-budget
  validation; direct tool tests prove write_file, the nested-quote regression,
  command chaining, and the read-only vs full tool exposure.

### Removed
- **The command guards were removed (owner directive, 2026-08-16):** the
  destructive-command blocklist, the read-only command allowlist, the
  chain/redirection block, and the `--cwd` path jail are gone, and
  `--allow-write` is replaced by an inverted `--read-only` (full power is the
  default). This was an owner directive for a harness on the owner's own
  hardware against trusted local models directed to run freely. **Note (audit,
  2026-08-16, see [Unreleased] above): the `--cwd` path jail specifically is
  restored by default, since an unbounded filesystem escape is out of scope for
  the guard removal.** The read/write boundary is the set of
  exposed tools (`--read-only`), not string inspection.

### Fixed
- **`run_command` no longer silently eats quoted commands on Windows.** It ran
  commands as `["cmd","/c", <string>]`, whose list-quoting mangled nested
  quotes, so e.g. `python -c "print('x')"` returned empty output with exit 0.
  It now passes the command string with `shell=True`.
- **Windows output is explicitly UTF-8.** `local_agent.py` reconfigures stdout
  and stderr with `encoding="utf-8"` and replacement error handling so a local
  model's Unicode output cannot discard a successful run on a legacy console
  code page.
- **The bundled test file is cp437-safe.** Its non-ASCII UTF-8 fixtures are
  built with `chr()` instead of literals, so the install guard's
  literal-value scan passes.

## [0.3.10] - 2026-08-10

Extends live model discovery to Codex and Antigravity, matching the pattern
Ollama and LM Studio already had via `/api/tags` and `/v1/models`. Prompted by
Scott noticing `references/codex.md`'s model table listed specific slugs as
hardcoded prose with nothing checking them against reality.

### Added
- **`scripts/codex_models.sh`** — reads Codex's own `~/.codex/models_cache.json`
  (respecting `$CODEX_HOME`), the cache Codex CLI maintains as part of its own
  normal operation. Verified live on this machine: 9 models, `fetched_at` age
  0.0 days. **Verified specifically which command refreshes it**: `codex
  doctor` does not touch the cache's mtime; a real `codex exec` call does —
  confirmed both ways rather than assumed, since the wrong answer would have
  shipped as documentation telling users to run the wrong command.
  `--model NAME` for full detail, `--list` for slugs only, `--json` for raw
  passthrough (SIGPIPE-safe when piped into `head`/`jq`).
- **`tests/test_codex_models.py`** — 29 checks, fixture-driven via
  `CODEX_MODELS_CACHE`, needs no real Codex install. Includes a deliberately
  sparse fixture entry (most fields absent) because a rich-only fixture would
  not have caught a `m["field"]` vs `m.get("field")` mistake.
- **A live-selection heuristic for Antigravity**, in `references/cross-agent.md`
  — `agy models` was already documented as live and authoritative; what was
  missing was which tier to pick for which job, mapped by capability rather
  than by exact slug (Google renames tiers the same way OpenAI does).
- **`references/codex.md`'s model table now says to verify before trusting a
  slug**, via `scripts/codex_models.sh --list`. The job-shape reasoning stays
  — it is durable — but the exact IDs are now a checked claim, not a permanent
  one. The existing "models_cache.json is low-trust" finding (2026-08-08,
  `missing field 'base_instructions'`) is kept, not overwritten; today's live
  check found the cache fresh and complete on the current Codex version, and
  both dated findings stand side by side.
- **A `bash -n` syntax guard for every shipped script**, added to
  `test_install.py`. `codex_models.sh` shipped three separate syntax errors
  during development — an f-string quoting bug, then a "fix" that used
  single-quoted Python strings which broke the *bash* single-quoted block
  those strings lived inside, then the same thing again from an apostrophe in
  a comment ("CI's 3.11"). Re-reading the file by eye missed it three times
  running. `bash -n` is free, needs no execution, and catches this class
  immediately — proven by feeding it a reintroduced copy of the exact bug.
- Claude subagent model docs now mention `fable`, which the Agent tool's own
  enum already accepted — `SKILL.md` only listed three of the four.

### Fixed
- **The new bash-syntax guard was blind to its own subject on arrival.**
  `git ls-files scripts/*.sh` only sees tracked files, so it silently checked
  the two already-committed scripts and never `codex_models.sh` itself, which
  was untracked at the moment the guard was written — the exact defect class
  this repo has hit six times now, freshly reintroduced in the guard meant to
  catch a different one. Fixed by unioning with `--others --exclude-standard`,
  the same fix the payload-drift guard needed for the same reason.
- **That same guard then failed differently once fixed**, discovered by
  running the shipped suite from a real install with no `.git` anywhere: a
  completed `git ls-files` with a non-zero return code (running outside any
  repository) is not success with empty output, but the guard only checked
  `is not None` and treated it as one, reporting "(0) scripts checked" instead
  of falling back to a directory glob. Fixed to check the return code too,
  matching the pattern `git_files()` already used correctly elsewhere in this
  file — inlined rather than calling that helper, since it is defined later
  in the file and calling it here would repeat an ordering bug from earlier
  the same day.

Suites 16 + 29 + 29 + 31 = 105 green on Windows/py3.13, WSL Ubuntu
26.04/py3.14/bash 5.3.9 (bash -n run against real POSIX bash, not Git Bash's
emulation), and with git entirely absent.
## [0.3.9] - 2026-08-10

### Fixed
- **`SKILL.md`'s `description` field exceeded claude.ai's own 1024-character
  upload limit.** It shipped at 967 chars, already tight, and grew to 1068
  when OpenCode Zen was added to the trigger list two releases ago — nothing
  checked it against the platform's actual constraint, so the first anyone
  learned of it was the upload dialog rejecting the file outright: *"field
  'description' in SKILL.md must be at most 1024 characters."* Trimmed to 953
  chars (71 of margin) without dropping any trigger phrase — the batch-work
  signal, the backend list, or the exclusion clause.
- **A regression test now enforces the limit.** Extracts the folded YAML
  block scalar with a targeted regex — no PyYAML import, so the suite still
  runs on bare stdlib everywhere it always has — and fails if the field ever
  exceeds 1024 chars again. Proven to fire: padding the field on purpose
  produced the same 1024 failure the upload dialog would, and the file
  restores cleanly to a full pass.
## [0.3.8] - 2026-08-10

### Fixed
- **The backend-roster drift test crashed the shipped suite in every real
  install.** Added two commits ago to stop the landing page from drifting, it
  read `docs/index.html` unconditionally — but that file is deliberately
  excluded from `PAYLOAD`, published only via Pages, and absent from every
  install by design. Running the shipped `tests/test_install.py` from an
  actual installed copy for the first time (building a downloadable package
  surfaced it) died with `FileNotFoundError` instead of the roster check it
  was meant to be. `README.md` and `docs/MANUAL.md` are in `PAYLOAD`, so they
  are still checked everywhere; `docs/index.html` is now checked only where it
  is actually present. Proven both ways: the repo still checks all 3 surfaces,
  an install checks 2, and planting drift in an install's `README.md` still
  fails the check that previously would have crashed before reaching it.
## [0.3.7] - 2026-08-09

### Fixed
- **The published landing page was stale one tag after the fact.** `v0.3.6`
  added OpenCode Zen to the routing ladder and rewrote the privacy rule, but
  `docs/index.html` still drew a four-tier ladder without it and still carried
  the sentence the rewrite removed: *"never to a third-party cloud without your
  say-so"* — the claim this tool breaks on every call. That was live on
  <https://scottconverse.github.io/multi-model-routing-skill/>. Ladder redrawn
  to five tiers, backend table updated, privacy note replaced with the honest
  version, meta description corrected.
- **The roster drift test no longer exempts the landing page.** It was excluded
  as "a marketing surface, not a reference" and went stale within a single tag,
  which is what an exemption buys you. All three human surfaces — `README.md`,
  `docs/MANUAL.md`, `docs/index.html` — are now checked against the roster
  `SKILL.md` declares. Roster names are normalised (`Codex CLI` matches a table
  cell reading `Codex`) so the check fails for drift, not for phrasing.
- **`docs/index.html` gained Open Graph and Twitter Card meta tags.** The
  published landing page had none — sharing the link showed a bare URL, no
  title, no description, no card. Text-only for now; no image asset exists.

## [0.3.6] - 2026-08-09

### Added
- **OpenCode Zen is in the routing ladder**, above Codex, because it is free.
  No API key and no account: `GET https://opencode.ai/zen/v1/models` lists 61
  models and the `-free` ones need no credentials. *Verified 2026-08-09 from
  this machine:* a one-word reply in **9.1 s**, `[receipt] in=88 out=21`. It is
  an OpenAI-dialect gateway, so callers pass `CALL_LOCAL_DIALECT=openai` rather
  than letting `auto` probe — Zen serves `/v1/messages` only for paid Claude
  models. On the open benchmark data `deepseek-v4-flash-free` scores 152.53,
  above `gpt-5.4-mini` at 148.91, a paid tier further down the same ladder.
  The capability already existed through `call_local.sh`; what was missing was
  automatic placement.
- **A drift test for the backend roster.** The roster lives in three places —
  `SKILL.md`'s numbered list, `README.md`'s opening paragraph and
  `docs/MANUAL.md`'s cost table — and adding a backend means touching all
  three. The test reads the roster *from `SKILL.md`* and asserts each name
  appears on the human surfaces, so a seventh backend is covered the moment it
  lands. Doc drift has been this repo's most repeated defect.
- **`--limit N` and `--refresh` are documented.** Both were implemented and
  validated but reached no reader — absent from `references/benchmarks.md`
  (the file the skill tells the agent to load), `docs/MANUAL.md` and
  `README.md`. `references/benchmarks.md` now carries a full flag table, and
  the parser-derived flag list that already guarded `--help` guards both doc
  surfaces, so a flag cannot ship undocumented again.
- **WSL as a real Linux surface**, plus a CI Python matrix (3.11 and 3.13 on
  Ubuntu and Windows). A test helper had used `shutil.rmtree(onexc=)`, which is
  3.12+, and passed locally on 3.13 while dying on CI's 3.11.

### Changed
- **The privacy rule was dishonest and has been rewritten.** It said not to
  send content to "a third-party cloud backend without an explicit OK" — a rule
  this tool violates on every call, since the harness running it sends
  everything to Anthropic, Codex to OpenAI and Antigravity to Google. A rule
  that forbids what you are already doing is not a rule. The docs now say it
  plainly: only the local backends keep data on the machine, everything else is
  somebody's cloud, so **pick on cost** — and the distinction that actually
  matters is account-bound (Codex, Antigravity, Claude, under your own accounts
  and terms) versus anonymous (Zen's free tier: no key, no commitment, no
  controllable quota). Genuinely sensitive material stays local.
- **Ten audit reports collapsed into one post-mortem.** They had reached 913
  lines against 117 lines of product change in the same span. `docs/audits/`
  now holds a single 71-line file keeping the two defect classes worth
  remembering and the practice that caught them; the detail lives in
  `git log v0.3.5..`.

### Fixed
- **The payload drift guard could not run where it ships.** Outside a checkout
  `git ls-files` exits 128 with empty stdout; the return code was never
  inspected, so "git cannot answer" became "nothing is unaccounted for" and
  the guard printed `ok` in every installed copy — exactly where `tests/`
  ships, for users to verify their own install. Correcting that exposed a
  second mode: installed under a user's own project, git succeeds and
  enumerates **their** repo, so the guard failed and named
  `references/local-notes.md` — the file the installer had just created for
  them on purpose. It now tests repository *identity*
  (`git rev-parse --show-toplevel` against the test's own root) and skips with
  a reason, naming each check that did not run.
- **The test harness crashed on cp437, and only when a test failed.** Em
  dashes sat in the failure branches of `test_install.py` and
  `test_benchmarks.py`, so on cmd.exe a genuine failure surfaced as
  `UnicodeEncodeError` instead of the name of the broken check. The rule was
  already enforced for `install.py` — by a guard that read `install.py` **by
  name**. It now enumerates `git ls-files '*.py'` with a directory-walk
  fallback.
- **A missing flag value answered in bash's voice, not the script's.**
  `${2:?...}` produced `benchmarks.sh: line 45: 2: --measure needs a value` —
  a positional parameter the user never typed, and a line number that drifts
  with every edit above it. Now `benchmarks.sh: --measure needs a value`.
- **`--help` was built from a hardcoded `sed -n '5,28p'`**, which broke the
  moment the header grew: it spilled `set -euo pipefail` into the output and
  omitted `--limit` entirely. Delimited by explicit markers now.
- **`--help` documented `$CALL_LOCAL_CACHE`**, which the script never reads.
  The real variable is `BENCHMARKS_CACHE`.
- **`NOT_SHIPPED` hardcoded a dated audit filename**, guaranteeing that the
  next report would fail the drift guard. Entries may now end in `/` to cover
  a directory, and no entry may contain a date.

### Notes
- **The CI "no CRLF" check could not fail.** `.gitattributes` is
  `* text=auto eol=lf` with no `-text` exception, so a fresh checkout
  normalises every text file to LF *before* the step grepped the working tree
  — 0 of 28 committed blobs contained CRLF, and a fresh clone found nothing, as
  it always would. It now checks `git ls-files --eol` for any `i/crlf`, which
  is what a clone actually receives, and prints the tracked-file count so a
  vacuous pass is visible. Verified against a purpose-built repo whose index
  genuinely stores CRLF. The working-tree grep is kept underneath it: it does
  catch a `-text` path, so the two together are stronger than either.
- **The cp437 guard checked four hardcoded call patterns, not "printed
  strings".** It scanned lines containing one of
  `("print(", "actions.append(", "sys.exit(", "return dest, [")`, so
  `sys.stderr.write()`, `sys.stdout.write()`, `raise SystemExit()` and
  `logging.*()` all evaded it. No live exposure — none of those forms is used
  today — but `install.py` already uses `sys.exit("...")`, one keystroke from
  the form that escaped. The guard's *file* scope had been widened to every
  shipped `.py` without anyone asking whether the *pattern* scope was right,
  and no later change touched the line. It now parses each file and checks
  every non-docstring string literal; docstrings stay exempt and comments drop
  out for free. 6/6 under perturbation, including the docstring exemption.
- **The "git is spawned only through `git_run()`" guard matched
  `subprocess.run` alone**, so `check_output(["git", ...])` and
  `Popen(["git", ...])` sailed through — and `check_output` is the natural
  choice for the read-only queries this file makes, raising `FileNotFoundError`
  identically. It now matches any `subprocess.<attr>` whose first argument is a
  list starting with `"git"`: 4 of 4 entry points caught, where 3 of 4 escaped.
- **The suite no longer requires git.** Nothing about this skill does —
  `install.py` is pure Python, the shell scripts want curl and python3 — but
  `tests/test_install.py` spawned git at eight call sites without a guard, so on
  a machine without it the suite died with a `FileNotFoundError` traceback
  instead of skipping. One `git_run()` chokepoint now catches it, and an AST
  check asserts nothing spawns git any other way. Fixing that exposed nine
  further checks that vanished silently when git was absent — one block
  announced its skip with a bare `print()`, invisible to the tally, and
  another had no `else` at all. Skips are now announced per check and counted:
  `ran + skipped` is 25 with or without git.
- `scripts/benchmarks.sh` gained a test suite it had shipped without.
  Suites are now 16 + 25 + 31 = **72 checks**, green on Windows/Python 3.13,
  four CI jobs, WSL Ubuntu 26.04 / Python 3.14 / bash 5.3.9, and with git
  entirely absent on both platforms.

## [0.3.5] — 2026-08-09

### Fixed
- **`scripts/benchmarks.sh` shipped non-executable.** It was committed as
  `100644` while `call_local.sh` was `100755`, so every Linux and macOS clone
  got a script it couldn't run directly. Found by the pre-release lifecycle
  check, not by CI — because the CI guard tested `scripts/call_local.sh` **by
  name** and knew nothing about a second script. Both the executable-bit guard
  and shellcheck now iterate `git ls-files 'scripts/*.sh'`, so a new script is
  covered the moment it lands rather than whenever someone remembers.

  The guard reads the **git index**, not the working tree: the index is what a
  POSIX clone actually gets, and the working-tree bit is meaningless on
  Windows — which is exactly why this went unnoticed here for a release.

### Added
- **`CALL_LOCAL_DIALECT=auto|anthropic|openai`.** `auto` (unchanged default)
  probes Anthropic then falls back on 404/405/501 — right for a local server,
  which either serves a dialect or doesn't. **Wrong for a gateway**, where the
  dialect depends on the *model*: OpenCode Zen serves `/v1/messages` only for
  paid Claude models and answers 401/400 for free ones, while
  `/v1/chat/completions` serves them fine. Widening the fallback to 400 would
  have traded a working guard for convenience — a 400 is usually a genuine bad
  request and retrying would hide it — so the caller states the dialect
  instead. Verified against the live gateway **with no API key**:
  `deepseek-v4-flash-free` returned in 6.5 s, `[receipt] in=91 out=16`.
- **OpenCode Zen probed and documented**: 61 models advertised, 8 free,
  anonymous inference returning HTTP 200 without a key. Notably
  `deepseek-v4-flash-free` scores 152.53 on Epoch's data — above `gpt-5.4-mini`
  (148.91), a paid tier this skill routes to. Not yet added to the routing
  ladder: free-tier access is **not private** (prompts reach OpenCode and its
  upstream provider) and has no controllable quota, so that placement is a
  judgment call left open deliberately.

### Fixed
- **The wrong timeout knob was named when a connection never opened.** curl
  returns exit 28 for both a connect timeout and a whole-call timeout, and the
  handler assumed the latter — so a blackholed host failed after 5 s but
  reported "timed out after 300s … raise `CALL_LOCAL_TIMEOUT`". Wrong number,
  and it pointed at a limit that was never the problem. `do_post` now carries
  `time_total` and the message distinguishes them.

  Measured failure times for an absent backend, all fast and all loud:
  unresolvable host **0.65 s**, nothing listening **2.6 s**, blackholed
  **5.4 s**, benchmark fetch offline with no cache **10 s**. With a cache it
  degrades to it rather than failing.

### Added
- **`scripts/benchmarks.sh` — the freshness mechanism.** A number pasted into a
  document is a fossil the moment a model ships, so the skill no longer carries
  rankings; it fetches them. The script pulls Epoch AI's open data
  (CC-BY, no account, no key), **refetches whenever the cache is older than a
  week** (`BENCHMARKS_MAX_AGE_DAYS`), falls back to the cache when offline and
  says so, and prints the attribution CC-BY requires on every run.

  ```bash
  scripts/benchmarks.sh --open              # best open-weights models
  scripts/benchmarks.sh --measure coding    # code work specifically
  scripts/benchmarks.sh --model deepseek    # one family
  ```

- **Open source first, as a routing rule.** Where an open-weights model can do
  the job, prefer it — over a paid API model, and when choosing what to pull.
  Not only about cost: open weights run locally, keep data on the machine, cost
  nothing per call, and can't be deprecated out from under you. **And it is no
  longer a capability sacrifice** — on the open data, `kimi-k3` (157.01, open
  weights) outscores `claude-sonnet-5` (155.53) and `gemini-3.6-flash` (153.98),
  two paid tiers this skill routes to.

  ⚠️ **With the caveat that makes the rule usable: "open weights" means
  downloadable, not runnable.** `kimi-k3` is 2.8T parameters, ~594 GB
  quantized, and needs 8× H200 to serve — against 25.8 GB of RAM here that is
  not a close call. The skill now separates three questions: *is it good* (the
  data), *can I run it* (size against free RAM — a 17.99 GB model already
  failed to load at 17.5 GB free), and *can I reach it another way* (API
  providers, or Antigravity's free `gpt-oss-120b`). A frontier open model
  reached over someone else's API is an option with better licensing — it is
  **not local and not private**, and the privacy rule applies to it exactly as
  it does to Codex.

  Also flagged for verification rather than assumed: Epoch's accessibility
  column marks `kimi-k3` "Open weights (non-commercial)" while release
  reporting describes Apache 2.0 weights. Both cannot be right — check the
  model card before making a licensing decision. A metadata column is a
  summary, not the licence.

## [0.3.4] — 2026-08-09

### Added
- **`references/benchmarks.md` — tier assignments are now grounded in a source
  rather than in prose.** Artificial Analysis is the reference of record, and
  the method is a *query*, not a recollection: the OpenRouter MCP exposes the
  Intelligence, Coding Agent and Agentic indices directly
  (`list-benchmarks source=artificial-analysis`, or `list-models` with
  `sort=coding-high-to-low` / `min_coding_index=`). The web page is
  JavaScript-rendered, so a plain fetch returns methodology text and no
  numbers — worth knowing before anyone tries.

  The reason it matters here more than in most skills: **AA scores open-weights
  models on the same indices as proprietary ones**, which puts the models on
  this machine and the models behind an API on one scale. "Is the local model
  good enough, or does this need a tier up?" becomes a comparison instead of a
  judgment call.

  Rules attached: cite the index *and the date*; re-check anything older than a
  month; a measured result on this machine still outranks a leaderboard; and
  **never invent a score** — if the source is unavailable, say so. Recorded
  as of 2026-08-09 the OpenRouter connector on this machine reports
  `! Needs authentication`, which makes those queries silently unavailable
  until it is reconnected.

- **The official Data API, documented with its licence line.** A free tier
  exists: `https://artificialanalysis.ai/api/v2`, `x-api-key` header, 100
  requests/24h, returning the headline indices, median performance and token
  pricing. Verified live from this machine (401 without a key, 401 with a bad
  one) — a key is the only blocker, and obtaining one is an account signup the
  owner must do. ⚠️ **The free tier is internal use only, no redistribution**,
  with attribution required on every tier: routing decisions are fine,
  publishing API-sourced scores into this public repo is not. Ready-made
  clients (`davidhariri/artificial-analysis-mcp`, `aneym/artificial-analysis-cli`)
  and ranked fallbacks are recorded; scraping the site and reciting remembered
  rankings are ruled out explicitly.

### Fixed
- **The drift guard could not see a file until it was staged.** It used
  `git ls-files`, which lists only tracked files, so a brand-new reference doc
  stayed invisible locally until `git add` — CI caught it, but a step later
  than the author needed. It now also reads
  `git ls-files --others --exclude-standard`, which respects `.gitignore` so
  `local-notes.md` and `__pycache__` stay exempt. Found by writing a new
  reference file and watching the guard stay green when it should not have.

## [0.3.3] — 2026-08-09

Fix-forward for four defects introduced or missed in 0.3.2. One of them could
have destroyed a repository.

### Fixed
- **`install()` would have deleted 11 tracked files from a git checkout.** The
  VCS skip added in 0.3.2 only covered paths *inside* `.git/`, but the files at
  risk sit beside it: `.gitignore`, `.gitattributes`,
  `.github/workflows/test.yml`, `docs/index.html`, `docs/.nojekyll`,
  `CHANGELOG.md`, `CONTRIBUTING.md`, `DISCUSSIONS_SEED.md`. That is the CRLF
  guard, the private-notes guard, all of CI, and the landing page — and the
  documented personal install *is* a checkout. `install()` now reuses the same
  `VCS_MARKERS` check `uninstall()` has and skips pruning entirely in a working
  copy, saying so. Pruning exists to clean stale files out of a **copied**
  install; in a checkout, git already does that job.
- **The em dash was not cosmetic.** cp1252 hides the problem because that
  codepage *has* the character at 0x97. cp437 — the historic `cmd.exe` default
  — does not, and `install.py` died with
  `UnicodeEncodeError: 'charmap' codec can't encode character '—'`,
  exit 1, **after files had been copied**, leaving a partial install. All
  printed strings in `install.py` are now ASCII, as is `call_local.sh`'s
  empty-reply diagnostic, which carried the same hazard — a traceback there
  would have replaced the message telling you to raise `max_tokens`.
- **The drift guard now covers the same set pruning operates on.** The
  extension filter is gone; every tracked file must be named in `PAYLOAD` or
  `NOT_SHIPPED`, which forces `.gitignore`, `.gitattributes`, `docs/index.html`,
  `docs/.nojekyll` and the CI workflow to be listed deliberately. A guard whose
  set differs from the operation it guards is not a guard.
- **A stray `.pyc` was committed in 0.3.2**, created when the drift test
  imports `install.py`. Untracked, and `__pycache__/` plus `*.pyc` are now
  ignored.

  Worth keeping, because it generalizes: **the guard created the artifact it
  then had to catch.** The drift test imports `install.py` to read its payload
  lists; importing writes a `.pyc`; and the extension filter in that same
  test's first version — `.md`, `.sh`, `.py` — let the `.pyc` through. A test
  that touches the tree it audits changes what it is auditing, and its blind
  spots are exactly where its own leavings land. If a check reads the working
  tree, ask what it *writes* there, and make sure the check can see that too.

### On the ASCII rule
The fix is scoped to **printed strings, not files.** Comments never reach a
stream; seven non-ASCII characters remain in comments across `install.py` and
`call_local.sh`, and they should stay. Widening the check to whole files would
fail for a reason that cannot affect anyone, and a check that cries wolf gets
switched off. `tests/test_install.py` scopes itself to lines that print, on
purpose.

### Verified
Against the real checkout on this machine: `install.py --app claude` reports
`skipped pruning: .git/ is present`, with 20 tracked files before and after and
all four guard files intact. Under `chcp 437` with
`PYTHONIOENCODING=cp437:strict`: exit 0 on install, uninstall, and the
empty-reply path.

## [0.3.2] — 2026-08-09

Four defect fixes and one drift guard, from a code read by the agent working on
[WorkflowWright](https://github.com/scottconverse/WorkflowWright). Every finding
was reproduced before being fixed; where one didn't reproduce as reported, the
correction is recorded rather than quietly smoothed over.

### Fixed
- **`--uninstall` could destroy a git checkout.** The documented personal
  install *is* the git working copy, so the `SKILL.md` guard passed and
  `rmtree` took `.git` with it. On Windows this surfaced as an uncaught
  `PermissionError` traceback with the install **half-deleted**; on POSIX,
  unlink permission comes from the parent directory, so it removes the history
  outright. *(Measured on WSL Ubuntu 26.04 on 2026-08-09, not inferred: a plain
  `shutil.rmtree` over a git checkout succeeded silently and took `.git` with
  it. The Windows crash is incidental protection; the guard is what actually
  protects a POSIX user.)* Uninstall now refuses any directory containing
  `.git`/`.hg`/`.svn`, names the marker, and exits 0. Proven against the real
  checkout: 22 files before, 22 after.
- **The preserved-notes backup overwrote itself.** install → uninstall →
  install → uninstall wrote freshly templated notes over the backup holding
  every accumulated machine fact — data loss inside the feature meant to
  prevent it. Backups are now numbered and never overwritten.
- **An installed copy had no uninstaller.** `install.py` wasn't in `PAYLOAD`,
  so removing an install required the original clone. It now ships with every
  install.
- **After refusing, the program still printed "Uninstalled."** Not on the
  report list; found while fixing. The closing message now reflects whether
  anything was actually removed.

### Added
- **The prompt no longer has to fit in argv.** `-` reads stdin, `file:PATH`
  reads a file, and the literal form is unchanged. `curl` also stopped taking
  the body as an argument (`--data-binary @FILE` instead of `-d "$BODY"`) —
  without that, the ceiling would have stayed exactly where it was. Verified
  against real Ollama with a 24 KB prompt (`in=12533`).
  ⚠️ The file sigil is **`file:PATH`, not `@PATH`**: Git Bash on Windows
  expands a leading `@` as a *response file* before the script runs, so
  `@p.txt` containing "alpha beta gamma" arrives as three arguments and
  silently shifts everything after it. `@FILE` would have shipped that bug.
- **A drift guard with teeth.** Every tracked file must be in `PAYLOAD` or in
  an explicit `NOT_SHIPPED` list, enforced by a test — "forgotten" is no longer
  a state this repo can be in. Proven by adding a dummy doc and watching the
  suite go red naming it.
- **`docs/MANUAL.md` now ships with installs.** Shipping the test suite while
  withholding the human manual was backwards.
- **`install()` prunes stale files**, so a file renamed between versions no
  longer lingers where the agent might still read it. Never touches
  `local-notes.md` or a VCS directory.

### Corrected from the report
The argv finding predicted *silent* truncation at the first newline, producing
a plausible answer from a cut input. That did not reproduce. A 15 KB prompt
arrived intact with all 299 newlines; oversized prompts fail **loudly** —
`Argument list too long` (exit 1) via Git Bash, `The command line is too long.`
via a `.cmd` shim. It is a capability limit, not a correctness trap. Worth
fixing, but nobody has been silently getting wrong answers.

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
