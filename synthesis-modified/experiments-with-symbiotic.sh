#!/bin/bash

# Wrapper script to run experiments.sh with symbiotic synthesis included

# Get command line arguments (smoke-test, skip-omdt, etc.)
ARGS="$@"

echo "=========================================="
echo "Running symbiotic synthesis..."
echo "=========================================="

# Determine which benchmark directory to use based on arguments
benchmarks_dir="./benchmarks/all"
if [[ "$ARGS" == *"--model-subset"* ]] || [[ "$ARGS" == *"-m"* ]]; then
    benchmarks_dir="./benchmarks/subset"
fi
if [[ "$ARGS" == *"--smoke-test"* ]] || [[ "$ARGS" == *"-t"* ]]; then
    benchmarks_dir="./benchmarks/smoketest"
fi

# Get experiment name from arguments or use default
experiment_name="paynt-cav-final"
if [[ "$ARGS" == *"paynt-smoke-test"* ]]; then
    experiment_name="paynt-smoke-test"
fi

# Find all benchmark directories that contain model files
benchmark_dirs=$(find "$benchmarks_dir" -type f \( -name "model.prism" -o -name "model-random.drn" \) -exec dirname {} \; | sort -u)

if [ -z "$benchmark_dirs" ]; then
    echo "No benchmark directories found in $benchmarks_dir"
    exit 1
fi

# Create results directory if it doesn't exist
results_dir="./results/logs/${experiment_name}"
mkdir -p "$results_dir"

echo "Found benchmark directories in $benchmarks_dir:"
count=0
for benchmark_dir in $benchmark_dirs; do
    count=$((count + 1))
    echo "  [$count] $benchmark_dir"
done

echo ""
echo "Running symbiotic synthesis on $count models..."
echo ""

# Run symbiotic on each benchmark directory
counter=0
success=0
failed=0
timeout=0

for benchmark_dir in $benchmark_dirs; do
    counter=$((counter + 1))
    
    # Get model name from path (last two components: category/name)
    rel_path=${benchmark_dir#$benchmarks_dir/}
    model_name=$(echo "$rel_path" | sed 's|/|_|g')
    
    echo "[$counter] Running symbiotic on: $rel_path"
    
    # Create output directory for this model
    output_dir="$results_dir/symbiotic/$model_name"
    mkdir -p "$output_dir"
    
    # Determine which model and properties files to use
    sketch_file="model-random.drn"
    props_file="discounted.props"
    
    # For qcomp models, prefer model-random-enabled.drn if available
    if [[ "$benchmark_dir" == *"qcomp"* ]]; then
        if [ -f "$benchmark_dir/model-random-enabled.drn" ]; then
            sketch_file="model-random-enabled.drn"
        fi
    fi
    
    # Check if the required files exist
    if [ ! -f "$benchmark_dir/$sketch_file" ]; then
        echo "  ✗ Skipped: $sketch_file not found"
        failed=$((failed + 1))
        continue
    fi
    if [ ! -f "$benchmark_dir/$props_file" ]; then
        echo "  ✗ Skipped: $props_file not found"
        failed=$((failed + 1))
        continue
    fi
    
    # Run symbiotic synthesis with timeout
    echo "  → Output: $output_dir"
    echo "  → Using: $sketch_file, $props_file"
    
    timeout 300 python3 /opt/paynt/paynt.py "$benchmark_dir" \
        --sketch "$sketch_file" \
        --props "$props_file" \
        --method symbiotic \
        --symbiotic-iterations 5 \
        --symbiotic-subtree-depth 3 \
        --symbiotic-timeout 60 \
        --export-synthesis "$output_dir/tree" \
        > "$output_dir/stdout.txt" 2>&1
    
    exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        echo "  ✓ Success"
        success=$((success + 1))
    elif [ $exit_code -eq 124 ]; then
        echo "  ⚠ Timeout (300s)"
        timeout=$((timeout + 1))
    else
        echo "  ✗ Failed (exit code: $exit_code)"
        tail -20 "$output_dir/stdout.txt" | sed 's/^/    /'
        failed=$((failed + 1))
    fi
done

echo ""
echo "=========================================="
echo "Symbiotic synthesis complete!"
echo "Results summary:"
echo "  ✓ Successful: $success"
echo "  ⚠ Timeout: $timeout"
echo "  ✗ Failed: $failed"
echo "  Total: $counter"
echo ""
echo "All results are in ./results/logs/${experiment_name}/symbiotic/"
echo "=========================================="
