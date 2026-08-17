#!/usr/bin/env python3
"""local_agent.py -- bounded, tool-using agent loop for local models.

By default this talks to LM Studio on http://localhost:1234. A different
OpenAI-compatible server root can be supplied with --base-url or the
LOCAL_AGENT_BASE_URL environment variable. A non-localhost URL is not private;
the operator is responsible for approving where task data is sent.

ROUTE: primary route is the `lmstudio` Python SDK's agentic API,
`LLM.act(prompt, tools=[...])`: multi-round tool calls, clean per-round stats
(prompt/predicted/total tokens, stop reason) via the
on_prediction_completed callback, and automatic
"show the model its tool error, let it retry next round" behavior baked into
the SDK (a failed/invalid tool call becomes a tool-result message instead of
crashing the loop). If the SDK can't be imported/bootstrapped (e.g. no
network to pip-install it), the script automatically falls back to a plain
OpenAI-format tool loop hand-rolled against POST /v1/chat/completions, which
works with compatible servers that implement OpenAI chat-completions tool
calls. Outer CLI behavior is identical either way. Supplying a non-default
base URL selects the raw route automatically because the LM Studio SDK uses
its own application API rather than the OpenAI-compatible HTTP endpoint.

CONCURRENCY: keep to one loop per local server unless that server has been
verified under parallel load. Local inference commonly serializes or thrashes,
especially when concurrent requests force model swaps.

Usage:
    python local_agent.py --model <id> --task "..." \
        [--cwd DIR] [--max-steps N] [--allow-write] [--base-url URL] [--no-sdk]

Setup: this script is self-bootstrapping. On first run (or whenever the
`lmstudio` package is missing) it creates a venv at scripts/.venv-local-agent
next to this file via `uv venv` + `uv pip install lmstudio`, then re-execs
itself under that venv's interpreter. You do not need to activate anything
by hand; `python local_agent.py ...` from any Python (or `uv run
local_agent.py ...`) works. One-line manual setup if you'd rather do it
yourself:
    uv venv scripts/.venv-local-agent && uv pip install --python scripts/.venv-local-agent lmstudio

Exit codes: 0 only when the model reaches a model-declared final answer
(no further tool calls requested). Non-zero on step-budget exhaustion or a
genuine error -- see the printed summary for which.
"""

from __future__ import annotations

import argparse
import functools
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

LM_STUDIO_BASE_URL = "http://localhost:1234"
DEFAULT_BASE_URL = os.environ.get("LOCAL_AGENT_BASE_URL", LM_STUDIO_BASE_URL)
DEFAULT_API_KEY = os.environ.get("LOCAL_AGENT_API_KEY", "")

# --------------------------------------------------------------------------
# Self-bootstrap: ensure we're running under a venv that has `lmstudio`
# installed. Pure-stdlib only above this point.
# --------------------------------------------------------------------------

SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
VENV_DIR = SCRIPT_DIR / ".venv-local-agent"
VENV_PY = VENV_DIR / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _find_uv() -> str | None:
    uv = shutil.which("uv")
    if uv:
        return uv
    candidate = Path.home() / ".local" / "bin" / ("uv.exe" if os.name == "nt" else "uv")
    return str(candidate) if candidate.exists() else None


def _bootstrap_venv() -> bool:
    """Create scripts/.venv-local-agent and install `lmstudio` into it.

    Returns True on success, False if uv is unavailable or install failed
    (caller falls back to the raw HTTP loop in that case).
    """
    uv = _find_uv()
    if uv is None:
        print(
            "[bootstrap] uv not found on PATH or in ~/.local/bin -- cannot "
            "auto-install the lmstudio SDK. Falling back to the raw HTTP loop.",
            file=sys.stderr,
        )
        return False
    try:
        if not VENV_PY.exists():
            print(f"[bootstrap] creating venv at {VENV_DIR}", file=sys.stderr)
            subprocess.run([uv, "venv", str(VENV_DIR)], check=True)
        print("[bootstrap] installing lmstudio SDK into venv", file=sys.stderr)
        subprocess.run(
            [uv, "pip", "install", "--python", str(VENV_PY), "lmstudio"], check=True
        )
        return True
    except subprocess.CalledProcessError as exc:
        print(f"[bootstrap] failed: {exc}. Falling back to the raw HTTP loop.", file=sys.stderr)
        return False


