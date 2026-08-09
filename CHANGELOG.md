# Changelog

All notable changes to multi-model-routing are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); versioning is
[SemVer](https://semver.org/).

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
