# Kuma → Vesper monitor mapping

## Service removals and regrouping — 2026-11-13

Dashy and ClipCascade were removed from the stack, along with their checks, `nuc/dashy` (28) and `nuc/clipcascade` (8). MariaDB's runtime push check (55) moved from its own `nuc/docker-mariadb` service to `nuc/grimmory`, because MariaDB holds only Grimmory's `booklore` database. Its producer path is now `nuc/grimmory/kuma-55`; its token and thresholds are unchanged. Vesper now validates **58 checks across 40 services** on four machines. Older counts below are historical.

## Current alert ownership — 2026-11-10

Vesper is now the alerting authority for the **58 mapped checks across 40 services** (60 across 43 before the 2026-11-13 changes), with Telegram configured and every service's notifications enabled. The existing Kuma bot/chat credentials were transferred directly into restricted secret files without displaying their values. Telegram accepted Vesper's test at 16:19:28 UTC; this is API acceptance, not a read receipt. The owner separately confirmed successful production use.

Kuma is retired with the owner's approval. The three remaining checks, **www (2), gateway (50) and internet (51)**, were deleted through its API; their coverage is deliberately absent until the networking layer is added. Its container and Compose service were removed, and its Proxmox timer was disabled/stopped. Vesper's producers and Telegram alerts remain active. All 33 remaining containers kept their identities/start times/restart counts; Kuma's old URL now returns 404. Stable Vesper `kuma-*` IDs are retained to preserve history.

Kuma's stopped data directory and dormant Proxmox script/unit/credential files remain available for rollback. A consistent pre-deletion database and the former Compose file are saved privately in `data/vesper-backups/kuma-retirement-20261110/`; the earlier alert-cutover backup also remains. These databases contain credentials. No independent Vesper watchdog was found installed, so monitoring Vesper from another failure domain remains separate work.

The earlier Proxmox incident followed five failed heartbeat deliveries at 14:54 UTC despite healthy probes; the next cycle recovered. Existing logging cannot identify the precise transport error. All 105 subsequent results inspected from 15:00 UTC delivered successfully. See the rollout README for evidence, limitations and rollback. Local changes remain uncommitted.

## Historical shadow inventory and verification

The Vesper destinations below remain current, apart from the 2026-11-13 changes noted in their rows. Statements about notifications being disabled, Kuma owning alerts, the three deferred monitors remaining in Kuma, or preserving its running timer describe the earlier shadow stages and are superseded by the retirement above.

Prepared 2026-11-10 from the live Kuma SQLite database opened read-only, local Traefik routing, Docker inventory, and `scripts/proxmox-health-push.sh`. Vesper was subsequently deployed alongside Kuma with approval that day. No Kuma monitor, notification, producer, or existing running service was changed.

