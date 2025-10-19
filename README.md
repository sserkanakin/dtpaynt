# DTPAYNT - Decision Tree Synthesis for MDPs

This repository contains **DTPAYNT**, a decision tree synthesis tool for Markov Decision Processes (MDPs), with two variants:

1. **Original** (`synthesis-original/`): Standard PAYNT with AR, CEGIS, Hybrid methods
2. **Modified** (`synthesis-modified/`): Original + NEW **Symbiotic synthesis** method

---

## Quick Start: 4 Steps

### Step 1: Build Docker Images

```bash
cd /path/to/dtpaynt

# Build original version
docker build --build-arg SRC_FOLDER=synthesis-original -t dtpaynt-original .

# Build modified version with symbiotic synthesis
docker build --build-arg SRC_FOLDER=synthesis-modified -t dtpaynt-symbiotic .
```

### Step 2: Run Smoke Test (5 Models, ~5 mins each)

```bash
# Original
docker run -v="$(pwd)/results-original":/opt/cav25-experiments/results \
  dtpaynt-original ./experiments.sh --smoke-test --skip-omdt

# Symbiotic  
docker run -v="$(pwd)/results-symbiotic":/opt/cav25-experiments/results \
  dtpaynt-symbiotic ./experiments.sh --smoke-test --skip-omdt
```

### Step 3: Run Subset Tests (Full Benchmark Suite)

```bash
# Original
docker run -v="$(pwd)/results-original":/opt/cav25-experiments/results \
  dtpaynt-original ./experiments.sh --model-subset

# Symbiotic
docker run -v="$(pwd)/results-symbiotic":/opt/cav25-experiments/results \
  dtpaynt-symbiotic ./experiments.sh --model-subset
```

### Step 4: Compare Results

```bash
python3 compare_results.py \
  --original ./results-original \
  --symbiotic ./results-symbiotic \
  --output comparison_report.txt
```

---

## Results Structure

```
./results-original/ and ./results-symbiotic/
├─ logs/paynt-smoke-test/1/model_name/
│  ├─ stdout.txt     ← Synthesis logs (timings, tree size, quality metrics)
│  ├─ tree.dot       ← Decision tree in GraphViz format
│  └─ tree.png       ← Tree visualization
├─ generated-results/paynt-smoke-test.csv  ← All models summary
└─ results.csv       ← Final statistics
```

**Key metrics in stdout.txt:**
- `synthesis time:` - Duration in seconds
- `optimum:` - Objective value (goal is higher for maximization)
- `with X decision nodes` - Tree size (goal is smaller)

---

## What's New: Symbiotic Synthesis Method

The **modified** version adds a hybrid synthesis method that:

**Phase 1**: Fast initial tree from **dtcontrol**  
**Phase 2**: Iterative refinement on sub-trees using **DTPAYNT**  
**Phase 3**: Export optimized result  

**Benefits:**
- Combines speed of dtcontrol with optimality of DTPAYNT
- Produces smaller, higher-quality trees
- Configurable trade-offs via parameters

**Usage:**
```bash
docker run dtpaynt-symbiotic python3 /opt/paynt/paynt.py \
  /opt/cav25-experiments/models/maze \
  --method symbiotic \
  --symbiotic-iterations 10
```

---

## Understanding the Comparison Script

The `compare_results.py` script analyzes metrics across both versions:

```bash
python3 compare_results.py \
  --original ./results-original \
  --symbiotic ./results-symbiotic
```

**Output shows:**
- **Tree Size**: Decision nodes in tree (smaller is better)
- **Quality**: Objective value (higher is better)
- **Synthesis Time**: Duration in seconds
- **Improvements**: % change and whether worth the trade-off

Example:
```
Model: maze-steps
├─ Tree Size:    10 → 8 nodes        (-20% better)
├─ Quality:      -74.95 → -63.22     (+15.7% better)
├─ Synthesis:    0.23s → 1.67s       (-628% slower)
└─ Trade-off:    Better quality justifies slower synthesis
```

---

## Repository Structure

