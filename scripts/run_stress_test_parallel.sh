#!/usr/bin/env bash
set -euo pipefail

# Parallel version of the stress-test orchestrator.
# Spawns one container per (algorithm variant × benchmark) job.
# Defaults: 10 jobs total, concurrency limited by N_JOBS (default 5).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

HOST_RESULTS="${HOST_RESULTS:-${REPO_ROOT}/results}"
TIMEOUT="${TIMEOUT:-3600}"
# Make progress updates more frequent by default
PROGRESS_INTERVAL="${PROGRESS_INTERVAL:-1.0}"
TREE_DEPTH="${TREE_DEPTH:-5}"
N_JOBS="${N_JOBS:-5}"

# If PAYNT_RUN_ARGS is already set externally, use it; otherwise build default
if [[ -n "${PAYNT_RUN_ARGS:-}" ]]; then
  EXTRA_ARGS=( --extra-args "${PAYNT_RUN_ARGS}" )
else
  EXTRA_ARGS=( --extra-args "--tree-depth ${TREE_DEPTH} --add-dont-care-action" )
fi

# Allow external override of benchmarks
if [[ -n "${BENCHMARK_ARGS:-}" ]]; then
  # Parse benchmark name from BENCHMARK_ARGS (e.g., "--benchmark consensus-4-2" -> "consensus-4-2")
  BENCHMARKS=( $(echo "${BENCHMARK_ARGS}" | grep -oP '(?<=--benchmark )\S+') )
  echo "[stress_parallel] Using externally specified benchmarks: ${BENCHMARKS[@]}"
else
  BENCHMARKS=( csma-3-4 consensus-4-2 )
fi
ALPHAS=( 0.01 0.1 0.5 )

echo "[stress_parallel] Results directory: ${HOST_RESULTS}"
mkdir -p "${HOST_RESULTS}/logs"

echo "[stress_parallel] Building images..."
docker build --build-arg SRC_FOLDER=synthesis-original -t dtpaynt-original "${REPO_ROOT}"
docker build --build-arg SRC_FOLDER=synthesis-modified -t dtpaynt-modified "${REPO_ROOT}"

run_job() {
  local variant="$1"; shift
  local bench="$1"; shift
  echo "[stress_parallel] Launching ${variant} on ${bench}..."
  case "${variant}" in
    original)
      BENCHMARK_ARGS="--benchmark ${bench}" \
      PAYNT_RUN_ARGS="${EXTRA_ARGS[*]}" \
      SKIP_BUILD=1 \
      HOST_RESULTS="${HOST_RESULTS}" \
      TIMEOUT="${TIMEOUT}" \
      PROGRESS_INTERVAL="${PROGRESS_INTERVAL}" \
      bash "${SCRIPT_DIR}/run_original.sh" &
      ;;
    modified_value_only)
      BENCHMARK_ARGS="--benchmark ${bench}" \
      PAYNT_RUN_ARGS="${EXTRA_ARGS[*]}" \
      SKIP_BUILD=1 \
      HOST_RESULTS="${HOST_RESULTS}" \
      TIMEOUT="${TIMEOUT}" \
      PROGRESS_INTERVAL="${PROGRESS_INTERVAL}" \
      bash "${SCRIPT_DIR}/run_modified_value_only.sh" &
      ;;
    modified_value_size_alpha*)
      local alpha="${variant#modified_value_size_alpha}"
      BENCHMARK_ARGS="--benchmark ${bench}" \
      HEURISTIC_ALPHA="${alpha}" \
      PAYNT_RUN_ARGS="${EXTRA_ARGS[*]}" \
      SKIP_BUILD=1 \
      HOST_RESULTS="${HOST_RESULTS}" \
      TIMEOUT="${TIMEOUT}" \
      PROGRESS_INTERVAL="${PROGRESS_INTERVAL}" \
      bash "${SCRIPT_DIR}/run_modified_value_size.sh" &
      ;;
    *)
      echo "Unknown variant: ${variant}" >&2; return 1;;
  esac
}

# Queue jobs
variants=( original modified_value_only )
for a in "${ALPHAS[@]}"; do variants+=( "modified_value_size_alpha${a}" ); done

pids=()
running=0
for v in "${variants[@]}"; do
  for b in "${BENCHMARKS[@]}"; do
    run_job "${v}" "${b}"
    pids+=("$!")
    running=$((running+1))
    # throttle
    if (( running >= N_JOBS )); then
      # wait for any job to finish (bash 5+)
      if wait -n; then :; else echo "[stress_parallel] A job failed." >&2; fi
      running=$((running-1))
    fi
  done
done

# Wait for remaining jobs
wait
echo "[stress_parallel] All jobs finished. Logs under ${HOST_RESULTS}/logs."