def _ensure_sdk_or_reexec(no_sdk: bool) -> bool:
    """Return True if `lmstudio` is importable in THIS process.

    If we're not yet running under the venv python and the SDK isn't
    importable here, try to bootstrap the venv and re-exec this same script
    under it. If bootstrap fails or --no-sdk was passed, return False so the
    caller uses the raw HTTP fallback loop instead.
    """
    if no_sdk:
        return False
    try:
        import lmstudio  # noqa: F401

        return True
    except ImportError:
        pass

    already_in_venv = False
    try:
        already_in_venv = Path(sys.executable).resolve() == VENV_PY.resolve()
    except OSError:
        pass
    if already_in_venv:
        # We're already in the venv and it still can't import lmstudio --
        # something is wrong with the venv itself. Don't loop; fall back.
        return False

    if _bootstrap_venv() and VENV_PY.exists():
        print(f"[bootstrap] re-executing under {VENV_PY}", file=sys.stderr)
        result = subprocess.run([str(VENV_PY), str(SCRIPT_PATH), *sys.argv[1:]])
        sys.exit(result.returncode)
    return False


# --------------------------------------------------------------------------
# Shared tool implementations (used by both the SDK route and the raw loop)
# --------------------------------------------------------------------------

TRUNCATE_LIMIT = 4000

# Some local models (observed on qwen/qwen3.8-27b) emit hidden "thinking"
# text inline in the same string as the visible answer, delimited by this
# internal LM Studio sentinel. Strip everything up to and including it so
# only the actual answer is treated as the final text.
_REASONING_SENTINEL_RE = re.compile(
    r".*?__LM_STUDIO_INTERNAL_LSEP_SYNTHETIC_REASONING_END_[0-9a-f]+__", re.DOTALL
)


def _strip_reasoning(text: str) -> str:
    return _REASONING_SENTINEL_RE.sub("", text, count=1).strip()

def _audit_log(step, fn, call_args, out):
    """Optional audit trail: if the LOCAL_AGENT_LOG env var names a file, append
    every tool call and its result there as one JSON line. Off unless set. Now
    that the harness is unguarded, this is the record of exactly what a local
    model did -- keep it on for unattended runs you want to review afterward."""
    path = os.environ.get("LOCAL_AGENT_LOG")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "step": step, "tool": fn, "args": call_args,
                "result": out if isinstance(out, str) else str(out),
            }, ensure_ascii=False) + "\n")
    except OSError:
        pass

# The command guards -- a destructive-command blocklist, a read-only command
# allowlist, and a chain/redirection block -- were REMOVED 2026-08-16 by owner
# directive, and the --cwd PATH boundary was removed as a default by a later
# owner directive the same day. This harness runs on the owner's own hardware
# against trusted local models the owner has directed to run freely; run_command
# executes exactly what it is given and tool paths resolve anywhere by default.
#
# The path boundary is available as an opt-in (--confine-cwd) but is OFF unless
# asked for. The read/write TOOL boundary (see make_tools and --read-only) still
# governs which categories of action are exposed; run_command, when exposed,
# executes exactly what it is given, through the shell, with real chaining and
# redirection.


class ToolError(Exception):
    """Raised by a tool implementation; the message is shown back to the model."""


class ConfinedCwd:
    """Resolves tool paths relative to the working root. The root is NOT a
    boundary by default (owner directive, 2026-08-16): resolve() returns paths
    anywhere on the filesystem. Construct with allow_outside=False (the
    harness's --confine-cwd flag) to opt into the hard boundary, in which case
    resolve() refuses (raises ToolError) any path outside `root`."""

    def __init__(self, root: Path, allow_outside: bool = True):
        self.root = root.resolve()
        self.allow_outside = allow_outside

    def resolve(self, rel: str) -> Path:
        candidate = Path(rel)
        resolved = (candidate if candidate.is_absolute() else self.root / candidate).resolve()
        if not self.allow_outside:
            try:
                resolved.relative_to(self.root)
            except ValueError:
                raise ToolError(
                    f"Refused: {rel!r} resolves to {resolved}, which is "
                    f"outside the confined working directory {self.root}. "
                    f"Pass --allow-outside-cwd to the harness to permit paths "
                    f"outside --cwd."
                )
        return resolved


