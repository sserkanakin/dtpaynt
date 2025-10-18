#!/bin/bash
#
# ==============================================================================
# Comprehensive Test Runner for Hybrid DTPAYNT
# ==============================================================================
# This script validates the functionality and performance of the new hybrid
# synthesis algorithm by running a sequence of tests, from basic smoke checks
# to full performance regressions on key benchmarks.
#
# The script will exit immediately if any command fails.
set -e

# --- Configuration ---
# You can adjust these parameters if needed.
# Timeout for the final regression tests (in seconds).
REGRESSION_TIMEOUT=300
# Maximum depth of sub-trees to consider for optimization.
MAX_SUBTREE_DEPTH=7
# Maximum allowed performance loss (e.g., 0.01 = 1%).
MAX_PERFORMANCE_LOSS=0.01


# --- Helper Function ---
# Prints a formatted section header.
print_header() {
    echo ""
    echo "=============================================================================="
    echo "=> $1"
    echo "=============================================================================="
    echo ""
}

# Ensure pytest is available before running the test stages.
if ! python3 -m pytest --version >/dev/null 2>&1; then
    echo "Installing pytest dependency..."
    python3 -m pip install --quiet pytest
fi


# ==============================================================================
# STAGE 1: SMOKE TESTS
# ==============================================================================
# The purpose of these tests is to quickly verify that the main scripts are
# executable, dependencies are met, and the basic argument parsing works
# without performing a full, time-consuming synthesis.

print_header "STAGE 1: Running Smoke Tests"

# Test 1.1: Check if the main hybrid script responds to --help.
# This is the most basic check for script integrity and argument setup.
echo "Smoke Test 1.1: Verifying hybrid_synthesis.py --help..."
python3 hybrid_synthesis.py --help
echo "SUCCESS: --help command executed."
echo ""

# Test 1.2: Run a trivial synthesis task on a very small model.
# This ensures the entire pipeline can be initialized and can run on a simple
# case that should complete very quickly.
echo "Smoke Test 1.2: Running a trivial synthesis task..."
python3 hybrid_synthesis.py \
    models/mdp/simple \
    --prism sketch.templ \
    --prop sketch.props \
    --initial-dot models/mdp/simple/initial.dot \
    --hybrid-enabled \
    --max-subtree-depth 2 \
    --dtcontrol-timeout 15
echo "SUCCESS: Trivial synthesis task completed without errors."


# ==============================================================================
# STAGE 2: UNIT & INTEGRATION TESTS
# ==============================================================================
# This stage runs the specific tests you were instructed to create. It verifies
# that the individual components of the hybrid system (like the DOT parser and
# tree slicer) work as expected and that they integrate correctly.

print_header "STAGE 2: Running Unit and Integration Tests"

# Test 2.1: Run the component-level unit tests.
echo "Test 2.1: Executing component unit tests..."
if [ -f "tests/test_hybrid_components.py" ]; then
    python3 -m pytest tests/test_hybrid_components.py -v
    echo "SUCCESS: Component unit tests passed."
else
    echo "ERROR: tests/test_hybrid_components.py not found. This test is mandatory."
    exit 1
fi
echo ""

# Test 2.2: Run the end-to-end integration tests.
echo "Test 2.2: Executing integration tests..."
if [ -f "tests/test_hybrid_integration.py" ]; then
    python3 -m pytest tests/test_hybrid_integration.py -v
    echo "SUCCESS: Integration tests passed."
else
    echo "ERROR: tests/test_hybrid_integration.py not found. This test is mandatory."
    exit 1
fi


# ==============================================================================
# STAGE 3: PERFORMANCE REGRESSION TESTS (SUBSET)
# ==============================================================================
# This is the final and most important stage. It runs the full hybrid algorithm
# on a subset of challenging benchmarks from the paper. This validates that the
# system not only works but also achieves the desired goal: reducing tree size
# while maintaining near-optimal performance.

print_header "STAGE 3: Running Performance Regression Tests on a Subset of Benchmarks"

# Test 3.1: Run on the 'consensus' model.
# This model is known to be complex and is a key benchmark from the paper's
# Q4 experiment.
echo "Regression Test 3.1: Running on 'consensus-4-2' model..."
python3 hybrid_synthesis.py \
    models/dts-q4/consensus-4-2 \
    --prism model.prism \
    --prop model.props \
    --initial-dot models/dts-q4/consensus-4-2/decision_trees/default/scheduler/default.dot \
    --hybrid-enabled \
    --max-subtree-depth ${MAX_SUBTREE_DEPTH} \
    --max-loss ${MAX_PERFORMANCE_LOSS} \
    --dtcontrol-timeout ${REGRESSION_TIMEOUT}
echo "SUCCESS: 'consensus-4-2' benchmark completed."
echo ""

# Test 3.2: Run on the 'csma' model.
# This is another key benchmark from the paper that tests scalability.
echo "Regression Test 3.2: Running on 'csma-3-4' model..."
python3 hybrid_synthesis.py \
    models/dts-q4/csma-3-4 \
    --prism model.prism \
    --prop model.props \
    --initial-dot models/dts-q4/csma-3-4/decision_trees/default/scheduler/default.dot \
    --hybrid-enabled \
    --max-subtree-depth ${MAX_SUBTREE_DEPTH} \
    --max-loss ${MAX_PERFORMANCE_LOSS} \
    --dtcontrol-timeout ${REGRESSION_TIMEOUT}
echo "SUCCESS: 'csma-3-4' benchmark completed."


# ==============================================================================
# Final Success Message
# ==============================================================================
print_header "All tests completed successfully!"
