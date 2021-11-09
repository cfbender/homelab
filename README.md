# Docker Home Server

docker-based server using custom subdomains over https

## Initial installation

Clone this repo, or fork it first if you want to! Be sure to install the pre-commit hook following the instructions in that file. It will strip out the values from `.env` and generate a `env.sample` file with only the keys. It also will strip emails and the pilot token from `traefik/traefik.yml` and generate a `traefik/traefik.yml.sample`.

## Motivation

- host each service as a subdomain of a personal domain with cloudflare/letsencrypt
- run public maintained images with no modifications
- require minimal configuration and setup

## Containers

- [Netdata](https://www.netdata.cloud/) - Troubleshoot slowdowns and anomalies in your infrastructure with thousands of metrics, interactive visualizations, and insightful health alarms.
- [Traefik](https://traefik.io/) - modern HTTP reverse proxy and load balancer that makes deploying microservices easy.
- [Home Assistant](https://www.home-assistant.io/) - Open source home automation that puts local control and privacy first.
- [ESPHome](https://esphome.io/) - system to control your ESP8266/ESP32 by simple yet powerful configuration files and control them remotely through Home Automation systems.
- [code-server](https://github.com/cdr/code-server) - Run VS Code on any machine anywhere and access it in the browser.
- [personal-site](https://github.com/cfbender/personal-site) - my personal site, built with Phoenix LiveView.
- [AdGuard Home](https://adguard.com/en/adguard-home/overview.html) - network-wide software for blocking ads & tracking.
- [Watchtower](https://containrrr.dev/watchtower/) - container-based solution for automating Docker container base image updates.
- [Portainer CE](https://www.portainer.io/) - lightweight ‘universal’ management GUI that can be used to easily manage Docker, Swarm, Kubernetes and ACI environments.
- [Z-waveJS](https://github.com/zwave-js/node-zwave-js) - Z-Wave device driver written entirely in JavaScript/TypeScript \*
- [Unifi controller](https://docs.linuxserver.io/images/docker-unifi-controller) - powerful, enterprise wireless software engine ideal for high-density client deployments requiring low latency and high uptime performance.
- [Bookstack](https://www.bookstackapp.com/) - simple, self-hosted, easy-to-use platform for organising and storing information.
- [Wireguard](https://www.wireguard.com/) - extremely simple yet fast and modern VPN that utilizes state-of-the-art cryptography.
- [fail2ban](https://www.fail2ban.org/wiki/index.php/Main_Page) - scans log files and bans IPs that show the malicious signs -- too many password failures, seeking for exploits, etc.
- [mosquitto](https://mosquitto.org/) - an open source (EPL/EDL licensed) message broker that implements the MQTT protocol versions 5.0, 3.1.1 and 3.1. *
- [docker-wyze-bridge](https://github.com/mrlt8/docker-wyze-bridge) - expose a local RTMP, RTSP, and HLS stream for ALL your Wyze cameras including the outdoor and doorbell cams. *
\*not exposed even in external configuration

## Requirements

- dedicated server or PC
- [docker](https://docs.docker.com/install/linux/docker-ce/debian/) and [docker-compose](https://docs.docker.com/compose/install/#install-compose)
- (optional) personal domain with configurable sub-domains (eg. netdata.example.com)

## Internal Configuration (local network only)

Copy `env.sample` to `.env` and populate all fields in the `COMMON` section.

Create a link in order to append `docker-compose.internal.yml` to future docker-compose commands.

```bash
ln -sf docker-compose.internal.yml docker-compose.override.yml
```

Review the merged configs by running `docker-compose config`.

## External Configuration (exposed to internet)

Copy `env.sample` to `.env` and populate all fields in the `COMMON` and `EXTERNAL` sections.

Create a link in order to append `docker-compose.external.yml` to future docker-compose commands.

```bash
ln -sf docker-compose.external.yml docker-compose.override.yml
```

Review the merged configs by running `docker-compose config`.

Copy `traefik/traefik.yml.sample` to `traefik/traefik.yml` and fill in the `ACME_EMAIL` and `PILOT_TOKEN` variables (the pilot token is an optional property for Traefik Pilot, feel free to remove the section all-together).

Be sure to port forward `:443` on your router to get access externally.

It is recommended to use the `staging` cert resolver initially to avoid any potential rate limits from Let's Encrypt for any misconfigured services.

## Other configuration / Notes

### Wireguard

You will need to forward port 51820/udp, and be sure that it is not proxied through Cloudflare, as the CF proxy only allows HTTP traffic.

On initial startup, the container should generate 5 peer QR codes. You can view them with:

```bash
docker-compose logs -tf wireguard
```

### AdGuard

On startup for the intial configuration the web interface will bind to port `3000`. If you have local access to the server, you can access it there (ie. `10.0.0.10:3000`), and then be sure that it does not bind to port `80`, but instead `3333` (defined in external labels for loadbalancer).

If you do not have direct network access to the server, you can launch the first time with the loadbalancer port to `:3000`, configure it to bind to `3333`, then restart with the original port in the label configuration.

### DNS

I have manually overriden the DNS of many of the containers, to get around any networking weirdness with it being on the same machine, as well as any potential interference from AdGuard. This is probably not needed and you are free to experiment.

### Home assistant

Using the [linuxserver](https://linuxserver.io) container fixes many issues you may run into with Home Assistant docker, however the networking can still be an issue. The network mode needs to be `host`, so that it can discover and manage devices on the network, and then this the interface is exposed to traefik through `extra_hosts`. I also have the DNS pointing to AdGuard so that it can resolve local hostnames.

## Deployment

Pull and deploy containers with docker-compose.

```bash
docker-compose pull
docker-compose up -d
```

## Cloudflare

This configuration is set up for a domain proxied through Cloudflare. You can remove this by removing the `CF_API_KEY` and `CF_API_EMAIL` environment cariables, as well as the `entrypoints.websecure.forwardedHeaders.trustedIPs` config in `traefik/traefik.yml`.

## Middlewares

### ipallowlist

If you are using mediaserver locally and are not exposing any ports to the Internet, you can skip
this section or set `IPALLOWLIST=0.0.0.0/0,::/0` in your `.env` file.

Set the `IPALLOWLIST` to only IP ranges that we want to explictly allow access.

This functionality can be enabled/disabled per service in `docker-compose.external.yml`
with the `ipallowlist` middleware.

### traefik-forward-auth

Uses [traefik-forward-auth](https://github.com/thomseddon/traefik-forward-auth) to handle OAuth through google. Just follow the setup instructions there, and fill in the relevant fields in env.

### basicauth

This functionality can be enabled/disabled per service in `docker-compose.external.yml`
with the `basicauth` middleware.

Users can be added to basic auth in 2 ways. If both methods are used they are merged and the
htpasswd file takes priority.

1. Add users in your `.env` file with the `BASICAUTH_USERS` variable.

2. Add users via htpasswd file in the traefik service.

The first user added requires `htpasswd -c` in order to create the password file.
Subsequent users should only use `htpasswd` to avoid overwriting the file.

```bash
docker-compose exec traefik apk add --no-cache apache2-utils
docker-compose exec traefik htpasswd -c /etc/traefik/.htpasswd <user1>
docker-compose exec traefik htpasswd /etc/traefik/.htpasswd <user2>
```

## Acknowledgments

Started with setup from [klutchell's mediaserver](https://github.com/klutchell/mediaserver)

[Buy them a beer](https://buymeacoffee.com/klutchell)
