echo "Starting: 1. Original (DFS)"
echo "Starting: 2. Modified (BFS, value_only)"
echo "Starting: 3. Modified (BFS, value_size, alpha=0.01)"
echo "Starting: 4. Modified (BFS, value_size, alpha=0.1)"
echo "Starting: 5. Modified (BFS, value_size, alpha=0.5)"
echo "----------------------------------------------------------------------"
echo "All 5 experiments launched in parallel."
echo "Monitoring logs in $BASE_RESULTS_DIR/"
echo "Waiting for all runs to complete..."
#!/bin/bash
set -euo pipefail

# =============================================================================
# SIMPLE RACE EXPERIMENT (Docker edition)
# =============================================================================
# This script launches all 5 algorithm variants inside the recommended Docker
# images. Each run mounts results/simple_race into the container so progress
# logs, exports, and metadata remain on the host. Every run uses the
# '--stop-on-first-improvement' flag to exit once a non-trivial tree is found.
# =============================================================================

TIMEOUT="${TIMEOUT:-600}"
BENCHMARK_PATH="${BENCHMARK_PATH:-models/dts-q4/consensus-4-2}"
MAX_DEPTH="${MAX_DEPTH:-4}"
HOST_RESULTS_DIR="$(pwd)/results/simple_race"

mkdir -p "$HOST_RESULTS_DIR"

ensure_image() {
    local image="$1"
    local build_args="$2"
    if ! docker image inspect "$image" >/dev/null 2>&1; then
        echo "Building Docker image '$image'..."
        if [[ -n "$build_args" ]]; then
            docker build $build_args -t "$image" .
        else
            docker build -t "$image" .
        fi
    fi
}

ensure_image "dtpaynt-modified" ""
ensure_image "dtpaynt-original" "--build-arg SRC_FOLDER=synthesis-original"

run_variant() {
    local variant="$1"
    local image="$2"
    local workdir="$3"
    local heuristic_args="$4"

    local variant_dir="$HOST_RESULTS_DIR/$variant"
    local container_root="/results/$variant"
    local output_root="$container_root/logs"
    local export_base="$container_root/tree"

    mkdir -p "$variant_dir"

    echo "Starting: $variant ($image)"

    local docker_cmd="cd /opt/$workdir && python3 experiments-dts.py"
    docker_cmd+=" --benchmark $BENCHMARK_PATH"
    docker_cmd+=" --timeout $TIMEOUT"
    docker_cmd+=" --output-root $output_root"
    if [[ -n "$heuristic_args" ]]; then
        docker_cmd+=" $heuristic_args"
    fi
    docker_cmd+=" --extra-args \"--tree-depth $MAX_DEPTH --add-dont-care-action --export-synthesis $export_base --stop-on-first-improvement\""

    docker run --rm \
        -v "$HOST_RESULTS_DIR":/results \
        "$image" \
        bash -lc "$docker_cmd" \
        &> "$variant_dir/run.log" &

    pids+=("$!")
}

declare -a pids=()

echo "Starting Simple Race (Docker) on $BENCHMARK_PATH..."
echo "Max depth: $MAX_DEPTH  |  Timeout: $TIMEOUT s"
echo "Results directory: $HOST_RESULTS_DIR"
echo "----------------------------------------------------------------------"

run_variant "original" "dtpaynt-original" "synthesis-original" ""
run_variant "modified_value_only" "dtpaynt-modified" "synthesis-modified" "--heuristic value_only"
run_variant "modified_value_size_001" "dtpaynt-modified" "synthesis-modified" "--heuristic value_size --heuristic-alpha 0.01"
run_variant "modified_value_size_01" "dtpaynt-modified" "synthesis-modified" "--heuristic value_size --heuristic-alpha 0.1"
run_variant "modified_value_size_05" "dtpaynt-modified" "synthesis-modified" "--heuristic value_size --heuristic-alpha 0.5"

echo "----------------------------------------------------------------------"
echo "All containers launched. Monitor logs under $HOST_RESULTS_DIR."

for pid in "${pids[@]}"; do
    wait "$pid"
done

echo "All runs completed."
