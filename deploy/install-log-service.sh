#!/usr/bin/env bash
set -Eeuo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this installer as root (for example: sudo $0)." >&2
  exit 1
fi

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="${repo_dir}/docker-compose.prod.yml"

if [[ ! -f ${compose_file} ]]; then
  echo "Missing ${compose_file}." >&2
  exit 1
fi

docker_bin="$(command -v docker || true)"
if [[ -z ${docker_bin} ]]; then
  echo "Docker is not installed." >&2
  exit 1
fi

install -D -m 0644 "${repo_dir}/deploy/systemd/brandvideo-log.service" /etc/systemd/system/brandvideo-log.service
install -D -m 0644 "${repo_dir}/deploy/logrotate/brandvideo" /etc/logrotate.d/brandvideo
install -D -m 0755 "${repo_dir}/deploy/log_router.py" /usr/local/lib/brandvideo/log_router.py

# The unit deliberately receives an absolute path so it works regardless of
# which account performs future deployments.
printf 'BRANDVIDEO_COMPOSE_FILE=%q\n' "${compose_file}" > /etc/default/brandvideo-log

printf 'DOCKER_BIN=%q\n' "${docker_bin}" >> /etc/default/brandvideo-log

systemctl daemon-reload
systemctl enable --now brandvideo-log.service
logrotate --debug /etc/logrotate.d/brandvideo >/dev/null

echo "BrandVideo logs are now written to /var/log/brandvideo/backend.log"
echo "Follow them with: tail -F /var/log/brandvideo/backend.log"
