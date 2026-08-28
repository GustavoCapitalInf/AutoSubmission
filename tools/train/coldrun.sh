#!/usr/bin/env bash
# The train's cold archive run and the batch-8 comparison, run ONCE over the
# composed tree after the stage-version bumps.
#
#   bash tools/train/coldrun.sh <log-path> <base-run-dir> <cold-data-dir> [<out-dir>]
#
#   <base-run-dir>   the comparison base — EXPLICIT, never defaulted. Batch 8
#                    (Gustavo, 2026-08-28, Windows host): the SAME-HOST batch-7
#                    control run produced by tools/train/control_b7.sh at
#                    302f8f2, not the historical run of record and not the
#                    Linux reconstruction. The historical record (356a4269:
#                    2,469 / 17 / 72 / 809 / 13) stays the historical reference
#                    and is neither rewritten nor used as this base.
#   <cold-data-dir>  an ABSENT or EMPTY directory, exported as WEBAPP_DATA_DIR:
#                    the run starts with no OCR and no analysis artifact — the
#                    same cold posture as the control run — and never touches
#                    the checkout's own webapp_data/ (the batch-7 cache the
#                    instruments replay against).
#   <out-dir>        report directory (default discovery_reports/TRAIN8-<tree>).
#
# The comparison is tools/train8_compare.py with the Option-B ACCOUNTING
# quarantine (tools/train/recon_b7_quarantine_nonnative_208.shas): the 208
# non-native shas are excluded from the historical-comparable headline, their
# positive movement is reported separately and never counted, ANY regression
# (comparable or quarantined) fails --fail-on-regression with exit 2, and the
# full per-sha table for the 208 is in the report. `discovery.compare`'s
# canonical output is embedded in the same report; it is never the headline.
# Exit 2 from the comparison stops the line unless the moved document is a
# ceremony named in advance.
#
# Detached; hours when OCR_STAGE_VERSION moved (every scanned document is
# re-OCR'd). The new run directory is identified by its summary.json content
# (a full-archive run holds >= 3,400 documents), never by timestamp. The run
# itself executes under tools/train/winrun.py (committed-memory cap, wall
# timeout, free-memory floor, peak telemetry) — CAP_GB / RUN_TIMEOUT / FLOOR_GB
# override the defaults. Provenance (host, toolchain, tree, keys, inventory,
# cache posture, env) is recorded before the run beside the log and after it
# inside the run directory. CORPUS_ROOT overrides the corpus root; the runner's
# frozen-baseline check is never skipped.
set -u
cd "$(dirname "$0")/../.." || exit 9
LOG="${1:?log path}"
BASE="${2:?base run dir (explicit; the same-host batch-7 control run)}"
COLD="${3:?cold data dir (absent or empty; becomes WEBAPP_DATA_DIR)}"
TREE=$(git rev-parse --short HEAD)
OUT="${4:-discovery_reports/TRAIN8-$TREE}"
ROOT="${CORPUS_ROOT:-Bank Statements}"
QUARANTINE="tools/train/recon_b7_quarantine_nonnative_208.shas"
: > "$LOG"
echo "TREE=$TREE BASE=$BASE COLD=$COLD ROOT=$ROOT OUT=$OUT START=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"

if [ ! -f "$BASE/rows.csv" ] || [ ! -f "$BASE/summary.json" ]; then
  echo "REFUSED: base run dir '$BASE' lacks rows.csv/summary.json" >> "$LOG"; echo "EXIT=refused-base" >> "$LOG"; exit 3
fi
if [ ! -f "$QUARANTINE" ]; then
  echo "REFUSED: quarantine file '$QUARANTINE' missing" >> "$LOG"; echo "EXIT=refused-quarantine" >> "$LOG"; exit 3
fi
if [ -e "$COLD" ] && [ -n "$(ls -A "$COLD" 2>/dev/null)" ]; then
  echo "REFUSED: cold data dir '$COLD' is not empty — the run must start cold" >> "$LOG"; echo "EXIT=refused-cache" >> "$LOG"; exit 4
fi
mkdir -p "$COLD" "$OUT"
export WEBAPP_DATA_DIR="$(cd "$COLD" && pwd -W)"
echo "WEBAPP_DATA_DIR=$WEBAPP_DATA_DIR" >> "$LOG"

python tools/train/provenance.py --checkout . --root "$ROOT" --data-dir "$COLD" \
  --label "train8-coldrun-pre $TREE" --out "$LOG.provenance-pre.json" >> "$LOG" 2>&1
echo "PROVENANCE_PRE_EXIT=$?" >> "$LOG"

before=$(ls -1d "$OUT"/*/ 2>/dev/null | sort)
python tools/train/winrun.py --cap-gb "${CAP_GB:-10}" --timeout "${RUN_TIMEOUT:-28800}" \
  --floor-gb "${FLOOR_GB:-4.0}" --log "$LOG.winrun.jsonl" --label "train8-coldrun-$TREE" -- \
  python -m discovery --scanned --root "$ROOT" --out "$OUT" --quiet >> "$LOG" 2>&1
echo "RUN_EXIT=$?" >> "$LOG"
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
  python tools/train/provenance.py --checkout . --root "$ROOT" --data-dir "$COLD" \
    --label "train8-coldrun-post $TREE" --out "$NEW/provenance.json" >> "$LOG" 2>&1
  echo "PROVENANCE_POST_EXIT=$?" >> "$LOG"
  echo "=== train8_compare (Option-B accounting quarantine) base=$BASE candidate=$NEW ===" >> "$LOG"
  python -m tools.train8_compare --base "$BASE" --candidate "$NEW" --quarantine "$QUARANTINE" \
    --report "$NEW/train8_compare.md" --fail-on-regression > "$LOG.compare" 2>&1
  echo "COMPARE_EXIT=$?" >> "$LOG"
else
  echo "COMPARE_EXIT=skipped (no full-archive run directory found)" >> "$LOG"
fi
echo "=== COLD RUN DONE $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" >> "$LOG"
echo "EXIT=done" >> "$LOG"
