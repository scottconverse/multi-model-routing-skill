#!/usr/bin/env python3
"""Offline tests for scripts/local_agent.py.

Run: python tests/test_local_agent.py

These encode the harness's behaviour AFTER:
  - the 2026-08-16 owner directive that removed the command guards
    (destructive-command block, read-only allowlist, chain/redirection block)
    and added the write_file tool, and
  - the 2026-08-16 audit fix that restored the --cwd PATH boundary by default
    (with an explicit --allow-outside-cwd escape hatch), made write_file
    byte-exact and report the resolved path, made the grep fallback survive
    an out-of-root path, and wired LOCAL_AGENT_LOG into both loops including
    rejected/malformed calls.
The command guards (destructive-command block, allowlist, chain block) stay
removed; the read/write TOOL boundary is still the set of exposed tools
(--read-only), not string inspection. The PATH boundary is separate and is
back on by default. Non-ASCII literals are written as \\u escapes on purpose:
the install guard requires every shipped .py file to be cp437-safe.
"""

import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import types
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "local_agent.py"
failures = []
checks = 0


def check(label, condition, detail=""):
    global checks
    checks += 1
    if condition:
        print(f"PASS: {label}")
    else:
        failures.append(label)
        print(f"FAIL: {label}{': ' + detail if detail else ''}")


spec = importlib.util.spec_from_file_location("local_agent_under_test", SCRIPT)
local_agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(local_agent)


SNOWMAN = chr(0x2603)  # a non-cp437 char, built via chr() so no shipped string
CHECK = chr(0x2713)    # literal carries it (the install guard scans literal values)

