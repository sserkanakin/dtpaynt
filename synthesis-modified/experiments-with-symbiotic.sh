#!/bin/bash

# Wrapper script to run experiments.sh with symbiotic synthesis included

# Get command line arguments (smoke-test, skip-omdt, etc.)
ARGS="$@"

echo "=========================================="
echo "Running standard experiments (AR, CEGIS, Hybrid)..."
echo "=========================================="
./experiments.sh $ARGS

echo ""
echo "=========================================="
echo "Running symbiotic synthesis on smoke test models..."
echo "=========================================="

# Models from smoke test
MODELS=(
    "dts-q4/consensus-4-2"
    "dts-q4/csma-3-4"
    "mdp/maze"
    "mdp/simple/simple"
    "dtmc/herman"
)

# Create results directory if it doesn't exist
mkdir -p /opt/cav25-experiments/results/logs/paynt-smoke-test

# Run symbiotic on each model
for model in "${MODELS[@]}"; do
    echo ""
    echo "Running symbiotic on: $model"
    
    # Get model number for logging
    model_dir="/opt/cav25-experiments/models/$model"
    
    if [ ! -d "$model_dir" ]; then
        echo "  ⚠ Model not found: $model_dir (skipping)"
        continue
    fi
    
    # Create output directory for this model
    model_name=$(basename "$model")
    output_dir="/opt/cav25-experiments/results/logs/paynt-smoke-test/symbiotic/$model_name"
    mkdir -p "$output_dir"
    
    # Run symbiotic synthesis with timeout
    echo "  → Output: $output_dir"
    
    timeout 300 python3 /opt/paynt/paynt.py "$model_dir" \
        --method symbiotic \
        --symbiotic-iterations 5 \
        --symbiotic-subtree-depth 3 \
        --symbiotic-timeout 60 \
        --export-synthesis "$output_dir/tree" \
        > "$output_dir/stdout.txt" 2>&1
    
    exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        echo "  ✓ Success"
    elif [ $exit_code -eq 124 ]; then
        echo "  ⚠ Timeout (300s)"
    else
        echo "  ✗ Failed (exit code: $exit_code)"
    fi
done

echo ""
echo "=========================================="
echo "Experiments complete!"
echo "Results are in /opt/cav25-experiments/results/"
echo "=========================================="
