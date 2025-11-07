#!/bin/bash
# Single run for original algorithm at depth 4 (the missing one)

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}"

HOST_RESULTS="${HOST_RESULTS:-${REPO_ROOT}/results}"
PROGRESS_INTERVAL="${PROGRESS_INTERVAL:-2.0}"
BENCHMARK="consensus-4-2"
TIMEOUT=1800
DEPTH=4

echo "========================================================================"
echo "Original Algorithm - Depth 4 Run (Missing)"
echo "========================================================================"
echo "Results dir: ${HOST_RESULTS}"
echo "Timeout: ${TIMEOUT}s"
echo "Depth: ${DEPTH}"
echo ""

mkdir -p "${HOST_RESULTS}/logs"

# Ensure Docker image exists
if ! docker image inspect dtpaynt-original > /dev/null 2>&1; then
  echo "[Setup] Building dtpaynt-original..."
  docker build --build-arg SRC_FOLDER=synthesis-original -t dtpaynt-original "${REPO_ROOT}" > /dev/null 2>&1
fi

CMD="cd /opt/synthesis-original && python3 experiments-dts.py --timeout ${TIMEOUT} --output-root /results/logs --progress-interval ${PROGRESS_INTERVAL} --quiet --force --benchmark ${BENCHMARK} --extra-args \"--tree-depth ${DEPTH} --add-dont-care-action\""

echo "[Starting] Original DFS at depth ${DEPTH}..."
timeout $((TIMEOUT + 30)) docker run --rm \
  -v "${HOST_RESULTS}/logs":/results/logs \
  dtpaynt-original \
  bash -lc "${CMD}"

echo "[Done] Original depth 4 run completed"
