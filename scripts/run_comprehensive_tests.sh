#!/bin/bash

# Run comprehensive comparison tests in Docker

echo "Building Docker image..."
docker build --platform linux/amd64 -t dtpaynt-test -f dtpaynt/Dockerfile dtpaynt/

echo ""
echo "Running comprehensive comparison tests in Docker..."
echo "This will test both algorithms on multiple models with different characteristics."
echo ""

docker run --platform linux/amd64 --rm dtpaynt-test \
    pytest -v -s /opt/synthesis-modified/tests/test_comprehensive_comparison.py
