#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

: "${TIMEOUT:=3600}"
: "${PROGRESS_INTERVAL:=10.0}"
: "${BENCHMARK_ARGS:=--benchmark csma-3-4-depth3 --benchmark models/dtmc/maze/concise --benchmark models/dtmc/grid/grid}"
: "${HEURISTIC_ALPHA:=0.1}"

export TIMEOUT PROGRESS_INTERVAL BENCHMARK_ARGS HEURISTIC_ALPHA

exec "${SCRIPT_DIR}/run_all_experiments.sh"
