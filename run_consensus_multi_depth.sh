#!/bin/bash
# Focused multi-depth runner: depths 4, 5, 6, 7 with appropriate timeouts
# Usage: bash run_consensus_multi_depth.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}"

HOST_RESULTS="${HOST_RESULTS:-${REPO_ROOT}/results}"
PROGRESS_INTERVAL="${PROGRESS_INTERVAL:-2.0}"
BENCHMARK="consensus-4-2"

echo "========================================================================"
echo "Consensus-4-2: Multi-Depth Comparison (Depths 4-7, Original + Modified)"
echo "========================================================================"
echo "Results dir: ${HOST_RESULTS}"
echo "Progress interval: ${PROGRESS_INTERVAL}s"
echo ""

mkdir -p "${HOST_RESULTS}/logs"

# Ensure Docker images exist
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

# Helper function to run a solver variant
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
  
  # Launch docker with watchdog timeout
  (
    timeout $((timeout + 30)) docker run --rm \
      -v "${HOST_RESULTS}/logs":/results/logs \
      "${image}" \
      bash -lc "${cmd}" 2>&1 | tail -3
  ) &
  echo "  [$variant_label] PID: $! (Timeout: ${timeout}s, Depth: ${depth})"
}

# Launch all depths in parallel
echo "[Parallel] Launching multi-depth experiments in parallel..."
echo ""

# Depth 4: 30 minutes
echo "== DEPTH 4 (1800s timeout) =="
run_variant_bg "D4-ORIGINAL"              "dtpaynt-original"  "synthesis-original"  "1800"  "4"  ""             ""
run_variant_bg "D4-MOD-VALUE_ONLY"        "dtpaynt-modified"  "synthesis-modified"  "1800"  "4"  "value_only"  ""
run_variant_bg "D4-MOD-VALUE_SIZE-0.1"    "dtpaynt-modified"  "synthesis-modified"  "1800"  "4"  "value_size"  "0.1"
run_variant_bg "D4-MOD-VALUE_SIZE-0.5"    "dtpaynt-modified"  "synthesis-modified"  "1800"  "4"  "value_size"  "0.5"
run_variant_bg "D4-MOD-BOUNDS_GAP"        "dtpaynt-modified"  "synthesis-modified"  "1800"  "4"  "bounds_gap"  ""
echo ""

# Depth 5: 60 minutes
echo "== DEPTH 5 (3600s timeout) =="
run_variant_bg "D5-ORIGINAL"              "dtpaynt-original"  "synthesis-original"  "3600"  "5"  ""             ""
run_variant_bg "D5-MOD-VALUE_ONLY"        "dtpaynt-modified"  "synthesis-modified"  "3600"  "5"  "value_only"  ""
run_variant_bg "D5-MOD-VALUE_SIZE-0.1"    "dtpaynt-modified"  "synthesis-modified"  "3600"  "5"  "value_size"  "0.1"
run_variant_bg "D5-MOD-VALUE_SIZE-0.5"    "dtpaynt-modified"  "synthesis-modified"  "3600"  "5"  "value_size"  "0.5"
run_variant_bg "D5-MOD-BOUNDS_GAP"        "dtpaynt-modified"  "synthesis-modified"  "3600"  "5"  "bounds_gap"  ""
echo ""

# Depth 6: 60 minutes
echo "== DEPTH 6 (3600s timeout) =="
run_variant_bg "D6-ORIGINAL"              "dtpaynt-original"  "synthesis-original"  "3600"  "6"  ""             ""
run_variant_bg "D6-MOD-VALUE_ONLY"        "dtpaynt-modified"  "synthesis-modified"  "3600"  "6"  "value_only"  ""
run_variant_bg "D6-MOD-VALUE_SIZE-0.1"    "dtpaynt-modified"  "synthesis-modified"  "3600"  "6"  "value_size"  "0.1"
run_variant_bg "D6-MOD-VALUE_SIZE-0.5"    "dtpaynt-modified"  "synthesis-modified"  "3600"  "6"  "value_size"  "0.5"
run_variant_bg "D6-MOD-BOUNDS_GAP"        "dtpaynt-modified"  "synthesis-modified"  "3600"  "6"  "bounds_gap"  ""
echo ""

# Depth 7: 60 minutes
echo "== DEPTH 7 (3600s timeout) =="
run_variant_bg "D7-ORIGINAL"              "dtpaynt-original"  "synthesis-original"  "3600"  "7"  ""             ""
run_variant_bg "D7-MOD-VALUE_ONLY"        "dtpaynt-modified"  "synthesis-modified"  "3600"  "7"  "value_only"  ""
run_variant_bg "D7-MOD-VALUE_SIZE-0.1"    "dtpaynt-modified"  "synthesis-modified"  "3600"  "7"  "value_size"  "0.1"
run_variant_bg "D7-MOD-VALUE_SIZE-0.5"    "dtpaynt-modified"  "synthesis-modified"  "3600"  "7"  "value_size"  "0.5"
run_variant_bg "D7-MOD-BOUNDS_GAP"        "dtpaynt-modified"  "synthesis-modified"  "3600"  "7"  "bounds_gap"  ""
echo ""

echo "[Parallel] All 20 variants launched in background!"
echo "[Parallel] Total estimated runtime: ~3600s per depth (depths run in parallel)"
echo ""
echo "To monitor progress, use:"
echo "  tail -f /tmp/multi_depth_run.log"
echo "  find /root/dtpaynt/results/logs -name progress.csv | xargs wc -l"
echo ""