def _truncate(text: str, limit: int = TRUNCATE_LIMIT) -> str:
    if len(text) <= limit:
        return text
    omitted = len(text) - limit
    return text[:limit] + f"\n...[truncated, {omitted} more characters omitted]"


def make_tools(confined: ConfinedCwd, read_only: bool):
    """Build the tool implementations bound to the working directory.

    Read-only runs (--read-only) expose only read_file, list_dir, and grep, so
    the agent provably cannot modify anything -- useful for review/analysis.
    The default (full) run also exposes run_command and write_file, both
    unrestricted; that is the mode for real work."""

    def read_file(path: str, start_line: int = 0, end_line: int = 0) -> str:
        """Read a text file. `path` is relative to the working directory
        (or an absolute path).
        If start_line and end_line are both given (1-indexed, inclusive),
        only that line range is returned; otherwise the whole file is
        returned (truncated if very large)."""
        p = confined.resolve(path)
        if not p.exists():
            raise ToolError(f"File not found: {path}")
        if not p.is_file():
            raise ToolError(f"Not a file: {path}")
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        except OSError as exc:
            raise ToolError(f"Could not read {path}: {exc}")
        if start_line and end_line:
            lo = max(1, start_line)
            hi = min(len(lines), end_line)
            content = "".join(lines[lo - 1 : hi])
        else:
            content = "".join(lines)
        return _truncate(content)

    def list_dir(path: str = ".") -> str:
        """List the immediate contents (files and subdirectories) of a
        directory inside the working directory. `path` defaults to the
        working directory root."""
        p = confined.resolve(path)
        if not p.exists():
            raise ToolError(f"Directory not found: {path}")
        if not p.is_dir():
            raise ToolError(f"Not a directory: {path}")
        entries = []
        for child in sorted(p.iterdir(), key=lambda c: (c.is_file(), c.name.lower())):
            kind = "dir" if child.is_dir() else "file"
            size = "" if child.is_dir() else f" ({child.stat().st_size}B)"
            entries.append(f"{kind}\t{child.name}{size}")
        return _truncate("\n".join(entries) if entries else "(empty directory)")

    def grep(pattern: str, path: str = ".", glob: str = "") -> str:
        """Search for a regex pattern in files under `path` (relative to the
        working directory). Uses ripgrep if available on PATH, otherwise a
        pure-Python fallback. `glob` optionally restricts to matching
        filenames (e.g. "*.py")."""
        p = confined.resolve(path)
        if not p.exists():
            raise ToolError(f"Path not found: {path}")
        rg = shutil.which("rg")
        if rg:
            cmd = [rg, "-n", "--no-heading", pattern, str(p)]
            if glob:
                cmd[1:1] = ["--glob", glob]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            out = proc.stdout or proc.stderr
            if not out.strip():
                return "(no matches)"
            return _truncate(out)
        # Pure-Python fallback
        try:
            rx = re.compile(pattern)
        except re.error as exc:
            raise ToolError(f"Invalid regex {pattern!r}: {exc}")
        matches = []
        files_iter = [p] if p.is_file() else p.rglob(glob or "*")
        for f in files_iter:
            if not f.is_file():
                continue
            try:
                # relative_to raises ValueError when f falls outside
                # confined.root -- the common case now that the boundary is off
                # by default, and also reachable via a symlink under --confine-cwd.
                # Skip rather than crash the whole grep run over one file's path.
                rel = f.relative_to(confined.root)
            except ValueError:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), start=1):
                if rx.search(line):
                    matches.append(f"{rel}:{i}:{line}")
                    if len(matches) >= 500:
                        break
            if len(matches) >= 500:
                break
        return _truncate("\n".join(matches) if matches else "(no matches)")

    def run_command(command: str) -> str:
        """Run a shell command in the working directory. Executes exactly what
        it is given, through the system shell, so chaining (&&, |, ;) and
        redirection (>, <) all work. No allowlist and no destructive-command
        block -- the caller is trusted. Times out after 120s. Only exposed when
        the harness is NOT in --read-only mode."""
        stripped = command.strip()
        if not stripped:
            raise ToolError("Empty command.")
        try:
            # Pass the command STRING (shell=True), never a ["cmd","/c",str]
            # list: Windows list-quoting mangles nested quotes and silently
            # ate the output of e.g. python -c "print('x')" (fixed 2026-08-16).
            proc = subprocess.run(
                stripped,
                shell=True,
                cwd=str(confined.root),
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            raise ToolError("Command timed out after 120s.")
        out = proc.stdout
        if proc.returncode != 0:
            out += f"\n[exit code {proc.returncode}]\n{proc.stderr}"
        return _truncate(out if out.strip() else "(no output)")

    def write_file(path: str, content: str) -> str:
        """Create or overwrite a text file with `content`. `path` is relative
        to the working directory (or absolute). Parent directories are created
        as needed. Only exposed when the harness is NOT in --read-only mode."""
        p = confined.resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        # newline="" disables universal-newline translation on write, so an LF
        # `content` string is written back byte-exact instead of Python's
        # default text-mode write silently turning \n into \r\n on Windows.
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.write(content)
        return f"Wrote {len(content)} characters to {p}"

    if read_only:
        return [read_file, list_dir, grep]
    return [read_file, list_dir, grep, run_command, write_file]


OPENAI_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read a text file inside the working directory. path is relative "
                "to the confined working directory. If start_line and end_line are "
                "both given (1-indexed, inclusive), only that range is returned."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List the immediate contents of a directory inside the working directory.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": (
                "Search for a regex pattern in files under path. Uses ripgrep if "
                "available, else a Python fallback. glob optionally restricts filenames."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string"},
                    "glob": {"type": "string"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Run a shell command in the working directory. Runs exactly what "
                "you give it, through the shell -- chaining (&&, |, ;) and "
                "redirection (>, <) work. Use it to run tests, git, build steps, "
                "or any tool. 120s timeout."
            ),
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Create or overwrite a text file with the given content. Parent "
                "directories are created as needed. Use this to apply code fixes "
                "and write new files."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "You are a local coding/research assistant running fully offline. Use the "
    "provided tools to investigate the working directory and complete the "
    "task: read_file, list_dir, and grep to read; run_command to run tests, "
    "git, or any shell command; write_file to apply fixes and create files. "
    "(In read-only mode only the read tools are available.) When the task is "
    "complete, reply with plain text and no further tool calls. Be concise and "
    "factual -- if a requested file does not exist, say so plainly rather than "
    "guessing its contents."
)


