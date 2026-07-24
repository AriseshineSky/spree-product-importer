#!/usr/bin/env bash
# Nightly Spree import for one store + vendor profile.
# Usage: run_nightly_import.sh em-spree topselected
#        run_nightly_import.sh em-spree em-hu
set -euo pipefail

STORE_CODE="${1:?store_code required, e.g. em-spree}"
VENDOR_NAME="${2:?vendor name/key required, e.g. topselected or em-hu}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${HOME}/logs/spree-import"
LOCK_SUFFIX="${STORE_CODE}-${VENDOR_NAME}"
LOCK_FILE="/tmp/spree-import-${LOCK_SUFFIX}.lock"
mkdir -p "$LOG_DIR"

DAY="$(TZ=America/Chicago date +%Y%m%d)"
LOG_FILE="${LOG_DIR}/${LOCK_SUFFIX}-${DAY}.log"

export PATH="${HOME}/.local/bin:/usr/local/bin:${PATH}"

if ! command -v flock >/dev/null 2>&1; then
  echo "flock not found" | tee -a "$LOG_FILE"
  exit 1
fi

exec flock -n "$LOCK_FILE" bash -c "
  set -euo pipefail
  cd \"$ROOT\"
  {
    echo \"==== \$(date -Is) start store=${STORE_CODE} vendor=${VENDOR_NAME} ====\"
    uv run spree-product-importer -s \"$STORE_CODE\" -vn \"$VENDOR_NAME\"
    echo \"==== \$(date -Is) done store=${STORE_CODE} vendor=${VENDOR_NAME} ====\"
  } 2>&1 | tee -a \"$LOG_FILE\"
"
