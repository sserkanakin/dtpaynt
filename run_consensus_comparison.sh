#!/bin/bash
# Unified runner: Original + Modified (value_only, value_size with multiple alphas) in parallel
# Usage: TIMEOUT=240 bash run_consensus_comparison.sh   # 4 minutes quick test
#        TIMEOUT=1800 bash run_consensus_comparison.sh  # 30 minutes full run

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}"

HOST_RESULTS="${HOST_RESULTS:-${REPO_ROOT}/results}"
TIMEOUT="${TIMEOUT:-240}"
PROGRESS_INTERVAL="${PROGRESS_INTERVAL:-2.0}"
BENCHMARK="consensus-4-2"
TREE_DEPTH="${TREE_DEPTH:-4}"

echo "=============================================="
echo "Consensus-4-2 Comparison: Original + Modified"
echo "=============================================="
echo "Results dir: ${HOST_RESULTS}"
echo "Timeout: ${TIMEOUT}s"
echo "Tree depth: ${TREE_DEPTH}"
echo "Progress interval: ${PROGRESS_INTERVAL}s"
echo ""

mkdir -p "${HOST_RESULTS}/logs"

# Build images once (skip if already exist)
echo "[Setup] Checking Docker images..."
if ! docker image inspect dtpaynt-original > /dev/null 2>&1; then
  echo "[Setup] Building dtpaynt-original..."
  docker build --build-arg SRC_FOLDER=synthesis-original -t dtpaynt-original "${REPO_ROOT}" > /dev/null 2>&1
fi
if ! docker image inspect dtpaynt-modified > /dev/null 2>&1; then
  echo "[Setup] Building dtpaynt-modified..."
  docker build --build-arg SRC_FOLDER=synthesis-modified -t dtpaynt-modified "${REPO_ROOT}" > /dev/null 2>&1
fi
echo "[Setup] Docker images ready."
echo ""

# Launch all variants in parallel
echo "[Parallel] Launching 11 solver variants in parallel (TIMEOUT=${TIMEOUT}s)..."

run_variant_bg() {
  local variant_label="$1"
  local image="$2"
  local folder="$3"
  local heur_flag="$4"
  local heur_alpha="$5"
  
  local cmd="cd /opt/${folder} && python3 experiments-dts.py --timeout ${TIMEOUT} --output-root /results/logs --progress-interval ${PROGRESS_INTERVAL} --quiet --force --benchmark ${BENCHMARK} --extra-args \"--tree-depth ${TREE_DEPTH} --add-dont-care-action\""
  
  if [[ -n "${heur_flag}" ]]; then
    cmd="${cmd} --heuristic ${heur_flag}"
    if [[ -n "${heur_alpha}" ]]; then
      cmd="${cmd} --heuristic-alpha ${heur_alpha}"
    fi
  fi
  
  # Launch docker with watchdog timeout in background
  (
    timeout $((TIMEOUT + 30)) docker run --rm \
      -v "${HOST_RESULTS}/logs":/results/logs \
      "${image}" \
      bash -lc "${cmd}" 2>&1 | tail -3
  ) &
  echo "  [$variant_label] PID: $!"
}

# Launch all 11 variants: 1 original + 1 value_only + 8 value_size alphas + 1 bounds_gap
run_variant_bg "ORIGINAL"              "dtpaynt-original"  "synthesis-original"  ""             ""
run_variant_bg "MOD-VALUE_ONLY"        "dtpaynt-modified"  "synthesis-modified"  "value_only"  ""
run_variant_bg "MOD-VALUE_SIZE-0.01"   "dtpaynt-modified"  "synthesis-modified"  "value_size"  "0.01"
run_variant_bg "MOD-VALUE_SIZE-0.25"   "dtpaynt-modified"  "synthesis-modified"  "value_size"  "0.25"
run_variant_bg "MOD-VALUE_SIZE-0.1"    "dtpaynt-modified"  "synthesis-modified"  "value_size"  "0.1"
run_variant_bg "MOD-VALUE_SIZE-0.5"    "dtpaynt-modified"  "synthesis-modified"  "value_size"  "0.5"
run_variant_bg "MOD-VALUE_SIZE-0.75"   "dtpaynt-modified"  "synthesis-modified"  "value_size"  "0.75"
run_variant_bg "MOD-VALUE_SIZE-0.9"    "dtpaynt-modified"  "synthesis-modified"  "value_size"  "0.9"
run_variant_bg "MOD-VALUE_SIZE-0.99"   "dtpaynt-modified"  "synthesis-modified"  "value_size"  "0.99"
run_variant_bg "MOD-BOUNDS_GAP"        "dtpaynt-modified"  "synthesis-modified"  "bounds_gap"  ""

echo "[Parallel] Waiting for all runs to complete..."
wait
echo "[Parallel] All runs completed."
echo ""

# Generate comparison plots and tables
echo "[PostProcess] Generating comparison tables and plots..."
if ! python3 process_results.py \
  --logs-root "${HOST_RESULTS}/logs" \
  --output-dir "${HOST_RESULTS}/analysis" \
  --benchmark "${BENCHMARK}" 2>&1 | grep -v "^$"; then
  echo "(post-processing completed or encountered issues)"
fi

echo ""
echo "=============================================="
echo "Results Summary"
echo "=============================================="
echo "Progress logs: ${HOST_RESULTS}/logs/"
echo "Analysis tables: ${HOST_RESULTS}/analysis/"
echo "Plots directory: ${HOST_RESULTS}/analysis/figures/"
echo ""
echo "Generated files:"
find "${HOST_RESULTS}/analysis/" -type f \( -name "*.csv" -o -name "*.png" \) 2>/dev/null | sort || echo "  (no files yet)"
echo ""
