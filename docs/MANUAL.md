# multi-model-routing — Manual

A skill that teaches a coding agent to send bulk, mechanical work to the
cheapest backend that can actually do it — the free LLMs already on your
machine first, then Codex, then Claude's cheap tier, with premium Claude
reserved for work that needs it.

---

## 1. What it is (and isn't)

**It is** a markdown instruction file (`SKILL.md`) plus one small bash script.
Your agent reads the file and changes how it dispatches work. There is no
daemon, no background process, no account to create, and nothing to configure
beyond one optional notes file.

**It isn't** a model router in the API sense. It doesn't proxy your traffic,
sit in front of an endpoint, or rewrite requests. It's a policy your agent
follows, plus a helper for talking to local servers.

**It isn't a privacy boundary either.** See [Honest limits](#10-honest-limits).

The point is cost. A request like *"summarize every log in this folder"* is
200 mechanical calls. Without this, all 200 go to a premium model built for
architecture review. With it, they go to a model already sitting idle on your
own hardware, and something better checks the result.

---

## 2. Install

**The installer is the short path.** It auto-detects Claude Code and
Antigravity, installs into each, creates your notes file from the template, and
will never overwrite an existing one:

```bash
git clone https://github.com/scottconverse/multi-model-routing-skill.git
cd multi-model-routing-skill
python3 install.py
```

| Flag | Effect |
|---|---|
| `--list` | dry run — prints what it would do, changes nothing |
| `--app claude` / `--app antigravity` | just that harness (repeatable) |
| `--project DIR` | into `DIR/.claude/skills` for one project only |

**Install it in every harness you use.** Routing advice only helps the session
that can read it — a skill living in one agent can't tell the others what to
route where.

**If you installed by cloning, prefer `git pull` to re-running the installer.**
Both work — the installer detects a working copy and skips its cleanup step,
because git already manages stale files there — but `git pull` is the natural
update path for a checkout and won't leave your working tree showing modified
files.

### By hand

Skills are auto-discovered from two locations. Personal install (every project
on the machine) is what most people want:

```bash
git clone https://github.com/scottconverse/multi-model-routing-skill.git \
  ~/.claude/skills/multi-model-routing
```

For one project only, clone into that project's
`.claude/skills/multi-model-routing` instead.

> **The folder must be named `multi-model-routing`.** That's what the `name:`
> field in `SKILL.md` expects. The repo's name on GitHub is different and that
> is fine — the folder name is what matters.

Then create your machine's notes file:

```bash
cd ~/.claude/skills/multi-model-routing
cp references/local-notes.example.md references/local-notes.md
```

That's it. The agent picks the skill up on its next session — nothing to
enable, no restart beyond starting a new session.

**Updating:** `git pull` inside the installed folder. Your `local-notes.md` is
git-ignored, so updates never touch it and never conflict with it.

**Requirements:** `bash`, `curl`, and `python3` (standard library only — no
`pip install`). You do **not** need all four backends; it works with whatever
subset you have.

---

## 3. The routing rule

Two axes, and they point in opposite directions.

**Cost — cheapest tier that can do the job:**

| Tier | Backend | Cost |
|---|---|---|
| 1 | Ollama (local) | free, no quota |
| 2 | LM Studio (local) | free, no quota |
| 3 | Codex CLI | your ChatGPT quota |
| 4 | Claude Haiku | cheap Claude tier |
| 5 | Premium Claude | reserve for reasoning, architecture, review |

**Privacy — runs the other way.** Local models keep everything on the machine.
Codex ships content to OpenAI. Sensitive or private material goes to local
models or Claude, never to a third-party cloud backend without your explicit
OK.

**The rule that makes it safe:** local output is raw material. It never ships
unreviewed — the agent (or a Claude subagent) reviews it before it counts.

**Escalate, don't loop.** If a backend's output fails review twice on the same
piece of work, it moves up one tier. It does not burn a third attempt at the
same level.

---

## 4. The backends

The agent probes a backend the first time it's about to send real work there —
not in a sweep when the skill loads — and caches the result for the session. A
backend only counts as available after it returns a one-word smoke reply, so
"available" always means *proven this session*, not *installed*.

| Backend | Probe | Healthy looks like |
|---|---|---|
| Ollama | `GET http://localhost:11434/api/tags` | models + `capabilities` |
| LM Studio | `GET http://localhost:1234/v1/models` | JSON list of models |
| Codex CLI | `codex doctor` | active model, auth, install health |
| Antigravity | `agy models` | model IDs + display names |
| Claude subagents | always available | — |

