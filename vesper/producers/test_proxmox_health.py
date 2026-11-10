"""CLI tests with local command fixtures and a real, isolated HTTPS receiver."""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import https_receiver


SCRIPT = Path(__file__).with_name("proxmox-health.py")
PATHS = {
    61: "proxmox/host-health/kuma-61", 62: "proxmox/host-health/kuma-62",
    63: "proxmox/truenas-web/kuma-63", 64: "proxmox/host-health/kuma-64",
    65: "proxmox/host-health/kuma-65", 66: "proxmox/host-health/kuma-66",
    67: "proxmox/host-health/kuma-67",
}


class ProxmoxHealthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        fixture = f"#!{sys.executable}\n" + '''
import json, sys, time
from pathlib import Path
root = Path(__file__).parent
name = Path(sys.argv[0]).name
if name == "qm":
    name += "_list" if "list" in sys.argv else "_status"
elif name == "smartctl":
    name += "_scan" if "--scan" in sys.argv else "_health"
elif name == "findmnt":
    name += "_" + Path(sys.argv[-1]).name
data = json.loads((root / "responses.json").read_text())[name]
time.sleep(data.get("sleep", 0))
output = data.get("output", "")
if name == "pvesh" and "age" in data:
    output = json.dumps([{"status": data.get("status", "OK"), "starttime": int(time.time() - data["age"])}])
print(output)
print(data.get("stderr", ""), file=sys.stderr)
sys.exit(data.get("code", 0))
'''
        for name in ["pvesm", "lvs", "qm", "smartctl", "pvesh", "findmnt", "stat", "systemctl"]:
            path = self.root / name
            path.write_text(fixture)
            path.chmod(0o700)

    def run_adapter(self, overrides=None, args=(), env=None):
        responses = {
            "pvesm": {"output": "Name Type Status Total (KiB) Used (KiB) Available (KiB) %\nlocal dir active 1000 849 151 84.9%\nfrigate lvm active 100 100 0 100%\ntruenas cifs disabled 0 0 0 N/A"},
            "lvs": {"output": "pve data 84.9 12.0"},
            "qm_list": {"output": json.dumps({"exited": 1, "exitcode": 0, "out-data": "tank ONLINE 84%"})},
            "qm_status": {"output": json.dumps({"exited": 1, "exitcode": 0, "out-data": "all pools are healthy"})},
            "smartctl_scan": {"output": "/dev/sda -d sat # SATA disk"},
            "smartctl_health": {"output": "SMART overall-health self-assessment test result: PASSED"},
            "pvesh": {"age": 26 * 3600 - 60},
            "findmnt_unas": {}, "findmnt_backup": {}, "stat": {}, "systemctl": {},
        }
        responses.update(overrides or {})
        (self.root / "responses.json").write_text(json.dumps(responses))
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--secrets-dir", str(self.root / "tokens"), *args],
            env={**os.environ, "PATH": str(self.root) + os.pathsep + os.environ["PATH"], **(env or {})},
            text=True, capture_output=True, timeout=15,
        )
        records = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(records), 7, result.stderr)
        self.assertEqual({r["path"] for r in records}, set(PATHS.values()))
        self.assertEqual(result.returncode, 3 if any(not r["healthy"] or not r.get("delivered", True) for r in records) else 0)
        return {int(r["path"].split("-")[-1]): r for r in records}, result

    def test_dry_run_and_thresholds(self):
        records, _ = self.run_adapter()
        self.assertTrue(all(r["healthy"] for r in records.values()))
        self.assertTrue(all("delivered" not in r for r in records.values()))
        # Opposite sides of the utilization/age boundaries, including metadata-only failure.
        records, _ = self.run_adapter({
            "pvesm": {"output": "Name Type Status Total Used Available %\nlocal dir active 100 85 15 85%"},
            "lvs": {"output": "pve data 20.0 85.0"},
            "qm_list": {"output": json.dumps({"exited": 1, "exitcode": 0, "out-data": "tank ONLINE 85%"})},
            "pvesh": {"age": 26 * 3600},
        })
        self.assertEqual({i for i, r in records.items() if not r["healthy"]}, {61, 62, 63, 65})

    def test_failed_commands_and_malformed_results_are_down(self):
        for overrides, expected in [
            ({"qm_list": {"output": json.dumps({"exited": 1, "exitcode": 1, "out-data": "tank ONLINE 2%"})},
              "systemctl": {"code": 1}}, {63, 67}),
            ({"pvesm": {"output": "unexpected table"}, "lvs": {"output": "pve data NaN 2"},
              "pvesh": {"output": "[]"}, "smartctl_scan": {"output": ""},
              "findmnt_backup": {"code": 1}}, {61, 62, 64, 65, 66}),
            ({"qm_status": {"output": "not JSON"}, "smartctl_health": {"code": 8, "output": "PASSED"},
              "pvesh": {"age": -60}, "systemctl": {"output": "bad.service loaded failed failed"}}, {63, 64, 65, 67}),
            ({"pvesm": {"output": "Name Type Status Total Used Available %\nfrigate lvm inactive 100 100 0 100%"},
              "lvs": {"output": ""}}, {61}),
        ]:
            with self.subTest(expected=expected):
                records, _ = self.run_adapter(overrides)
                self.assertEqual({i for i, r in records.items() if not r["healthy"]}, expected)

    def test_slow_probe_does_not_hide_other_results(self):
        for overrides, failed_id in [
            ({"pvesm": {"sleep": 10}}, 61),
            ({"qm_list": {"sleep": 0.7, "output": json.dumps({"exited": 1, "exitcode": 0, "out-data": "tank ONLINE 2%"})},
              "qm_status": {"sleep": 0.7, "output": json.dumps({"exited": 1, "exitcode": 0, "out-data": "all pools are healthy"})}}, 63),
        ]:
            with self.subTest(signal=failed_id):
                started = time.monotonic()
                records, _ = self.run_adapter(overrides, args=["--probe-timeout", "1"])
                self.assertLess(time.monotonic() - started, 5)
                self.assertEqual({i for i, r in records.items() if not r["healthy"]}, {failed_id})

    def test_https_delivery_isolated_and_explicit(self):
        script = {61: [302], 62: [401], 63: [503, 204], 64: ["hang"], 65: [502], 66: ["drop", 204], 67: [204]}
        origin, cert, received = https_receiver.start(
            self, self.root, lambda i, n: script[i][min(n, len(script[i])) - 1])
        self.run_adapter(args=["--url", origin])
        self.assertEqual(received, [])  # No token directory, no network in default mode.
        (self.root / "tokens").mkdir()
        tokens = [f"{i:064x}" for i in PATHS]
        for i in PATHS:
            (self.root / "tokens" / f"kuma-{i}-push").write_text(f"{i:064x}")
        trusted = {"CURL_CA_BUNDLE": str(cert), "HTTPS_PROXY": "http://127.0.0.1:1",
                   "https_proxy": "http://127.0.0.1:1", "NO_PROXY": "", "no_proxy": ""}
        started = time.monotonic()
        records, result = self.run_adapter(
            {"systemctl": {"code": 1}}, env=trusted,
            args=["--send", "--url", origin, "--delivery-attempts", "2", "--delivery-budget", "3"])
        self.assertLess(time.monotonic() - started, 6)
        https_receiver.assert_sanitized(self, result, records.values(), tokens)
        self.assertEqual({i: (r["delivery"]["outcome"], r["delivery"]["attempts"], r["delivery"]["errors"])
                          for i, r in records.items()}, {
            61: ("terminal", 1, ["http_302"]),            # Redirect refused, never followed.
            62: ("terminal", 1, ["http_401"]),            # Rejected token is not retried.
            63: ("delivered", 2, ["http_503"]),           # Transient upstream error recovers.
            64: ("deadline_exhausted", 1, ["timeout"]),   # Elapsed budget stops a third attempt.
            65: ("attempts_exhausted", 2, ["http_502", "http_502"]),
            66: ("delivered", 2, ["connection"]),         # Empty reply recovers.
            67: ("delivered", 1, []),
        })
        self.assertLessEqual(records[64]["delivery"]["elapsed_s"], 3.5)
        self.assertEqual({i for i, r in records.items() if not r["delivered"]}, {61, 62, 64, 65})
        self.assertEqual(sorted(int(path.split("-")[-1]) for path, _, _ in received),
                         [61, 62, 63, 63, 64, 65, 65, 66, 66, 67])
        for path, authorization, body in received:
            i = int(path.split("-")[-1])
            self.assertEqual(path, "/api/heartbeat/" + PATHS[i])
            self.assertEqual(authorization, f"Bearer {i:064x}")
            self.assertEqual(body, {"healthy": i != 67})

        # The run deadline caps every delivery even when the per-heartbeat budget is larger.
        received.clear()
        script.update({i: ["hang"] for i in PATHS})
        started = time.monotonic()
        records, result = self.run_adapter(env=trusted, args=["--send", "--url", origin, "--deadline", "2"])
        self.assertLess(time.monotonic() - started, 4)
        https_receiver.assert_sanitized(self, result, records.values(), tokens)
        self.assertTrue(all(r["delivery"]["outcome"] == "deadline_exhausted" and r["delivery"]["attempts"] == 1
                            and r["delivery"]["errors"] == ["timeout"] for r in records.values()))

        # Untrusted certificates cannot receive tokens and are not retried.
        received.clear()
        records, result = self.run_adapter(args=["--send", "--url", origin],
                                           env={"CURL_CA_BUNDLE": "/etc/ssl/certs/ca-certificates.crt"})
        https_receiver.assert_sanitized(self, result, records.values(), tokens)
        self.assertTrue(all(r["delivery"]["errors"] == ["certificate"] and r["delivery"]["outcome"] == "terminal"
                            for r in records.values()))
        self.assertEqual(received, [])

        # Connection refusal is transient but bounded by attempts; a missing token is terminal.
        (self.root / "tokens" / "kuma-67-push").unlink()
        with socket.socket() as closed:
            closed.bind(("127.0.0.1", 0))
            refused = f"https://127.0.0.1:{closed.getsockname()[1]}"
        records, result = self.run_adapter(args=["--send", "--url", refused, "--delivery-attempts", "2"])
        https_receiver.assert_sanitized(self, result, records.values(), tokens)
        self.assertEqual(records.pop(67)["delivery"],
                         {"attempts": 0, "outcome": "terminal", "errors": ["token_unreadable"], "elapsed_s": 0.0})
        self.assertTrue(all(r["delivery"]["errors"] == ["connect", "connect"]
                            and r["delivery"]["outcome"] == "attempts_exhausted" for r in records.values()))

if __name__ == "__main__":
    unittest.main()
