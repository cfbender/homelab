# Docker Plex & Usenet Media Server

docker-based server using custom subdomains over https

Mostly copied from [klutchell's mediaserver](https://github.com/klutchell/mediaserver)

## Motivation

- host each service as a subdomain of a personal domain with letsencrypt
- run public maintained images with no modifications
- require minimal configuration and setup

## Features

- [Netdata](https://www.netdata.cloud/) - Troubleshoot slowdowns and anomalies in your infrastructure with thousands of metrics, interactive visualizations, and insightful health alarms.
- [Traefik](https://traefik.io/) is a modern HTTP reverse proxy and load balancer that makes deploying microservices easy.

## Requirements

- dedicated server or PC
- [docker](https://docs.docker.com/install/linux/docker-ce/debian/) and [docker-compose](https://docs.docker.com/compose/install/#install-compose)
- (optional) personal domain with configurable sub-domains (eg. plex.example.com)

## Direct Configuration

Copy `env.sample` to `.env` and populate all fields in the `COMMON` section.

Create a link in order to append `docker-compose.direct.yml` to future docker-compose commands.

```bash
ln -sf docker-compose.direct.yml docker-compose.override.yml
```

Review the merged configs by running `docker-compose config`.

## Letsencrypt Configuration

Copy `env.sample` to `.env` and populate all fields in the `COMMON` and `LETSENCRYPT` sections.

Create a link in order to append `docker-compose.letsencrypt.yml` to future docker-compose commands.

```bash
ln -sf docker-compose.letsencrypt.yml docker-compose.override.yml
```

Review the merged configs by running `docker-compose config`.

## Deployment

Pull and deploy containers with docker-compose.

```bash
docker-compose pull
docker-compose up -d
```

## Authorization

There are currently two methods of authentication enabled, and I recommend using them
both if the Letsencrypt configuration is in use. If it's not exposed to the Internet you can
remove one or both of these middlewares from `docker-compose.letsencrypt.yml`.

### ipallowlist

This is our first layer of security, and probably the most important.

If you are using mediaserver locally and are not exposing any ports to the Internet, you can skip
this section or set `IPALLOWLIST=0.0.0.0/0,::/0` in your `.env` file.

To avoid unauthorized users from even seeing our login pages, we should set the `IPALLOWLIST` to
only IP ranges that we want to explictly allow access.

Access from any other IP will result in "403 Forbidden" giving you some peice of mind!

This functionality can be enabled/disabled per service in `docker-compose.letsencrypt.yml`
with the `ipallowlist` middleware.

### traefik-forward-auth

Uses [traefik-forward-auth](https://github.com/thomseddon/traefik-forward-auth) to handle OAuth through google. Just follow the setup instructions there, and fill in the relevant fields in env

### basicauth

This functionality can be enabled/disabled per service in `docker-compose.letsencrypt.yml`
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

By default only Duplicati and Netdata have basic http auth enabled.

For the remaining services I suggest enabling the built-in authentication via the app.
This avoids the need to add manual exceptions for API access where required and simplifies our proxy rules.

## Original Author

Kyle Harding <https://klutchell.dev>

[Buy them a beer](https://buymeacoffee.com/klutchell)

## Acknowledgments

I didn't create any of these docker images myself, so credit goes to the
maintainers, and the original software creators.

- <https://hub.docker.com/r/netdata/netdata/>
- <https://hub.docker.com/r/thomseddon/traefik-forward-auth>
- <https://hub.docker.com/_/traefik/>