`agy` is usually **not on PATH** — on Windows, `%LOCALAPPDATA%\agy\bin\agy.exe`.

### Ollama

Base URL `http://localhost:11434`. List installed models with `ollama list`.
Pull new ones with `ollama pull <model>` — but the skill will confirm with you
before any multi-gigabyte download.

### LM Studio

Base URL `http://localhost:1234`. The server isn't always running; start it
with `lms server start`. The CLI often isn't on `PATH` — it commonly lives at
`~/.lmstudio/bin/lms` (`lms.exe` on Windows). Record the real path in your
notes file so the agent doesn't have to hunt for it.

Useful commands: `lms ls` (everything downloaded), `lms ps` (currently
loaded), `lms load <key> -c <context>`, `lms get <search>`.

> LM Studio JIT-loads: `lms ps` can report nothing loaded while the server
> still answers requests fine. It loads the model on the first call, which is
> why that call is slow.

### Codex CLI

```bash
codex exec --skip-git-repo-check -c model="<MODEL>" -c sandbox_mode="read-only" "task"
```

- **Pass the model explicitly, every time.** Pick by quota, not habit. Record
  which model actually has quota in your notes file.
- **Keep `sandbox_mode="read-only"` for questions and reviews.** Codex's
  default is workspace-write with approval never — it *will* edit files
  without asking if you drop that flag.
- Multi-turn: `codex exec resume --last "follow-up"`.

### Antigravity (`agy`)

The CLI is usually **not on PATH** — on Windows it's at
`%LOCALAPPDATA%\agy\bin\agy.exe`.

```bash
agy models                                        # free, first-class discovery
agy -p "task" --model gemini-3.6-flash-low
agy -p "task" --model <M> --output-format json --json-schema schema.json
```

It reaches models nothing else here does — **Gemini** and **GPT-OSS 120B** —
and offers Claude Sonnet/Opus 4.6 on a **meter separate from your Claude
quota**, which matters when Claude is running tight.

It's also the best structured-batch surface available: `--json-schema` (which
requires `--output-format json`) returns a parsed `structured_output` object
plus a token receipt in the same payload, in about two seconds.

⚠️ It injects a large system prompt — roughly 27k input tokens even for a
one-line request. Fast and reliable, but not cheap per item; for very large
batches, weigh it against a local model.

### Claude subagents

Mechanical bulk work that must stay on Claude goes to Haiku. Fan-out is
capped and tracked — never fire-and-forget.

**Delegate WHAT, never HOW.** A subagent gets the outcome and picks its own
route. Handing it the URL to fetch, the search to run, or a numbered procedure
spends tokens writing instructions it could derive, and caps the result at the
delegator's guess instead of the agent's investigation. If you're writing
step 3, you're doing the work twice.

**You can route the routing.** Deciding *where* work goes is classification,
and classification is what small local models measurably do well — a 7B scored
12/12 on the benchmark above. On a long sweep, letting a local model pre-sort
items into "needs judgment" and "mechanical" costs nothing and keeps premium
tokens for the work rather than the dispatch. Review the split before acting on
it, same as any local output.

**Calling local models works. Running *on* one doesn't.** Your agent calling a
local model via `call_local.sh` is this skill's core path — proven, fast, with
receipts. What fails is replacing Claude Code's *own inference backend* with a
local server (`ANTHROPIC_BASE_URL`): protocol-compatible, but a large system
prompt costs ~42 s of prompt processing per call on a small local model and
Claude Code makes several calls per turn. Tested twice; never completed in
5 minutes. Calling local models, yes. Being one, no.

### Codex running on your local models (free)

```bash
codex exec --oss --local-provider ollama -m gemma4:e4b -s read-only \
  --skip-git-repo-check "task"
```

Codex's agent loop, tooling and sandbox on free local weights — verified at
zero API cost. **The local model must support thinking**: `qwen2.5:7b` fails
with `"does not support thinking"`, `gemma4:e4b` works. Check the
`capabilities` array in Ollama's `/api/tags` before routing here.

### Agents driving each other (MCP)

MCP is the common bus between these systems, and it runs both ways.

**Expose Codex to another agent.** `codex mcp-server` turns Codex into an MCP
server over stdio (protocol `2025-06-18`), offering two tools: `codex` to run a
session and `codex-reply` to continue a thread. Register it in the client's MCP
config — for Antigravity that's `~/.gemini/config/mcp_config.json`:

