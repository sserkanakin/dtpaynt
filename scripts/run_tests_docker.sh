#!/bin/bash

# Script to run priority search comparison tests in Docker
# This script builds the Docker image and runs the comparison tests

set -e  # Exit on error

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "========================================================================"
echo "Building Docker image for DTPAYNT priority search testing..."
echo "========================================================================"

# Build the Docker image from the script's directory
cd "$SCRIPT_DIR"
docker build -t dtpaynt-better-value --build-arg SRC_FOLDER=synthesis-modified .

echo ""
echo "========================================================================"
echo "Running priority search comparison tests..."
echo "========================================================================"

# Run the tests inside the container
docker run --rm dtpaynt-better-value \
    bash -c "cd /opt/synthesis-modified && python tests/test_priority_search_comparison_docker.py"

echo ""
echo "========================================================================"
echo "Tests completed!"
echo "========================================================================"
echo ""
echo "The tests compared the original stack-based search with the new"
echo "priority-queue-based search. Check the output above for detailed results."
