# Vesper rollout — primary alerts enabled

Vesper runs as service and container `vesper` in the main `docker-compose.yml`, under the `homelab` project. This directory holds producer scripts and rollout history, not a separate stack. The former `vesper-shadow` project is retired; do not start a second instance against the same database.

Compose uses `ghcr.io/cfbender/vesper:latest` directly. Configuration, data and secrets use the main stack's `${CONFIG_DIR}/vesper`, `${DATA_DIR}/vesper` and `${SECRETS_DIR}/vesper` paths. Discovery remains disabled; Telegram alerts remain enabled. Historical image pins below record what was deployed, not the tag's future contents.

For an approved Vesper-only update, run from the homelab root:

```sh
docker compose pull vesper
docker compose up -d --no-deps --no-build --pull never vesper
```

The main-stack migration preserves the existing image, bind mounts, UID, resource limits, Authelia policy and LAN-only heartbeat rules. Traefik object names now use `vesper` instead of `vesper-shadow`. The pre-migration database, YAML, icons and old Compose configuration are backed up under ignored, owner-only `data/vesper-backups/compose-migration-20261110/`. Stop the current Vesper container before any rollback to the old project; never run both against the database.

## Reviewed discovery release deployed — 2026-11-10

At 18:13:34 UTC, only Vesper was recreated using `up -d --no-deps --no-build --pull never vesper`, with owner approval. The deployed image was `ghcr.io/cfbender/vesper@sha256:eb277947c1c8cef73605573978c463e82d15755f1738e9581bbdfc118b3b0918`, source revision `8f23739c9f7f412e35d9f30527c73a3ac64dc2a1`. All five [CI jobs](https://github.com/cfbender/vesper/actions/runs/42871670570), including container smoke testing and publication, passed. The host pull's digest, architecture and revision matched; the new image validated the live 4-machine, 43-service, 60-check inventory offline. Rendered Compose changed only the image.

**Discovery remains disabled:** no `VESPER_DISCOVER_*` environment variables, no Docker socket mount, and configuration stays mounted read-only with `VESPER_CONFIG_READ_ONLY=true`. The new discovery code is present but inactive. Telegram, service notification flags, monitor configuration and both producer installations are unchanged.

By 18:14:21 UTC all 60 checks had post-start results, including all 17 naturally scheduled producer receipts; all 43 services were healthy, with no configuration error or open incidents. Prior samples remained for every check, SQLite `quick_check` returned `ok`, and the container was healthy with zero restarts. The other 32 containers retained their IDs, start times, restart counts and states. Public HTTPS dashboard/API requests still redirect to Authelia with valid TLS; an untrusted direct API request with a spoofed identity returned 403. The recreated backend's dynamic address is now `172.20.69.21`; Traefik discovered it automatically.

A consistent pre-upgrade SQLite backup, YAML, icons, old image pin and verification snapshots are retained under owner-only, ignored `data/vesper-backups/discovery-release-20261110/`. The old image remains cached. Any rollback should explicitly override the Compose image with the saved old digest and recreate only Vesper, without restoring the database or touching other services unless separately approved.

## Public access — 2026-11-10

With the owner's approval, `vesper.cfb.dev` is now a proxied Cloudflare CNAME to the existing homelab tunnel, `eb2bf674-e1ec-40df-b556-a91f54671c1f.cfargotunnel.com`, with automatic TTL. Record ID: `775d4be03b35e2a46892bd9cbf8b6866`. No tunnel, Traefik, Authelia, producer or container configuration changed.

Cloudflare API read-back and public DNS-over-HTTPS confirmed publication. HTTPS requests pinned to the public Cloudflare edge, bypassing LAN split DNS, returned Authelia redirects for `/` and `/api/snapshot`; following the dashboard redirect reached the login page with HTTP 200. Certificate verification passed. An unauthenticated POST to a nonexistent heartbeat route returned 403 at the public edge, preserving LAN-only producer access. No valid heartbeat or notification was sent. Signed-in access was not independently tested.

## Current alert ownership — 2026-11-10

With the owner's approval, Vesper now sends Telegram alerts for all **43 services / 60 checks**. The existing Kuma bot token and chat ID were transferred programmatically into restricted, Git-ignored files under `secrets/vesper`, without printing either value. Root YAML references `telegram-bot-token` and `telegram-chat-id`; UID 10001 has read access. The actual Vesper test endpoint returned Telegram acceptance at **16:19:28 UTC**. Acceptance is not a read receipt; the owner separately reported successful production use. No reminders were enabled.

After successful testing and hot reload, the 60 corresponding Kuma monitors had their notification associations removed through Kuma's local application API. The owner then approved full retirement: **www (2), gateway (50), and internet (51)** were deleted through that API, and the Kuma container and its main Compose service were removed. Those three checks are now deliberately unmonitored pending the future networking layer. `uptime.cfb.dev` returns 404 because its Traefik routers disappeared with the container; DNS and certificates were not changed.

The Kuma-only `proxmox-health-push.timer` was disabled and stopped, and its service stopped. Its script, unit files and protected environment file remain dormant for rollback. Vesper's independent Proxmox timer remains enabled/active, and its NUC cron is unchanged. Keep `kuma-*` Vesper check IDs and token filenames: they are stable identities, not a dependency on Kuma. No independent Vesper watchdog was found installed; monitoring Vesper from another failure domain remains follow-up work.

Verification found all 60 Vesper checks healthy, all 43 service notification flags enabled, no configuration error or open incident, and database integrity `ok`. The earlier resolved, unnotified incident was not replayed. All 33 remaining containers, including Vesper, retained their identities, start times, restart counts and running states. Compose validation passed. Local configuration and rollout documentation remain uncommitted.

Consistent pre-cutover Vesper/Kuma database backups and a YAML snapshot are in owner-only, ignored `data/vesper-backups/alert-cutover-20261110/`. A separate pre-deletion Kuma backup and the old Compose file are in `data/vesper-backups/kuma-retirement-20261110/`. Kuma's stopped data directory remains at `data/uptime-kuma`; its checkpointed database passes integrity checks. These databases contain credentials and must remain private. Include Vesper's new Telegram secret files and their access permissions in normal backups. Any rollback requires separately approved recreation of only Kuma's service, followed by deliberate restoration of alert ownership and its producer timer; do not run a broad stack redeploy or overwrite the current Compose file with the backup.

### Earlier Proxmox heartbeat failure

At 14:54 UTC, five healthy Proxmox observations failed delivery while storage and backup observations succeeded. Their previous heartbeats were at 14:48:56–59; exceeding the 300-second interval plus 120-second grace opened an incident at 14:55:57. All signals delivered again at 14:59:16–19 and the incident resolved. The producer's `SuccessExitStatus=3` treats reported failures as data, so a successful systemd result alone does not prove delivery.

Traefik's retained 4xx-only access log contains no corresponding rejected request, and its error log showed no matching event. The producer discarded curl's exit code and stderr, so the precise transport failure cannot be reconstructed. Connection/DNS/TLS timeout is plausible, not proven; absence from a 4xx-only log does not exclude a 5xx response. All 105 subsequent Proxmox results checked from 15:00 UTC were healthy and delivered. No timeout, security setting or health threshold was weakened. Sanitized transport diagnostics and bounded transient retries were reviewed, tested and deployed to both producers at 16:47 UTC; see the [delivery contract](producers/README.md#heartbeat-delivery-contract-both-producers). NUC uses a total-transfer timeout after a slow-response regression exposed the proposed socket timeout's weakness. Existing cron/systemd deadlines, configuration and notification settings remain unchanged.

## Historical shadow preparation and verification

The entries below record the pre-cutover state. References to notifications being off, Kuma owning alerts, or preserving its running timer apply to those historical steps, not the current ownership and retirement above.

- [Complete monitor mapping](monitor-mapping.md): 58 configured checks plus three deliberately deferred Kuma monitors, their Vesper IDs, semantic differences and missing coverage.
- `../home-config/vesper/` (relative to the homelab repository root): authoritative machine-keyed YAML, moved unchanged from `vesper/config/` and mounted read-only at `/config`. Checks run every 30 seconds, with three failures/two passes. Telegram is absent and every service has `notifications: false`.
- `compose.yaml`: existing Traefik + Authelia for this homelab, no published ports or Docker socket, exact proxy trust `172.20.69.20/32`, read-only configuration, non-root UID/GID 10001, and narrowly scoped LAN-only bearer heartbeat routes.
- `rollout.env`: pinned GHCR digest for source revision `fcf3e46bf9df8288affcf62cd1cf41601b946106` (linux/amd64), verified by [the image's publishing CI](https://github.com/cfbender/vesper/actions/runs/42845693321) and a pull on this Docker host. The package is public; anonymous manifest/config verification passed and no registry login is required.

The configuration has **four machines, 43 services and 60 enabled checks (43 HTTP/TCP and 17 push checks), with none paused**. Related application checks share one tile, including ManaVault main/demo, AdGuard UI/DNS/sync, Dockhand API/MCP and TrueNAS UI/SMB/NFS/ZFS. Six Proxmox signals remain under **Host health**; guest ZFS belongs to TrueNAS. All grouped checks have individual names for drill-down. Display names no longer include “container”. Frigate and TrueNAS UI use their existing credential-free LAN HTTP endpoints, with browser HTTPS unchanged. KVM is grouped under Proxmox at the owner's request; its check target is unchanged. NUC, AdGuard replica and UNAS remain separate machines. Gateway and External were removed at the owner's request; Kuma IDs 2 (www), 50 (gateway ping) and 51 (internet ping) remain covered only by Kuma pending a future networking layer. Their NUC producer entries and the www-only outbound allowlist entries were also removed.

The ten NUC Docker/DNS probes run every minute from cfb's existing crontab; the seven Proxmox signals run through the independent `vesper-proxmox.timer` every five minutes. Both [host-side producers](producers/README.md) deliver over verified HTTPS with notifications off. The NUC uses a non-overlap lock and 45-second timeout plus five-second kill grace. Proxmox uses a 90-second oneshot deadline and five-second stop grace. Existing cron jobs and Kuma remain unchanged; no container restart was needed for either activation. Telegram remains absent.

During the earlier machine regrouping, moved service IDs started new history under Proxmox while preserving the database. Only Vesper was recreated at that stage. Subsequent grouping changes hot-reloaded without restarting. The installed Proxmox producer sends six checks to `proxmox/host-health` and ZFS to `proxmox/truenas-web/kuma-63`; the NUC manifest matches its consolidated services. The latest application consolidation moved twelve check IDs, which start fresh history; existing database records were not rewritten or deleted. Existing destination keys are retained to avoid resetting more history just for naming. The pinned validator accepts 4 machines, 43 services and 60 checks. Endpoints, thresholds, tokens and producer cadence are unchanged.

### Full-width overview deployed — 2026-11-10

With explicit approval, only `vesper-shadow-vesper-1` was recreated at 15:43 UTC using `up -d --no-deps --no-build --pull never vesper`. The new immutable image is `ghcr.io/cfbender/vesper@sha256:a3d4d01444c309d344f97683e05c95e295441a31f35d6566a1182a2ad46db42d`, source revision `fcf3e46bf9df8288affcf62cd1cf41601b946106`. The downloaded image's platform/revision and offline validation of all 60 configured checks passed before deployment. Rendered Compose differed only in the Vesper image.

- All 43 services and 60 checks are healthy. Every HTTP/TCP check produced at least two healthy post-deployment samples, and all 17 push checks received healthy scheduled producer heartbeats after restart. Prior history remains present for every check ID; SQLite `quick_check` returned `ok`.
- The runtime configuration is identical to the pre-upgrade configuration: notifications off for every service, Telegram absent, no pauses or load error, zero notification delivery rows. YAML, producer files, Compose routing and the main homelab Compose file were unchanged. All 33 other containers, including Kuma, retained their IDs, start times, restart counts and running states.
- Verified HTTPS still redirects anonymous UI/API requests to Authelia; an untrusted direct API request with a spoofed user is rejected with 403. No authentication policy changed.
- Deployed JS/CSS bytes match the captured-data preview. Inspected desktop/mobile renders show all 43 icons, full-width desktop rows (NUC 404px high at 1440px), and two mobile columns with no horizontal overflow. This is rendering verification using captured live API data, not a signed-in Authelia browser test.

A consistent pre-upgrade SQLite backup, YAML copy, uploaded icons and old image pin are retained in ignored, owner-only `data/vesper-backups/full-width-20261110/`. The prior image remains cached. For an approved rollback, explicitly override the Compose image with the digest saved in that backup's `rollout.env`; passing the old environment file alone no longer overrides the image. Do not restore the database or change Kuma merely to roll back this UI-only release.

### Service icons

Every service explicitly selects a bundled logo or a local uploaded PNG. Nineteen additional logos came from the [Dashboard Icons collection](https://github.com/homarr-labs/dashboard-icons) or the installed application's own favicon/logo; [icon-sources.json](icon-sources.json) records their sources and final IDs. Dashboard Icons is Apache-2.0 licensed; application artwork and trademarks retain their respective owners' rights. Imported images were converted to RGBA PNG, fitted within 256×256, and normalized again by Vesper's upload API.

Back up **`data/vesper/icons/` together with the YAML and database**: `upload:<hash>.png` references require those files at `/data/icons/<hash>.png` after restoration. The dashboard serves all artwork from Vesper itself, with no runtime CDN requests. All 54 icon URLs were fetched and checked as PNGs; the deployed frontend rendered all 54 without broken images using a captured live API snapshot on desktop and mobile. This isolated visual check did not exercise Authelia login or alter the live authentication policy.

## Initial shadow deployment verified — 2026-11-10 (before regrouping)

Only `vesper-shadow-vesper-1` was started, using the pinned image with `up -d --no-deps --no-build --pull never vesper`. The moved configuration passed the image's offline validator: 17 machines, 63 services and 63 checks, revision `sha256:d54b48982d8c42e6e0cb0e304edcf411e7766bc1906818b353e83690aa459e7f`.

- `https://vesper.cfb.dev` has a publicly trusted certificate. Anonymous requests to `/`, `/api/snapshot`, `/api/config`, `/api/csrf` and a heartbeat GET redirect to the existing Authelia login. No TLS verification bypass was used.
- API reads from Traefik's trusted network peer confirmed all 42 active checks healthy with advancing sample timestamps. All 21 other checks remain paused; push histories are empty. This verifies actual container-side checks, including DNS and Proxmox CA trust.
- Runtime configuration is read-only, has no load error, all 63 services have notifications disabled, and Telegram is not configured. SQLite contains collected samples and no notification delivery rows; `PRAGMA quick_check` returned `ok`. UID 10001 successfully created the database under the persistent data mount.
- An untrusted direct backend request with spoofed identity/forwarding headers returned 403. Direct `/healthz` returned 200 as intended.
- All 33 preexisting containers, including Kuma, retained their IDs, start times and restart counts and stayed running. No producer or timer was installed, and no heartbeat was sent by this deployment verification.

Signed-in browser access has not been verified: no authenticated Authelia session was available. Trusted-peer API reads are not proof of an end-to-end login. Producer delivery, scheduled timing, restart durability and backups remain separate verification steps. No public Cloudflare hostname record was added; access was verified through LAN split DNS. Repository changes remain uncommitted.

## Offline review

From the homelab repository root, this renders configuration only; it does not pull, create or start containers:

```sh
docker compose config --quiet
```

With a trusted Vesper binary available, this validates YAML without starting a server, opening SQLite, resolving secrets or sending network probes:

```sh
VESPER_CONFIG_DIR="$PWD/../home-config/vesper" /path/to/vesper validate
```

`validate` checks syntax and contracts, not target reachability, CA trust or producer operation. The runtime must use the published image, not this validation binary.

### Historical preparation checks (before deployment)

- The actual Vesper validator accepted **17 machines, 63 services and 63 checks**. Validation ran offline with the existing implementation build (application source unchanged from the pinned image revision); no Vesper server or container was started. The transferred binary's SHA-256 was verified before use.
- An independent comparison against Kuma's read-only database found every active non-group monitor exactly once, preserved all HTTP/TCP endpoints and the two explicit 401 expectations, and checked all documented pauses, notification flags and token references.
- Docker Compose rendered successfully. Checks covered digest pinning, mount paths, read-only settings, exact trusted peer, no published ports/socket, authenticated dashboard routing and narrow heartbeat path matching. An empty image setting was rejected.
- Live host-side probes matched all 37 enabled HTTP expectations and connected to all four TCP ports. Container names used inspected bridge IPs; actual container DNS must still be checked after deployment. Code-server's PORT=8843 and HTTP 200 resolve the apparent EXPOSE 8443 discrepancy without changing the target.
- `vesper.cfb.dev` already resolves to 10.0.69.69 on the LAN. Traefik's immediate peer is 172.20.69.20. Most monitored public names use split DNS; `www.cfb.dev` instead uses public Cloudflare addresses, now narrowly enumerated in the outbound policy.
- The host producer's dry-run returned healthy observations for eight Docker containers, two actual DNS queries and two actual ICMP probes. CLI tests cover unhealthy/starting containers, DNS NXDOMAIN/NODATA and command failure. A disposable localhost HTTPS receiver verified bearer payloads, default no-send behavior, redirect refusal, untrusted-certificate refusal and continued delivery after another check's rejection. No heartbeat was sent to Vesper or Kuma.
- Created only unused local `data/vesper` and `secrets/vesper` directories. Generated 19 independent 256-bit heartbeat tokens without printing their values. Files are Git-ignored. POSIX ACLs grant UID 10001 data read/write and secret read access; group/other entries grant no access. The owner remains `cfb`; the ACL tools were extracted temporarily, not installed system-wide. Preserve ACLs in backup/restore, since a later chmod can change their effective mask.
- Existing `README.md`, `docker-compose.yml` and `scripts/proxmox-health-push.sh` matched their pre-preparation checksums. No Vesper container, DNS/auth rule, producer timer or live service configuration was installed or changed.

At that preparation stage, no live Vesper authentication/heartbeat test or Telegram delivery had occurred. After the owner made the GHCR package public, an anonymous pull with a fresh empty Docker credential configuration succeeded on 2026-11-10. The downloaded digest matches `rollout.env`, its platform is linux/amd64, and its source-revision label matches `9317b770dcbb501622119e9fee0e03b51f93eabc`. That pull did not create or start a container. Later disposable validation attempts are documented below.

## Access and certificate blockers

1. **Proxmox adapter — installed and enabled:** the independent script and systemd units are installed on Proxmox, with only the seven dedicated Vesper tokens transferred over verified SSH. `/etc/vesper-proxmox` is root-owned mode 700, with mode-600 token files. Unit validation and the installed script's dry-run passed; the real systemd service delivered all seven healthy results with exit 0. The five-minute timer is enabled for boot and active. Kuma's script, service and active timer are unchanged. See the producer notes for execution and delivery verification.
2. **Frigate/TrueNAS monitoring — enabled over existing HTTP:** the owner approved `http://10.0.69.80:5000/api/version` and `http://10.0.69.74/ui/`, both expecting exact 200 with redirects disabled. These credential-free LAN checks verify Frigate application response and TrueNAS web-interface availability, not camera/recording or storage health. Frigate's port 5000 already exposes its unauthenticated API; no listener or access rule was changed. Certificates, browser HTTPS and Authelia remain unchanged. Frigate's self-signed `CN=*` has no SAN and TrueNAS's certificate only identifies `localhost`, so direct HTTPS checks would still fail identity/trust verification. Certificate replacement is optional separate work, not a monitoring prerequisite. Both checks are enabled with notifications off.
3. **Administrator policy — approved and unchanged:** the owner approved retaining the existing Authelia policy, which defaults to `one_factor` for all authenticated users (only www has a bypass). Vesper admits every authorized proxy user as a full administrator; no Vesper-specific user/group restriction is required for this shadow rollout. The user database remains unreadable by this account, so membership was not independently verified. Anonymous rejection passed after deployment; signed-in browser access remains unverified.
4. **Vesper hostname TLS — resolved:** Traefik's `prod` resolver issued the certificate during the approved deployment. HTTPS chain and hostname verification passed on the LAN. Public Cloudflare DNS publication, if wanted, remains a separate change.

### Proxmox trust and inspection completed

The trusted Proxmox runner reported ED25519 fingerprint `SHA256:jB90Hg0Ec98ru9kzt1h8MdkyUn8whzJ/P95sqobVVg0`, matching the NUC's network observation. The exact public key is pinned for 10.0.69.72 in the NUC user's known_hosts; strict, noninteractive SSH authenticated as root using existing credentials.

Retrieved `/etc/pve/pve-root-ca.pem` through that verified SSH connection into ignored `secrets/vesper/proxmox-root-ca.pem`. Local and remote file SHA-256 match: `eec29ff9821c4953b2b31ca95bb795593bf147d6eeedba937df56cf95937daf0`. The certificate SHA-256 fingerprint is `EA:74:40:C6:D1:72:6D:49:DF:93:50:D6:D1:C3:F5:5D:74:23:D9:C0:26:B4:BC:33:B6:B3:0C:9B:65:7A:22:4D`. It expires July 11, 2033; the current server certificate expires June 29, 2027 and includes IP SAN 10.0.69.72.

An HTTPS probe with this CA returned 200 with certificate verification result 0. A negative control without it failed trust verification (curl exit 60). `network.private_ca_file: proxmox-root-ca.pem` resolves under `/run/secrets` and extends Vesper's public trust roots; it does not change host-wide trust or disable TLS verification. The file carries the same restricted UID 10001 read ACL as the heartbeat tokens. The Proxmox web check is now enabled only in the staged YAML, bringing host-verified HTTP candidates to 38 plus four TCP listeners.

The installed health script exactly matches `scripts/proxmox-health-push.sh`. The five-minute timer is active; the inspected last run took six seconds and exited 0. It has no overall timeout, and exit 0 does not prove successful checks or delivery. See [producer inspection](producers/README.md#proxmox-inspection--2026-11-10) for failure-handling and timing findings. The script was not manually run or modified.

The binary extracted from the exact published image validated the updated YAML offline: 17 machines, 63 services, 63 checks. Compose rendering also passed. Two disposable, network-disabled container validation attempts were rejected before application startup with `operation not permitted` (both `/bin/sh` and `/usr/bin/tini`); their containers were removed. The cause was subsequently traced to Snap Docker's AppArmor transition, documented below. No security restriction was relaxed to bypass it. No Vesper server, database or producer was started.

### Container execution resolved: approved Snap Docker compatibility exception

On 2026-11-10, the NUC runs Docker snap 29.8.0 revision 3618, snapd 2.78 revision 28332, Ubuntu 24.04 and kernel 6.8.0-124-generic. Kernel audit records identify an AppArmor exec denial with `info="no new privs"`, source profile `snap.docker.dockerd` and target `docker-default`. The failure occurs while changing profiles at exec, before application code starts.

Reproduced independently with the already-cached Alpine image's `/bin/true` and the pinned Vesper image's `/usr/local/bin/vesper --help`. Both used no mounts, no network, UID:GID 10001, a read-only root filesystem, all capabilities dropped and `no-new-privileges:true`. Both exited 255 with the same kernel denial. This rules out Vesper configuration, private CA permissions, bind mounts and tini as causes of this execution failure. Both disposable containers were removed; no production container was restarted or modified.

This matches [Launchpad bug 1908448](https://bugs.launchpad.net/snapd/+bug/1908448). The upstream remedy stacks the Docker container profile with the existing Snap daemon profile, retaining both restrictions instead of replacing one under no-new-privileges. [snapd PR 17730](https://github.com/canonical/snapd/pull/17730) merged on October 20 and targets snapd 2.79. [Docker snap PR 405](https://github.com/canonical/docker-snap/pull/405) is still open according to the live GitHub API on November 10 and requires snapd 2.79 or later. The fetched HTML summary incorrectly marked that PR merged; the API explicitly returned `merged: false`. Store stable channels still offer snapd 2.78 and Docker revision 3618, so a stable refresh is not a verified remedy.

The owner subsequently approved removing only `no-new-privileges` from Vesper's prepared Compose configuration. With that option omitted, the exact pinned image's normal entrypoint successfully ran `validate`: 17 machines, 63 services, 63 checks. A second disposable check confirmed UID 10001 can read the CA, `docker-default (enforce)` remains active, seccomp is in filter mode (2), and effective/bounding capabilities are zero. `NoNewPrivs` is now 0; this explicitly gives up that extra restriction on exec-time privilege changes. Non-root execution, read-only root/config, dropped capabilities, resource limits, and default AppArmor/seccomp remain unchanged.

Both successful checks were network-disabled, had no published ports or Traefik route, and used no database mount. Their containers were removed. No Vesper server was started, and the shared Docker runtime, profiles and Snap channels were not modified. The startup-execution blocker is resolved; this is not yet an end-to-end deployment test.

## Remaining deployment verification

Published-image validation, database writes, active target checks, TLS, anonymous UI/API rejection, untrusted-peer rejection and real producer heartbeat delivery passed. Signed-in browser access has not been independently verified. All configured checks are now enabled; enabling notifications, changing live certificate/auth configuration, or publishing DNS still requires approval. Do not run a broad homelab `up`, `pull` or redeploy. The heartbeat exception remains limited to exact LAN-only POST routes with per-check tokens; there is no broad `/api` bypass.

## Parallel monitoring and cutover gates

Leave Kuma alerts and producers intact. Vesper is running without Telegram; compare live observations, then use a separate Telegram test destination after approval. Adding Telegram alone is insufficient: service notifications remain false until deliberately enabled. Review open incidents before enabling; existing unresolved incidents can trigger notifications.

Compare the active NUC Docker/DNS and Proxmox health producers with Kuma over time. Frigate and TrueNAS HTTP checks deliberately do not test TLS availability or certificate validity; retain separate coverage if that matters at cutover. Gateway/external checks are intentionally deferred to a future networking layer. Verify redirects/status expectations and distinguish LAN routing from external availability. Use disposable endpoints for failure/recovery tests rather than deliberately breaking production services.

Keep a comparison log: at a 30-second cadence, Vesper's 500 retained samples per check cover only about four hours (the UI's 60 samples about 30 minutes). A week-long comparison cannot rely on raw history alone. Verify a Vesper restart, a backup cycle and actual Telegram outage/recovery receipt; then agree on alert ownership before muting any Kuma notification.

For rollback during shadow operation, stop only Vesper; Kuma remains the alerting authority. After an explicitly approved notification cutover, re-enable Kuma notifications before disabling Vesper notifications. Preserve both data stores. Before removing Kuma entirely, replace the bundled watchdog's dependency on Kuma and run independent monitoring outside Vesper's failure domain.
