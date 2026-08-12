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

## 2. Call a compatible local endpoint

`scripts/call_local.sh` accepts a base URL, model identifier, prompt, and token
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

If using an agent loop over local weights, query the installed CLI's live help
for supported local-provider values and pass the engine chosen by the
inventory rule. Verify that the selected model supports the loop's required
reasoning/tool capabilities before starting a long run.

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
