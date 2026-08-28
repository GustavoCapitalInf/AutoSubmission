#!/usr/bin/env bash
# The SAME-HOST batch-7 control baseline: the batch-7 code (302f8f2) over the
# frozen corpus, on the host and toolchain the train-8 cold run will use, from
# a cold isolated cache — the regression and movement base for train 8.
#
#   bash tools/train/control_b7.sh <log-path> <b7-worktree> "<corpus-root>" [<cold-data-dir>]
#
# Run from the TRAIN checkout (this script, winrun.py, provenance.py and the
# recon_b7_check checker live here; the batch-7 tree has none of them). The
# worktree must be at 302f8f2 and clean — the batch-7 code is not changed.
# <cold-data-dir> (default <b7-worktree>/webapp_data) must be absent or empty
# and becomes WEBAPP_DATA_DIR for every stage. Stages, each with its own EXIT=
# line (CONTROL_STAGES selects a subset, e.g. "g1 g2" for the cheap gates):
#
#   g1  --dry-run over the corpus root: the pinned 109 through the batch-7 tree
#   g2  corpus_gate.py in the worktree (its own tracked pinned copies)
#   g3  --scanned over the corpus root: the full cold run, under winrun
#   g4  tools/recon_b7_check.py (train checkout) against the new run — G3/G4/G5
#       of the recorded acceptance logic; on THIS host Tesseract is 5.5.0, the
#       batch-7 version, so the historical scanned side may reproduce outright.
#
# Provenance is written before g1 beside the log and after g3 inside the run
# directory. The control run does NOT rewrite the historical run of record; it
# is labelled CONTROL-B7-WIN-<tree> and its accepted figures are recorded in
# BATCH8_TRANSITION.md.
set -u
cd "$(dirname "$0")/../.." || exit 9
TRAIN=$(pwd)
LOG="${1:?log path}"
WT="${2:?batch-7 worktree (detached at 302f8f2)}"
ROOT="${3:?corpus root}"
COLD="${4:-$WT/webapp_data}"
STAGES="${CONTROL_STAGES:-g1 g2 g3 g4}"
: > "$LOG"
B7=$(git -C "$WT" rev-parse --short HEAD)
DIRTY=$(git -C "$WT" status --porcelain | grep -c .)
OUT="$WT/discovery_reports/CONTROL-B7-WIN-$B7"
echo "TRAIN=$(git rev-parse --short HEAD) B7=$B7 DIRTY=$DIRTY WT=$WT ROOT=$ROOT COLD=$COLD OUT=$OUT STAGES=$STAGES START=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"

if [ "$B7" != "302f8f2" ]; then echo "REFUSED: worktree is at $B7, not 302f8f2" >> "$LOG"; echo "EXIT=refused-tree" >> "$LOG"; exit 3; fi
if [ "$DIRTY" != "0" ]; then echo "REFUSED: worktree is dirty ($DIRTY entries)" >> "$LOG"; echo "EXIT=refused-dirty" >> "$LOG"; exit 3; fi
if [ -e "$COLD" ] && [ -n "$(ls -A "$COLD" 2>/dev/null)" ]; then
  echo "REFUSED: cold data dir '$COLD' is not empty" >> "$LOG"; echo "EXIT=refused-cache" >> "$LOG"; exit 4
fi
mkdir -p "$COLD" "$OUT"
export WEBAPP_DATA_DIR="$(cd "$COLD" && pwd -W)"
echo "WEBAPP_DATA_DIR=$WEBAPP_DATA_DIR" >> "$LOG"

python "$TRAIN/tools/train/provenance.py" --checkout "$WT" --root "$ROOT" --data-dir "$COLD" \
  --label "control-b7-pre $B7" --out "$LOG.provenance-pre.json" >> "$LOG" 2>&1
echo "PROVENANCE_PRE_EXIT=$?" >> "$LOG"

cd "$WT" || exit 9
case " $STAGES " in *" g1 "*)
  echo "=== g1 dry run ===" >> "$LOG"
  python "$TRAIN/tools/train/winrun.py" --cap-gb "${CAP_GB:-6}" --timeout 3600 --floor-gb "${FLOOR_GB:-4.0}" \
    --log "$LOG.winrun.jsonl" --label "control-b7-g1-dryrun" -- \
    python -m discovery --dry-run --root "$ROOT" --out "$OUT" --quiet >> "$LOG" 2>&1
  echo "DRYRUN_EXIT=$?" >> "$LOG" ;;
esac
case " $STAGES " in *" g2 "*)
  echo "=== g2 corpus gate ===" >> "$LOG"
  python "$TRAIN/tools/train/winrun.py" --cap-gb "${CAP_GB:-6}" --timeout 3600 --floor-gb "${FLOOR_GB:-4.0}" \
    --log "$LOG.winrun.jsonl" --label "control-b7-g2-gate" -- \
    python corpus_gate.py >> "$LOG" 2>&1
  echo "GATE_EXIT=$?" >> "$LOG" ;;
esac
NEW=""
case " $STAGES " in *" g3 "*)
  echo "=== g3 full cold run ===" >> "$LOG"
  before=$(ls -1d "$OUT"/*/ 2>/dev/null | sort)
  python "$TRAIN/tools/train/winrun.py" --cap-gb "${CAP_GB:-10}" --timeout "${RUN_TIMEOUT:-28800}" --floor-gb "${FLOOR_GB:-4.0}" \
    --log "$LOG.winrun.jsonl" --label "control-b7-g3-scanned" -- \
    python -m discovery --scanned --root "$ROOT" --out "$OUT" --quiet >> "$LOG" 2>&1
  echo "RUN_EXIT=$?" >> "$LOG"
  after=$(ls -1d "$OUT"/*/ | sort)
  while IFS= read -r d; do
    if python - "$d" <<'PY'
import json, sys
summary = json.load(open(sys.argv[1] + "/summary.json", encoding="utf-8"))
documents = sum((summary.get("classification") or {}).values())
sys.exit(0 if documents >= 3400 else 1)
PY
    then NEW="$d"; fi
  done < <(comm -13 <(echo \"$before\") <(echo \"$after\") | sed 's#/$##')
  echo \"NEW_RUN_DIR=$NEW\" >> "$LOG"
  if [ -n "$NEW" ]; then
    python "$TRAIN/tools/train/provenance.py" --checkout "$WT" --root "$ROOT" --data-dir "$COLD" \
      --label "control-b7-post $B7" --out "$NEW/provenance.json" >> "$LOG" 2>&1
    echo "PROVENANCE_POST_EXIT=$?" >> "$LOG"
  fi ;;
esac
case " $STAGES " in *" g4 "*)
  if [ -z "$NEW" ]; then NEW="${CONTROL_RUN_DIR:-}"; fi
  if [ -n "$NEW" ]; then
    echo "=== g4 recon_b7_check (train checkout) run=$NEW ===" >> "$LOG"
    ( cd "$TRAIN" && python -m tools.recon_b7_check --run "$NEW" --report "$NEW/recon_b7_check.md" ) >> "$LOG" 2>&1
    echo "CHECK_EXIT=$?" >> "$LOG"
  else
    echo "CHECK_EXIT=skipped (no run directory)" >> "$LOG"
  fi ;;
esac
echo "=== CONTROL DONE $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" >> "$LOG"
echo "EXIT=done" >> "$LOG"
