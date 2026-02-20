#!/bin/bash

# Load environment variables from .env
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

# Stop and remove existing container if it exists
docker rm -f dockhand || true

docker run -d \
  --name dockhand \
  --restart unless-stopped \
  --network homelab_default \
  --group-add 1001 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "${DATA_DIR}/dockhand:/app/data" \
  -v ./:/homelab \
  --label "traefik.enable=true" \
  --label "traefik.docker.network=homelab_default" \
  --label "traefik.http.routers.dockhand.tls.certresolver=prod" \
  --label "traefik.http.routers.dockhand.rule=Host(\`${DOCKHAND_HOST}\`)" \
  --label "traefik.http.routers.dockhand.middlewares=hsts-header, authelia" \
  --label "traefik.http.services.dockhand.loadbalancer.server.port=3000" \
  --label "traefik.http.services.dockhand.loadbalancer.server.scheme=http" \
  fnsys/dockhand:latest
