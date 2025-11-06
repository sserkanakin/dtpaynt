#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

HOST_RESULTS="${HOST_RESULTS:-${REPO_ROOT}/results}"
TIMEOUT="${TIMEOUT:-1800}"
# Default to more frequent progress
PROGRESS_INTERVAL="${PROGRESS_INTERVAL:-1.0}"
BENCHMARK_ARGS="${BENCHMARK_ARGS:---benchmark csma-3-4 --benchmark consensus-4-2 --benchmark obstacles-depth2}"
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

# Control verbosity via VERBOSE env (1 -> verbose; default -> quiet)
if [[ "${VERBOSE:-0}" == "1" ]]; then
  cmd+=( --verbose )
else
  cmd+=( --quiet )
fi

if [[ -n "${BENCHMARK_ARGS}" ]]; then
  read -r -a bench_tokens <<< "${BENCHMARK_ARGS}"
  cmd+=("${bench_tokens[@]}")
fi

if [[ -n "${EXTRA_ARGS}" ]]; then
  # If EXTRA_ARGS begins with --extra-args, keep the following string together as a single value
  if [[ "${EXTRA_ARGS}" == --extra-args* ]]; then
    rest="${EXTRA_ARGS#--extra-args }"
    cmd+=("--extra-args" "${rest}")
  else
    read -r -a extra_tokens <<< "${EXTRA_ARGS}"
    cmd+=("${extra_tokens[@]}")
  fi
fi

printf -v cmd_str '%q ' "${cmd[@]}"
cmd_str=${cmd_str% }
RUN_COMMAND=$'set -e\ncd /opt/synthesis-modified\n'"${cmd_str}"

echo "[run_modified_value_size] Launching experiments (alpha=${HEURISTIC_ALPHA})..."
# Use external timeout to ensure the container is terminated after TIMEOUT seconds if needed
if command -v timeout >/dev/null 2>&1; then
  CIDDIR=$(mktemp -d)
  CIDFILE="${CIDDIR}/cid"
  docker run --cidfile "${CIDFILE}" --rm ${DOCKER_RUN_ARGS:-} \
    -v "${HOST_RESULTS}/logs":/results/logs \
    dtpaynt-modified \
    bash -lc "${RUN_COMMAND}" &
  DOCKER_PID=$!
  ( sleep "${TIMEOUT}"; if [ -f "${CIDFILE}" ]; then CID=$(cat "${CIDFILE}"); if [ -n "$CID" ]; then docker kill "$CID" >/dev/null 2>&1 || true; fi; fi ) &
  WATCH_PID=$!
  set +e
  wait $DOCKER_PID
  STATUS=$?
  set -e
  kill $WATCH_PID 2>/dev/null || true
  rm -rf "${CIDDIR}"
  if [[ $STATUS -ne 0 ]]; then
    echo "[run_modified_value_size] Container exited with status $STATUS" >&2
    exit $STATUS
  fi
else
  docker run --rm ${DOCKER_RUN_ARGS:-} \
    -v "${HOST_RESULTS}/logs":/results/logs \
    dtpaynt-modified \
    bash -lc "${RUN_COMMAND}"
fi

echo "[run_modified_value_size] Completed. Logs stored under ${HOST_RESULTS}/logs/modified_value_size_alpha${HEURISTIC_ALPHA}"