```
dtpaynt/
├─ README.md                    ← You are here
├─ IMPLEMENTATION_DETAILS.md    ← Technical details, code changes, tests
├─ compare_results.py           ← Analysis script (shows improvements)
├─ Dockerfile                   ← Docker build configuration
├─
├─ synthesis-original/          ← Standard PAYNT (unchanged baseline)
│  ├─ paynt/
│  │  ├─ cli.py                 ← Original CLI
│  │  ├─ synthesizer/
│  │  │  └─ synthesizer.py      ← Original synthesizer
│  │  └─ ...
│  ├─ Dockerfile
│  └─ ...
│
└─ synthesis-modified/          ← PAYNT + Symbiotic synthesis
   ├─ paynt/
   │  ├─ cli.py                 ← ✏️ Modified (added symbiotic method)
   │  ├─ synthesizer/
   │  │  ├─ synthesizer.py      ← ✏️ Modified (added routing)
   │  │  └─ synthesizer_symbiotic.py  ← 🆕 NEW (531 lines - main algorithm)
   │  └─ ...
   ├─ tests/
   │  └─ test_symbiotic.py      ← 🆕 NEW (412 lines - 20+ tests)
   ├─ Dockerfile                ← ✏️ Modified (added dtcontrol)
   ├─ install.sh                ← ✏️ Modified (added dtcontrol)
   └─ ...
```

---

## For Complete Technical Details

See **`IMPLEMENTATION_DETAILS.md`** which covers:

- ✅ All code changes (with line numbers and examples)
- ✅ Test cases and coverage strategy
- ✅ Algorithm phases (3-phase process explained)
- ✅ Performance characteristics
- ✅ Configuration parameters
- ✅ How to extend/customize

---

## Reproducibility: Fresh Machine

To run on a completely new machine (only Docker needed):

```bash
# 1. Clone
git clone <repo-url> dtpaynt
cd dtpaynt

# 2. Build both images
docker build --build-arg SRC_FOLDER=synthesis-original -t dtpaynt-original .
docker build --build-arg SRC_FOLDER=synthesis-modified -t dtpaynt-symbiotic .

# 3. Run smoke test on new image
mkdir results
docker run -v="$(pwd)/results":/opt/cav25-experiments/results \
  dtpaynt-symbiotic ./experiments.sh --smoke-test --skip-omdt

# 4. Results appear in ./results/
```

Everything is self-contained in Docker - no setup needed!

---

## All Available Methods

### Both Versions (Original and Symbiotic)

```bash
docker run dtpaynt-original python3 /opt/paynt/paynt.py <model> --method ar
docker run dtpaynt-original python3 /opt/paynt/paynt.py <model> --method cegis
docker run dtpaynt-original python3 /opt/paynt/paynt.py <model> --method hybrid
docker run dtpaynt-original python3 /opt/paynt/paynt.py <model> --method ar_multicore
docker run dtpaynt-original python3 /opt/paynt/paynt.py <model> --method onebyone
```

### Symbiotic Only (Modified Version)

```bash
docker run dtpaynt-symbiotic python3 /opt/paynt/paynt.py <model> --method symbiotic
```

**Parameters for Symbiotic:**
- `--dtcontrol-path TEXT` - Path to dtcontrol (default: "dtcontrol")
- `--symbiotic-iterations INT` - Refinement iterations (default: 10)
- `--symbiotic-subtree-depth INT` - Sub-tree depth target (default: 5)
- `--symbiotic-error-tolerance FLOAT` - Max quality drop 0.0-1.0 (default: 0.01)
- `--symbiotic-timeout INT` - Per-subproblem timeout seconds (default: 120)

---

## Timeline: From Zero to Results

| Step | Time | Command |
|------|------|---------|
| Build original | 5-10 min | `docker build ... -t dtpaynt-original` |
| Build symbiotic | 5-10 min | `docker build ... -t dtpaynt-symbiotic` |
| Smoke test (original) | 3-5 min | `docker run ... dtpaynt-original ./experiments.sh --smoke-test --skip-omdt` |
| Smoke test (symbiotic) | 3-5 min | `docker run ... dtpaynt-symbiotic ./experiments.sh --smoke-test --skip-omdt` |
| Compare results | 1 min | `python3 compare_results.py ...` |
| **Total for full smoke test** | **~30 mins** | |
| Subset experiments (original) | 30-60 min | `./experiments.sh --model-subset` |
| Subset experiments (symbiotic) | 30-60 min | `./experiments.sh --model-subset` |
| **Total for full suite** | **~2 hours** | |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Cannot find experiments.sh" | It's in the container at `/opt/cav25-experiments/`. Container starts there automatically. |
| "Results directory empty" | Check volume mount: `-v="$(pwd)/results:/opt/cav25-experiments/results"`. Ensure local `results/` exists. |
| "dtcontrol not found" | Only in symbiotic image. Installed automatically during Docker build. |
| "Synthesis timeout" | Increase `--symbiotic-timeout` parameter. |
| "Out of memory" | Reduce `--symbiotic-subtree-depth` or `--symbiotic-iterations`. |

