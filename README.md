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
# Original (AR, CEGIS, Hybrid methods)
docker run -v="$(pwd)/results-original-smoke":/opt/cav25-experiments/results \
  dtpaynt-original ./experiments.sh --smoke-test --skip-omdt

# Symbiotic (AR, CEGIS, Hybrid + NEW Symbiotic synthesis)
docker run -v="$(pwd)/results-symbiotic-smoke":/opt/cav25-experiments/results \
  dtpaynt-symbiotic ./experiments-with-symbiotic.sh --smoke-test --skip-omdt
```

**Note**: Use `experiments-with-symbiotic.sh` for the symbiotic version to automatically run both standard methods AND symbiotic synthesis on each model.

### Step 3: Run Subset Tests (Full Benchmark Suite)

```bash
# Original
docker run -v="$(pwd)/results-original":/opt/cav25-experiments/results \
  dtpaynt-original ./experiments.sh --model-subset

# Symbiotic (includes symbiotic synthesis on all models)
docker run -v="$(pwd)/results-symbiotic":/opt/cav25-experiments/results \
  dtpaynt-symbiotic ./experiments-with-symbiotic.sh --model-subset
```

**Note**: The symbiotic version runs both standard methods (AR, CEGIS, Hybrid) AND symbiotic synthesis, organizing results in separate directories.

### Step 4: Compare Results

```bash
python3 compare_results.py \
  --original ./results-original \
  --symbiotic ./results-symbiotic \
  --output comparison_report.txt
```

python3 compare_results.py \
  --original ./results-original-smoke \
  --symbiotic ./results-symbiotic-smoke \
  --output comparison_report_smoke.txt


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

**Usage (with benchmark models):**
```bash
docker run dtpaynt-symbiotic python3 /opt/paynt/paynt.py \
  ./benchmarks/smoketest/maze/steps \
  --sketch model-random.drn \
  --props discounted.props \
  --method symbiotic \
  --symbiotic-iterations 5
```

**Parameters for Symbiotic:**
- `--dtcontrol-path TEXT` - Path to dtcontrol (default: "dtcontrol")
- `--symbiotic-iterations INT` - Refinement iterations (default: 10)
- `--symbiotic-subtree-depth INT` - Sub-tree depth target (default: 5)
- `--symbiotic-error-tolerance FLOAT` - Max quality drop 0.0-1.0 (default: 0.01)
- `--symbiotic-timeout INT` - Per-subproblem timeout seconds (default: 120)

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

# 3. Run smoke test on original image
mkdir results-original
docker run -v="$(pwd)/results-original":/opt/cav25-experiments/results \
  dtpaynt-original ./experiments.sh --smoke-test --skip-omdt

# 4. Run smoke test on symbiotic image (includes both standard + symbiotic)
mkdir results-symbiotic
docker run -v="$(pwd)/results-symbiotic":/opt/cav25-experiments/results \
  dtpaynt-symbiotic ./experiments-with-symbiotic.sh --smoke-test --skip-omdt

# 5. Results appear in ./results-original/ and ./results-symbiotic/
```

Everything is self-contained in Docker - no setup needed!

---

## All Available Methods

### Both Versions (Original and Symbiotic)

```bash
docker run dtpaynt-original python3 /opt/paynt/paynt.py <model_dir> --method ar
docker run dtpaynt-original python3 /opt/paynt/paynt.py <model_dir> --method cegis
docker run dtpaynt-original python3 /opt/paynt/paynt.py <model_dir> --method hybrid
docker run dtpaynt-original python3 /opt/paynt/paynt.py <model_dir> --method ar_multicore
docker run dtpaynt-original python3 /opt/paynt/paynt.py <model_dir> --method onebyone
```

### Symbiotic Only (Modified Version)

```bash
docker run dtpaynt-symbiotic python3 /opt/paynt/paynt.py <model_dir> \
  --sketch model-random.drn \
  --props discounted.props \
  --method symbiotic
```

---

## Timeline: From Zero to Results

| Step | Time | Command |
|------|------|---------|
| Build original | 5-10 min | `docker build ... -t dtpaynt-original` |
| Build symbiotic | 5-10 min | `docker build ... -t dtpaynt-symbiotic` |
| Smoke test (original) | 5-10 min | `docker run ... dtpaynt-original ./experiments.sh --smoke-test --skip-omdt` |
| Smoke test (symbiotic) | 5-10 min | `docker run ... dtpaynt-symbiotic ./experiments-with-symbiotic.sh --smoke-test --skip-omdt` |
| Compare results | 1 min | `python3 compare_results.py ...` |
| **Total for full smoke test** | **~30-40 mins** | |
| Subset experiments (original) | 30-60 min | `./experiments.sh --model-subset` |
| Subset experiments (symbiotic) | 30-60 min | `./experiments-with-symbiotic.sh --model-subset` |
| **Total for full suite** | **~2-3 hours** | |

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

👉 Read **`IMPLEMENTATION_DETAILS.md`** and **`SYMBIOTIC_INTEGRATION_SUMMARY.md`** for:
- Code changes explained
- Test strategy
- Algorithm deep-dive
- Extension points
- Performance notes
- All root causes and fixes