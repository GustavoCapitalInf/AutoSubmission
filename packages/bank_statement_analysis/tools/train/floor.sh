#!/usr/bin/env bash
# The train's authoritative proof floor, run ONCE over the composed tree.
#
#   "C:\Program Files\Git\bin\bash.exe" tools/train/floor.sh <log-path>
#
# Detached: the whole floor takes ~1 h on this host (suite ~12 min, gate
# ~25 min, corpus-marked slice ~15 min). Every step writes its own EXIT= line;
# a result without its exit code is not a result. Run on an IDLE host — the
# detect-budget test in the corpus-marked slice is timing-sensitive under
# sibling load (batch-8 ruling: a red slice under load is re-run idle, not
# carried). Batch-7 helper made durable in batch 8.
set -u
cd "$(dirname "$0")/../.." || exit 9
LOG="${1:?log path}"; : > "$LOG"
echo "TREE=$(git rev-parse --short HEAD) START=$(date)" >> "$LOG"

echo "=== 1. full default suite ===" >> "$LOG"
python -m pytest -q -p no:cacheprovider >> "$LOG" 2>&1; echo "SUITE_EXIT=$?" >> "$LOG"

echo "=== 2. canonical guards (5 files) ===" >> "$LOG"
python -m pytest -q -p no:cacheprovider \
  tests/test_no_statement_hardcodes.py tests/test_no_parser_helper_clones.py \
  tests/test_r1_hardcodes.py tests/test_experiments_are_not_wired.py \
  tests/test_filename_boundary.py >> "$LOG" 2>&1; echo "GUARDS_EXIT=$?" >> "$LOG"

echo "=== 3. canonical conformance (7 files) ===" >> "$LOG"
python -m pytest -q -p no:cacheprovider \
  tests/test_parser_conformance.py tests/test_parser_registry_entries.py \
  tests/test_parser_detection_markers.py tests/test_parser_registry.py \
  tests/test_parser_crash_shapes.py tests/test_parser_exception_boundary.py \
  tests/test_count_semantics.py >> "$LOG" 2>&1; echo "CONFORMANCE_EXIT=$?" >> "$LOG"

echo "=== 4. corpus gate ===" >> "$LOG"
python corpus_gate.py >> "$LOG" 2>&1; echo "GATE_EXIT=$?" >> "$LOG"

echo "=== 5. corpus-marked slice ===" >> "$LOG"
python -m pytest -q -p no:cacheprovider -m corpus >> "$LOG" 2>&1; echo "CORPUS_EXIT=$?" >> "$LOG"

echo "=== FLOOR DONE $(date) ===" >> "$LOG"
echo "EXIT=done" >> "$LOG"