# Wait in background and generate analysis when done
(
  wait
  echo "[PostProcess] All runs completed! Generating focused comparison plots..."
cd /root/dtpaynt
python3 << 'ANALYSIS_EOF'
import csv
import json
from pathlib import Path
from collections import defaultdict
import sys

try:
    import pandas as pd
    import matplotlib.pyplot as plt
except ImportError:
    print("[Warning] pandas/matplotlib not available; skipping plots")
    sys.exit(0)

results_dir = Path("results/logs")
analysis_dir = Path("results/analysis")
analysis_dir.mkdir(parents=True, exist_ok=True)

# Group runs by depth
depth_runs = defaultdict(list)
for algo_dir in results_dir.iterdir():
    if not algo_dir.is_dir():
        continue
    for bench_dir in algo_dir.iterdir():
        if not bench_dir.is_dir():
            continue
        for run_dir in bench_dir.iterdir():
            if not run_dir.is_dir():
                continue
            
            # Extract depth from extra_args in run-info.json
            info_file = run_dir / "run-info.json"
            if not info_file.exists():
                continue
            
            with open(info_file) as f:
                run_info = json.load(f)
            
            # Find --tree-depth in extra_args
            depth = None
            for arg in run_info.get("extra_args", []):
                if arg == "--tree-depth" or arg.startswith("--tree-depth="):
                    continue
                # Check if previous arg was --tree-depth
            
            extra_args = run_info.get("extra_args", [])
            for i, arg in enumerate(extra_args):
                if arg == "--tree-depth" and i + 1 < len(extra_args):
                    try:
                        depth = int(extra_args[i + 1])
                    except:
                        pass
            
            if depth:
                progress_file = run_dir / "progress.csv"
                if progress_file.exists():
                    depth_runs[depth].append({
                        'run_dir': run_dir,
                        'progress_file': progress_file,
                        'algo': algo_dir.name,
                        'run_id': run_dir.name
                    })

print(f"Found {len(depth_runs)} depth groups")
for depth in sorted(depth_runs.keys()):
    print(f"  Depth {depth}: {len(depth_runs[depth])} runs")

# Generate plots only for value_vs_time, tree_size_vs_time, families_evaluated_vs_time
for depth in sorted(depth_runs.keys()):
    depth_dir = analysis_dir / f"consensus-4-2_depth{depth}"
    depth_dir.mkdir(parents=True, exist_ok=True)
    
    # Collect data
    all_data = []
    for run in depth_runs[depth]:
        df = pd.read_csv(run['progress_file'])
        if df.empty:
            continue
        df['algo'] = run['algo']
        all_data.append(df)
    
    if not all_data:
        continue
    
    combined = pd.concat(all_data, ignore_index=True)
    
    # Plot 1: Value vs Time
    plt.figure(figsize=(12, 6))
    for algo in combined['algo'].unique():
        data = combined[combined['algo'] == algo].dropna(subset=['timestamp', 'best_value'])
        if not data.empty:
            plt.plot(data['timestamp'], data['best_value'], label=algo, linewidth=2, marker='o')
    plt.xlabel('Time (s)', fontsize=12)
    plt.ylabel('Best Value', fontsize=12)
    plt.title(f'Consensus-4-2 Depth {depth}: Value Convergence', fontsize=14, fontweight='bold')
    plt.legend(fontsize=10)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(depth_dir / 'value_vs_time.png', dpi=150)
    plt.close()
    
    # Plot 2: Tree Size vs Time
    plt.figure(figsize=(12, 6))
    for algo in combined['algo'].unique():
        data = combined[combined['algo'] == algo].dropna(subset=['timestamp', 'tree_size'])
        if not data.empty:
            plt.plot(data['timestamp'], data['tree_size'], label=algo, linewidth=2, marker='s')
    plt.xlabel('Time (s)', fontsize=12)
    plt.ylabel('Tree Size', fontsize=12)
    plt.title(f'Consensus-4-2 Depth {depth}: Tree Size Growth', fontsize=14, fontweight='bold')
    plt.legend(fontsize=10)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(depth_dir / 'tree_size_vs_time.png', dpi=150)
    plt.close()
    
    # Plot 3: Families Evaluated vs Time
    plt.figure(figsize=(12, 6))
    for algo in combined['algo'].unique():
        data = combined[combined['algo'] == algo].dropna(subset=['timestamp', 'families_evaluated'])
        if not data.empty:
            plt.plot(data['timestamp'], data['families_evaluated'], label=algo, linewidth=2, marker='^')
    plt.xlabel('Time (s)', fontsize=12)
    plt.ylabel('Families Evaluated', fontsize=12)
    plt.title(f'Consensus-4-2 Depth {depth}: Search Efficiency', fontsize=14, fontweight='bold')
    plt.legend(fontsize=10)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(depth_dir / 'families_evaluated_vs_time.png', dpi=150)
    plt.close()
    
    print(f"Generated plots for depth {depth} in {depth_dir}")

echo "All plots generated successfully!"
ANALYSIS_EOF

  echo ""
  echo "========================================================================"
  echo "Results Summary"
  echo "========================================================================"
  echo "Progress logs: ${HOST_RESULTS}/logs/"
  echo "Analysis plots: ${HOST_RESULTS}/analysis/"
  echo ""
  echo "Key output directories:"
  find "${HOST_RESULTS}/analysis" -type d -name "consensus-4-2_depth*" | sort
  echo ""
  echo "Trees exported:"
  find "${HOST_RESULTS}/logs" -name "tree.png" | wc -l
  echo " tree visualizations created"
  echo ""
) &
ANALYSIS_PID=$!

echo "Analysis will run in background (PID: $ANALYSIS_PID)"
echo ""
