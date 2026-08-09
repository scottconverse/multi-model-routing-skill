# Local backends — verified capabilities

What Ollama and LM Studio can actually do, established by live calls on
2026-08-08. Anything not listed here has not been tested; treat it as unknown
rather than assuming.

---

## 1. Both speak the Anthropic Messages API

Not just OpenAI-compatible — both serve `/v1/messages` well enough to drive a
real agent loop:

| Capability | Ollama | LM Studio |
|---|---|---|
| text + correct `stop_reason` | ✅ | ✅ |
| top-level `system` prompt (honored) | ✅ | ✅ |
| `tool_use` block + `stop_reason=tool_use` | ✅ | ✅ |
| streaming SSE (`message_start`, `content_block_delta`, …) | ✅ | ✅ |
| `/v1/messages/count_tokens` | ❌ 404 | ❌ |
| prompt caching (`cache_read_input_tokens` in usage) | — | ✅ observed |

`scripts/call_local.sh` tries `/v1/messages` first for exactly this reason. On
this machine the OpenAI fallback never fires — both servers answer the
Anthropic path — so that branch is only exercised by the test suite's mocks.

**Tool support is a property of the MODEL, not the server.** A coder-tuned
model may have no tool training at all: `qwen2.5-coder-7b-instruct` returned
plain text for a tool request under *both* dialects, while `gemma-4-12b` on the
same server emitted a correct `tool_use` block. If tools appear unsupported,
change the model before blaming the server.

---

## 2. Ask for plain text, not JSON schema

Measured on one model and one prompt:

| Output mode | Accuracy | Notes |
|---|---|---|
| Constrained plain text ("answer with ONE word") | **12/12** | the real batch run |
| Ollama native `format` schema, single enum field | 1 of 3 wrong | no degeneration, still less accurate |
| Same schema plus a free-text `string` field | wrong **and** degenerate | 600-token repeat loop |

Schema-forcing costs accuracy at 7B, and free-text string fields inside a
schema are what trigger runaway repetition. Parse one-word replies yourself, or
route structured work to a tier that handles it — `agy --json-schema` or
`codex --output-schema`.

---

## 3. Vision

*Verified:* `qwen2.5vl:3b` via `/v1/messages` with a base64 image block
correctly read a two-band test image ("Red, Blue"), 1,099 input tokens for a
120×60 PNG.

```json
{"role":"user","content":[
  {"type":"image","source":{"type":"base64","media_type":"image/png","data":"<b64>"}},
  {"type":"text","text":"..."}]}
```

Images are expensive in input tokens relative to their size — budget for it on
a batch, and downscale before sending.

## 4. Embeddings

*Verified:* `text-embedding-nomic-embed-text-v1.5` on LM Studio,
`POST /v1/embeddings`, returns 768-dimensional vectors. Cosine similarity
behaved sensibly — "auth failure" vs "login denied" **0.614**, vs "disk full"
**0.349**.

Useful and almost free for the mechanical half of batch work: dedupe near
identical records, cluster before summarizing, or pre-filter a large set down
to what actually needs a model call. 84 MB on disk, negligible RAM.

---

## 5. Codex can drive both (`--oss`)

| Provider | Result | Cost | Time |
|---|---|---|---|
| `ollama` (`gemma4:e4b`) | ✅ | 9,479 tokens, $0 API | 2 m 11 s |
| `lmstudio` (`gemma-4-12b-it-qat@q4_k_xl`) | ✅ | 17,242 tokens, $0 API | 4 m 9 s |

Both work. **The model must support thinking** — `qwen2.5:7b` fails outright
with `"does not support thinking"`. Check the `capabilities` array from
Ollama's `/api/tags`.

Ollama was roughly twice as fast for half the tokens here, so prefer it for
`--oss` unless you specifically need a model only LM Studio has. Either way
this is far slower than a direct `call_local.sh` call — you're paying for a
full agent loop. Use it when you want Codex's tooling and sandboxing on free
weights, not for simple one-shot prompts.

---

## 6. RAM discipline

Free RAM is the real constraint, not disk. Measured here: 25.8 GB total, and
free RAM swung between 3.0 GB and 14.0 GB during a single session depending on
what was loaded.

- Check free RAM before choosing a size; a model that barely fits will thrash.
- `lms unload --all` frees LM Studio's held models; it recovered 7.7 GB in one
  step during testing.
- LM Studio JIT-loads: `lms ps` can show nothing loaded while the server still
  answers, because it loads on first request. That's why a first call is slow.
- Cold start is real — 10–15 s for a 5–9 GB model, and one Antigravity model
  took 60 s cold. Budget for it on the first item of a sweep, not every item.