```json
{ "mcpServers": { "codex": {
    "command": "<absolute path to codex.exe>", "args": ["mcp-server"], "env": {} } } }
```

**Point Codex at someone else's tools.**

```bash
codex mcp list
codex mcp add chrome-devtools -- npx -y chrome-devtools-mcp@latest
```

Both directions were verified on real hardware: an Antigravity → Codex round
trip in 17.9 s, and 20+ Chrome DevTools browser tools exposed to Codex in
21.8 s.

⚠️ **Use the absolute path to the real executable, never a PATH shim.** On
Windows the `codex` entry on PATH is a `.cmd` wrapper, and stdio MCP clients
routinely fail to spawn it. This is the single most likely reason a bridge
silently doesn't work.

⚠️ **A call through a bridge spends the *callee's* quota.** Routing
Antigravity → Codex bills Codex, not Antigravity. That's useful when one meter
is tight — just be deliberate, and say which meter you're spending.

⚠️ **Registration is per-agent, not global.** Adding a server to Codex does not
make it appear in Antigravity or Claude Code — each keeps its own config
(`~/.codex/config.toml`, `~/.gemini/config/mcp_config.json`, `~/.claude.json`)
and each must be wired separately. What you reuse is the server itself, so the
second and third registrations are a one-line command rather than new work.
Never assume a tool is present just because another agent has it.

---

## 5. Calling a local model by hand

```bash
scripts/call_local.sh <base-url> <model> <prompt|-|file:PATH> [max_tokens]
```

```bash
# literal — fine for short prompts
scripts/call_local.sh http://localhost:11434 qwen2.5:7b "Reply with exactly: OK" 512

# from a file — use this for anything large
scripts/call_local.sh http://localhost:11434 qwen2.5:7b file:prompt.txt 2048

# from stdin — the natural form inside a batch loop
cat big.log | scripts/call_local.sh http://localhost:11434 qwen2.5:7b - 2048
```

**Use `-` or `file:` for real inputs.** A literal prompt has to fit in the OS
argument limit, and a batch input will exceed it: past ~32k, curl fails with
`Argument list too long`; through a `.cmd` shim the whole command line caps
near 8k with `The command line is too long.` Both fail loudly rather than
truncating — you won't get a quiet wrong answer — but the call simply won't
run. Reading a file or stdin has no such limit.

⚠️ **The file sigil is `file:PATH`, deliberately not `@PATH`.** Git Bash on
Windows expands a leading `@` as a *response file* before the script starts:
`@p.txt` containing "alpha beta gamma" arrives as three separate arguments and
silently shifts every argument after it.

It sends an Anthropic-format request to `<base-url>/v1/messages`, and falls
back to OpenAI-format `/v1/chat/completions` if the server says it doesn't
serve that endpoint (404, 405 or 501). The reply goes to stdout; a
`[receipt] in=<n> out=<n>` token line goes to stderr.

**Keep the receipt.** It's the evidence that a backend actually did the work.
Any claim the agent makes about offloading should be backed by one.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Reply on stdout |
| `1` | Transport, HTTP, or parse failure — details on stderr |
| `2` | Server replied 200 but the visible text was empty |

Exit `2` matters more than it looks. Reasoning-style models spend hidden
"thinking" tokens before visible output, so a small `max_tokens` can return
*nothing* while still being a valid HTTP 200. Treating that as success means a
batch job silently records empty answers. Give at least a few hundred tokens —
the script defaults to 1024.

### Timeouts

| Variable | Default | Covers |
|---|---|---|
| `CALL_LOCAL_CONNECT_TIMEOUT` | 5 s | establishing the connection |
| `CALL_LOCAL_TIMEOUT` | 300 s | the whole call |

A server that accepts the connection and then stalls will not hang the script
forever. Raise `CALL_LOCAL_TIMEOUT` for genuinely long generations.

### Picking the API dialect

`CALL_LOCAL_DIALECT` is `auto` by default: try Anthropic `/v1/messages`, fall
back to OpenAI `/v1/chat/completions` if the server answers 404, 405 or 501.
That's right for a local server, which either serves a dialect or doesn't.

**It's wrong for a gateway**, where the dialect depends on the *model*.
OpenCode Zen serves `/v1/messages` only for paid Claude models and answers
401/400 for everything else, while its free models work fine on
`/v1/chat/completions`. Those codes deliberately don't trigger a fallback — a
400 is usually a genuine bad request and retrying would hide it. So state the
dialect when you know it:

