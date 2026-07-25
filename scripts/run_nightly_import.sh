#!/usr/bin/env bash
# Nightly Spree import for one store + vendor (+ optional source).
# Usage: run_nightly_import.sh em-spree topselected
#        run_nightly_import.sh em-spree topselected amz_ca
#        run_nightly_import.sh em-spree em-hu
set -euo pipefail

STORE_CODE="${1:?store_code required, e.g. em-spree}"
VENDOR_NAME="${2:?vendor name/key required, e.g. topselected or em-hu}"
SOURCE_NAME="${3:-}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${HOME}/logs/spree-import"
if [[ -n "$SOURCE_NAME" ]]; then
  LOCK_SUFFIX="${STORE_CODE}-${VENDOR_NAME}-${SOURCE_NAME}"
else
  LOCK_SUFFIX="${STORE_CODE}-${VENDOR_NAME}"
fi
LOCK_FILE="/tmp/spree-import-${LOCK_SUFFIX}.lock"
mkdir -p "$LOG_DIR"

DAY="$(TZ=America/Chicago date +%Y%m%d)"
LOG_FILE="${LOG_DIR}/${LOCK_SUFFIX}-${DAY}.log"

export PATH="${HOME}/.local/bin:/usr/local/bin:${PATH}"

if ! command -v flock >/dev/null 2>&1; then
  echo "flock not found" | tee -a "$LOG_FILE"
  exit 1
fi

LABEL="store=${STORE_CODE} vendor=${VENDOR_NAME}"
CMD=(uv run spree-product-importer -s "$STORE_CODE" -vn "$VENDOR_NAME")
if [[ -n "$SOURCE_NAME" ]]; then
  CMD+=(-src "$SOURCE_NAME")
  LABEL="${LABEL} source=${SOURCE_NAME}"
fi

(
  flock -n 9 || {
    echo "already running: ${LOCK_FILE}" | tee -a "$LOG_FILE"
    exit 1
  }
  cd "$ROOT"
  {
    echo "==== $(date '+%Y-%m-%dT%H:%M:%S%z') start ${LABEL} ===="
    "${CMD[@]}"
    echo "==== $(date '+%Y-%m-%dT%H:%M:%S%z') done ${LABEL} ===="
  } 2>&1 | tee -a "$LOG_FILE"
) 9>"$LOCK_FILE"