---

## License

See `LICENSE` files in `synthesis-original/` and `synthesis-modified/`

---

## Next: Detailed Technical Information

👉 Read **`IMPLEMENTATION_DETAILS.md`** for:
- Code changes explained
- Test strategy
- Algorithm deep-dive
- Extension points
- Performance notes

-----

# DTPAYNT Search Algorithm Extension

This project contains a modified version of the DTPAYNT tool, originally provided as a supplement to the CAV'25 paper, "Small Decision Trees for MDPs with Deductive Synthesis".

This repository is structured to manage two versions of the algorithm:

1.  **The original Depth-First Search (DFS) algorithm.**
2.  **Our modified Best-First Search (BFS) algorithm using a priority queue.**

This README provides a complete guide to building the Docker environment for both versions, understanding our algorithmic improvements, and running experiments.

-----

## 1\. Setup and Build Instructions

Follow these steps to build the Docker containers for both the original and modified algorithms.

### Prerequisites

  * **Docker**: Must be installed on your system.
  * **This Git Repository**: You should have this repository cloned to your local machine.

### Folder Structure

This repository uses a two-folder approach to manage the different code versions. The `Dockerfile` is configured to build from either folder using a build argument. The structure is:

```
.
├── Dockerfile
├── synthesis-original/     <-- Contains the original DFS code
└── synthesis-modified/     <-- Contains our new Best-First Search code
```

## Building Docker Images

Navigate to the repository root and build the images:

```bash
# Build image with synthesis-modified (symbiotic synthesis included)
docker build --build-arg SRC_FOLDER=synthesis-modified -t dtpaynt-symbiotic .

# Build image with synthesis-original (original PAYNT)
docker build --build-arg SRC_FOLDER=synthesis-original -t dtpaynt-original .
```

Both images are now ready for use.

## Using the Symbiotic Synthesis Method

The symbiotic synthesis method combines dtcontrol (fast tree generation) with DTPAYNT (optimal synthesis).

### Basic Usage

```bash
# Run symbiotic synthesis on a model
docker run dtpaynt-symbiotic \
  python3 paynt.py /opt/cav25-experiments/models/dts-q4/consensus-4-2 \
  --method symbiotic
```

### With Custom Parameters

```bash
docker run dtpaynt-symbiotic \
  python3 paynt.py /opt/cav25-experiments/models/dts-q4/consensus-4-2 \
  --method symbiotic \
  --symbiotic-iterations 20 \
  --symbiotic-subtree-depth 4 \
  --symbiotic-error-tolerance 0.05 \
  --symbiotic-timeout 180
```

### Symbiotic Synthesis Parameters

- `--dtcontrol-path TEXT` - Path to dtcontrol executable (default: "dtcontrol")
- `--symbiotic-iterations INTEGER` - Number of refinement iterations (default: 10)
- `--symbiotic-subtree-depth INTEGER` - Depth of sub-trees to optimize (default: 5)
- `--symbiotic-error-tolerance FLOAT` - Max performance degradation 0.0-1.0 (default: 0.01)
- `--symbiotic-timeout INTEGER` - Timeout per DTPAYNT sub-problem in seconds (default: 120)

### Run Symbiotic Tests

```bash
docker run dtpaynt-symbiotic pytest /opt/paynt/tests/test_symbiotic.py -v
```

## Running Experiments (Original PAYNT)

### Smoke Test (Quick Verification)

```bash
docker run -v="$(pwd)/results":/opt/cav25-experiments/results \
  dtpaynt-original ./experiments.sh --smoke-test --skip-omdt
```

### Full Benchmark Suite

```bash
docker run -v="$(pwd)/results":/opt/cav25-experiments/results \
  dtpaynt-original ./experiments.sh --skip-omdt
```

### With Model Subset (Recommended)

