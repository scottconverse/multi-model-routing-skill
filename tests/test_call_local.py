# SPDX-License-Identifier: MIT
"""Smoke-test call_local.sh against mock local-LLM servers.

Covers the happy paths plus every failure mode found in the 2026-08-08 audit:
dialect fallback (404 and 405), empty replies, error bodies served with HTTP
200, null OpenAI content, and stalled servers.

Run: python3 tests/test_call_local.py (from the skill root or anywhere).
"""
import json
import os
import tempfile
import pathlib
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# as_posix() so the path survives being handed to bash on Windows, where
# backslashes would be swallowed as escapes ("C:\Users" -> "C:Users").
# Identical to str() on Linux/macOS.
SCRIPT = (pathlib.Path(__file__).resolve().parent.parent / "scripts" / "call_local.sh").as_posix()


def find_bash():
    """Locate a bash that can reach this script and our localhost servers.

    On Windows, `bash` on PATH is usually the WSL shim (System32\\bash.exe).
    That's the wrong bash here twice over: it can't resolve C:/ paths, and
    under WSL2 its 127.0.0.1 is a different loopback than the one the mock
    servers below bind to. So prefer Git Bash, which shares both with us.
    """
    if sys.platform != "win32":
        return "bash"
    found = shutil.which("bash")
    if found and "system32" not in found.lower() and "windowsapps" not in found.lower():
        return found
    git = shutil.which("git")  # ...\Git\cmd\git.exe -> ...\Git\bin\bash.exe
    if git:
        cand = pathlib.Path(git).resolve().parent.parent / "bin" / "bash.exe"
        if cand.is_file():
            return str(cand)
    for cand in (r"C:\Program Files\Git\bin\bash.exe",
                 r"C:\Program Files (x86)\Git\bin\bash.exe"):
        if pathlib.Path(cand).is_file():
            return cand
    # Exit 0: no POSIX bash is a legitimate skip, not a failed assertion. A
    # non-zero exit here would show up as a red build on machines that simply
    # can't run the script.
    print("SKIP: no Git Bash found; call_local.sh needs a POSIX bash on Windows")
    sys.exit(0)


BASH = find_bash()

ANTHROPIC_OK = {"content": [{"type": "text", "text": "OK-anthropic"}],
                "usage": {"input_tokens": 5, "output_tokens": 3}}
OPENAI_OK = {"choices": [{"message": {"content": "OK-openai"}}],
             "usage": {"prompt_tokens": 5, "completion_tokens": 3}}


def make(messages_status, messages_body=None, chat_body=None, stall=False):
    """Build a handler: how /v1/messages behaves, and what /v1/chat/completions returns."""
    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))))
            assert req["messages"][0]["role"] == "user"
            if stall:
                threading.Event().wait(120)   # accept, then never answer
                return
            if self.path == "/v1/messages":
                if messages_status == 200:
                    return self.reply(200, messages_body)
                return self.reply(messages_status, {"error": {"message": "nope"}})
            if self.path == "/v1/chat/completions":
                return self.reply(200, chat_body)
            self.reply(404, {})

        def reply(self, code, obj):
            data = json.dumps(obj if obj is not None else {}).encode()
            self.send_response(code)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a):
            pass
    return H


def serve(port, handler):
    srv = HTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def run(port, env=None, max_tokens="100", prompt="hi", stdin=None):
    full = None
    if env:
        import os
        full = {**os.environ, **env}
    return subprocess.run([BASH, SCRIPT, f"http://127.0.0.1:{port}", "m", prompt, max_tokens],
                          capture_output=True, text=True, timeout=180, env=full,
                          input=stdin)


class EchoHandler(BaseHTTPRequestHandler):
    """Reports the prompt it received, so tests assert on what ARRIVED."""
    def do_POST(self):
        n = int(self.headers.get("content-length", 0))
        got = json.loads(self.rfile.read(n))["messages"][0]["content"]
        body = {"content": [{"type": "text",
                             "text": f"LEN={len(got)} NL={got.count(chr(10))} "
                                     f"HEAD={got[:12]} TAIL={got[-12:]}"}],
                "usage": {"input_tokens": 1, "output_tokens": 1}}
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


CASES = [
    (18811, make(200, ANTHROPIC_OK)),                       # anthropic happy path
    (18812, make(404, chat_body=OPENAI_OK)),                # 404 -> openai fallback
    (18813, make(405, chat_body=OPENAI_OK)),                # 405 -> openai fallback
    (18814, make(200, {"content": [], "usage": {"input_tokens": 9, "output_tokens": 0}})),
    (18815, make(200, {"type": "error", "error": {"message": "overloaded"}})),
    (18816, make(404, chat_body={"choices": [{"message": {"content": None}}]})),
    (18817, make(200, stall=True)),                         # accepts, never replies
]
for port, handler in CASES:
    serve(port, handler)

# --- happy paths ------------------------------------------------------------
r = run(18811)
assert r.returncode == 0 and r.stdout.strip() == "OK-anthropic", (r.stdout, r.stderr)
assert "[receipt] in=5 out=3" in r.stderr, r.stderr