with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    (root / "cafe.txt").write_text(f"snowman: {SNOWMAN}\n", encoding="utf-8")
    confined = local_agent.ConfinedCwd(root)

    # make_tools now returns a LIST, and its second arg is read_only.
    read_only_tools = local_agent.make_tools(confined, True)
    full_tools = local_agent.make_tools(confined, False)
    ro_names = {fn.__name__ for fn in read_only_tools}
    full_names = {fn.__name__ for fn in full_tools}
    full = {fn.__name__: fn for fn in full_tools}

    check("read_file preserves UTF-8", SNOWMAN in full["read_file"]("cafe.txt"))
    check("list_dir sees working-dir files", "cafe.txt" in full["list_dir"]())

    check(
        "--read-only exposes ONLY the read tools",
        ro_names == {"read_file", "list_dir", "grep"},
        str(sorted(ro_names)),
    )
    check(
        "full mode adds run_command and write_file",
        full_names == {"read_file", "list_dir", "grep", "run_command", "write_file"},
        str(sorted(full_names)),
    )

    # write_file: creates parent dirs, round-trips UTF-8 content.
    full["write_file"]("sub/new.txt", f"hello {SNOWMAN}")
    written = (root / "sub" / "new.txt").read_text(encoding="utf-8")
    check("write_file creates file (parents made) with exact content", written == f"hello {SNOWMAN}")

    # --- fix 3: write_file is byte-exact and reports the resolved path -----
    # Python's default text-mode write translates '\n' -> os.linesep, which is
    # '\r\n' on Windows -- an LF file came back CRLF. newline="" disables that
    # translation. Checked via raw bytes, not read_text(), because read_text()
    # applies the SAME universal-newline translation on the way back in and
    # would hide the bug it is meant to catch.
    lf_content = "alpha\nbeta\ngamma\n"
    write_result = full["write_file"]("lf/roundtrip.txt", lf_content)
    lf_path = root / "lf" / "roundtrip.txt"
    raw = lf_path.read_bytes()
    check(
        "fix3: write_file round-trips LF content byte-exact (no CRLF translation)",
        raw == lf_content.encode("utf-8"),
        repr(raw),
    )
    check(
        "fix3: write_file's return string reports the RESOLVED path",
        str(lf_path.resolve()) in write_result,
        write_result,
    )

    # Quoting-bug regression: nested single-inside-double quotes must survive to
    # the shell. Before the fix, ["cmd","/c",str] mangled these to empty output.
    quoted = full["run_command"](f'"{sys.executable}" -c "print(\'quoted-ok\')"')
    check("run_command handles nested quotes (quoting-bug regression)", "quoted-ok" in quoted, quoted)

    # Chaining now works (was refused by the removed CHAIN_MARKERS guard).
    chained = full["run_command"]("echo one && echo two")
    check("run_command allows chaining (&&)", "one" in chained and "two" in chained, chained)

    # No destructive-command block anymore: a delete actually runs. The
    # command guards (unlike the path boundary below) stay removed.
    (root / "victim.txt").write_text("x", encoding="utf-8")
    rm_cmd = f'del "{root / "victim.txt"}"' if os.name == "nt" else f'rm "{root / "victim.txt"}"'
    full["run_command"](rm_cmd)
    check("no destructive-command block: delete runs", not (root / "victim.txt").exists())

    # --- fix 1: the --cwd path boundary is back on by default --------------
    escape_path = root.parent / "escaped-by-local-agent-test.txt"
    try:
        rel_escape = f"../{escape_path.name}"

        raised = False
        try:
            full["write_file"](rel_escape, "should never land here")
        except local_agent.ToolError:
            raised = True
        check("fix1: default mode refuses write_file outside --cwd", raised)
        check("fix1: refused write_file did not create the file", not escape_path.exists())

        raised = False
        try:
            full["read_file"](rel_escape)
        except local_agent.ToolError:
            raised = True
        check("fix1: default mode refuses read_file outside --cwd", raised)

        raised = False
        try:
            full["list_dir"]("..")
        except local_agent.ToolError:
            raised = True
        check("fix1: default mode refuses list_dir outside --cwd", raised)
    finally:
        if escape_path.exists():
            escape_path.unlink()

    # --allow-outside-cwd restores the pre-audit unbounded resolve() -- an
    # explicit opt-in, not the default.
    confined_allow = local_agent.ConfinedCwd(root, allow_outside=True)
    allow_tools = {fn.__name__: fn for fn in local_agent.make_tools(confined_allow, False)}
    with tempfile.TemporaryDirectory() as outside:
        outside_file = pathlib.Path(outside) / "beyond.txt"
        outside_file.write_text("beyond-the-jail", encoding="utf-8")
        got = allow_tools["read_file"](str(outside_file))
        check(
            "fix1: --allow-outside-cwd restores the old unbounded resolve()",
            "beyond-the-jail" in got,
            got,
        )

    # --- fix 4: the pure-Python grep fallback survives an out-of-root path -
    # rg is forced off (shutil.which patched) so this exercises the fallback
    # even on a machine that happens to have ripgrep on PATH -- the fallback
    # is the live path on the machine this audit was done on (no rg
    # installed), and this suite must not depend on that being true here too.
    original_which = local_agent.shutil.which
    local_agent.shutil.which = lambda name: None if name == "rg" else original_which(name)
    try:
        grep_tools = {fn.__name__: fn for fn in local_agent.make_tools(confined_allow, False)}
        with tempfile.TemporaryDirectory() as outside2:
            (pathlib.Path(outside2) / "needle.txt").write_text("find-the-needle\n", encoding="utf-8")
            # confined_allow permits a search root outside confined.root (only
            # reachable via --allow-outside-cwd); every match under it then
            # fails f.relative_to(confined.root) -- must be skipped, not
            # crash the whole grep call with an uncaught ValueError.
            grep_result = grep_tools["grep"]("needle", path=outside2)
        check(
            "fix4: pure-Python grep fallback does not crash on an out-of-root path",
            isinstance(grep_result, str),
            repr(grep_result),
        )
        # And the ordinary in-root case still finds matches through the same
        # fallback (proves the ValueError guard didn't just swallow everything).
        in_root_result = full["grep"]("snowman", path=".")
        check(
            "fix4: pure-Python grep fallback still matches in-root files",
            "cafe.txt" in in_root_result,
            in_root_result,
        )
    finally:
        local_agent.shutil.which = original_which


