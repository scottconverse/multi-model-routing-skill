#!/usr/bin/env python3
"""Offline tests for scripts/local_agent.py.

Run: python tests/test_local_agent.py
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


with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    (root / "café.txt").write_text("snowman: ☃\n", encoding="utf-8")
    confined = local_agent.ConfinedCwd(root)
    read_file, list_dir, grep, run_command = local_agent.make_tools(confined, False)

    check("read_file preserves UTF-8", "☃" in read_file("café.txt"))
    check("list_dir sees confined files", "café.txt" in list_dir())
    try:
        read_file(str(root.parent / "outside.txt"))
    except local_agent.ToolError:
        escaped = False
    else:
        escaped = True
    check("file tools reject paths outside --cwd", not escaped)

    _, _, _, writable_command = local_agent.make_tools(confined, True)
    try:
        writable_command("rm café.txt")
    except local_agent.ToolError:
        destructive_ran = False
    else:
        destructive_ran = True
    check("rm remains blocked with --allow-write", not destructive_ran)


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
                            "SYNTHETIC_REASONING_END_deadbeef__OK ✓"
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
check("reasoning sentinel is stripped from UTF-8 final output", proc.stdout.strip() == "OK ✓", proc.stdout)
check("per-step receipt is printed", "[step 0] tool_call(s)" in proc.stderr)
check("total receipt sums all steps", "[receipt] total tokens in=220 out=30" in proc.stderr)

help_proc = subprocess.run(
    [sys.executable, str(SCRIPT), "--help"],
    capture_output=True,
    encoding="utf-8",
    timeout=10,
)
check("--help succeeds", help_proc.returncode == 0, help_proc.stderr)
check("--help documents provider-neutral base URL", "LOCAL_AGENT_BASE_URL" in help_proc.stdout)

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