```bash
docker run -v="$(pwd)/results":/opt/cav25-experiments/results \
  dtpaynt-original ./experiments.sh --skip-omdt --model-subset
```

### With Gurobi (Optional)

```bash
docker run \
  -v=/absolute/path/to/gurobi.lic:/opt/gurobi/gurobi.lic:ro \
  -v="$(pwd)/results":/opt/cav25-experiments/results \
  dtpaynt-original ./experiments.sh --smoke-test
```

## Accessing Results and Debugging

### Results

All generated logs, CSV files, and figures will appear in the `results` folder on your local machine.

### Interactive Shell

```bash
# Explore the symbiotic synthesis version
docker run -it dtpaynt-symbiotic bash

# Explore the original version
docker run -it dtpaynt-original bash
```



- **QUICK_REFERENCE.md** - Fast lookup guide for symbiotic synthesis
- **README_SYMBIOTIC.md** - Complete user guide with examples
- **SYMBIOTIC_IMPLEMENTATION.md** - Technical implementation details
- **INDEX.md** - Navigation guide to all documentation

## Key Innovations in Symbiotic Synthesis

### The Challenge
- **dtcontrol**: Fast but produces large, non-optimal trees
- **DTPAYNT**: Finds small, optimal trees but can be slow on large problems

### The Solution
The symbiotic method combines both:
1. **Phase 1**: Generate initial tree quickly using dtcontrol
2. **Phase 2**: Iteratively select and optimize sub-trees using DTPAYNT
3. **Phase 3**: Export and analyze results

This gives you:
- ✅ Speed of dtcontrol
- ✅ Optimality of DTPAYNT
- ✅ Quality guarantees through error tolerance mechanism
- ✅ Flexible configuration for different tradeoffs

## Running Experiments

### Smoke Test with Modified Version (Symbiotic-enabled)
```bash
docker run -v="$(pwd)/results":/opt/cav25-experiments/results \
  dtpaynt-symbiotic ./experiments.sh --smoke-test --skip-omdt
```

### Full Experiments with Modified Version
```bash
docker run -v="$(pwd)/results":/opt/cav25-experiments/results \
  dtpaynt-symbiotic ./experiments.sh
```

### Smoke Test with Original Version
```bash
docker run -v="$(pwd)/results":/opt/cav25-experiments/results \
  dtpaynt-original ./experiments.sh --smoke-test --skip-omdt
```

### Run Specific Symbiotic Synthesis on a Model
```bash
docker run -v="$(pwd)/models":/opt/models \
  dtpaynt-symbiotic python3 /opt/paynt/paynt.py /opt/models/maze \
  --method symbiotic \
  --symbiotic-iterations 10 \
  --symbiotic-subtree-depth 5
```

## Testing the Implementation

### All Tests
```bash
docker run dtpaynt-symbiotic python3 -m pytest /opt/paynt/tests/ -v
```

### Just Symbiotic Tests
```bash
docker run dtpaynt-symbiotic python3 -m pytest /opt/paynt/tests/test_symbiotic.py -v
```

### With Coverage Report
```bash
docker run dtpaynt-symbiotic \
  python3 -m pytest /opt/paynt/tests/test_symbiotic.py \
  --cov=paynt.synthesizer.synthesizer_symbiotic \
  --cov-report=term-missing
```

## Verification Checklist

- [x] Symbiotic synthesis method implemented
- [x] 5 new CLI parameters added
- [x] 20+ tests included
- [x] Docker support for both versions
- [x] Comprehensive documentation
- [x] Mock dtcontrol for testing
- [x] Error handling and logging
- [x] Backward compatibility maintained

## Support and Troubleshooting

### "dtcontrol: command not found"
dtcontrol is installed in the container. Use `--dtcontrol-path dtcontrol` (the default).

### "Synthesis timeout"
Increase `--symbiotic-timeout` parameter (default is 120 seconds).

### "Memory issues"
Reduce `--symbiotic-subtree-depth` or `--symbiotic-iterations`.

### "Tests not running"
Make sure you're using the `dtpaynt-symbiotic` image which includes test dependencies.

## Additional Resources

- Original PAYNT Paper: CAV'25 - "Small Decision Trees for MDPs with Deductive Synthesis"
- dtcontrol: https://gitlab.com/live-lab/software/dtcontrol
- Storm: https://www.stormchecker.org/

## License

See LICENSE file in synthesis-modified directory.