# --------------------------------------------------------------------------
# Route A: lmstudio SDK's LLM.act()
# --------------------------------------------------------------------------


def run_sdk_loop(args, confined: ConfinedCwd) -> int:
    import lmstudio as lms

    # Give the SDK plain callables; it derives name/schema from type hints
    # and the whole docstring as description (verified via inspect.getsource
    # of ToolFunctionDef.from_callable during development). make_tools returns
    # only the read tools in --read-only mode, all of them otherwise.
    tools = make_tools(confined, args.read_only)

    model = lms.llm(args.model)

    totals = {"prompt": 0, "predicted": 0, "total": 0}
    state = {"round": None, "final_text": None, "malformed_streak": 0}

    def _current_step():
        return state["round"]["index"] if state["round"] else None

    def _audited(fn):
        """Wrap a tool implementation so every call -- success or failure --
        is written to LOCAL_AGENT_LOG. This is the SDK lane's audit trail
        (fix: _audit_log was previously wired only into run_raw_loop, so the
        default lane never logged anything). functools.wraps preserves the
        signature and docstring the SDK inspects to build the tool schema."""

        @functools.wraps(fn)
        def wrapper(*call_args, **call_kwargs):
            step = _current_step()
            try:
                result = fn(*call_args, **call_kwargs)
            except (ToolError, TypeError) as exc:
                _audit_log(step, fn.__name__, call_kwargs, f"ERROR: {exc}")
                raise
            _audit_log(step, fn.__name__, call_kwargs, result)
            return result

        return wrapper

    tools = [_audited(fn) for fn in tools]

    def on_round_start(round_index: int) -> None:
        state["round"] = {"index": round_index, "tools": [], "stats": None}

    def on_prediction_completed(result) -> None:
        stats = result.stats
        r = state["round"]
        r["stats"] = stats
        p = stats.prompt_tokens_count or 0
        d = stats.predicted_tokens_count or 0
        t = stats.total_tokens_count or (p + d)
        totals["prompt"] += p
        totals["predicted"] += d
        totals["total"] += t

    def on_message(msg) -> None:
        cls = type(msg).__name__
        r = state["round"]
        if cls == "AssistantResponse":
            tool_names = []
            text_parts = []
            for item in msg.content:
                iname = type(item).__name__
                if iname == "ToolCallRequestData":
                    tool_names.append(item.tool_call_request.name)
                elif iname == "TextData":
                    text_parts.append(item.text)
            if tool_names:
                r["tools"].extend(tool_names)
                stats = r["stats"]
                p = stats.prompt_tokens_count if stats else "?"
                d = stats.predicted_tokens_count if stats else "?"
                print(
                    f"[step {r['index']}] tool_call(s)={tool_names} "
                    f"tokens(in={p},out={d})",
                    file=sys.stderr,
                )
            else:
                state["final_text"] = _strip_reasoning("\n".join(text_parts))
                stats = r["stats"]
                p = stats.prompt_tokens_count if stats else "?"
                d = stats.predicted_tokens_count if stats else "?"
                print(
                    f"[step {r['index']}] final answer tokens(in={p},out={d})",
                    file=sys.stderr,
                )

    def handle_invalid_tool_request(exc, request) -> str | None:
        state["malformed_streak"] += 1
        name = getattr(request, "name", "?")
        # Named call_kwargs, not args: this closure shares a scope with
        # run_sdk_loop's own `args` (the CLI Namespace) and a same-named
        # local would only shadow it here, but the collision is confusing to
        # read even though it can't mutate the outer value.
        call_kwargs = dict(getattr(request, "arguments", None) or {})
        error_text = f"Invalid tool call for {name!r}: {exc}"
        print(
            f"[step {state['round']['index'] if state['round'] else '?'}] "
            f"MALFORMED tool call (attempt {state['malformed_streak']}) "
            f"tool={name!r}: {exc}",
            file=sys.stderr,
        )
        # exc.__cause__ is set only when this callback fires because a tool
        # IMPLEMENTATION raised (see _audited above) -- that case is already
        # logged there, with the real call kwargs. Log here only the cases
        # that never reached a tool implementation at all: unknown tool name,
        # arguments that failed schema parsing, or a tool call the model
        # emitted that could not even be parsed (request is None). That is
        # the injection/rejection evidence this audit trail exists for.
        if getattr(exc, "__cause__", None) is None:
            _audit_log(_current_step(), name, call_kwargs, f"REJECTED: {error_text}")
        # Returning the error message (rather than None/raising) feeds it back
        # to the model as the tool result, so it gets one more round to
        # correct itself -- the step budget is the hard backstop.
        return error_text

    from lmstudio import LMStudioPredictionError

    chat = lms.Chat(SYSTEM_PROMPT)
    chat.add_user_message(args.task)

    start = time.time()
    try:
        result = model.act(
            chat,
            tools=tools,
            max_prediction_rounds=args.max_steps,
            on_round_start=on_round_start,
            on_prediction_completed=on_prediction_completed,
            on_message=on_message,
            handle_invalid_tool_request=handle_invalid_tool_request,
        )
    except LMStudioPredictionError as exc:
        if "final prediction round" in str(exc):
            elapsed = time.time() - start
            print(
                f"\n=== STEP BUDGET EXHAUSTED ({args.max_steps} steps, {elapsed:.1f}s) ===",
                file=sys.stderr,
            )
            print(
                "The model still wanted to call a tool when the step budget ran "
                "out. Honest summary: no final answer was reached.",
                file=sys.stdout,
            )
            print(
                f"[receipt] total tokens in={totals['prompt']} out={totals['predicted']} "
                f"sum={totals['total']}",
                file=sys.stderr,
            )
            return 1
        raise

    elapsed = time.time() - start
    print(f"\n=== DONE ({result.rounds} rounds, {elapsed:.1f}s) ===", file=sys.stderr)
    print(
        f"[receipt] total tokens in={totals['prompt']} out={totals['predicted']} "
        f"sum={totals['total']}",
        file=sys.stderr,
    )
    if state["final_text"]:
        print(state["final_text"])
        return 0
    print(
        "[warn] loop ended with no tool calls pending but no final text was "
        "captured -- printing nothing further.",
        file=sys.stderr,
    )
    return 0


