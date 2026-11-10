#!/usr/bin/env python3
"""Read-only host probes. Dry-run by default; --send opts into Vesper heartbeats."""

import argparse
import ipaddress
import json
import re
import subprocess
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


TRANSIENT_HTTP = {408, 429, 500, 502, 503, 504}
CURL_ERRORS = {
    6: ("dns", True), 7: ("connect", True), 28: ("timeout", True), 35: ("tls_handshake", True),
    16: ("connection", True), 18: ("connection", True), 52: ("connection", True),
    55: ("connection", True), 56: ("connection", True),
    51: ("certificate", False), 58: ("certificate", False), 60: ("certificate", False),
    77: ("certificate", False), 83: ("certificate", False), 90: ("certificate", False),
    91: ("certificate", False),
}
ATTEMPT_TIMEOUT = 5  # curl's total transfer timeout, including DNS and response headers.
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


def probe(check):
    kind, target = check["kind"], check["target"]
    try:
        if kind == "docker":
            command = ["docker", "inspect", "--format", "{{json .State}}", target]
        elif kind == "dns":
            command = ["dig", f"@{target}", check["hostname"], "A",
                       "+time=3", "+tries=1", "+noall", "+comments", "+answer"]
        elif kind == "ping":
            command = ["ping", "-n", "-c", "1", "-W", "3", "-w", "5", target]
        else:
            raise ValueError("unknown probe kind")
        result = subprocess.run(command, capture_output=True, text=True, timeout=8, check=False)
        if result.returncode != 0:
            return False, f"{kind} command failed"
        if kind == "docker":
            state = json.loads(result.stdout)
            healthy = state.get("Status") == "running" and not state.get("Restarting", False)
            healthy = healthy and state.get("Health", {}).get("Status", "healthy") == "healthy"
            return healthy, "container running/health state"
        if kind == "dns":
            answers = re.findall(r"^\S+\s+\d+\s+IN\s+A\s+(\S+)\s*$", result.stdout, re.MULTILINE)
            healthy = "status: NOERROR," in result.stdout and bool(answers)
            healthy = healthy and all(ipaddress.ip_address(a).version == 4 for a in answers)
            return healthy, "DNS NOERROR with an IPv4 A answer"
        return True, "ICMP reply received"
    except (OSError, subprocess.TimeoutExpired, ValueError, TypeError, AttributeError):
        return False, f"{kind} probe unavailable or invalid response"


def deliver(path, healthy, args, deadline):
    try:
        token = (args.secrets_dir / (path.split("/")[-1] + "-push")).read_text().strip()
    except (OSError, UnicodeError):
        return {"attempts": 0, "outcome": "terminal", "errors": ["token_unreadable"], "elapsed_s": 0.0}
    if not re.fullmatch(r"[a-f0-9]{64}", token):  # Expected a locally generated 256-bit token.
        return {"attempts": 0, "outcome": "terminal", "errors": ["token_invalid"], "elapsed_s": 0.0}

    def send(timeout):
        # Total transfer deadline, not a per-read timeout. Token stays on stdin.
        try:
            result = subprocess.run([
                "curl", "-q", "--silent", "--fail", "--noproxy", "*", "--proto", "=https",
                "--connect-timeout", f"{min(3, timeout):.3f}", "--max-time", f"{timeout:.3f}",
                "--output", "/dev/null", "--write-out", "%{http_code}", "--config", "-",
                "--header", "Content-Type: application/json", "--data", json.dumps({"healthy": healthy}),
                "--url", args.url.rstrip("/") + "/api/heartbeat/" + path,
            ], input=f'header = "Authorization: Bearer {token}"\n', text=True,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout + 0.25)
        except subprocess.TimeoutExpired:
            return "timeout", True
        except OSError:
            return "curl_unavailable", False
        status, code = result.stdout.strip(), result.returncode
        if code in (0, 22) and re.fullmatch(r"[1-5][0-9]{2}", status):
            if code == 0 and status.startswith("2"):
                return None, False
            return f"http_{status}", int(status) in TRANSIENT_HTTP
        return CURL_ERRORS.get(code, (f"curl_exit_{code}", False))

    return with_retries(send, args.delivery_attempts, deadline)


def main():
    started = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checks", type=Path, default=Path(__file__).with_name("nuc-checks.json"))
    parser.add_argument("--send", action="store_true", help="send results; omitted means no heartbeats")
    parser.add_argument("--url", default="https://vesper.cfb.dev")
    parser.add_argument("--secrets-dir", type=Path, default=Path(__file__).resolve().parents[2] / "secrets/vesper")
    parser.add_argument("--delivery-attempts", type=int, default=3, help="attempts per heartbeat (1-5)")
    parser.add_argument("--delivery-budget", type=float, default=10,
                        help="seconds per heartbeat, including retries and backoff")
    parser.add_argument("--deadline", type=float, default=40,
                        help="seconds after start by which deliveries stop; below cron's 45-second timeout")
    args = parser.parse_args()
    if not (1 <= args.delivery_attempts <= 5 and args.delivery_budget > 0 and args.deadline > 0):
        parser.error("invalid delivery attempts (1-5), budget or deadline")
    origin = urllib.parse.urlsplit(args.url)
    if (origin.scheme != "https" or not origin.hostname or origin.username or origin.password
            or origin.path not in ("", "/") or origin.query or origin.fragment):
        parser.error("--url must be an HTTPS origin without credentials, query or path")
    checks = json.loads(args.checks.read_text())
    paths = set()
    for check in checks:
        path = check["path"]
        if not re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_-]+/kuma-[0-9]+", path) or path in paths:
            parser.error("check paths must be unique machine/service/kuma-ID values")
        paths.add(path)
        if check["kind"] not in ("docker", "dns", "ping"):
            parser.error("unknown probe kind")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", check["target"]) or check["target"].startswith("-"):
            parser.error("invalid probe target")
        if check["kind"] == "dns" and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*", check["hostname"]):
            parser.error("invalid DNS hostname")

    def run_check(check):
        healthy, message = probe(check)
        result = {"path": check["path"], "healthy": healthy, "message": message}
        if args.send:
            deadline = min(time.monotonic() + args.delivery_budget, started + args.deadline)
            delivery = deliver(check["path"], healthy, args, deadline)
            result["delivered"] = delivery["outcome"] == "delivered"
            result["delivery"] = delivery
        return result

    failed = False
    # Bound the twelve-check cycle without letting a slow target stall other probes.
    with ThreadPoolExecutor(max_workers=4) as workers:
        for result in workers.map(run_check, checks):
            failed = failed or not result["healthy"] or not result.get("delivered", True)
            print(json.dumps(result), flush=True)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