```bash
CALL_LOCAL_DIALECT=openai call_local.sh https://opencode.ai/zen \
  deepseek-v4-flash-free "Reply with exactly: OK" 200
```

Values: `auto` (default), `anthropic`, `openai`. Anything else is rejected
rather than guessed at.

### Concurrency

**Keep local calls to 1–2 at a time.** Local servers serialize or thrash under
parallel load, especially when requests force a model swap. Parallelism here
makes things slower, not faster.

### "Local" means the endpoint, not the machine

`call_local.sh` takes a base URL and has no localhost assumption, so **any**
Ollama-compatible endpoint works — including one on another computer:

```bash
call_local.sh http://192.168.1.50:11434 gemma-4-26b "..." 2048
```

That's the escape hatch when a model won't fit in your RAM: a box with more
memory can serve it over the LAN, no code change.

Two things to know before relying on it:

- **The serving machine needs configuring.** Ollama binds `127.0.0.1` by
  default and will refuse LAN connections until it's started with
  `OLLAMA_HOST=0.0.0.0` (and the firewall allows it). One config change on that
  box, not zero.
- ⚠️ **A remote endpoint is not private.** The privacy property comes from
  `localhost`, not from the word "local." Once the URL points elsewhere, your
  prompt leaves this machine and the same consent rule applies as for any cloud
  backend. The script enforces nothing — it posts wherever you point it.

---

## 6. `local-notes.md` — your machine's file

`references/local-notes.md` is the only place machine- and account-specific
facts live: which Codex model has quota, where `lms` actually is, how much RAM
you have, which local models are installed. `SKILL.md` stays generic so the
skill works anywhere; your notes hold everything that's true only of your
setup.

**It is git-ignored and never committed.** It describes one machine, so it has
no business in version control. Keeping it out means `git status` stays clean,
`git pull` never conflicts on it, and no stray `git add -A` can publish your
hardware or account details. The repo ships
`references/local-notes.example.md` as the template — copy it and edit the
copy.

**Every entry carries an as-of date.** Anything older than a month is a
hypothesis to re-verify, not a fact. When the agent learns a durable fact
during a session, it should offer to record it there with today's date.

---

## 7. What gets routed where

**Goes local first** — high volume, low stakes, mechanically checkable:
log and JSON triage, file summarization sweeps, test-data generation, format
conversion, classification and tagging, first-draft docstrings, commit-message
drafts, bulk renaming plans, extracting TODOs.

**Never routed to a local model or Codex without review:** architecture
decisions, security-sensitive code, final audit verdicts, anything that ships
unreviewed, and judgment calls you'll rely on.

**Not a fit at all:** single-item analysis, design work, security review, and
prose writing. The skill deliberately declines to trigger on those.

---

## 8. Choosing a local model

1. **Inventory first.** Prefer an installed model that fits — zero download.
2. **If nothing fits** (vision, stronger coding, longer context), pick the best
   current open model for the job. Research it rather than trusting stale
   knowledge; this landscape moves monthly.
3. **Respect the hardware.** Check free RAM/VRAM before choosing a size. A
   model that barely fits will thrash — prefer a quantization with headroom.
   With ~10 GB free, a 9 GB model is a bad idea and a 4.7 GB one is fine.
4. **Confirm before big downloads.** A multi-gigabyte pull needs your OK.
5. **Smoke-test after loading**, before routing real work at it.

Rough fit: general work → mid-size instruct model; code → a coder-tuned
variant; images → a VL model; long sweeps → whatever holds the largest stable
context on your hardware.

---

## 9. Grounding model choice in benchmarks

Which model belongs in which tier is a claim about capability, and a number
typed into prose six months ago is a fossil, not evidence. So the skill doesn't
store rankings — **it fetches them**:

```bash
scripts/benchmarks.sh --open              # best open-weights models
scripts/benchmarks.sh --measure coding    # code work specifically
scripts/benchmarks.sh --model deepseek    # one family
scripts/benchmarks.sh --limit 10          # how many rows (default 25)
scripts/benchmarks.sh --refresh           # refetch now, ignoring cache age
scripts/benchmarks.sh --list              # which measures are available
```

`scripts/benchmarks.sh --help` prints the same list. The full flag table,
including the two environment variables, is in `references/benchmarks.md`.

