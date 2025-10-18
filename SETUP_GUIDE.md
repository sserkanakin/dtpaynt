# DTPAYNT Setup Guide

## Problem Summary

The `stormpy` module dependency issue prevented running `hybrid_synthesis.py` because:
1. Stormpy requires Storm (a probabilistic model checker) and its Python bindings
2. On macOS, building Storm and Stormpy from source requires many native dependencies (cmake, carl, pycarl, etc.)
3. The installation script `install.sh` is designed for Ubuntu/Linux systems

## Solution: Using Docker

Since building all dependencies natively on macOS is complex and time-consuming, the recommended solution is to use Docker, which provides a pre-configured environment with all dependencies.

### Step 1: Build the Docker Image

From the root of the dtpaynt project, run:

```bash
cd /Users/deniskrylov/Developer/dtpaynt
docker build --platform linux/amd64 --build-arg SRC_FOLDER=synthesis-modified -t dtpaynt-modified .
```

This builds a Docker image named `dtpaynt-modified` based on the official PAYNT base image with all Storm dependencies pre-installed.

**Note**: The `--platform linux/amd64` flag is necessary on Apple Silicon Macs because the base PAYNT image is only available for AMD64 architecture.

### Step 2: Run Commands in Docker

Once the image is built, you can run any command inside the container:

```bash
# Test that stormpy works
docker run --rm dtpaynt-modified python3 -c "import stormpy; print('stormpy version:', stormpy.__version__)"

# Run hybrid_synthesis.py help
docker run --rm dtpaynt-modified python3 /opt/paynt/hybrid_synthesis.py --help

# Run your smoke tests
docker run --rm dtpaynt-modified python3 /opt/paynt/experiments-dts.py
```

### Step 3: Working with Local Files

If you need to access files from your local machine or save results:

```bash
docker run --rm -it \
    -v "$(pwd)/synthesis-modified":/opt/paynt \
    -v "$(pwd)/results-modified":/opt/results \
    dtpaynt-modified \
    python3 /opt/paynt/hybrid_synthesis.py [YOUR_ARGS]
```

The `-v` flag mounts your local directories into the container so changes are persistent.

## Alternative: Native Installation (Advanced)

If you prefer to install natively on macOS, you would need to:

1. Install Homebrew dependencies:
   ```bash
   brew install cmake boost gmp cln ginac eigen xerces-c hwloc z3
   ```

2. Build Carl library from source
3. Build Storm from source
4. Build pycarl Python bindings
5. Build stormpy Python bindings
6. Install PAYNT dependencies

This process can take 1-2 hours and is more error-prone on macOS. **Docker is strongly recommended**.

## Helper Script

A helper script `run-in-docker.sh` has been created in `synthesis-modified/` to make running commands easier:

```bash
# Make it executable (if not already)
chmod +x synthesis-modified/run-in-docker.sh

# Use it to run commands
./synthesis-modified/run-in-docker.sh python3 hybrid_synthesis.py --help
```

## Verification

Once Docker image is built, verify the installation:

```bash
# Check stormpy
docker run --rm dtpaynt-modified python3 -c "import stormpy; print('Success!')"

# Check PAYNT
docker run --rm dtpaynt-modified python3 /opt/paynt/paynt.py --help

# Check hybrid synthesis
docker run --rm dtpaynt-modified python3 /opt/paynt/hybrid_synthesis.py --help
```

All three commands should complete without errors.