# --------------------------------------------------------------------------
# Raw loop (--no-sdk / custom --base-url): mock HTTP server, 3 rounds --
# round 1 is a rejected (unknown-tool) call, round 2 a real one, round 3 the
# final answer. Exercises fix 2 (audit log completeness) on this lane.
# --------------------------------------------------------------------------

requests = []
auth_headers = []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        payload = json.loads(body.decode("utf-8"))
        requests.append(payload)
        auth_headers.append(self.headers.get("Authorization"))

        if len(requests) == 1:
            # An unknown tool name -- the model asking for something that was
            # never advertised. Exercises the "rejected/malformed" audit path.
            response = {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [{
                            "id": "call-0",
                            "type": "function",
                            "function": {"name": "delete_everything", "arguments": "{}"},
                        }],
                    }
                }],
                "usage": {"prompt_tokens": 50, "completion_tokens": 5},
            }
        elif len(requests) == 2:
            response = {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [{
                            "id": "call-1",
                            "type": "function",
                            "function": {"name": "list_dir", "arguments": "{}"},
                        }],
                    }
                }],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20},
            }
        else:
            response = {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": (
                            "hidden __LM_STUDIO_INTERNAL_LSEP_"
                            "SYNTHETIC_REASONING_END_deadbeef__OK " + CHECK
                        ),
                    }
                }],
                "usage": {"prompt_tokens": 120, "completion_tokens": 10},
            }

        data = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


server = HTTPServer(("127.0.0.1", 0), Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()

try:
    with tempfile.TemporaryDirectory() as tmp:
        audit_log_path = pathlib.Path(tmp) / "audit.jsonl"
        env = os.environ.copy()
        env["LOCAL_AGENT_API_KEY"] = "test-secret"
        env["LOCAL_AGENT_LOG"] = str(audit_log_path)
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--model",
                "mock-model",
                "--task",
                "Inspect the directory, then answer OK.",
                "--cwd",
                tmp,
                "--base-url",
                f"http://127.0.0.1:{server.server_port}/",
                "--max-steps",
                "4",
            ],
            capture_output=True,
            encoding="utf-8",
            env=env,
            timeout=15,
        )
        audit_lines = []
        if audit_log_path.exists():
            for line in audit_log_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    audit_lines.append(json.loads(line))
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)

check("custom endpoint selects raw loop without SDK bootstrap", proc.returncode == 0, proc.stderr)
check("raw loop made three model rounds", len(requests) == 3, str(len(requests)))
check("system message stays first", requests[0]["messages"][0]["role"] == "system")
check(
    "tool result is returned to the model",
    any(m.get("role") == "tool" for m in requests[1]["messages"]),
)
check("environment API key becomes a bearer header", auth_headers == ["Bearer test-secret"] * 3)
check("reasoning sentinel is stripped from UTF-8 final output", proc.stdout.strip() == "OK " + CHECK, proc.stdout)
check("per-step receipt is printed", "[step 0] tool_call(s)" in proc.stderr)
check("total receipt sums all steps", "[receipt] total tokens in=270 out=35" in proc.stderr)

# --- fix 2: LOCAL_AGENT_LOG covers the raw loop, including the rejected call
rejected_entries = [e for e in audit_lines if e.get("tool") == "delete_everything"]
check(
    "fix2 (raw loop): the rejected unknown-tool call is written to LOCAL_AGENT_LOG",
    len(rejected_entries) == 1 and "REJECTED" in rejected_entries[0]["result"]
    and "Unknown tool" in rejected_entries[0]["result"],
    str(rejected_entries),
)
success_entries = [e for e in audit_lines if e.get("tool") == "list_dir"]
check(
    "fix2 (raw loop): a successful tool call is also written to LOCAL_AGENT_LOG",
    len(success_entries) == 1,
    str(success_entries),
)


# --------------------------------------------------------------------------
# Behavioral tool-filtering proof for --read-only (fix: replaces grepping
# --help text, which only proves the flag is DOCUMENTED, not that it changes
# what gets sent to the model).
# --------------------------------------------------------------------------

ro_requests = []


class ReadOnlyHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        ro_requests.append(json.loads(body.decode("utf-8")))
        response = {
            "choices": [{"message": {"role": "assistant", "content": "OK"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 1},
        }
        data = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


ro_server = HTTPServer(("127.0.0.1", 0), ReadOnlyHandler)
ro_thread = threading.Thread(target=ro_server.serve_forever, daemon=True)
ro_thread.start()

try:
    with tempfile.TemporaryDirectory() as tmp:
        ro_proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--model",
                "mock",
                "--task",
                "noop",
                "--cwd",
                tmp,
                "--base-url",
                f"http://127.0.0.1:{ro_server.server_port}/",
                "--max-steps",
                "2",
                "--read-only",
            ],
            capture_output=True,
            encoding="utf-8",
            timeout=15,
        )
finally:
    ro_server.shutdown()
    ro_server.server_close()
    ro_thread.join(timeout=5)

sent_tool_names = (
    {t["function"]["name"] for t in ro_requests[0]["tools"]} if ro_requests else set()
)
check("--read-only run succeeds", ro_proc.returncode == 0, ro_proc.stderr)
check(
    "behavioral: --read-only advertises ONLY the read tools to the model "
    "(not a --help grep)",
    sent_tool_names == {"read_file", "list_dir", "grep"},
    str(sorted(sent_tool_names)),
)

ro_help = subprocess.run(
    [sys.executable, str(SCRIPT), "--help"],
    capture_output=True,
    encoding="utf-8",
    timeout=10,
)
check("--help succeeds", ro_help.returncode == 0, ro_help.stderr)
check("--help documents provider-neutral base URL", "LOCAL_AGENT_BASE_URL" in ro_help.stdout)
check("--help documents --allow-outside-cwd", "--allow-outside-cwd" in ro_help.stdout)

bad_budget = subprocess.run(
    [
        sys.executable,
        str(SCRIPT),
        "--model",
        "mock",
        "--task",
        "noop",
        "--no-sdk",
        "--max-steps",
        "0",
    ],
    capture_output=True,
    encoding="utf-8",
    timeout=10,
)
check("non-positive step budget is rejected before connecting", bad_budget.returncode == 2)


# --------------------------------------------------------------------------
# SDK loop (run_sdk_loop): fix 2's audit-log wiring, unit-tested against a
# fake `lmstudio` module injected into sys.modules. There is no real LM
# Studio server in CI/offline, so this proves the WRAPPING logic --
# successful calls, calls that raise ToolError inside the tool itself (path
# escape, fix 1), and calls rejected before ever reaching a tool (unknown
# tool name) -- without needing a live model. It also proves the dedup: a
# ToolError raised inside a tool must be logged exactly once, not twice, even
# though the real SDK also routes execution failures through
# handle_invalid_tool_request.
# --------------------------------------------------------------------------


class _FakeToolCallRequest:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments
        self.id = name


class _FakeToolCallRequestData:
    def __init__(self, name, arguments=None):
        self.tool_call_request = _FakeToolCallRequest(name, arguments or {})


_FakeToolCallRequestData.__name__ = "ToolCallRequestData"


class _FakeTextData:
    def __init__(self, text):
        self.text = text


_FakeTextData.__name__ = "TextData"


class _FakeAssistantResponse:
    def __init__(self, content):
        self.content = content


_FakeAssistantResponse.__name__ = "AssistantResponse"


class _FakeStats:
    prompt_tokens_count = 1
    predicted_tokens_count = 1
    total_tokens_count = 2


class _FakePredictionRoundResult:
    stats = _FakeStats()


class _FakeActResult:
    rounds = 1


class _FakeLMStudioPredictionError(Exception):
    pass


class _FakeChat:
    def __init__(self, system_prompt):
        self.system_prompt = system_prompt

    def add_user_message(self, text):
        pass


