#!/usr/bin/env python3
"""Offline tests for scripts/local_agent.py.

Run: python tests/test_local_agent.py

These encode the harness's behaviour AFTER the 2026-08-16 owner directive that
removed the command guards (destructive-command block, read-only allowlist,
chain/redirection block, and path jail) and added the write_file tool. The
read/write boundary is now the set of exposed tools (--read-only), not string
inspection. Non-ASCII literals are written as \\u escapes on purpose: the
install guard requires every shipped .py file to be cp437-safe.
"""

import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
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

    # Quoting-bug regression: nested single-inside-double quotes must survive to
    # the shell. Before the fix, ["cmd","/c",str] mangled these to empty output.
    quoted = full["run_command"](f'"{sys.executable}" -c "print(\'quoted-ok\')"')
    check("run_command handles nested quotes (quoting-bug regression)", "quoted-ok" in quoted, quoted)

    # Chaining now works (was refused by the removed CHAIN_MARKERS guard).
    chained = full["run_command"]("echo one && echo two")
    check("run_command allows chaining (&&)", "one" in chained and "two" in chained, chained)

    # No destructive-command block anymore: a delete actually runs.
    (root / "victim.txt").write_text("x", encoding="utf-8")
    rm_cmd = f'del "{root / "victim.txt"}"' if os.name == "nt" else f'rm "{root / "victim.txt"}"'
    full["run_command"](rm_cmd)
    check("no destructive-command block: delete runs", not (root / "victim.txt").exists())

    # No path jail: file tools resolve a path outside --cwd.
    with tempfile.TemporaryDirectory() as outside:
        outside_file = pathlib.Path(outside) / "beyond.txt"
        outside_file.write_text("beyond-the-jail", encoding="utf-8")
        got = full["read_file"](str(outside_file))
        check("no path jail: read_file resolves outside --cwd", "beyond-the-jail" in got, got)


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
        env = os.environ.copy()
        env["LOCAL_AGENT_API_KEY"] = "test-secret"
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
                "3",
            ],
            capture_output=True,
            encoding="utf-8",
            env=env,
            timeout=15,
        )
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)

check("custom endpoint selects raw loop without SDK bootstrap", proc.returncode == 0, proc.stderr)
check("raw loop made two model rounds", len(requests) == 2, str(len(requests)))
check("system message stays first", requests[0]["messages"][0]["role"] == "system")
check(
    "tool result is returned to the model",
    any(m.get("role") == "tool" for m in requests[1]["messages"]),
)
check("environment API key becomes a bearer header", auth_headers == ["Bearer test-secret"] * 2)
check("reasoning sentinel is stripped from UTF-8 final output", proc.stdout.strip() == "OK " + CHECK, proc.stdout)
check("per-step receipt is printed", "[step 0] tool_call(s)" in proc.stderr)
check("total receipt sums all steps", "[receipt] total tokens in=220 out=30" in proc.stderr)

# In --read-only mode, the write tools must not even be advertised to the model.
ro_help = subprocess.run(
    [sys.executable, str(SCRIPT), "--help"],
    capture_output=True,
    encoding="utf-8",
    timeout=10,
)
check("--help succeeds", ro_help.returncode == 0, ro_help.stderr)
check("--help documents provider-neutral base URL", "LOCAL_AGENT_BASE_URL" in ro_help.stdout)
check("--help documents --read-only", "--read-only" in ro_help.stdout)

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

print(f"\n{checks - len(failures)}/{checks} checks passed")
if failures:
    print("Failed: " + ", ".join(failures))
    sys.exit(1)
