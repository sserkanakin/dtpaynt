#!/usr/bin/env bash
set -euo pipefail

# Orchestrate the "Stress Test" experiments described in the plan:
# - Benchmarks: csma-3-4, consensus-4-2
# - Timeout: 3600s
# - Extra args: --tree-depth 7 --add-dont-care-action
# - Algorithms:
#   * original (DFS)
#   * modified value_only (BFS)
#   * modified value_size with alpha in {0.01, 0.1, 0.5}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Allow overrides via env
HOST_RESULTS="${HOST_RESULTS:-${REPO_ROOT}/results}"
TIMEOUT="${TIMEOUT:-3600}"
PROGRESS_INTERVAL="${PROGRESS_INTERVAL:-5.0}"
TREE_DEPTH="${TREE_DEPTH:-7}"

# Only the two larger DTS-Q4 benchmarks
BENCHMARK_ARGS="--benchmark csma-3-4 --benchmark consensus-4-2"

# Always pass explicit depth and ensure don't-care action is on (presets also include it)
EXTRA_ARGS=( --extra-args "--tree-depth ${TREE_DEPTH} --add-dont-care-action" )

echo "[stress_test] Results directory: ${HOST_RESULTS}"
mkdir -p "${HOST_RESULTS}/logs"

# Build images once
echo "[stress_test] Building Docker images (original, modified)..."
docker build --build-arg SRC_FOLDER=synthesis-original -t dtpaynt-original "${REPO_ROOT}"
docker build --build-arg SRC_FOLDER=synthesis-modified -t dtpaynt-modified "${REPO_ROOT}"

export HOST_RESULTS TIMEOUT PROGRESS_INTERVAL

echo "[stress_test] Running ORIGINAL (DFS) ..."
BENCHMARK_ARGS="${BENCHMARK_ARGS}" \
PAYNT_RUN_ARGS="${EXTRA_ARGS[*]}" \
SKIP_BUILD=1 \
bash "${SCRIPT_DIR}/run_original.sh"

echo "[stress_test] Running MODIFIED value_only (BFS) ..."
BENCHMARK_ARGS="${BENCHMARK_ARGS}" \
PAYNT_RUN_ARGS="${EXTRA_ARGS[*]}" \
SKIP_BUILD=1 \
bash "${SCRIPT_DIR}/run_modified_value_only.sh"

for alpha in 0.01 0.1 0.5; do
  echo "[stress_test] Running MODIFIED value_size (alpha=${alpha}) ..."
  BENCHMARK_ARGS="${BENCHMARK_ARGS}" \
  HEURISTIC_ALPHA="${alpha}" \
  PAYNT_RUN_ARGS="${EXTRA_ARGS[*]}" \
  SKIP_BUILD=1 \
  bash "${SCRIPT_DIR}/run_modified_value_size.sh"
done

echo "[stress_test] All runs launched. Logs under ${HOST_RESULTS}/logs."
