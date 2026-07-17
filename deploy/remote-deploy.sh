#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed on the ECS host." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "The Docker Compose plugin is not installed on the ECS host." >&2
  exit 1
fi

if [[ ! -f .env.deploy ]]; then
  echo "Missing $(pwd)/.env.deploy. Copy .env.deploy.example and fill production values first." >&2
  exit 1
fi

docker compose -p brandvideo -f docker-compose.prod.yml config --quiet
docker compose -p brandvideo -f docker-compose.prod.yml up -d --build --remove-orphans

for attempt in {1..30}; do
  if curl --fail --silent --show-error http://127.0.0.1/api/health >/dev/null; then
    docker compose -p brandvideo -f docker-compose.prod.yml ps
    echo "Deployment succeeded."
    exit 0
  fi
  sleep 4
done

docker compose -p brandvideo -f docker-compose.prod.yml ps
docker compose -p brandvideo -f docker-compose.prod.yml logs --tail=100 backend nginx
echo "Deployment health check failed." >&2
exit 1
