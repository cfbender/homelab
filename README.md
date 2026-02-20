# Docker Home Server

docker-based server using custom subdomains over https

## Initial installation

Clone this repo, or fork it first if you want to! Be sure to install the pre-commit hook following the instructions in that file. It will strip out the values from `.env` and generate a `env.sample` file with only the keys. It also will strip emails and the pilot token from `traefik/traefik.yml` and generate a `traefik/traefik.yml.sample`.

## Motivation

- host each service as a subdomain of a personal domain with cloudflare/letsencrypt
- run public maintained images with no modifications
- require minimal configuration and setup

## Containers

- [Traefik](https://traefik.io/) - modern HTTP reverse proxy and load balancer that makes deploying microservices easy.
- [Dockhand](https://github.com/fnsys/dockhand) - A web-based Docker container manager.
- [ESPHome](https://esphome.io/) - system to control your ESP8266/ESP32 by simple yet powerful configuration files and control them remotely through Home Automation systems.
- [code-server](https://github.com/cdr/code-server) - Run VS Code on any machine anywhere and access it in the browser.
- [personal-site](https://github.com/cfbender/personal-site) - my personal site, built with Phoenix LiveView.
- [AdGuard Home](https://adguard.com/en/adguard-home/overview.html) - network-wide software for blocking ads & tracking.
- [adguardhome-sync](https://github.com/bakito/adguardhome-sync)- Synchronize AdGuardHome config to a replica instance. *
- [Authelia](https://www.authelia.com/) - The Single Sign-On Multi-Factor portal for web apps.
- [mosquitto](https://mosquitto.org/) - an open source (EPL/EDL licensed) message broker that implements the MQTT protocol versions 5.0, 3.1.1 and 3.1. *
- [dashy](https://github.com/Lissy93/dashy) - 🚀 A self-hostable personal dashboard built for you. Includes status-checking, widgets, themes, icon packs, a UI editor and tons more!
- [edison](https://github.com/cfbender/edison) - a little discord bot I run for some random tasks *
- [Homebox](https://github.com/hay-kot/homebox) - An inventory and organization system for your home.
- [Booklore](https://github.com/booklore-app/booklore) - A self-hosted eBook library manager and reader.
- [MariaDB](https://mariadb.org/) - A popular open source database server. *
- [Overseerr](https://overseerr.dev/) - A request management and media discovery tool for your home media server.
- [NZBGet](https://nzbget.net/) - A popular usenet downloader.
- [Radarr](https://radarr.video/) - A movie collection manager for Usenet and BitTorrent users.
- [Sonarr](https://sonarr.tv/) - A PVR for Usenet and BitTorrent users.
- [IT-Tools](https://it-tools.tech/) - A collection of useful tools for developers.
- [Copyparty](https://github.com/copyparty/copyparty) - A file sharing server.
- [ClipCascade](https://github.com/sathvikrao/clipcascade) - A self-hosted clipboard manager.
- [abs-kosync](https://github.com/cporcellijr/abs-kosync-bridge) - A bridge between Audiobookshelf and KOReader. *
- [convert](https://github.com/p2r3/convert) - Truly universal online file converter

*not exposed

## Requirements

- dedicated server or PC
- [docker](https://docs.docker.com/install/linux/docker-ce/debian/) and [docker-compose](https://docs.docker.com/compose/install/#install-compose)
- personal domain with configurable sub-domains (eg. netdata.example.com)

## Configuration (exposed to internet)

Copy `env.sample` to `.env` and populate all fields in the `COMMON` and `EXTERNAL` sections.

Since switching to dockhand, I have started storing secrets in there, so there may be some missing in the .env file. Open the stack in dockhand, and fill in the required missing variables.

Copy `traefik/traefik.yml.sample` to `traefik/traefik.yml` and fill in the `ACME_EMAIL` and `PILOT_TOKEN` variables (the pilot token is an optional property for Traefik Pilot, feel free to remove the section all-together).

Be sure to port forward `:443` on your router to get access externally.

It is recommended to use the `staging` cert resolver initially to avoid any potential rate limits from Let's Encrypt for any misconfigured services.

## Other configuration / Notes

### AdGuard

On startup for the intial configuration the web interface will bind to port `3000`. If you have local access to the server, you can access it there (ie. `10.0.0.10:3000`), and then be sure that it does not bind to port `80`, but instead `3333` (defined in external labels for loadbalancer).

If you do not have direct network access to the server, you can launch the first time with the loadbalancer port to `:3000`, configure it to bind to `3333`, then restart with the original port in the label configuration.

I set up a replica instance on a Raspberry Pi, so that I can have a backup DNS in case I need to take the server down for some reason. Just use the default config file (`${CONFIG_DIR}/adguard/adguardhome-sync.yaml`) from [the adguardhome-sync repo](https://github.com/bakito/adguardhome-sync) entering in the username and password for each, and you should be good to go! (Note: I turn off the stats and query log syncing because I find it useful to see what hits the fallback server)

### DNS/Networks

I have set up only the single default network, and assigned it a subnet so that I can assign an IP to AdGuard for containers to reference as DNS. This allows more granular insight into container network activity, as they will no longer be agregated at the host level.

In order to see container names in AdGuard, set `[/69.20.172.in-addr.arpa/]127.0.0.11` in the "Private DNS servers" field in AdGuard. This tells AdGuard to send PTR requests in the docker network to the internal docker DNS resolver. The main downside here is that any containers that run in "host" mode (in this case, just Home Assistant) will show up in AdGuard as the subnet gateway address for the internal network.

I have a couple of containers in "host" networking mode, this is to mainly make a few things work a little cleaner (UPnP, mDNS, DNS over IPv6). You can turn these off if you don't want any of these.

### Home assistant

This stack utilizes Home Assistant via a VM managed in proxmox. I set it up using [this script from tteck](https://tteck.github.io/Proxmox/). The files in `traefik/conf_example` with the info filled in should get you going to route to the external host.

Set the following into `${CONFIG_DIR}/home/configuration.yaml`:
**Note:** for running HA at a different IP, you will need to include the server IP running this compose stack where the `<YOUR SERVER IP>` is.

```yaml
http:
  use_x_forwarded_for: true
  trusted_proxies:
    - 127.0.0.1
    - <YOUR SERVER IP>
    # cloudflare IPs for skipping in X-Forwarded-For header
    - 103.21.244.0/22
    - 103.22.200.0/22
    - 103.31.4.0/22
    - 104.16.0.0/13
    - 104.24.0.0/14
    - 108.162.192.0/18
    - 131.0.72.0/22
    - 141.101.64.0/18
    - 162.158.0.0/15
    - 172.64.0.0/13
    - 173.245.48.0/20
    - 188.114.96.0/20
    - 190.93.240.0/20
    - 197.234.240.0/22
    - 198.41.128.0/17
```

If you have any devices (in my case a Xiaomi Air Purifier 3H) that don't seem to be able to discover, you may want to put them on the same VLAN. I did this by running the following commands:

```sh
echo -e '[keyfile]\nunmanaged-devices=none' | sudo tee -a /etc/NetworkManager/conf.d/10-globally-managed-devices.conf
sudo nmcli con add type vlan con-name enp0s25@vlan10 dev enp0s25 id 10
sudo service network-manager restart
```

I had previously set up a VLAN 10 tagged port on the switch for my server, with the base network as the secure network.

This should allow device discovery with the devices being in separate VLANs

## Deployment

### Dockhand

Dockhand is used to manage the containers. To start it, run the following script:

```bash
chmod +x start-dockhand.sh
./start-dockhand.sh
```

### Main Stack

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

This stack uses the TFA host mode, which is hosted at `AUTH_HOST`. Thus, the redirect URI you enter into google will be `https://<AUTH_HOST>/_oauth`. This way you don't need to make an individual entry for every subdomain.

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

Special thanks to [brettinternet](https://github.com/brettinternet) for the help and inspiration along the way.
