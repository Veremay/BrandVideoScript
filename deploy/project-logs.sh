#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  echo "Usage: $0 [--follow] PROJECT_ID" >&2
  exit 2
}

follow=0
if [[ ${1:-} == "--follow" ]]; then
  follow=1
  shift
fi

project_id=${1:-}
[[ -n ${project_id} ]] || usage

log_file=${BRANDVIDEO_LOG_FILE:-/var/log/brandvideo/projects/${project_id}/backend.log}
if [[ ! -r ${log_file} ]]; then
  echo "Cannot read ${log_file}; try sudo or set BRANDVIDEO_LOG_FILE." >&2
  exit 1
fi

if (( follow )); then
  tail -n 0 -F "${log_file}"
else
  cat "${log_file}"
fi