Of the **63 active non-group Kuma monitors**, **60 remain configured and enabled in Vesper across four machines and 43 services, with none paused**. Active checks comprise 43 HTTP/TCP checks, ten NUC-produced Docker/DNS push checks and seven Proxmox push checks. Six Proxmox producer checks share **Host health**; guest ZFS is grouped with TrueNAS's UI/SMB/NFS checks. Each grouped check has its own display name and result in drill-down. Frigate and TrueNAS UI use their existing credential-free LAN HTTP endpoints; browser HTTPS and certificates remain unchanged. Gateway and External were removed at the owner's request: www (#2), gateway ping (#50) and internet ping (#51) are deferred to a future networking layer and remain in Kuma only. Notifications remain disabled for every service, and Telegram is absent. The NUC producer runs every minute from cfb's crontab; the independent Proxmox systemd timer runs every five minutes.

Read-only `qm list` and `pct list` confirmed Proxmox owns Home Assistant (VM 100), TrueNAS (VM 101), The Gathering (LXC 102), Audiobookshelf (103), Plex (104), NZBGet (105), Frigate (106), Ollama (107), Jellyfin (108) and Fladder (109). Their services now live under `proxmox`; the owner also requested grouping KVM there, without changing its target or claiming it is a VM. NUC, AdGuard replica and UNAS remain separate. Only Vesper was recreated during the original machine regrouping; subsequent changes hot-reloaded without restarting it. Moved check IDs start new history; old records were not manually rewritten or deleted. All 43 services select a bundled or locally uploaded app icon; see `icon-sources.json` and the README's icon backup notes.

Application consolidation groups ManaVault main/demo, AdGuard web/DNS/sync, Authelia API/runtime, Dockhand API/MCP, Nimotsu routed/direct API, Mosquitto TCP/runtime, Cloudflare readiness/runtime, TrueNAS UI/SMB/NFS/ZFS and replica AdGuard web/DNS. Unrelated applications remain separate. Display names omit “container”; existing destination service keys are retained wherever possible to minimize history resets. Twelve moved check IDs start new history, with endpoints, thresholds, tokens and producer cadence unchanged. The machine service counts are NUC 28, Proxmox 13, replica 1 and UNAS 1.

Application consolidation verification: the pinned validator and seven producer tests passed. All 60 live checks were healthy, with at least two successes on every HTTP/TCP check and real receipt on all 17 push routes. Subsequent NUC cron and Proxmox timer runs delivered successfully, including ZFS under TrueNAS. Every service still has notifications off, Telegram is absent and the delivery table is empty. All container IDs/start times/restart counts, Kuma producer files and both Proxmox timer definitions were unchanged. The deployed frontend rendered all 43 icons without broken images; a captured-data browser check confirmed two mobile columns and the four named TrueNAS checks. The uneven desktop layout led to the subsequently approved full-width rows.

The full-width overview was deployed to Vesper only at 15:43 UTC on 2026-11-10, using source revision `fcf3e46bf9df8288affcf62cd1cf41601b946106` and pinned image digest `sha256:a3d4d01444c309d344f97683e05c95e295441a31f35d6566a1182a2ad46db42d`. All 43 services and 60 checks recovered healthy with new post-restart samples and scheduled heartbeats. Runtime configuration and all notification flags are unchanged; Telegram is absent and notification deliveries remain zero. All 33 other containers, including Kuma, retained their identities/start times/restart counts. Prior history survived for every check; database integrity passed. Captured production data rendered with the deployed assets shows full-width desktop rows and two mobile columns. The README records the pre-upgrade backup and rollback pin; signed-in Authelia browser access remains unverified.

Each supported check has ID `kuma-<original-id>`. The destination column below is `machine/service`; its source is `../home-config/vesper/machines/<machine>.yaml` relative to the homelab repository root, mounted read-only at `/config/machines/<machine>.yaml`. The YAML was moved unchanged out of this repository. A heartbeat's eventual path is `/api/heartbeat/<machine>/<service>/kuma-<id>`.

The dashboard is at `https://vesper.cfb.dev` on LAN split DNS. TLS validation, anonymous redirects to the existing Authelia login and direct untrusted-peer rejection passed. Signed-in browser access has not been independently verified. SQLite writes and integrity checks passed; no notification delivery rows were present. NUC activation required no container restart or Kuma changes. Kuma remains the alerting authority.

## Status and deliberate differences

- **Candidate:** active in the deployed YAML, but still being compared with Kuma before cutover. All 37 HTTP and four TCP checks reported healthy after regrouping, including container-name targets and Proxmox with its authentic CA. Long-running parity and application-level health remain to be verified.
- **LAN HTTP:** Frigate checks `http://10.0.69.80:5000/api/version` for 200 instead of HTTPS/8971 for 401; TrueNAS checks `http://10.0.69.74/ui/` for 200 instead of its HTTPS root. Neither sends credentials or follows redirects. These verify Frigate application response and TrueNAS UI availability, not TLS, camera/recording or storage health. Both endpoints were already LAN-accessible; no backend listener, authentication or certificate configuration changed.
- **Active producer:** the ten NUC Docker/DNS checks are unpaused, with real HTTPS heartbeat receipt verified. cfb's per-minute cron entry uses `flock` for non-overlap and a 45-second timeout plus five-second kill grace. Existing cron jobs are preserved; journal messages use the `vesper-nuc` tag.
- **Active Proxmox producer:** all seven signals are unpaused. The independent script and service/timer are installed, and the timer is enabled for boot. The seven dedicated Vesper tokens were transferred over verified SSH to a root-owned mode-700 directory with mode-600 files. The installed dry-run and initial systemd run reported every signal healthy; all seven real HTTPS receipts succeeded. Kuma's producer is unchanged.
- **Port resolved:** code-server explicitly configures PORT=8843 and returns HTTP 200 there. Port 8443 refuses connections despite the image's EXPOSE metadata. The original Kuma URL was correct and is now enabled in the prepared Vesper YAML.

For all HTTP candidates accepting Kuma's `200–299`, Vesper is configured with **exact 200**, a stricter provisional expectation, because this version accepts only one status code. NZBGet retains exact **401**; Frigate's new HTTP API check expects **200**. Redirect following remains enabled for the other checks to preserve Kuma's intended navigation behavior, but is disabled for Frigate and TrueNAS so a redirect cannot hide the intended response. A login page returning 200 does not prove application health; verify final destinations and body expectations before cutover.

Active polling deliberately changes from Kuma's 60 seconds to **30 seconds, 5-second timeout, three consecutive failures, two passes**. Kuma's `maxretries` is not assumed to mean the same thing as Vesper's threshold. DNS/ICMP and Docker checks are not replaced with TCP reachability. TCP checks only prove a listener is reachable, not successful SMB/NFS/MQTT operations.

Public service hostnames use the existing LAN split-DNS path and do not prove Cloudflare/external reachability. The removed www check's four Cloudflare addresses were removed from the outbound allowlist. No dependency suppression is configured until host health signals are proven.

## Complete mapping

| Kuma ID | Kuma monitor | Type | Vesper machine/service | Prepared state |
| --- | --- | --- | --- | --- |
| 2 | www | HTTP | — | Deferred; removed with External, remains in Kuma |
| 3 | AdGuard | HTTP | `nuc/adguard-web` | Candidate |
| 4 | Homebox | HTTP | `nuc/homebox` | Candidate |
| 5 | Grimmory (books) | HTTP | `nuc/grimmory` | Candidate |
| 6 | Seerr (request) | HTTP | `nuc/seerr` | Candidate |
| 7 | IT-Tools | HTTP | `nuc/tools` | Candidate |
| 8 | ClipCascade | HTTP | — | Removed 2026-11-13 with the service |
| 9 | Convert | HTTP | `nuc/convert` | Candidate |
| 10 | ManaVault | HTTP | `nuc/manavault` | Candidate |
| 11 | ManaVault demo | HTTP | `nuc/manavault` | Candidate |
| 12 | Nimotsu API | HTTP | `nuc/nimotsu-public` | Candidate |
| 13 | Authelia | HTTP | `nuc/authelia-web` | Candidate |
| 14 | Home Assistant | HTTP | `proxmox/home-assistant` | Candidate |
| 15 | Jellyfin | HTTP | `proxmox/jellyfin` | Candidate |
| 16 | Audiobookshelf | HTTP | `proxmox/audiobookshelf` | Candidate |
| 17 | Fladder (stream) | HTTP | `proxmox/fladder` | Candidate |
| 18 | The Gathering | HTTP | `proxmox/gathering` | Candidate |
| 19 | KVM | HTTP | `proxmox/kvm` | Candidate; grouped under Proxmox by request |
| 21 | Radarr | HTTP | `nuc/radarr` | Candidate |
| 22 | Sonarr | HTTP | `nuc/sonarr` | Candidate |
| 23 | Bazarr | HTTP | `nuc/bazarr` | Candidate |
| 24 | Prowlarr | HTTP | `nuc/prowlarr` | Candidate; gluetun network namespace |
| 25 | Shelfmark | HTTP | `nuc/shelfmark` | Candidate; gluetun network namespace |
| 26 | Copyparty | HTTP | `nuc/copyparty` | Candidate |
| 27 | code-server | HTTP | `nuc/code-server` | Candidate; configured 8843 verified HTTP 200 |
| 28 | Dashy | HTTP | — | Removed 2026-11-13 with the service |
| 29 | ESPHome | HTTP | `nuc/esphome` | Candidate; host-network endpoint |
| 30 | Dockhand | HTTP | `nuc/dockhand` | Candidate |
| 31 | BookBridge | HTTP | `nuc/bookbridge` | Candidate |
| 32 | Nimotsu | HTTP | `nuc/nimotsu-public` | Candidate |
| 33 | Frigate | HTTP | `proxmox/frigate` | LAN HTTP; port 5000 API, expected 200 |
| 34 | Proxmox UI | HTTP | `proxmox/web` | Candidate; authentic CA and IP SAN verified, HTTP 200 |
| 35 | Houndarr | HTTP | `nuc/houndarr` | Candidate |
| 36 | Dockhand MCP | HTTP | `nuc/dockhand` | Candidate |
| 38 | Plex | HTTP | `proxmox/plex` | Candidate |
| 39 | NZBGet | HTTP | `proxmox/nzbget` | Candidate; expected 401 |
| 40 | Ollama | HTTP | `proxmox/ollama` | Candidate |
| 41 | TrueNAS UI | HTTP | `proxmox/truenas-web` | LAN HTTP; /ui/, expected 200 |
| 42 | TrueNAS SMB | TCP | `proxmox/truenas-web` | Candidate |
| 43 | TrueNAS NFS | TCP | `proxmox/truenas-web` | Candidate |
| 44 | UNAS NFS | TCP | `unas/nfs` | Candidate |
| 45 | AdGuard replica UI | HTTP | `replica/web` | Candidate |
| 47 | AdGuard DNS (nuc) | DNS → push | `nuc/adguard-web` | Active producer; real A query and receipt verified |
| 48 | AdGuard DNS (replica) | DNS → push | `replica/web` | Active producer; real A query and receipt verified |
| 49 | Mosquitto MQTT | TCP | `nuc/mqtt` | Candidate |
| 50 | Gateway | ICMP | — | Deferred networking layer; remains in Kuma |
| 51 | Internet (1.1.1.1) | ICMP | — | Deferred networking layer; remains in Kuma |
| 53 | traefik | Docker | `nuc/docker-traefik` | Active producer |
| 54 | authelia | Docker | `nuc/authelia-web` | Active producer |
| 55 | mariadb | Docker | `nuc/grimmory` | Active producer; moved from `nuc/docker-mariadb` 2026-11-13 |
| 56 | gluetun | Docker | `nuc/docker-gluetun` | Active producer |
| 57 | mosquitto | Docker | `nuc/mqtt` | Active producer |
| 58 | recyclarr | Docker | `nuc/docker-recyclarr` | Active producer |
| 59 | adguard-sync | Docker | `nuc/adguard-web` | Active producer |
| 61 | PVE storage | Push | `proxmox/host-health` | Active Proxmox producer |
| 62 | LVM thin pools | Push | `proxmox/host-health` | Active Proxmox producer |
| 63 | TrueNAS ZFS pools | Push | `proxmox/truenas-web` | Active Proxmox producer |
| 64 | Disk SMART | Push | `proxmox/host-health` | Active Proxmox producer |
| 65 | vzdump backups | Push | `proxmox/host-health` | Active Proxmox producer |
| 66 | NFS and backup mounts | Push | `proxmox/host-health` | Active Proxmox producer |
| 67 | PVE systemd units | Push | `proxmox/host-health` | Active Proxmox producer |
| 68 | Cloudflare tunnel | HTTP | `nuc/cloudflare-tunnel` | Candidate; local readiness only |
| 69 | cloudflared | Docker | `nuc/cloudflare-tunnel` | Active producer |

## Producer prerequisites

All 17 configured push checks use unique secret filenames `kuma-<id>-push` under `/run/secrets`. Independent 256-bit tokens were generated in the ignored `secrets/vesper` directory; the two unused ICMP tokens remain untouched. No Kuma token was copied. All 17 tokens are now used for HTTPS heartbeat delivery. On the NUC, owner and UID 10001 ACLs permit access with no access for other users. The seven Proxmox tokens also reside under `/etc/vesper-proxmox` on that host, protected by root ownership and directory/file modes 700/600. Paused heartbeat routes reject submissions until deliberately enabled.

`producers/host-health.py` emits one result per check using `producers/nuc-checks.json`. Docker IDs 53–59 and 69 require running and, when present, healthy status. DNS IDs 47/48 require NOERROR and an A answer; ICMP IDs 50/51 have been removed from this manifest. The installed cadence is 60 seconds plus 60 seconds grace, stale after 180 seconds. It runs on the NUC; Vesper has no Docker socket or remote execution capability. Confirm running/health semantics against Kuma over time, especially jobs such as Recyclarr. DNS uses push checks in Vesper: a reported failure is immediate rather than a native three-sample failure streak. Compare that deliberate difference before cutover.

For Proxmox IDs 61–67, `producers/proxmox-health.py` independently implements the existing seven signals and thresholds: storage/thin-pool/ZFS usage, SMART health, latest vzdump success/freshness, mounted/responding filesystems and failed units. It defaults to dry-run, does not invoke Kuma's script or read its credentials, and requires `--send` for delivery. It rejects malformed output, unsuccessful commands and failed guest exit codes rather than claiming health. Six report to `proxmox/host-health/kuma-<id>`; TrueNAS ZFS reports to `proxmox/truenas-web/kuma-63`. The live Kuma script and timer remain unchanged.

The first temporary Proxmox run caught a storage-header mismatch: real `pvesm status` output includes `(KiB)` units. A fixture reproducing that output failed before the parser fix; all seven local tests passed afterward, and the corrected real-host run returned seven healthy signals. No thresholds or live Kuma files changed.

Proxmox push deadlines are 300 seconds expected interval + 120 seconds grace, stale after 600 seconds. The installed Vesper timer uses a five-minute interval and 15-second accuracy; its separate service has a 90-second timeout. Each signal has a 45-second probe budget plus bounded delivery, normally finishing within about 52 seconds. Real delivery passed from the installed service. The existing Kuma timer remains at five minutes with one-minute accuracy and no whole-run timeout. These are deliberately not Kuma's 600-second/300-second-retry settings. Vesper treats a missed deadline or unhealthy heartbeat as Down immediately and recovers on one healthy heartbeat, unlike active-check failure/pass streaks.

The installed Kuma Proxmox script matches the repository copy and was not edited or manually run. Exit status 0 does not prove successful Kuma health checks or delivery; see `producers/README.md` for the inspection findings. Both Vesper producers are now scheduled independently of Kuma. Published-image validation passes with the owner-approved no-new-privileges exception for Snap Docker compatibility; default AppArmor/seccomp and the other container restrictions remain. See README.md for remaining access, TLS and cutover gates.

The normal Proxmox timer cycle at 09:18:16 EST on 2026-11-10 independently verified scheduled delivery: all seven journal results were healthy and delivered, the service exited 0, and all seven Vesper receipt timestamps advanced. The snapshot showed 58 healthy and two paused checks. All 60 notification flags remained false, Telegram was absent, and there were zero notification deliveries. Kuma's script/service/timer hashes and active timer were unchanged; all 34 NUC containers retained their IDs, start times and restart counts.

Subsequent host-health consolidation preserved all 60 checks and their thresholds/tokens, reducing the service count from 60 to 54. The image validator and all seven producer tests passed. The updated installed producer delivered seven healthy results to the grouped service, and the API confirmed their individual names and receipts: 52 healthy services and two paused, comprising 58 healthy checks and two paused. All 54 notification flags remained false, with zero notification deliveries. No container restarted, neither timer configuration changed, and Kuma's files remained unchanged. Only the seven moved checks start fresh history; old database records remain intact.