# --------------------------------------------------------------------------
# Route B: raw OpenAI-format /v1/chat/completions loop (fallback)
# --------------------------------------------------------------------------


def _post_chat_completions(base_url: str, payload: dict, api_key: str = "") -> dict:
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(
        f"{base_url}/v1/chat/completions",
        data=data,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {base_url}: {body}")


def run_raw_loop(args, confined: ConfinedCwd) -> int:
    impls = {fn.__name__: fn for fn in make_tools(confined, args.read_only)}
    active_schemas = [
        s for s in OPENAI_TOOL_SCHEMAS if s["function"]["name"] in impls
    ]

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": args.task},
    ]

    totals = {"prompt": 0, "predicted": 0}
    final_text = None
    last_malformed_signature = None
    start = time.time()

    for step in range(args.max_steps):
        payload = {
            "model": args.model,
            "messages": messages,
            "tools": active_schemas,
            "tool_choice": "auto",
            "max_tokens": 2000,
        }
        resp = _post_chat_completions(args.base_url, payload, args.api_key)
        usage = resp.get("usage", {})
        p_tok = usage.get("prompt_tokens", 0)
        d_tok = usage.get("completion_tokens", 0)
        totals["prompt"] += p_tok
        totals["predicted"] += d_tok

        choice = resp["choices"][0]
        message = choice["message"]
        tool_calls = message.get("tool_calls") or []

        if not tool_calls:
            final_text = _strip_reasoning(message.get("content") or "")
            print(
                f"[step {step}] final answer tokens(in={p_tok},out={d_tok})",
                file=sys.stderr,
            )
            messages.append(message)
            break

        messages.append(message)
        names = [tc["function"]["name"] for tc in tool_calls]
        print(
            f"[step {step}] tool_call(s)={names} tokens(in={p_tok},out={d_tok})",
            file=sys.stderr,
        )

        for tc in tool_calls:
            fn = tc["function"]["name"]
            raw_args = tc["function"].get("arguments", "{}")
            tool_call_id = tc.get("id", fn)
            try:
                call_args = json.loads(raw_args) if raw_args else {}
            except json.JSONDecodeError as exc:
                signature = (fn, "json_error")
                error_text = f"Malformed tool call: could not parse arguments JSON: {exc}"
                # Log the attempted-but-rejected call BEFORE branching: this
                # is the injection/rejection evidence, and it must appear
                # whether the model gets a retry or the loop gives up.
                _audit_log(step, fn, {"raw_arguments": raw_args}, f"REJECTED: {error_text}")
                if signature == last_malformed_signature:
                    print(
                        f"[step {step}] repeated malformed call for {fn!r} -- "
                        f"already retried once, failing honestly.",
                        file=sys.stderr,
                    )
                    elapsed = time.time() - start
                    print(
                        f"\n=== FAILED ({elapsed:.1f}s): repeated malformed tool "
                        f"call for {fn!r}, giving up after one retry ===",
                        file=sys.stdout,
                    )
                    print(
                        f"[receipt] total tokens in={totals['prompt']} "
                        f"out={totals['predicted']}",
                        file=sys.stderr,
                    )
                    return 1
                last_malformed_signature = signature
                messages.append(
                    {"role": "tool", "tool_call_id": tool_call_id, "content": error_text}
                )
                continue

            impl = impls.get(fn)
            if impl is None:
                error_text = f"Unknown tool {fn!r}."
                _audit_log(step, fn, call_args, f"REJECTED: {error_text}")
                messages.append(
                    {"role": "tool", "tool_call_id": tool_call_id, "content": error_text}
                )
                continue

            try:
                out = impl(**call_args)
            except ToolError as exc:
                out = f"ERROR: {exc}"
            except TypeError as exc:
                out = f"ERROR: bad arguments for {fn!r}: {exc}"
            _audit_log(step, fn, call_args, out)
            messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": out})
            last_malformed_signature = None
    else:
        elapsed = time.time() - start
        print(
            f"\n=== STEP BUDGET EXHAUSTED ({args.max_steps} steps, {elapsed:.1f}s) ===",
            file=sys.stdout,
        )
        print(
            f"[receipt] total tokens in={totals['prompt']} out={totals['predicted']}",
            file=sys.stderr,
        )
        return 1

    elapsed = time.time() - start
    print(f"\n=== DONE ({step + 1} steps, {elapsed:.1f}s) ===", file=sys.stderr)
    print(
        f"[receipt] total tokens in={totals['prompt']} out={totals['predicted']}",
        file=sys.stderr,
    )
    print(final_text or "")
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        description=(
            "Local, tool-using agent loop via the LM Studio SDK or an "
            "OpenAI-compatible chat-completions endpoint."
        )
    )
    ap.add_argument("--model", required=True, help="model id exposed by the selected server")
    ap.add_argument("--task", required=True, help="Task/prompt for the agent")
    ap.add_argument("--cwd", default=".", help="Working directory the tools are confined to")
    ap.add_argument("--max-steps", type=int, default=20, help="Hard cap on agent rounds")
    ap.add_argument(
        "--read-only",
        action="store_true",
        help=(
            "Expose only the read tools (read_file, list_dir, grep) so the agent "
            "cannot modify anything -- for review/analysis. Default is full "
            "power: run_command and write_file, both unrestricted."
        ),
    )
    ap.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=(
            "OpenAI-compatible server root (default: %(default)s; env: "
            "LOCAL_AGENT_BASE_URL)"
        ),
    )
    ap.add_argument(
        "--api-key",
        default=DEFAULT_API_KEY,
        help="Bearer token for the raw route (prefer env: LOCAL_AGENT_API_KEY)",
    )
    ap.add_argument("--no-sdk", action="store_true", help="Force the raw HTTP loop, skip the SDK route")
    ap.add_argument(
        "--allow-outside-cwd",
        action="store_true",
        help="Deprecated no-op: tool paths resolve outside --cwd by default now.",
    )
    ap.add_argument(
        "--confine-cwd",
        action="store_true",
        help=(
            "Opt into the --cwd path boundary: read_file, list_dir, grep, and "
            "write_file refuse (ToolError, shown to the model) a path that "
            "resolves outside --cwd. Off by default (owner directive)."
        ),
    )
    return ap.parse_args(argv)


