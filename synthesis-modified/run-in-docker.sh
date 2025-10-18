#!/bin/bash

# Helper script to run commands in the dtpaynt Docker container
# Usage: ./run-in-docker.sh [command]
# Example: ./run-in-docker.sh python3 hybrid_synthesis.py --help
# Example: ./run-in-docker.sh python3 paynt.py --help

# Note: Platform warning is expected on Apple Silicon Macs (amd64 vs arm64)
# The image runs via emulation but works correctly.

docker run --rm -it \
    --platform linux/amd64 \
    -v "$(pwd)":/opt/paynt \
    -w /opt/paynt \
    dtpaynt-modified \
    "$@"
