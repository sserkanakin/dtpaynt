#!/bin/bash

# Build and run simple priority search test in Docker

echo "Building Docker image..."
docker build --platform linux/amd64 -t dtpaynt-test -f dtpaynt/Dockerfile dtpaynt/

echo ""
echo "Running simple test in Docker..."
docker run --platform linux/amd64 --rm dtpaynt-test pytest -v /opt/synthesis-modified/tests/test_simple_priority_search.py::test_simple_sketch
