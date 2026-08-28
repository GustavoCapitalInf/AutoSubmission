#!/usr/bin/env bash
# The train's cold archive run and the regression comparison against the run
# of record, run ONCE over the composed tree after the stage-version bumps.
#
#   "C:\Program Files\Git\bin\bash.exe" tools/train/coldrun.sh <log-path> [<base-run-dir>]
#
# Detached; hours when OCR_STAGE_VERSION moved (every scanned document is
# re-OCR'd). The new run directory is identified by its summary.json content
# (a full-archive run holds >= 3,400 documents), never by timestamp. The
# comparison is `discovery.compare --fail-on-regression`: exit 2 means a
# document moved DOWN — either an approved truth-set ceremony named in advance,
# or a stop-the-line. Batch-7 helper made durable in batch 8; BASE defaults to
# the batch-7 official run of record.
set -u
cd "$(dirname "$0")/../.." || exit 9
LOG="${1:?log path}"
BASE="${2:-discovery_reports/2026-08-23T020128.909387-0000-356a4269}"
# Batch-8 recovery (2026-08-27): the historical run of record is gone and the
# on-disk archive carries three post-freeze additions, so the corpus root and
# the report directory are overridable. CORPUS_ROOT must still pass the
# runner's frozen-baseline check — this script never passes --skip-baseline.
ROOT="${CORPUS_ROOT:-Bank Statements}"
OUT="${DISCOVERY_OUT:-discovery_reports}"
: > "$LOG"
echo "TREE=$(git rev-parse --short HEAD) BASE=$BASE ROOT=$ROOT OUT=$OUT START=$(date)" >> "$LOG"

mkdir -p "$OUT"
before=$(ls -1d "$OUT"/*/ 2>/dev/null | sort)
python -m discovery --scanned --root "$ROOT" --out "$OUT" >> "$LOG" 2>&1; echo "RUN_EXIT=$?" >> "$LOG"
after=$(ls -1d "$OUT"/*/ | sort)

NEW=""
for d in $(comm -13 <(echo "$before") <(echo "$after") | sed 's#/$##'); do
  if python - "$d" <<'PY'
import json, sys
summary = json.load(open(sys.argv[1] + "/summary.json", encoding="utf-8"))
documents = sum((summary.get("classification") or {}).values())
sys.exit(0 if documents >= 3400 else 1)
PY
  then NEW="$d"; fi
done
echo "NEW_RUN_DIR=$NEW" >> "$LOG"

if [ -n "$NEW" ]; then
  echo "=== compare vs run of record ===" >> "$LOG"
  python -m discovery.compare "$BASE" "$NEW" --fail-on-regression > "$LOG.compare" 2>&1
  echo "COMPARE_EXIT=$?" >> "$LOG"
else
  echo "COMPARE_EXIT=skipped (no full-archive run directory found)" >> "$LOG"
fi
echo "=== COLD RUN DONE $(date) ===" >> "$LOG"
echo "EXIT=done" >> "$LOG"
