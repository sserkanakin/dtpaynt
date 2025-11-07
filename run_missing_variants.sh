#!/bin/bash
# Start all missing runs

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}"
HOST_RESULTS="${HOST_RESULTS:-${REPO_ROOT}/results}"
PROGRESS_INTERVAL="${PROGRESS_INTERVAL:-2.0}"
BENCHMARK="consensus-4-2"

mkdir -p "${HOST_RESULTS}/logs"

# Ensure Docker images exist
if ! docker image inspect dtpaynt-original > /dev/null 2>&1; then
  docker build --build-arg SRC_FOLDER=synthesis-original -t dtpaynt-original "${REPO_ROOT}" > /dev/null 2>&1
fi
if ! docker image inspect dtpaynt-modified > /dev/null 2>&1; then
  docker build --build-arg SRC_FOLDER=synthesis-modified -t dtpaynt-modified "${REPO_ROOT}" > /dev/null 2>&1
fi

run_variant_bg() {
  local variant_label="$1"
  local image="$2"
  local folder="$3"
  local timeout="$4"
  local depth="$5"
  local heur_flag="$6"
  local heur_alpha="$7"
  
  local cmd="cd /opt/${folder} && python3 experiments-dts.py --timeout ${timeout} --output-root /results/logs --progress-interval ${PROGRESS_INTERVAL} --quiet --force --benchmark ${BENCHMARK} --extra-args \"--tree-depth ${depth} --add-dont-care-action\""
  
  if [[ -n "${heur_flag}" ]]; then
    cmd="${cmd} --heuristic ${heur_flag}"
    if [[ -n "${heur_alpha}" ]]; then
      cmd="${cmd} --heuristic-alpha ${heur_alpha}"
    fi
  fi
  
  (
    timeout $((timeout + 30)) docker run --rm \
      -v "${HOST_RESULTS}/logs":/results/logs \
      "${image}" \
      bash -lc "${cmd}" 2>&1 | tail -3
  ) &
}

# Start missing runs
run_variant_bg "original-D5"                 "dtpaynt-original"  "synthesis-original"  "3600"  "5"  ""             ""
run_variant_bg "value_only-D6"               "dtpaynt-modified"  "synthesis-modified"  "3600"  "6"  "value_only"  ""
run_variant_bg "value_size0.1-D5"            "dtpaynt-modified"  "synthesis-modified"  "3600"  "5"  "value_size"  "0.1"
run_variant_bg "value_size0.25-D5"           "dtpaynt-modified"  "synthesis-modified"  "3600"  "5"  "value_size"  "0.25"
run_variant_bg "value_size0.5-D5"            "dtpaynt-modified"  "synthesis-modified"  "3600"  "5"  "value_size"  "0.5"
run_variant_bg "value_size0.01-D7"           "dtpaynt-modified"  "synthesis-modified"  "3600"  "7"  "value_size"  "0.01"
run_variant_bg "value_size0.75-D7"           "dtpaynt-modified"  "synthesis-modified"  "3600"  "7"  "value_size"  "0.75"
run_variant_bg "value_size0.9-D6"            "dtpaynt-modified"  "synthesis-modified"  "3600"  "6"  "value_size"  "0.9"
run_variant_bg "value_size0.99-D7"           "dtpaynt-modified"  "synthesis-modified"  "3600"  "7"  "value_size"  "0.99"

wait
