#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

HOST_RESULTS="${HOST_RESULTS:-${REPO_ROOT}/results}"
TIMEOUT="${TIMEOUT:-1800}"
# More frequent progress updates by default
PROGRESS_INTERVAL="${PROGRESS_INTERVAL:-1.0}"
BENCHMARK_ARGS="${BENCHMARK_ARGS:---benchmark csma-3-4 --benchmark consensus-4-2 --benchmark obstacles-depth2}"
EXTRA_ARGS="${PAYNT_RUN_ARGS:-}" # optional extra flags forwarded to experiments-dts.py

mkdir -p "${HOST_RESULTS}/logs"

if [[ "${SKIP_BUILD:-0}" != "1" ]]; then
  echo "[run_original] Building dtpaynt-original image..."
  docker build --build-arg SRC_FOLDER=synthesis-original -t dtpaynt-original "${REPO_ROOT}"
else
  echo "[run_original] Skipping image build (SKIP_BUILD=1)."
fi

cmd=(
  python3 experiments-dts.py
  --timeout "${TIMEOUT}"
  --output-root /results/logs
  --progress-interval "${PROGRESS_INTERVAL}"
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
    # split into the flag and the rest of the string
    # remove the leading "--extra-args" and any following space
    rest="${EXTRA_ARGS#--extra-args }"
    cmd+=("--extra-args" "${rest}")
  else
    read -r -a extra_tokens <<< "${EXTRA_ARGS}"
    cmd+=("${extra_tokens[@]}")
  fi
fi

printf -v cmd_str '%q ' "${cmd[@]}"
cmd_str=${cmd_str% }
RUN_COMMAND=$'set -e\ncd /opt/synthesis-original\n'"${cmd_str}"

echo "[run_original] Launching experiments..."
# Prefer an external watchdog timeout to guarantee the container is stopped after TIMEOUT seconds
if command -v timeout >/dev/null 2>&1; then
  # Use a cidfile + watchdog to ensure the container is killed after TIMEOUT even if the process
  # inside is uncooperative. This avoids leaving orphan containers running when the docker
  # client is terminated by timeout.
  CIDDIR=$(mktemp -d)
  CIDFILE="${CIDDIR}/cid"
  # start docker run in background so we can launch a watchdog that kills the container id
  docker run --cidfile "${CIDFILE}" --rm ${DOCKER_RUN_ARGS:-} \
    -v "${HOST_RESULTS}/logs":/results/logs \
    dtpaynt-original \
    bash -lc "${RUN_COMMAND}" &
  DOCKER_PID=$!
  # watchdog: after TIMEOUT seconds, if container still exists, send SIGTERM first, then SIGKILL
  ( sleep "${TIMEOUT}"; if [ -f "${CIDFILE}" ]; then CID=$(cat "${CIDFILE}"); if [ -n "$CID" ]; then docker kill --signal=SIGTERM "$CID" >/dev/null 2>&1 || true; sleep 10; docker kill "$CID" >/dev/null 2>&1 || true; fi; fi ) &
  WATCH_PID=$!
  set +e
  wait $DOCKER_PID
  STATUS=$?
  set -e
  kill $WATCH_PID 2>/dev/null || true
  rm -rf "${CIDDIR}"
  if [[ $STATUS -ne 0 ]]; then
    echo "[run_original] Container exited with status $STATUS" >&2
    exit $STATUS
  fi
else
  docker run --rm ${DOCKER_RUN_ARGS:-} \
    -v "${HOST_RESULTS}/logs":/results/logs \
    dtpaynt-original \
    bash -lc "${RUN_COMMAND}"
fi

echo "[run_original] Completed. Logs stored under ${HOST_RESULTS}/logs/original"
