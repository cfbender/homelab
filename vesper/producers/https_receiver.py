"""Disposable local HTTPS heartbeat receiver for producer tests; never contacts the homelab."""

import json
import re
import ssl
import subprocess
import threading
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Response content that producers must never print.
SENTINEL = "response-body-sentinel"
DELIVERY_KEYS = {"attempts", "outcome", "errors", "elapsed_s"}


def start(test, root, behaviour):
    """Serve on 127.0.0.1; behaviour(i, n) returns a status, "hang" or "drop" for kuma-i's n-th request."""
    cert, key = root / "cert.pem", root / "key.pem"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                    "-keyout", str(key), "-out", str(cert), "-subj", "/CN=localhost",
                    "-addext", "subjectAltName=IP:127.0.0.1"], check=True, capture_output=True)
    received, counts = [], Counter()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            received.append((self.path, self.headers.get("Authorization"), body))
            i = int(self.path.rsplit("-", 1)[-1])
            counts[i] += 1
            action = behaviour(i, counts[i])
            if action == "hang":
                time.sleep(10)  # Longer than any client deadline under test.
                return
            if action == "drop":
                self.close_connection = True  # Close without any HTTP response.
                return
            if action == "drip":
                # Frequent bytes defeat a per-read socket timeout, not a total deadline.
                try:
                    for byte in b"HTTP/1.0 204 No Content\r\n\r\n":
                        self.wfile.write(bytes([byte]))
                        self.wfile.flush()
                        time.sleep(0.2)
                except OSError:
                    pass
                return
            self.send_response(action)
            if 300 <= action < 400:
                self.send_header("Location", "/unexpected-redirect")
            # Echo the bearer header back to prove producers never print response headers.
            self.send_header("X-Echo", self.headers.get("Authorization", ""))
            payload = b"" if action == 204 else SENTINEL.encode()
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    test.addCleanup(server.server_close)
    test.addCleanup(server.shutdown)
    return f"https://127.0.0.1:{server.server_port}", cert, received


def assert_sanitized(test, result, records, tokens):
    """Delivery diagnostics are fixed categories; no token, header or body text reaches output."""
    output = result.stdout + result.stderr
    test.assertEqual(result.stderr, "")
    for secret in [*tokens, "Bearer", "Authorization", SENTINEL, "Traceback"]:
        test.assertNotIn(secret, output)
    for record in records:
        test.assertEqual(set(record["delivery"]), DELIVERY_KEYS)
        test.assertEqual(record["delivered"], record["delivery"]["outcome"] == "delivered")
        for error in record["delivery"]["errors"]:
            test.assertRegex(error, re.compile(r"[a-z0-9_]+\Z"))
