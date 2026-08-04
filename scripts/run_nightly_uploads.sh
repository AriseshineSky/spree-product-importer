#!/usr/bin/env bash
# Unified nightly upload manager (mongo VPS).
# Cron should call this once at America/Chicago 23:00; jobs run sequentially.
#
# Usage:
#   ./scripts/run_nightly_uploads.sh           # run JOBS below
#   ./scripts/run_nightly_uploads.sh --dry-run # print jobs only
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="${ROOT}/scripts/run_nightly_import.sh"
LOG_DIR="${HOME}/logs/spree-import"
MANAGER_LOCK="/tmp/spree-import-nightly-uploads.lock"
mkdir -p "$LOG_DIR"

DAY="$(TZ=America/Chicago date +%Y%m%d)"
MANAGER_LOG="${LOG_DIR}/nightly-uploads-${DAY}.log"

# store  vendor           [source]
# Edit this list to enable/disable nightly uploads.
# Order: UK DE CA MX PL NL FR JP IN IT BR (no AE/US). UK=46 DE/EM-EU=51 MX=50 NL=61.
JOBS=(
  "em-spree em-uk amz_uk"
  "em-spree em-eu amz_de"
  "em-spree topselected amz_ca"
  "em-spree em-mx amz_mx"
  "em-spree em-pl amz_pl"
  "em-spree em-nl amz_nl"
  "em-spree em-fr amz_fr"
  "em-spree jp-cmedia amz_jp"
  "em-spree em-in amz_in"
  "em-spree everymarket-it amz_it"
  "em-spree em-horizon amz_br"
  # "em-spree dubai-essence amz_ae"
  # "em-spree topselected amz_us"
  # "em-spree topselected ebay_us"
  # "em-spree em-hu"
)

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

export PATH="${HOME}/.local/bin:/usr/local/bin:${PATH}"

log() {
  echo "$*" | tee -a "$MANAGER_LOG"
}

run_jobs() {
  local failed=0
  local job store vendor source
  log "==== $(date '+%Y-%m-%dT%H:%M:%S%z') nightly uploads start (America/Chicago) ===="
  for job in "${JOBS[@]}"; do
    # shellcheck disable=SC2086
    set -- $job
    store="${1:?}"
    vendor="${2:?}"
    source="${3:-}"
    if [[ "$DRY_RUN" -eq 1 ]]; then
      if [[ -n "$source" ]]; then
        log "[dry-run] ${RUNNER} ${store} ${vendor} ${source}"
      else
        log "[dry-run] ${RUNNER} ${store} ${vendor}"
      fi
      continue
    fi
    log "---- $(date '+%Y-%m-%dT%H:%M:%S%z') job: store=${store} vendor=${vendor} source=${source:-ALL} ----"
    if [[ -n "$source" ]]; then
      if ! "$RUNNER" "$store" "$vendor" "$source"; then
        log "ERROR: job failed store=${store} vendor=${vendor} source=${source}"
        failed=1
      fi
    else
      if ! "$RUNNER" "$store" "$vendor"; then
        log "ERROR: job failed store=${store} vendor=${vendor}"
        failed=1
      fi
    fi
  done
  log "==== $(date '+%Y-%m-%dT%H:%M:%S%z') nightly uploads done (failed=${failed}) ===="
  return "$failed"
}

if [[ "$DRY_RUN" -eq 1 ]]; then
  run_jobs
  exit 0
fi

if ! command -v flock >/dev/null 2>&1; then
  log "flock not found"
  exit 1
fi

(
  flock -n 9 || {
    log "already running: ${MANAGER_LOCK}"
    exit 1
  }
  run_jobs
) 9>"$MANAGER_LOCK"
