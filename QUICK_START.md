# DTPAYNT Quick Start Guide

## ✅ Solution Implemented

The stormpy dependency issue has been resolved by using Docker. The `dtpaynt-modified` Docker image is now built and ready to use.

## Quick Test Commands

### Test stormpy is working:
```bash
docker run --rm dtpaynt-modified python3 -c "import stormpy; print('stormpy version:', stormpy.__version__)"
```
**Expected output:** `stormpy version: 1.9.0`

### Test hybrid_synthesis.py:
```bash
docker run --rm dtpaynt-modified python3 /opt/paynt/hybrid_synthesis.py --help
```
**Expected output:** Help text showing all available options

### Test paynt.py:
```bash
docker run --rm dtpaynt-modified python3 /opt/paynt/paynt.py --help
```
**Expected output:** PAYNT usage information

## Running Your Scripts

### Option 1: Direct Docker Commands

Run any Python script from the synthesis-modified directory:

```bash
docker run --rm --platform linux/amd64 dtpaynt-modified python3 /opt/paynt/hybrid_synthesis.py [ARGS]
```

### Option 2: Using the Helper Script

A helper script has been created for convenience:

```bash
cd /Users/deniskrylov/Developer/dtpaynt/synthesis-modified
./run-in-docker.sh python3 hybrid_synthesis.py --help
```

### Option 3: Interactive Session

Start an interactive bash session in the container:

```bash
docker run --rm -it --platform linux/amd64 \
    -v "$(pwd)/synthesis-modified":/opt/paynt \
    -v "$(pwd)/results-modified":/opt/results \
    dtpaynt-modified \
    /bin/bash
```

Then run commands inside:
```bash
cd /opt/paynt
python3 hybrid_synthesis.py --help
python3 experiments-dts.py
```

## Running Smoke Tests

To run your smoke tests mentioned in the original issue:

```bash
# First smoke test (help command)
docker run --rm dtpaynt-modified python3 /opt/paynt/hybrid_synthesis.py --help

# Run the full experiments script
docker run --rm --platform linux/amd64 \
    -v "$(pwd)/results-modified":/opt/results \
    dtpaynt-modified \
    python3 /opt/paynt/experiments-dts.py
```

## Mounting Local Directories

To work with local files and save results:

```bash
docker run --rm --platform linux/amd64 \
    -v "$(pwd)/synthesis-modified":/opt/paynt \
    -v "$(pwd)/results-modified":/opt/results \
    -v "$(pwd)/synthesis-modified/models":/opt/models \
    dtpaynt-modified \
    python3 /opt/paynt/hybrid_synthesis.py PROJECT --prism model.prism --prop model.props
```

## Platform Warning (Normal on Apple Silicon)

You may see this warning on Apple Silicon Macs:
```
WARNING: The requested image's platform (linux/amd64) does not match the detected host platform (linux/arm64/v8)
```

**This is normal and expected.** The image runs correctly via Docker's emulation layer. The warning can be safely ignored.

## Troubleshooting

### If you need to rebuild the image:

```bash
cd /Users/deniskrylov/Developer/dtpaynt
docker build --platform linux/amd64 --build-arg SRC_FOLDER=synthesis-modified -t dtpaynt-modified .
```

### If you get "image not found" errors:

Make sure the image was built successfully:
```bash
docker images | grep dtpaynt-modified
```

You should see an entry like:
```
dtpaynt-modified    latest    7499c44b6e71    X minutes ago    XXX MB
```

## Next Steps

You can now:
1. ✅ Run `hybrid_synthesis.py --help` (works!)
2. ✅ Run your full smoke test suite
3. ✅ Execute any PAYNT commands inside the Docker container
4. ✅ Mount local directories to work with your own models and save results

For more detailed information, see `SETUP_GUIDE.md` in the project root.
