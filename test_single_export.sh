#!/usr/bin/env bash
set -euo pipefail

# Simple test to verify tree export works

cd /root/dtpaynt
NOW=$(date -u +%Y%m%d-%H%M%S)
RESULTS_DIR="/root/dtpaynt/results/single_test_${NOW}"

mkdir -p "${RESULTS_DIR}/logs"

export HOST_RESULTS="${RESULTS_DIR}"
export TIMEOUT=70
export PROGRESS_INTERVAL=1.0
export PAYNT_RUN_ARGS="--extra-args --tree-depth 4 --add-dont-care-action"
export BENCHMARK_ARGS="--benchmark consensus-4-2"
export SKIP_BUILD=1

echo "Running single test: modified_value_only on consensus-4-2"
echo "Results will be in: ${RESULTS_DIR}"

# Run just modified_value_only
bash scripts/run_modified_value_only.sh

echo "Test complete. Checking for tree files..."
find "${RESULTS_DIR}" -name "tree.*" -type f

echo "Done!"
