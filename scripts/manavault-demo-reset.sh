#!/usr/bin/env bash
# Reset the public ManaVault demo (manavault-demo.cfb.dev) to its seeded state.
#   scripts/manavault-demo-reset.sh           restore data/manavault-demo-seed
#   scripts/manavault-demo-reset.sh --snapshot save the current demo data as the seed
# The data is owned by the container user, so the copy runs in an alpine container.
set -euo pipefail
cd "$(dirname "$0")/.."
data="$PWD/data/manavault-demo"
seed="$PWD/data/manavault-demo-seed"

docker compose stop manavault-demo
trap "docker compose start manavault-demo" EXIT

if [[ "${1:-}" == "--snapshot" ]]; then
  src="$data" dst="$seed"
else
  [[ -f "$seed/manavault.db" ]] || { echo "no seed at $seed; run with --snapshot first" >&2; exit 1; }
  src="$seed" dst="$data"
fi

# Backups and caches are regenerated; keep them out of the seed.
docker run --rm -v "$src:/src:ro" -v "$dst:/dst" alpine sh -c \
  "apk add --no-cache rsync >/dev/null && rsync -a --delete --exclude backups/ --exclude cache/ /src/ /dst/"
echo "$(date -Is) manavault-demo ${1:---restore} done"
