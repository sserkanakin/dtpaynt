#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

HOST_RESULTS="${HOST_RESULTS:-${REPO_ROOT}/results}"
TIMEOUT="${TIMEOUT:-1800}"
PROGRESS_INTERVAL="${PROGRESS_INTERVAL:-5.0}"
BENCHMARK_ARGS="${BENCHMARK_ARGS:---benchmark csma-3-4 --benchmark consensus-4-2 --benchmark obstacles}"
HEURISTIC_ALPHA="${HEURISTIC_ALPHA:-0.1}"
EXTRA_ARGS="${PAYNT_RUN_ARGS:-}" # optional extra flags forwarded to experiments-dts.py

mkdir -p "${HOST_RESULTS}/logs"

if [[ "${SKIP_BUILD:-0}" != "1" ]]; then
  echo "[run_modified_value_size] Building dtpaynt-modified image..."
  docker build --build-arg SRC_FOLDER=synthesis-modified -t dtpaynt-modified "${REPO_ROOT}"
else
  echo "[run_modified_value_size] Skipping image build (SKIP_BUILD=1)."
fi

cmd=(
  python3 experiments-dts.py
  --timeout "${TIMEOUT}"
  --output-root /results/logs
  --progress-interval "${PROGRESS_INTERVAL}"
  --heuristic value_size
  --heuristic-alpha "${HEURISTIC_ALPHA}"
)

if [[ -n "${BENCHMARK_ARGS}" ]]; then
  read -r -a bench_tokens <<< "${BENCHMARK_ARGS}"
  cmd+=("${bench_tokens[@]}")
fi

if [[ -n "${EXTRA_ARGS}" ]]; then
  read -r -a extra_tokens <<< "${EXTRA_ARGS}"
  cmd+=("${extra_tokens[@]}")
fi

printf -v cmd_str '%q ' "${cmd[@]}"
cmd_str=${cmd_str% }
RUN_COMMAND=$'set -e\ncd /opt/synthesis-modified\n'"${cmd_str}"

echo "[run_modified_value_size] Launching experiments (alpha=${HEURISTIC_ALPHA})..."
docker run --rm \
  -v "${HOST_RESULTS}/logs":/results/logs \
  dtpaynt-modified \
  bash -lc "${RUN_COMMAND}"

echo "[run_modified_value_size] Completed. Logs stored under ${HOST_RESULTS}/logs/modified_value_size_alpha${HEURISTIC_ALPHA}"
