"""CLI contract tests; fixtures replace host commands, never contact the homelab."""

import json
import os
import subprocess
import sys
import tempfile
import socket
import time
import unittest
from pathlib import Path

import https_receiver


SCRIPT = Path(__file__).with_name("host-health.py")


class HostHealthTests(unittest.TestCase):
    def run_probe(self, kind, output, code=0, argv_out=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            command = root / {"docker": "docker", "dns": "dig", "ping": "ping"}[kind]
            argv_capture = (
                f"import json; open({str(argv_out)!r}, 'w').write(json.dumps(sys.argv[1:]))\n"
                if argv_out is not None else ""
            )
            command.write_text(
                f"#!{sys.executable}\nimport sys\n{argv_capture}print({output!r})\nsys.exit({code})\n"
            )
            command.chmod(0o700)
            checks = root / "checks.json"
            checks.write_text(json.dumps([{
                "kind": kind, "target": "example.test", "hostname": "service.test",
                "path": "host/service/kuma-99",
            }]))
            # A missing secret directory proves default dry-run never needs credentials.
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--checks", str(checks),
                 "--secrets-dir", str(root / "missing")],
                env={**os.environ, "PATH": str(root)}, text=True, capture_output=True, timeout=5,
            )
            record = json.loads(result.stdout)
            self.assertNotIn("delivered", record)
            self.assertEqual(record["path"], "host/service/kuma-99")
            self.assertEqual(result.returncode, int(not record["healthy"]))
            return record["healthy"]

    def test_container_health_is_not_just_running(self):
        for state, expected in [
            ({"Status": "running"}, True),
            ({"Status": "running", "Health": {"Status": "unhealthy"}}, False),
            ({"Status": "running", "Health": {"Status": "starting"}}, False),
            ({"Status": "running", "Restarting": True}, False),
            ({"Status": "exited"}, False),
        ]:
            with self.subTest(state=state):
                self.assertEqual(self.run_probe("docker", json.dumps(state)), expected)

    def test_dns_requires_success_and_an_a_answer(self):
        good = ";; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 1\nservice.test. 10 IN A 10.0.0.7"
        with tempfile.NamedTemporaryFile() as captured:
            self.assertTrue(self.run_probe("dns", good, argv_out=captured.name))
            self.assertIn("+tries=2", json.loads(Path(captured.name).read_text()))
        for output, expected in [
            (good, True),
            (good.replace("NOERROR", "NXDOMAIN"), False),
            (good.splitlines()[0], False),
            (good.replace("IN A 10.0.0.7", "IN CNAME other.test."), False),
            (good.replace("10.0.0.7", "not-an-address"), False),
        ]:
            with self.subTest(output=output):
                self.assertEqual(self.run_probe("dns", output), expected)

    def test_command_failure_is_not_healthy(self):
        self.assertTrue(self.run_probe("ping", "", 0))
        self.assertFalse(self.run_probe("ping", "", 1))
        self.assertFalse(self.run_probe("docker", "no such container", 1))

    def test_https_delivery_retries_and_diagnostics(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / "ping").write_text(f"#!{sys.executable}\n")
        (root / "ping").chmod(0o700)
        ids = range(1, 10)
        (root / "checks.json").write_text(json.dumps(
            [{"kind": "ping", "target": "example.test", "path": f"host/service/kuma-{i}"} for i in ids]))
        tokens_dir = root / "tokens"
        tokens_dir.mkdir()
        tokens = [f"{i:064x}" for i in ids]
        for i in ids:
            if i != 8:  # kuma-8 has no token; kuma-9's is malformed.
                (tokens_dir / f"kuma-{i}-push").write_text("short" if i == 9 else f"{i:064x}")
        script = {1: [204], 2: [503, 204], 3: [502], 4: [401], 5: [302], 6: ["hang"], 7: ["drop", 204]}
        origin, cert, received = https_receiver.start(
            self, root, lambda i, n: script[i][min(n, len(script[i])) - 1])

        def run(*args, cafile=cert):
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--checks", str(root / "checks.json"), "--send",
                 "--secrets-dir", str(tokens_dir), *args],
                env={**os.environ, "PATH": str(root) + os.pathsep + os.environ["PATH"],
                     "CURL_CA_BUNDLE": str(cafile),
                     "HTTPS_PROXY": "http://127.0.0.1:1", "https_proxy": "http://127.0.0.1:1",
                     "NO_PROXY": "", "no_proxy": ""},
                text=True, capture_output=True, timeout=20,
            )
            records = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual([r["path"] for r in records], [f"host/service/kuma-{i}" for i in ids])
            self.assertEqual(result.returncode, int(not all(r["delivered"] for r in records)))
            https_receiver.assert_sanitized(self, result, records, tokens)
            return {int(r["path"].split("-")[-1]): r["delivery"] for r in records}

        started = time.monotonic()
        deliveries = run("--url", origin, "--delivery-attempts", "2", "--delivery-budget", "3")
        self.assertLess(time.monotonic() - started, 8)
        self.assertEqual({i: (d["outcome"], d["attempts"], d["errors"]) for i, d in deliveries.items()}, {
            1: ("delivered", 1, []),
            2: ("delivered", 2, ["http_503"]),           # Transient upstream error recovers.
            3: ("attempts_exhausted", 2, ["http_502", "http_502"]),
            4: ("terminal", 1, ["http_401"]),            # Rejected token is not retried.
            5: ("terminal", 1, ["http_302"]),            # Redirect refused, never followed.
            6: ("deadline_exhausted", 1, ["timeout"]),   # Elapsed budget stops a second attempt.
            7: ("delivered", 2, ["connection"]),         # Closed connection recovers.
            8: ("terminal", 0, ["token_unreadable"]),
            9: ("terminal", 0, ["token_invalid"]),
        })
        self.assertLessEqual(deliveries[6]["elapsed_s"], 3.5)
        self.assertEqual(sorted(int(path.split("-")[-1]) for path, _, _ in received), [1, 2, 2, 3, 3, 4, 5, 6, 7, 7])
        for path, authorization, body in received:
            i = int(path.split("-")[-1])
            self.assertEqual((path, authorization, body),
                             (f"/api/heartbeat/host/service/kuma-{i}", f"Bearer {i:064x}", {"healthy": True}))

        # The run deadline also bounds checks still queued behind the four workers.
        received.clear()
        script.update({i: ["hang"] for i in script})
        started = time.monotonic()
        deliveries = run("--url", origin, "--deadline", "2")
        self.assertLess(time.monotonic() - started, 4)
        self.assertEqual({d["outcome"] for i, d in deliveries.items() if i < 8}, {"deadline_exhausted"})
        self.assertTrue(all(d["elapsed_s"] <= 2.25 for d in deliveries.values()))  # Scheduling slack only.
        self.assertLess(len(received), 7)  # Later checks never started an attempt.

        # Bytes arriving inside every socket timeout must not extend the total deadline.
        received.clear()
        script.update({i: ["drip"] for i in script})
        started = time.monotonic()
        deliveries = run("--url", origin, "--delivery-budget", "2", "--deadline", "3")
        self.assertLess(time.monotonic() - started, 4)
        self.assertTrue(all(d["outcome"] == "deadline_exhausted" for i, d in deliveries.items() if i < 8))

        # Untrusted certificates cannot receive tokens and are not retried.
        received.clear()
        deliveries = run("--url", origin, cafile="/etc/ssl/certs/ca-certificates.crt")
        self.assertEqual({d["errors"][0] for i, d in deliveries.items() if i < 8}, {"certificate"})
        self.assertTrue(all(d["outcome"] == "terminal" for d in deliveries.values()))
        self.assertEqual(received, [])

        # Connection refusal is transient but bounded by attempts.
        with socket.socket() as closed:
            closed.bind(("127.0.0.1", 0))
            refused = f"https://127.0.0.1:{closed.getsockname()[1]}"
        deliveries = run("--url", refused, "--delivery-attempts", "2")
        self.assertTrue(all(d["outcome"] == "attempts_exhausted" and d["errors"] == ["connect", "connect"]
                            for i, d in deliveries.items() if i < 8))


if __name__ == "__main__":
    unittest.main()