class _FakeModel:
    def act(self, chat, tools, max_prediction_rounds, on_round_start,
            on_prediction_completed, on_message, handle_invalid_tool_request):
        by_name = {fn.__name__: fn for fn in tools}
        on_round_start(0)

        # 1) a normal, successful call
        by_name["list_dir"]()

        # 2) a call that raises ToolError INSIDE our tool (fix 1's path
        #    boundary). The _audited wrapper must catch, log, and re-raise;
        #    the real SDK then routes the failure through
        #    handle_invalid_tool_request too, with exc.__cause__ set -- so
        #    this must NOT be logged a second time there.
        escaped_exc = None
        try:
            by_name["read_file"](path="../escaped-by-sdk-test.txt")
        except Exception as exc:  # local_agent.ToolError
            escaped_exc = exc
        cb_exc = _FakeLMStudioPredictionError(f"Unhandled Python exception: {escaped_exc!r}")
        cb_exc.__cause__ = escaped_exc
        handle_invalid_tool_request(
            cb_exc, _FakeToolCallRequest("read_file", {"path": "../escaped-by-sdk-test.txt"})
        )

        # 3) a call rejected before it ever reached a tool implementation
        #    (unknown tool name) -- exc.__cause__ stays None, matching the
        #    real SDK's _handle_invalid_tool_request for this case. This IS
        #    the injection/rejection evidence and must be logged here.
        handle_invalid_tool_request(
            _FakeLMStudioPredictionError("Cannot find tool with name 'bogus_tool'."),
            _FakeToolCallRequest("bogus_tool", {}),
        )

        on_prediction_completed(_FakePredictionRoundResult())
        on_message(_FakeAssistantResponse([_FakeTextData("done")]))
        return _FakeActResult()


fake_lmstudio = types.ModuleType("lmstudio")
fake_lmstudio.llm = lambda model_id: _FakeModel()
fake_lmstudio.Chat = _FakeChat
fake_lmstudio.LMStudioPredictionError = _FakeLMStudioPredictionError

with tempfile.TemporaryDirectory() as tmp:
    sdk_root = pathlib.Path(tmp)
    sdk_confined = local_agent.ConfinedCwd(sdk_root)
    sdk_audit_log = sdk_root / "sdk-audit.jsonl"

    args = types.SimpleNamespace(
        model="fake-model", task="fake task", max_steps=5, read_only=False
    )

    prior_lmstudio = sys.modules.get("lmstudio")
    os.environ["LOCAL_AGENT_LOG"] = str(sdk_audit_log)
    try:
        sys.modules["lmstudio"] = fake_lmstudio
        sdk_rc = local_agent.run_sdk_loop(args, sdk_confined)
    finally:
        del os.environ["LOCAL_AGENT_LOG"]
        if prior_lmstudio is not None:
            sys.modules["lmstudio"] = prior_lmstudio
        else:
            sys.modules.pop("lmstudio", None)

    check("fix2 (SDK loop): run_sdk_loop completes via the fake SDK", sdk_rc == 0, str(sdk_rc))

    sdk_audit_lines = []
    if sdk_audit_log.exists():
        for line in sdk_audit_log.read_text(encoding="utf-8").splitlines():
            if line.strip():
                sdk_audit_lines.append(json.loads(line))

    sdk_success = [e for e in sdk_audit_lines if e.get("tool") == "list_dir"]
    check(
        "fix2 (SDK loop): a successful tool call is written to LOCAL_AGENT_LOG "
        "(previously the default lane never logged anything)",
        len(sdk_success) == 1,
        str(sdk_audit_lines),
    )

    sdk_escaped = [e for e in sdk_audit_lines if e.get("tool") == "read_file"]
    check(
        "fix2 (SDK loop): a path-escape ToolError is logged exactly ONCE "
        "(the wrapper logs it; handle_invalid_tool_request must not double-log)",
        len(sdk_escaped) == 1 and "ERROR" in sdk_escaped[0]["result"],
        str(sdk_escaped),
    )

    sdk_rejected = [e for e in sdk_audit_lines if e.get("tool") == "bogus_tool"]
    check(
        "fix2 (SDK loop): a call rejected before execution (unknown tool) is "
        "logged -- the injection/rejection evidence",
        len(sdk_rejected) == 1 and "REJECTED" in sdk_rejected[0]["result"],
        str(sdk_rejected),
    )


print(f"\n{checks - len(failures)}/{checks} checks passed")
if failures:
    print("Failed: " + ", ".join(failures))
    sys.exit(1)