def main(argv=None) -> int:
    # Windows consoles are frequently on a legacy codepage (cp1252) that
    # can't encode characters some local models emit (em dashes, etc.);
    # avoid crashing on print() for those.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    args = parse_args(argv)

    args.base_url = args.base_url.rstrip("/")
    if not args.base_url.startswith(("http://", "https://")):
        print("error: --base-url must start with http:// or https://", file=sys.stderr)
        return 2
    if args.max_steps < 1:
        print("error: --max-steps must be at least 1", file=sys.stderr)
        return 2

    cwd_path = Path(args.cwd).resolve()
    if not cwd_path.exists() or not cwd_path.is_dir():
        print(f"error: --cwd {args.cwd!r} does not exist or is not a directory", file=sys.stderr)
        return 2
    confined = ConfinedCwd(cwd_path, allow_outside=not args.confine_cwd)

    print(
        f"[local_agent] model={args.model} cwd={confined.root} max_steps={args.max_steps} "
        f"mode={'read-only' if args.read_only else 'full (run_command + write_file)'} "
        f"path-boundary={'ON (--confine-cwd)' if args.confine_cwd else 'OFF'}",
        file=sys.stderr,
    )

    custom_endpoint = args.base_url != LM_STUDIO_BASE_URL
    if custom_endpoint and not args.no_sdk:
        print(
            "[local_agent] custom --base-url selects the raw HTTP route; "
            "the LM Studio SDK uses its separate application API",
            file=sys.stderr,
        )
    use_sdk = _ensure_sdk_or_reexec(args.no_sdk or custom_endpoint)
    if use_sdk:
        print("[local_agent] route=SDK (lmstudio.LLM.act)", file=sys.stderr)
        return run_sdk_loop(args, confined)
    print("[local_agent] route=raw HTTP loop (/v1/chat/completions)", file=sys.stderr)
    return run_raw_loop(args, confined)


if __name__ == "__main__":
    sys.exit(main())
