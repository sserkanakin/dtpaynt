#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

HOST_RESULTS="${HOST_RESULTS:-${REPO_ROOT}/results}"
TIMEOUT="${TIMEOUT:-1800}"
PROGRESS_INTERVAL="${PROGRESS_INTERVAL:-5.0}"
BENCHMARK_ARGS="${BENCHMARK_ARGS:---benchmark csma-3-4 --benchmark consensus-4-2 --benchmark obstacles-depth2}"
HEURISTIC_ALPHA="${HEURISTIC_ALPHA:-0.1}"

if [[ -z "${PAYNT_RUN_ARGS+x}" ]]; then
  PAYNT_RUN_ARGS="--force"
fi

mkdir -p "${HOST_RESULTS}/logs" "${HOST_RESULTS}/analysis"

# Clean up previous layout where runs were written to results/logs/logs/
if [[ -d "${HOST_RESULTS}/logs/logs" ]]; then
  echo "[run_all_experiments] Detected legacy logs/logs layout; migrating..."
  shopt -s dotglob nullglob
  for entry in "${HOST_RESULTS}/logs/logs"/*; do
    mv "${entry}" "${HOST_RESULTS}/logs/"
  done
  shopt -u dotglob nullglob
  rmdir "${HOST_RESULTS}/logs/logs" 2>/dev/null || true
fi

export HOST_RESULTS TIMEOUT PROGRESS_INTERVAL BENCHMARK_ARGS PAYNT_RUN_ARGS HEURISTIC_ALPHA

if [[ "${SKIP_BUILD:-0}" != "1" ]]; then
  echo "[run_all_experiments] Building base Docker images..."
  docker build --build-arg SRC_FOLDER=synthesis-original -t dtpaynt-original "${REPO_ROOT}"
  docker build --build-arg SRC_FOLDER=synthesis-modified -t dtpaynt-modified "${REPO_ROOT}"
  export SKIP_BUILD=1
else
  echo "[run_all_experiments] Skipping Docker builds (SKIP_BUILD=1)."
fi

scripts=(
  "${SCRIPT_DIR}/run_original.sh"
  "${SCRIPT_DIR}/run_modified_value_only.sh"
  "${SCRIPT_DIR}/run_modified_value_size.sh"
  "${SCRIPT_DIR}/run_modified_bounds_gap.sh"
)
labels=(
  "original"
  "modified_value_only"
  "modified_value_size"
  "modified_bounds_gap"
)

declare -a pids=()

for idx in "${!scripts[@]}"; do
  script="${scripts[$idx]}"
  label="${labels[$idx]}"
  echo "[run_all_experiments] Starting ${label} in background..."
  ( "${script}" ) &
  pids[$idx]=$!
done

status=0
for idx in "${!pids[@]}"; do
  if wait "${pids[$idx]}"; then
    echo "[run_all_experiments] ${labels[$idx]} completed successfully."
  else
    echo "[run_all_experiments] ${labels[$idx]} failed." >&2
    status=1
  fi
done

if [[ "${status}" != "0" ]]; then
  echo "[run_all_experiments] One or more runs failed. Aborting aggregation." >&2
  exit 1
fi

ALPHA_TOKEN=$(python3 - <<PY
alpha=float("${HEURISTIC_ALPHA}")
print("{:.3f}".format(alpha).rstrip("0").rstrip("."))
PY
)

VALUE_SIZE_DIR="modified_value_size_alpha${ALPHA_TOKEN}"

if ! python3 - <<'PYCHECK' >/dev/null 2>&1; then
import importlib
for name in ("pandas", "matplotlib"):
    importlib.import_module(name)
PYCHECK
  echo "[run_all_experiments] Missing pandas or matplotlib in host environment." >&2
  echo "Install them via: python3 -m pip install --upgrade pandas matplotlib" >&2
  exit 1
fi

echo "[run_all_experiments] Aggregating results with process_results.py..."
python3 "${REPO_ROOT}/process_results.py" \
  --algo-root "original=${HOST_RESULTS}/logs/original" \
  --algo-root "modified_value_only=${HOST_RESULTS}/logs/modified_value_only" \
  --algo-root "${VALUE_SIZE_DIR}=${HOST_RESULTS}/logs/${VALUE_SIZE_DIR}" \
  --algo-root "modified_bounds_gap=${HOST_RESULTS}/logs/modified_bounds_gap" \
  --output-dir "${HOST_RESULTS}/analysis"

echo "[run_all_experiments] Aggregation complete."
echo "  Tables: ${HOST_RESULTS}/analysis"
echo "  Plots: ${HOST_RESULTS}/plots"
echo "  Latest run summary: ${HOST_RESULTS}/analysis/run_summary.csv"