r = run(18812)
assert r.returncode == 0 and r.stdout.strip() == "OK-openai", (r.stdout, r.stderr)
assert "[receipt] in=5 out=3" in r.stderr, r.stderr

# --- regressions from the 2026-08-08 audit ----------------------------------
# 405 must fall back too, not just 404.
r = run(18813)
assert r.returncode == 0 and r.stdout.strip() == "OK-openai", ("405 fallback", r.stdout, r.stderr)

# An empty reply is a failure (exit 2), never an empty success.
r = run(18814)
assert r.returncode == 2, ("empty reply must exit 2", r.returncode, r.stdout, r.stderr)
assert r.stdout.strip() == "", r.stdout
assert "empty" in r.stderr.lower(), r.stderr
assert "[receipt] in=9 out=0" in r.stderr, ("receipt still emitted", r.stderr)

# HTTP 200 carrying an error body must be named, not a KeyError traceback.
r = run(18815)
assert r.returncode == 1, (r.returncode, r.stderr)
assert "overloaded" in r.stderr, r.stderr
assert "Traceback" not in r.stderr, ("must not leak a traceback", r.stderr)

# null OpenAI content must not print the string "None" as the answer.
r = run(18816)
assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
assert "None" not in r.stdout, r.stdout

# A stalled server must not hang forever.
r = run(18817, env={"CALL_LOCAL_TIMEOUT": "3", "CALL_LOCAL_CONNECT_TIMEOUT": "2"})
assert r.returncode == 1, (r.returncode, r.stderr)
assert "timed out" in r.stderr.lower(), r.stderr

# --- a large prompt must not have to fit in argv --------------------------
# A literal prompt is capped by the OS: curl reports "Argument list too long"
# past ~32k here, and a .cmd shim caps the whole command line near 8k. A batch
# caller passing a real log needs a path that isn't argv. Assert on what the
# SERVER received, not on exit status — a truncated prompt would still exit 0.
serve(18818, EchoHandler)

BIG = "\n".join(f"2026-08-09 line {i} ERROR padding padding padding" for i in range(4000))
assert len(BIG) > 200_000, len(BIG)

r = run(18818, prompt="-", stdin=BIG)
assert r.returncode == 0, ("stdin prompt failed", r.returncode, r.stderr[-400:])
assert f"LEN={len(BIG)}" in r.stdout, ("stdin prompt did not arrive intact",
                                       len(BIG), r.stdout.strip()[:200])
assert f"NL={BIG.count(chr(10))}" in r.stdout, ("newlines lost", r.stdout.strip()[:200])

with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                 encoding="utf-8") as fh:
    fh.write(BIG)
    big_path = fh.name
try:
    r = run(18818, prompt=f"file:{pathlib.Path(big_path).as_posix()}")
    assert r.returncode == 0, ("file: prompt failed", r.returncode, r.stderr[-400:])
    assert f"LEN={len(BIG)}" in r.stdout, ("file: prompt did not arrive intact",
                                           r.stdout.strip()[:200])
finally:
    os.unlink(big_path)

# the literal positional form must still behave exactly as before
r = run(18818, prompt="hello world")
assert r.returncode == 0 and "LEN=11" in r.stdout, ("literal prompt regressed",
                                                    r.stdout.strip()[:200])

# a missing @file is an error, not a prompt literally named "@missing"
r = run(18818, prompt="file:/nonexistent/prompt.txt")
assert r.returncode == 1 and "no such prompt file" in r.stderr, (r.returncode, r.stderr[:200])

# --- CALL_LOCAL_DIALECT --------------------------------------------------
# A gateway picks its dialect per MODEL, not per server: OpenCode Zen answers
# /v1/messages with 401/400 for free models while /v1/chat/completions works.
# `auto` correctly refuses to fall back on those codes (a 400 is usually a real
# bad request), so the caller states the dialect when it knows.
serve(18819, make(200, {"type": "error", "error": {"message": "wrong dialect"}}, OPENAI_OK))

# auto: /v1/messages answers 200-with-an-error-body, so no fallback happens
r = run(18819)
assert r.returncode == 1 and "wrong dialect" in r.stderr, ("auto must not fall back here",
                                                           r.returncode, r.stderr[:200])
# openai: skip the Anthropic probe entirely and the call succeeds
r = run(18819, env={"CALL_LOCAL_DIALECT": "openai"})
assert r.returncode == 0 and r.stdout.strip() == "OK-openai", ("forced openai dialect",
                                                               r.stdout, r.stderr[:200])
# anthropic: forced, so it must NOT silently fall back
r = run(18819, env={"CALL_LOCAL_DIALECT": "anthropic"})
assert r.returncode == 1, ("forced anthropic must not fall back", r.returncode, r.stdout)
# an unknown value is rejected rather than guessed at
r = run(18819, env={"CALL_LOCAL_DIALECT": "sideways"})
assert r.returncode == 1 and "must be auto" in r.stderr, r.stderr[:200]

print("PASS: anthropic, openai 404-fallback, 405-fallback, empty-reply, "
      "error-body, null-content, stall-timeout, big-prompt-stdin, "
      "big-prompt-file, literal-prompt, missing-prompt-file, "
      "dialect-auto, dialect-openai, dialect-anthropic, dialect-invalid")