**Source: [Epoch AI's Benchmarking Hub](https://epoch.ai/benchmarks)** — a
non-profit research institute publishing under **CC-BY 4.0**. No account, no
API key, no redistribution restriction. The script caches the data and
**refetches whenever the cache is over a week old** (`BENCHMARKS_MAX_AGE_DAYS`),
falls back to the cache when offline and says so, and prints the required
attribution every run.

It matters here for one reason: **it scores open-weights models on the same
scale as proprietary ones**, with a `Model accessibility` column marking which
is which. So "is the local model good enough, or does this need a tier up?"
becomes a comparison instead of a judgment call.

### ⚠️ Open weights means downloadable, not runnable

The top open model on that list is 2.8 trillion parameters and needs 8× H200 to
serve. Reading the `--open` list top-down as a shortlist of things you can host
is the wrong inference. Three separate questions:

1. **Is it good?** — the benchmark data
2. **Can I run it?** — size against free RAM (a 17.99 GB model failed to load
   here at 17.5 GB free)
3. **Can I reach it another way?** — API providers, or Antigravity's free
   `gpt-oss-120b`

A big open model reached over someone else's API is a *licensing* win, not a
privacy one — the privacy rule applies to it exactly as it does to Codex.

**Benchmarks rank; they don't decide.** A measured result on your machine beats
a leaderboard — see the next section. Full method, the gated Artificial
Analysis alternative, and fallbacks:
[`references/benchmarks.md`](../references/benchmarks.md).

## 10. What we measured

On 2026-08-08 the same adversarial code audit was routed to the two cheaper
tiers, and every finding either backend produced was then checked by hand
against the source it was shown:

| Backend | Cost | Findings | Actually real | Time |
|---|---|---|---|---|
| Local 7B coder | $0 | 10 | ~1 | 72 s |
| Codex | 25,122 tokens | 6 | 5 | 34 s |

### And the same local model on work it suits

A real batch on the same day and machine: twelve log files, classify each as an
authentication failure, another error, or clean, with a known correct answer
for all twelve. Routed local-first through `call_local.sh`, one call at a time.

| Job | Backend | Result | Cost | Time |
|---|---|---|---|---|
| Adversarial code review | local 7B | ~1 of 10 findings real | $0 | 72 s |
| **Classify 12 logs** | local 7B | **12 / 12 correct** | **$0** | **27 s** |

All three authentication failures found, nothing invented, twelve receipts.

**That gap is the entire argument for the ladder.** A small local model is not
"worse AI" you tolerate to save money — it has one sharp edge and one blunt
one. On bulk mechanical work it is free and exact; on a judgment call it will
confidently invent things. Route to the edge that's sharp, and check its work.

The local model didn't merely miss things — it invented them. Two of its ten
findings were contradicted by the code in its own prompt: it reported a
missing usage message in a script that prints one, and an unhandled error case
handled two lines later.

**This is the argument for the whole design.** A small local model is useful
for bulk mechanical passes and unreliable at judgment. That's not a knock on
local models; it's the reason the ladder exists and the reason local output
gets reviewed.

---

## 11. Honest limits

**It does not enforce "local."** `call_local.sh` posts to whatever base URL you
give it. The name says local; nothing in the code makes it so. Point it at a
remote host and your prompt goes to that host. Keeping private material on
localhost is the caller's job — the skill states this plainly rather than
implying a guarantee it can't keep.

**A cloud sandbox is not your machine.** If your agent runs in a hosted
container, its `localhost` is the container's, not yours. The skill has an
explicit guard: if it starts a server and finds an empty model list while you
say you have models installed, it stops and tells you instead of "fixing" it
by downloading gigabytes into a sandbox that's about to vanish.

**Cold starts are slow.** The first call to an unloaded model includes load
time — 10–15 seconds is normal for a 5–9 GB model. Warm calls are much faster.
Budget for it on the first item of a sweep, not every item.

**Codex costs real quota.** Spending ChatGPT quota before Claude quota is a
preference, not a law. A Codex run costs ~10k+ tokens even for a trivial
prompt, so it shouldn't be looped carelessly.

---

## 12. Troubleshooting

**"no server reachable at ..."** — nothing is listening. Start Ollama, or run
`lms server start`. Fails in about 5 seconds rather than hanging.

**"timed out after Ns"** — the server accepted the connection then stalled, or
the generation is genuinely long. Raise `CALL_LOCAL_TIMEOUT`.

**"could not connect within Ns"** — different problem, different knob. The
connection never opened: wrong host or port, firewall, or the server isn't
running. Raising `CALL_LOCAL_TIMEOUT` will not help; check the URL first, then
`CALL_LOCAL_CONNECT_TIMEOUT` if the host is just slow to accept.

**Exit 2, empty reply** — a reasoning model spent its budget on hidden tokens.
Raise `max_tokens` to at least a few hundred; try 1024+.

**"server returned an error: ..."** — the server replied HTTP 200 with an
error body. The message is the server's own; usually a bad model name or an
overloaded server.

**Windows: `bash` is the wrong bash.** `bash` on the Windows `PATH` is usually
the WSL shim, which can't resolve `C:/` paths and — under WSL2 — has a
different `127.0.0.1` than your Windows-side servers. Use Git Bash
(`C:\Program Files\Git\bin\bash.exe`). The test suite finds it automatically;
anything you run by hand won't.

**The agent isn't using the skill.** Check the folder is named exactly
`multi-model-routing`, that `SKILL.md` sits at its top level, and that you've
started a new session since installing.

---

## 13. FAQ

**Do I need all four backends?**
No. It works with whatever you have. A missing backend is a one-line note
("Codex isn't installed — install it and I'll use it next time"), never a
blocker.

**Does this make my agent dumber?**
Only where it should. Grunt work moves down; reasoning, architecture, security
work and final review stay on premium Claude by rule. And local output is
always reviewed before it counts.

**Will it download models without asking?**
No. Multi-gigabyte pulls need your explicit OK, with the size and source
stated first.

**Does it work outside Claude Code?**
The routing policy is plain markdown, so any agent that reads a file can
follow it. Auto-discovery from `~/.claude/skills/` is Claude Code and Cowork
specific; elsewhere, paste the body of `SKILL.md` into your agent's system
prompt or `AGENTS.md`.

**Will it leave servers running?**
It stops what it started, and leaves alone anything that was already running.

---

## 14. Further reading

These are written for the agent and load on demand, but they're the deepest
material in the repo and readable on their own:

| File | What's in it |
|---|---|
| [`references/codex.md`](../references/codex.md) | Codex model selection **by capability**, the full CLI surface, and two cost traps that reverse the obvious choice |
| [`references/cross-agent.md`](../references/cross-agent.md) | How Claude Code, Codex and Antigravity find each other; every MCP bridge with its verification |
| [`references/local-backends.md`](../references/local-backends.md) | What Ollama and LM Studio verifiably do — tools, vision, embeddings, prompt caching, RAM limits |
| [`../CONTRIBUTING.md`](../CONTRIBUTING.md) | The evidence rule, argued from the defects this repo shipped by breaking it |
| [`DISCUSSIONS_SEED.md`](./DISCUSSIONS_SEED.md) | Six open questions from building this |

`SKILL.md` stays deliberately short — it loads into context every time the
skill triggers, so length there is a tax on every session. Depth lives here.

## 15. Removal

```bash
python3 install.py --uninstall            # everywhere it's installed
python3 install.py --uninstall --list     # preview first, changes nothing
python3 install.py --uninstall --app antigravity
python3 install.py --uninstall --project DIR
```

**Your `local-notes.md` is preserved**, copied to
`multi-model-routing.local-notes.backup.md` beside where the skill was, and the
path is printed. Those are your measured machine facts — the uninstaller won't
throw them away. Repeat uninstalls get `.backup.2.md`, `.backup.3.md` and so
on; **an existing backup is never overwritten**, because the one it would
overwrite is the one holding everything you'd learned.

Two refusals protect you:

- **No `SKILL.md` in the directory** → nothing is deleted, so a mistyped
  `--project` can't take out something unrelated.
- **A `.git`/`.hg`/`.svn` directory is present** → nothing is deleted. If you
  installed by cloning (the documented personal install), the install *is* your
  git working copy, and removing it would delete your repository history —
  including commits you haven't pushed. Uninstall says so and stops. Remove it
  with git, or delete the directory yourself once you're sure.

Every install carries its own `install.py`, so you can uninstall from the
install itself without going back to the original clone.

By hand works just as well:

```bash
rm -rf ~/.claude/skills/multi-model-routing
```

Nothing else is installed anywhere — no config edits, no background services,
no registry entries. Removing the folder fully uninstalls it.

**MCP servers are separate.** If you registered Codex with an agent
(`claude mcp add codex …`, or an entry in `mcp_config.json`), that registration
lives in the agent's own config and survives uninstalling this skill. Remove it
with that agent's tooling if you want it gone.
