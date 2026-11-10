# Host health producers — Vesper's NUC and Proxmox sources

Uptime Kuma is retired. Its container and Compose service are removed, and the old Kuma Proxmox timer (`proxmox-health-push.timer`) is disabled and inactive. These two producers are now Vesper's only sources of host-level health. Vesper notifications are enabled, so a missing heartbeat is a real alert: a stopped producer turns its checks Down and notifies.

Check paths keep their historical `kuma-<id>` suffixes, and tokens keep their `kuma-<id>-push` filenames. These are stable Vesper identifiers, not a dependency on Kuma; do not rename them.

Both producers default to **dry-run**: they run probes, print one JSON record per check, and neither read tokens nor send requests. `--send` opts into bearer-authenticated HTTPS heartbeats to `https://vesper.cfb.dev/api/heartbeat/<path>` with body `{"healthy": <bool>}`.

Local fixture tests (no homelab contact, no real heartbeats):

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s vesper/producers -p 'test_*.py' -v
systemd-analyze verify "$PWD/vesper/producers/vesper-proxmox.service" "$PWD/vesper/producers/vesper-proxmox.timer"
```

## NUC Docker and DNS — `host-health.py`

Reads `nuc-checks.json`: eight Docker container states and two DNS resolvers queried for the A record of `home.cfb.dev`. Uses Python 3, curl, the Docker CLI and `dig` on the NUC host, not Docker from inside Vesper. Optional ping support remains for a future networking layer.

- Docker requires running status and, when Docker reports one, healthy status.
- DNS requires NOERROR plus an IPv4 A answer.
- ICMP requires an actual echo reply.
- Missing tools, invalid output and timeouts report `healthy: false`. These push checks report failure and recovery immediately; they have no three-failure/two-pass thresholds.

Four workers limit fan-out, and each probe command has an eight-second timeout. Exit 1 means at least one failed probe or, with `--send`, at least one undelivered heartbeat.

`vesper-nuc.cron` is one entry in **cfb's existing crontab**, alongside the ManaVault demo reset and Dockhand update jobs. It runs every minute: `flock` on `data/vesper-nuc.lock` prevents overlap, and `timeout --kill-after=5s 45s` bounds the process. The heartbeat deadline is 120 seconds. An explicit PATH includes Snap Docker. It uses this checkout's script and manifest, plus tokens in `secrets/vesper/kuma-<id>-push`, so keep those paths available. Output goes to the journal under `vesper-nuc`.

```sh
python3 vesper/producers/host-health.py           # dry-run
journalctl -t vesper-nuc --since '10 minutes ago' # scheduled results
```

## Proxmox — `proxmox-health.py`

Installed at `/usr/local/lib/vesper/proxmox-health.py`, with tokens `kuma-61-push` through `kuma-67-push` in `/etc/vesper-proxmox`. The token directory is root-owned mode 700 and the token files are 600. `vesper-proxmox.service` and `.timer` live in `/etc/systemd/system`.

| Signal | Vesper destination | Default condition |
| --- | --- | --- |
| Storage | `proxmox/host-health/kuma-61` | Active and below 85%; ignore only usage for `frigate` |
| Thin pools | `proxmox/host-health/kuma-62` | Data and metadata each below 85% |
| ZFS | `proxmox/truenas-web/kuma-63` | VM 101 guest commands succeed; pools ONLINE, below 85%, healthy status |
| SMART | `proxmox/host-health/kuma-64` | At least one disk; all commands succeed and health passes |
| Backups | `proxmox/host-health/kuma-65` | Latest vzdump status OK and age below 26 hours |
| Mounts | `proxmox/host-health/kuma-66` | `/mnt/unas` and `/mnt/pve/backup` are mounted and respond |
| Systemd | `proxmox/host-health/kuma-67` | Successful query with no failed units |

CLI flags expose these settings; run `--help` for their names. Run the script as root for PVE, LVM and SMART access. It depends on Python 3, curl, `pvesm`, `pvesh`, `qm`, `lvs`, `smartctl`, `findmnt`, `stat` and `systemctl`. Commands use the C locale, so table parsing stays stable. Guest exit codes are checked. A nonzero SMART result fails even when stdout says PASSED.

- Seven workers run the signals independently.
- Each signal has a 45-second command budget (`--probe-timeout`, maximum 90), with a 30-second ceiling per command. Timed-out process groups are killed.
- Exit 0 means all signals were healthy and, with `--send`, delivered. Exit 3 means an unhealthy signal or a failed delivery. Python crashes exit 1 and invalid arguments exit 2.

The timer runs the oneshot every five minutes: three minutes after boot, with 15-second accuracy, a 90-second `TimeoutStartSec` and a five-second stop grace. `SuccessExitStatus=3` keeps a reported health condition from failing the reporting unit itself. Crashes and timeouts still fail the unit. Vesper's heartbeat deadline is 420 seconds (a 300-second interval plus 120 seconds of grace).

```sh
python3 /usr/local/lib/vesper/proxmox-health.py   # dry-run on Proxmox
systemctl list-timers vesper-proxmox.timer
journalctl -u vesper-proxmox.service --since '15 minutes ago'
```

Check each record's `healthy`, `delivered` and `delivery` fields, not just the unit's state. `scripts/proxmox-health-push.sh` was the retired Kuma producer; this adapter never invoked, sourced or shared credentials with it.

## Heartbeat delivery contract (both producers)

Delivery safety:

- HTTPS only, with TLS verification on.
- Redirects are never followed. Proxy environment variables and curlrc (`curl -q`) are ignored on both hosts.
- Tokens reach curl on stdin, never in arguments.
- Tokens must be 64 lowercase hex characters.

Each heartbeat is retried only after **transient** failures, bounded by every one of these limits:

| Bound | NUC default | Proxmox default | Flag |
| --- | --- | --- | --- |
| Attempts per heartbeat | 3 | 3 | `--delivery-attempts` (1–5) |
| Elapsed time per heartbeat, including backoff | 10 s | 20 s | `--delivery-budget` |
| Run deadline, measured from process start | 40 s | 80 s | `--deadline` |
| Per-attempt timeout | curl `--max-time` 5 s (connect 3 s), capped at time remaining; 0.25 s kill backstop | curl `--max-time` 5 s (connect 3 s), capped at time remaining; 1 s kill backstop | — |

Backoff is 1 s before attempt 2 and 2 s before attempt 3. No attempt starts with less than 1 s left after its backoff.

| Category | Retried | Cause |
| --- | --- | --- |
| `timeout` | yes | Connect or response timeout |
| `dns` | yes | Name resolution failure |
| `connect` | yes | Could not connect (curl 7) |
| `connection` | yes | Reset, closed or empty reply, send/receive error, malformed HTTP |
| `tls_handshake` | yes | TLS handshake failure other than certificate verification |
| `http_408`, `http_429`, `http_500`, `http_502`, `http_503`, `http_504` | yes | Transient HTTP status |
| `http_<other>` | no | Authentication, routing or redirect, such as `http_401`, `http_404`, `http_302` |
| `certificate` | no | Certificate verification or CA problem |
| `token_unreadable`, `token_invalid` | no | Local token file missing, unreadable or malformed; no request is sent |
| `curl_unavailable`, `curl_exit_<n>` | no | Local configuration or unknown error |

With `--send`, every record adds the following fields:

```json
"delivered": false,
"delivery": {"attempts": 2, "outcome": "attempts_exhausted", "errors": ["http_502", "http_502"], "elapsed_s": 1.05}
```

- `outcome` is one of `delivered`, `terminal`, `attempts_exhausted` or `deadline_exhausted`.
- `errors` lists each failed attempt's category in order. A heartbeat that recovers keeps them, for example `{"attempts": 2, "outcome": "delivered", "errors": ["timeout"], ...}`, so transient trouble stays visible even when delivery succeeds.
- `delivered` is true only for `outcome: delivered`.

Diagnostics are fixed category strings only. They never include tokens, request or response headers, response bodies, curl stderr or exception text.

**Budget arithmetic.** NUC: ten checks across four workers is three rounds. The 40-second run deadline stops new attempts and caps attempt timeouts five seconds before cron's 45-second timeout, which has five seconds of kill grace on top. Proxmox: a 45-second probe budget plus a 20-second delivery budget is about 65 seconds, within the 80-second run deadline and the 90-second systemd timeout. Neither production deadline changed. Both transports use a total transfer timeout, so trickling response bytes cannot reset it; subprocess timeouts provide a kill backstop. These are delivery deadlines, not probe deadlines. Scheduling overhead and uninterruptible kernel I/O can outlast userspace deadlines. A missing heartbeat still becomes Down.

**Why retries were added.** At 14:54 UTC on 2026-11-10, five healthy Proxmox observations failed delivery. Their checks passed the 420-second deadline, and the next cycle recovered. The cause is unknown because the previous version discarded curl's status and exit code, and Traefik logged no matching 4xx. Retries are idempotent: a duplicate heartbeat only refreshes the same state.

## Operations

To pause either producer, pause the matching Vesper checks first so notifications don't fire, then disable only its own scheduler entry:

- **NUC:** pause the ten NUC checks, then remove only the `vesper-nuc` line from cfb's crontab (never replace the whole crontab).
- **Proxmox:** pause `proxmox/host-health` and `proxmox/truenas-web/kuma-63`, then disable `vesper-proxmox.timer` and stop the service if it is running. Leave TrueNAS's other checks running.

Installing an updated script is a separate, approved rollout. NUC cron executes this repository's script directly, so changing it deploys to NUC immediately; Proxmox executes a separately installed copy. The unit and cron files were not modified by the delivery-retry change.

## History

- **2026-11-10:** the NUC cron producer and the Proxmox adapter were activated with owner approval. Both were verified first with dry-runs, then with real deliveries over verified HTTPS. A temporary Proxmox dry-run found the real `pvesm status` header includes `(KiB)` units; the parser now normalizes them.
- **Later on 2026-11-10:** routes were consolidated. The six Proxmox host signals moved under `proxmox/host-health`, guest ZFS under `proxmox/truenas-web`, and the NUC DNS/runtime checks into their application services. Tokens, thresholds and timing were unchanged.
- **After that:** Uptime Kuma was retired, as described at the top of this file.
- **16:47 UTC, 2026-11-10:** bounded delivery retries and sanitized diagnostics were deployed with approval to both hosts using atomic script replacement. Review caught a NUC per-read timeout that could exceed its budget under trickled response headers; a real HTTPS regression failed before switching NUC delivery to curl's total-transfer timeout. All eight tests pass, including retry recovery, permanent failures, both deadline limits, slow headers and secret-free output. Real-host dry-runs passed before replacement. Cron, units, manifests, tokens, health thresholds and Vesper configuration were unchanged. Rollback source copies are in `data/vesper-backups/producer-retries-20261110/`; Proxmox also retains `/usr/local/lib/vesper/.proxmox-health-before-retries-20261110.py`. Local source changes are uncommitted.
- **Post-rollout verification:** four NUC cron cycles produced 40 healthy, delivered results with the new diagnostics. The next natural Proxmox timer run delivered all seven signals on their first attempts and exited 0; its timer remained enabled/active. Vesper independently received all 17 push checks after replacement and showed all 60 checks healthy, no open incidents, database integrity `ok`, and alerts enabled for all 43 services. No container restarted and the runtime configuration revision was unchanged. Transient failures were injected only into disposable HTTPS tests, never into production.
