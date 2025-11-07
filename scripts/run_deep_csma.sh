#!/usr/bin/env bash
set -euo pipefail

# Run a focused deep CSMA-3-4 experiment suite (5 runs) sequentially.
# Each run uses --tree-depth 6 and --add-dont-care-action with timeout=1800s.
# Usage:
#   ./scripts/run_deep_csma.sh
# Optional env:
#   SKIP_BUILD=1  (skip docker image builds)
#   PAYNT_NPROCS=8 (workers inside PAYNT when using ar_multicore)
#   HOST_RESULTS overrides results root

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
HOST_RESULTS="${HOST_RESULTS:-${REPO_ROOT}/results}"
TIMEOUT=1800
PROGRESS_INTERVAL=5.0
EXTRA_ARGS=(--tree-depth 6 --add-dont-care-action)
# Default benchmarks to run; can be overridden by setting BENCHMARKS env (space-separated)
DEFAULT_BENCHMARKS=(csma-3-4 maze-concise grid-hard)
if [[ -n "${BENCHMARKS:-}" ]]; then
  read -r -a BENCH_ARRAY <<< "${BENCHMARKS}"
else
  BENCH_ARRAY=("${DEFAULT_BENCHMARKS[@]}")
fi
FORCE=(--force)

mkdir -p "${HOST_RESULTS}/logs" "${HOST_RESULTS}/analysis" "${HOST_RESULTS}/plots"

if [[ "${SKIP_BUILD:-0}" != "1" ]]; then
  echo "[run_deep_csma] Building Docker images..."
  docker build --build-arg SRC_FOLDER=synthesis-original -t dtpaynt-original "${REPO_ROOT}"
  docker build --build-arg SRC_FOLDER=synthesis-modified -t dtpaynt-modified "${REPO_ROOT}"
else
  echo "[run_deep_csma] Skipping Docker builds (SKIP_BUILD=1)."
fi

# helper to run a command in docker
run_in_original(){
  local cmd=(python3 experiments-dts.py --timeout "${TIMEOUT}" --output-root /results/logs --progress-interval "${PROGRESS_INTERVAL}" --quiet "${FORCE[@]}" "${BENCHMARK[@]}" "${EXTRA_ARGS[@]}")
  printf -v cmd_str '%q ' "${cmd[@]}"
  cmd_str=${cmd_str% }
  RUN_COMMAND=$'set -e\ncd /opt/synthesis-original\n'"${cmd_str}"
  echo "[run_deep_csma] Running in original: ${cmd_str}"
  docker run --rm -e PAYNT_NPROCS="${PAYNT_NPROCS:-}" -v "${HOST_RESULTS}/logs":/results/logs dtpaynt-original bash -lc "${RUN_COMMAND}"
}

run_in_modified(){
  local heuristic_arg=()
  local alpha_arg=()
  if [[ -n "$1" ]]; then
    heuristic_arg=(--heuristic "$1")
  fi
  if [[ -n "$2" ]]; then
    alpha_arg=(--heuristic-alpha "$2")
  fi
  local cmd=(python3 experiments-dts.py --timeout "${TIMEOUT}" --output-root /results/logs --progress-interval "${PROGRESS_INTERVAL}" --quiet ${heuristic_arg[@]} ${alpha_arg[@]} --force "${BENCHMARK[@]}" "${EXTRA_ARGS[@]}")
  printf -v cmd_str '%q ' "${cmd[@]}"
  cmd_str=${cmd_str% }
  RUN_COMMAND=$'set -e\ncd /opt/synthesis-modified\n'"${cmd_str}"
  echo "[run_deep_csma] Running in modified: ${cmd_str}"
  docker run --rm -e PAYNT_NPROCS="${PAYNT_NPROCS:-}" -v "${HOST_RESULTS}/logs":/results/logs dtpaynt-modified bash -lc "${RUN_COMMAND}"
}

echo "\n=== Run 1: Original (DFS) baseline ==="
echo "\n=== Run 2: Modified (BFS) value_only ==="
echo "\n=== Run 3: Modified (value_size, alpha=0.01) ==="
echo "\n=== Run 4: Modified (value_size, alpha=0.1) ==="
echo "\n=== Run 5: Modified (value_size, alpha=0.5) ==="

for bm in "${BENCH_ARRAY[@]}"; do
  echo "\n=== Benchmark: ${bm} ==="
  # set benchmark tokens for functions
  BENCHMARK=(--benchmark ${bm})

  echo "\n--- Run 1: Original (DFS) baseline for ${bm} ---"
  run_in_original

  echo "\n--- Run 2: Modified (BFS) value_only for ${bm} ---"
  run_in_modified value_only

  echo "\n--- Run 3: Modified (value_size, alpha=0.01) for ${bm} ---"
  run_in_modified value_size 0.01

  echo "\n--- Run 4: Modified (value_size, alpha=0.1) for ${bm} ---"
  run_in_modified value_size 0.1

  echo "\n--- Run 5: Modified (value_size, alpha=0.5) for ${bm} ---"
  run_in_modified value_size 0.5
done

echo "\n[run_deep_csma] All runs submitted sequentially. Check ${HOST_RESULTS}/logs for outputs."

# hint: after runs complete, collect results with the helper script
echo "To aggregate and plot results run: python3 ${REPO_ROOT}/scripts/collect_deep_csma_results.py --results-root ${HOST_RESULTS}"
