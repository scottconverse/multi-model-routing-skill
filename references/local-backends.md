# Local engines — endpoint and inventory guidance

This reference keeps the local-model path engine-neutral. Do not assume a
particular local LLM engine; use the engine discovery and model-inventory
rules below with whatever is installed on the machine.

## 1. Discover the largest usable local inventory

1. Enumerate the local engines exposed by the machine using their native CLI,
   API, or other live discovery mechanism. Do not scan the network for remote
   endpoints.
2. For each engine under consideration, collect its reachable model list and
   capability metadata. Count only models that fit the available hardware and
   could satisfy the current task.
3. Select the engine with the largest usable model inventory. Then choose the
   best task-fit model from that engine. If the selected engine cannot provide
   a suitable model, fall back to the next-largest usable inventory.
4. Smoke-test the selected model with a constrained one-word prompt before
   routing real work. Cache the proven roster for the rest of the session.

Installed on disk does not necessarily mean available: the engine may be
stopped, the model may not fit in RAM/VRAM, or the model may lack the required
capability. Count a model only after the engine can list it and the model has
passed the smoke test.

## 2. Choose the one-shot or tool-loop lane

Use `scripts/call_local.sh` when one model response is enough. It accepts a
base URL, model identifier, prompt, and token
limit. It first tries the Anthropic Messages endpoint and falls back to the
OpenAI Chat Completions endpoint when the selected engine reports that the
first path is unsupported. If the engine requires a particular dialect, set
`CALL_LOCAL_DIALECT=anthropic` or `CALL_LOCAL_DIALECT=openai` explicitly.

```bash
scripts/call_local.sh <BASE_URL> <MODEL> "Reply with exactly: OK" 512
```

Use `-` or `file:PATH` for large prompts so the input does not pass through the
operating system's argument-length limit. Keep the `[receipt]` line printed
on stderr; it is evidence that the call actually happened.

Use `scripts/local_agent.py` when the model must inspect the working tree and
decide which tool to call next across multiple rounds:

```bash
python scripts/local_agent.py --model <MODEL> --task "<TASK>" --cwd <DIR> \
  [--max-steps N] [--read-only] [--base-url URL] [--no-sdk]
```

The primary route is LM Studio's SDK and `LLM.act()`. On first SDK use, the
script creates `scripts/.venv-local-agent` and installs the `lmstudio` package
there. The fallback (`--no-sdk`) is a stdlib-only OpenAI
`/v1/chat/completions` tool loop. Its base URL defaults to
`http://localhost:1234`; override it with `--base-url` or
`LOCAL_AGENT_BASE_URL` for another compatible server. If that endpoint needs a
bearer token, prefer `LOCAL_AGENT_API_KEY` over putting it on the command line.
A custom base URL selects the raw route automatically because the LM Studio SDK
uses a separate application API.

By default the harness exposes `read_file`, `list_dir`, `grep`, `run_command`,
and `write_file`, so the model can read, run tests, and apply fixes.
`run_command` is unrestricted — it runs exactly what it is given through the
shell, so chaining and redirection work, and there is no allowlist or
destructive-command block (removed 2026-08-16 by owner directive; see below for
the standing of that decision). Every tool path IS confined to `--cwd` by
default (restored 2026-08-16 by audit) — a resolved path outside it is refused
(`ToolError`, visible to the model and logged) rather than executed;
`--allow-outside-cwd` opts back into the old unbounded resolution. `--read-only`
narrows the exposed tool set to the three read tools, for an analysis run that
provably cannot modify anything; `--max-steps` bounds the loop. Run untrusted
work in a disposable `--cwd` copy and set `LOCAL_AGENT_LOG=<file>` to capture a
JSONL audit trail of every tool call, including rejected ones. It prints token
usage for every step and a final `[receipt]` total on stderr — keep those
lines: the per-step accounting satisfies the skill's receipts rule.

**Why the command guards are still unguarded, and why that claim is weaker than
it was (safety lab, 2026-08-16; audit, 2026-08-16).** A per-command nanny was
tested against a trap gauntlet and removed: it blocked a correct fix the model
could not apply, while the *unguarded* model completed the task and, on its own
judgment, refused a prompt-injection instruction embedded in a data file,
declined to exfiltrate a secrets file, and left a booby-trapped script alone.
That was read at the time as proof the guard was pure friction. An audit found
the run does not support that: it was one unblinded sample, and it was
confounded — the same commit that removed the guards also added the
`write_file` tool (which did not exist before that commit) and fixed a silent
`run_command` quoting bug that had been discarding output, so either of those
changes alone could explain the run succeeding where an earlier, guarded run
did not. The guards were never isolated as the variable. They stay removed
pending an isolated re-run; the `--cwd` boundary above is restored regardless,
because a filesystem escape is not something the confound excuses. The record
is the `LOCAL_AGENT_LOG` trail on unattended runs.

The endpoint can be on another machine, but a non-localhost endpoint is not
private. The privacy property comes from the prompt staying on the local
machine, not from the label "local." Ask for explicit approval before sending
sensitive material to a remote endpoint, and never scan the network looking
for one.

## 3. Capability checks

Tool support, vision, structured output, embeddings, context length, and
reasoning support are properties of the model and engine combination. Read
the selected engine's live metadata and documentation rather than inferring
capabilities from the model name.

For small local models, ask for constrained plain text instead of forcing a
JSON schema unless schema support has been verified. Parse one-word or
line-oriented replies yourself, or route schema-sensitive work to a tier that
has proven structured-output support.

For an agent loop, use `local_agent.py` and verify that the selected model can
emit OpenAI-style tool calls before starting a long run. Do not treat
`codex --oss` as the default loop: it is known-fragile on models whose chat
templates reject system messages inserted after the conversation begins. The
resulting Jinja error (`System message must be at the beginning`) prevents the
loop from running at all.

## 4. RAM, latency, and concurrency

- Check free RAM/VRAM immediately before loading a model. Leave headroom for
  the operating system, context, and generation; a model that barely fits can
  thrash or time out.
- Expect a cold-start delay when the engine loads a model. Budget that delay
  once at the start of a batch rather than assuming every call costs the same.
- Keep local calls to one or two at a time unless the selected engine has been
  tested under higher concurrency. Model swaps and parallel generations can
  saturate memory and make a batch slower.
- Stop only servers or processes started by the current task. Leave anything
  already running alone.

Local output is raw material. Review it before it becomes a shipped answer,
code change, or final judgment.
