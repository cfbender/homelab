#!/usr/bin/env python3
"""Independent Proxmox probes for Vesper. Dry-run unless --send is supplied."""

import argparse
import json
import os
import re
import shlex
import signal
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlsplit


CHECKS = {
    "storage": "proxmox/host-health/kuma-61",
    "thin": "proxmox/host-health/kuma-62",
    "zfs": "proxmox/truenas-web/kuma-63",
    "smart": "proxmox/host-health/kuma-64",
    "backup": "proxmox/host-health/kuma-65",
    "mounts": "proxmox/host-health/kuma-66",
    "systemd": "proxmox/host-health/kuma-67",
}


class CommandFailed(ValueError):
    def __init__(self, name, returncode, stdout):
        super().__init__(f"{name} failed")
        self.returncode, self.stdout = returncode, stdout


def command(argv, timeout, stdin=None):
    if timeout <= 0:
        raise TimeoutError("probe budget exhausted")
    with subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, start_new_session=True,
                          env={**os.environ, "LC_ALL": "C"}) as process:
        try:
            stdout, _ = process.communicate(stdin, timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise TimeoutError(f"{argv[0]} timed out") from None
        if process.returncode:
            # Commands may emit private data; report neither stderr nor arguments.
            raise CommandFailed(argv[0], process.returncode, stdout)
        return stdout


def percentage(value):
    number = float(value.rstrip("%"))
    if not 0 <= number <= 100:
        raise ValueError("invalid percentage")
    return number


class Probes:
    def __init__(self, args):
        self.args = args
        self.deadline = time.monotonic() + args.probe_timeout

    def run(self, *argv):
        return command(list(argv), min(30, self.deadline - time.monotonic()))

    def storage(self):
        lines = self.run("pvesm", "status").splitlines()
        header = lines[0].replace("(KiB)", "").split() if lines else []
        if header != ["Name", "Type", "Status", "Total", "Used", "Available", "%"]:
            raise ValueError("invalid storage table")
        rows = [line.split() for line in lines[1:] if line.strip()]
        if not rows:
            raise ValueError("no storage results")
        healthy = True
        for row in rows:
            name, _, status, _, _, _, used = row
            if status == "disabled":
                continue
            if status != "active":
                healthy = False
            elif name not in self.args.storage_ignore_usage:
                healthy = percentage(used) < self.args.usage_max and healthy
        return healthy

    def thin(self):
        output = self.run("lvs", "--noheadings", "--separator", " ", "-o",
                          "vg_name,lv_name,data_percent,metadata_percent", "-S", "segtype=thin-pool")
        healthy = True
        for line in output.splitlines():
            if not line.strip():
                continue
            _, _, data, metadata = line.split()
            healthy = max(percentage(data), percentage(metadata)) < self.args.usage_max and healthy
        return healthy  # A successful empty selection means there are no thin pools.

    def guest(self, *argv):
        result = json.loads(self.run("qm", "guest", "exec", str(self.args.truenas_vmid),
                                     "--timeout", "30", "--", *argv))
        if result.get("exited") != 1 or result.get("exitcode") != 0:
            raise ValueError("guest command failed or did not exit")
        output = result["out-data"]
        if not isinstance(output, str):
            raise ValueError("invalid guest output")
        return output

    def zfs(self):
        rows = [line.split() for line in self.guest("zpool", "list", "-H", "-o", "name,health,cap").splitlines()
                if line.strip()]
        if not rows:
            raise ValueError("no ZFS pools returned")
        healthy = True
        for row in rows:
            _, health, capacity = row
            healthy = health == "ONLINE" and percentage(capacity) < self.args.usage_max and healthy
        status = self.guest("zpool", "status", "-x")
        return "all pools are healthy" in status and healthy

    def smart(self):
        devices = [shlex.split(line.split("#", 1)[0]) for line in self.run("smartctl", "--scan").splitlines()]
        devices = [device for device in devices if device]
        if not devices:
            raise ValueError("no SMART devices returned")
        healthy = True
        for device in devices:
            output = self.run("smartctl", "-H", *device)
            healthy = bool(re.search(r"PASSED|: OK", output)) and healthy
        return healthy

    def backup(self):
        tasks = json.loads(self.run("pvesh", "get", f"/nodes/{socket.gethostname()}/tasks",
                                   "--typefilter", "vzdump", "--limit", "1", "--output-format", "json"))
        task = tasks[0]
        age = time.time() - int(task["starttime"])
        return task["status"] == "OK" and 0 <= age < self.args.backup_max_age_hours * 3600

    def mounts(self):
        for mount in self.args.mounts:
            self.run("findmnt", "-n", "--mountpoint", mount)
            self.run("stat", "-f", "--", mount)
        return True

    def systemd(self):
        return not self.run("systemctl", "--failed", "--no-legend", "--plain").strip()


TRANSIENT_HTTP = {408, 429, 500, 502, 503, 504}
# Fixed curl exit-code categories; curl's stderr is never read or printed.
CURL_ERRORS = {
    6: ("dns", True), 7: ("connect", True), 28: ("timeout", True), 35: ("tls_handshake", True),
    16: ("connection", True), 18: ("connection", True), 52: ("connection", True),
    55: ("connection", True), 56: ("connection", True),
    51: ("certificate", False), 58: ("certificate", False), 60: ("certificate", False),
    77: ("certificate", False), 83: ("certificate", False), 90: ("certificate", False),
    91: ("certificate", False),
}
ATTEMPT_TIMEOUT = 5  # curl --max-time per attempt, never beyond the delivery deadline.
MIN_ATTEMPT = 1  # Do not start an attempt with less time than this remaining.


def with_retries(send, attempts, deadline):
    """Call send(timeout) -> (error, transient) until delivered, terminal or out of attempts/time."""
    started, made, errors, outcome = time.monotonic(), 0, [], "attempts_exhausted"
    while made < attempts:
        delay = made  # Back off 1s, then 2s, ... between attempts.
        if deadline - time.monotonic() < delay + MIN_ATTEMPT:
            outcome = "deadline_exhausted"
            break
        time.sleep(delay)
        made += 1
        error, transient = send(min(ATTEMPT_TIMEOUT, deadline - time.monotonic()))
        if error is None:
            outcome = "delivered"
            break
        errors.append(error)
        if not transient:
            outcome = "terminal"
            break
    return {"attempts": made, "outcome": outcome, "errors": errors,
            "elapsed_s": round(time.monotonic() - started, 2)}


def deliver(path, healthy, args, deadline):
    try:
        token = (args.secrets_dir / (path.split("/")[-1] + "-push")).read_text().strip()
    except (OSError, UnicodeError):
        return {"attempts": 0, "outcome": "terminal", "errors": ["token_unreadable"], "elapsed_s": 0.0}
    if not re.fullmatch(r"[a-f0-9]{64}", token):
        return {"attempts": 0, "outcome": "terminal", "errors": ["token_invalid"], "elapsed_s": 0.0}

    def send(timeout):
        # -q ignores curlrc; no redirects/proxies, TLS verified, token only on stdin.
        try:
            status, code = command([
                "curl", "-q", "--silent", "--show-error", "--fail", "--noproxy", "*",
                "--proto", "=https", "--connect-timeout", f"{min(3, timeout):.3f}",
                "--max-time", f"{timeout:.3f}",
                "--output", "/dev/null", "--write-out", "%{http_code}", "--config", "-",
                "--header", "Content-Type: application/json", "--data", json.dumps({"healthy": healthy}),
                "--url", args.url.rstrip("/") + "/api/heartbeat/" + path,
            ], timeout + 1, stdin=f'header = "Authorization: Bearer {token}"\n'), 0
        except CommandFailed as error:
            status, code = error.stdout, error.returncode
        except TimeoutError:  # curl ignored --max-time; its process group was killed.
            return "timeout", True
        except OSError:
            return "curl_unavailable", False
        status = status.strip()
        if code in (0, 22) and re.fullmatch(r"[1-5][0-9]{2}", status):
            if code == 0 and status.startswith("2"):
                return None, False
            return f"http_{status}", int(status) in TRANSIENT_HTTP  # Redirects stay terminal.
        return CURL_ERRORS.get(code, (f"curl_exit_{code}", False))

    return with_retries(send, args.delivery_attempts, deadline)


def main():
    started = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--url", default="https://vesper.cfb.dev")
    parser.add_argument("--secrets-dir", type=Path, default=Path("/etc/vesper-proxmox"))
    parser.add_argument("--usage-max", type=int, default=85)
    parser.add_argument("--backup-max-age-hours", type=int, default=26)
    parser.add_argument("--truenas-vmid", type=int, default=101)
    parser.add_argument("--mounts", nargs="+", default=["/mnt/unas", "/mnt/pve/backup"])
    parser.add_argument("--storage-ignore-usage", nargs="*", default=["frigate"])
    parser.add_argument("--probe-timeout", type=float, default=45, help="seconds per signal, shared by its commands")
    parser.add_argument("--delivery-attempts", type=int, default=3, help="attempts per heartbeat (1-5)")
    parser.add_argument("--delivery-budget", type=float, default=20,
                        help="seconds per heartbeat, including retries and backoff")
    parser.add_argument("--deadline", type=float, default=80,
                        help="seconds after start by which deliveries stop; below systemd's 90-second timeout")
    args = parser.parse_args()
    origin = urlsplit(args.url)
    if (origin.scheme != "https" or not origin.hostname or origin.username or origin.password
            or origin.path not in ("", "/") or origin.query or origin.fragment):
        parser.error("--url must be an HTTPS origin without credentials, query or path")
    if not (0 < args.usage_max <= 100 and args.backup_max_age_hours > 0
            and args.truenas_vmid > 0 and 0 < args.probe_timeout <= 90):
        parser.error("invalid threshold, VM ID or probe timeout (maximum 90 seconds)")
    if not (1 <= args.delivery_attempts <= 5 and args.delivery_budget > 0 and args.deadline > 0):
        parser.error("invalid delivery attempts (1-5), budget or deadline")

    def check(name, path):
        try:
            healthy = getattr(Probes(args), name)()
            message = "healthy" if healthy else "health condition failed"
        except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError, TimeoutError):
            healthy, message = False, "probe unavailable, timed out or invalid response"
        result = {"path": path, "healthy": healthy, "message": message}
        if args.send:
            deadline = min(time.monotonic() + args.delivery_budget, started + args.deadline)
            delivery = deliver(path, healthy, args, deadline)
            result["delivered"] = delivery["outcome"] == "delivered"
            result["delivery"] = delivery
        return result

    failed = False
    # Each signal has its own budget and delivery; failures cannot block other signals.
    with ThreadPoolExecutor(max_workers=len(CHECKS)) as workers:
        futures = [workers.submit(check, name, path) for name, path in CHECKS.items()]
        for future in as_completed(futures):
            result = future.result()
            print(json.dumps(result), flush=True)
            failed = failed or not result["healthy"] or not result.get("delivered", True)
    return 3 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
