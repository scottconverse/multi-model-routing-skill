# SPDX-License-Identifier: MIT
"""Smoke-test call_local.sh against mock local-LLM servers.

Server A (port 18811): speaks Anthropic /v1/messages.
Server B (port 18812): 404s /v1/messages, speaks OpenAI /v1/chat/completions.

Run: python3 tests/test_call_local.py (from the skill root or anywhere).
"""
import json
import pathlib
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

SCRIPT = str(pathlib.Path(__file__).resolve().parent.parent / "scripts" / "call_local.sh")


class Handler(BaseHTTPRequestHandler):
    anthropic_ok = True

    def do_POST(self):
        n = int(self.headers.get("content-length", 0))
        req = json.loads(self.rfile.read(n))
        assert req["messages"][0]["role"] == "user"
        if self.path == "/v1/messages" and self.anthropic_ok:
            body = {
                "content": [{"type": "text", "text": "OK-anthropic"}],
                "usage": {"input_tokens": 5, "output_tokens": 3},
            }
        elif self.path == "/v1/chat/completions":
            body = {
                "choices": [{"message": {"content": "OK-openai"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            }
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"{}")
            return
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


class OpenAIOnly(Handler):
    anthropic_ok = False


def serve(port, cls):
    srv = HTTPServer(("127.0.0.1", port), cls)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


a = serve(18811, Handler)
b = serve(18812, OpenAIOnly)

r1 = subprocess.run([SCRIPT, "http://127.0.0.1:18811", "m", "hi", "100"],
                    capture_output=True, text=True)
r2 = subprocess.run([SCRIPT, "http://127.0.0.1:18812", "m", "hi", "100"],
                    capture_output=True, text=True)

assert r1.returncode == 0 and r1.stdout.strip() == "OK-anthropic", (r1.stdout, r1.stderr)
assert "[receipt] in=5 out=3" in r1.stderr, r1.stderr
assert r2.returncode == 0 and r2.stdout.strip() == "OK-openai", (r2.stdout, r2.stderr)
assert "[receipt] in=5 out=3" in r2.stderr, r2.stderr
print("PASS: anthropic path, openai 404-fallback path, receipts on stderr")
a.shutdown(); b.shutdown()
