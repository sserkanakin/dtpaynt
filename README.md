# DTPAYNT Heuristic Playground

This repository keeps two PAYNT source trees side by side so that refined best-first heuristics can be compared against the original stack-based search.

- `synthesis-original/` – upstream depth-first solver packaged with the CAV artefact.
- `synthesis-modified/` – priority-queue synthesizer with pluggable heuristics and enhanced logging.

Use the top-level `Dockerfile` and helper scripts to build images, execute benchmarks, and generate publication-ready tables and plots.

## Repository Layout

```
.
├── Dockerfile                     # Multi-stage image that builds either source tree
├── BENCHMARKS.md                  # Catalogue of preset models used in experiments
├── process_results.py             # pandas/matplotlib aggregation pipeline
├── results/                       # Host-side artefacts (logs, tables, plots)
├── run_tests_docker.sh            # Convenience wrapper that executes pytest in Docker
├── run_simple_test_docker.sh      # Single-benchmark smoke test in Docker
├── run_comprehensive_tests.sh     # Launches the full regression suite on bare metal
├── synthesis-original/            # Baseline PAYNT implementation (stack search)
└── synthesis-modified/            # Heuristic-enabled PAYNT implementation (priority queue)
```

## Build Docker Images

All commands below assume you are in the repository root.

1. Build the modified priority-queue solver (default `SRC_FOLDER`):
   ```bash
   docker build -t dtpaynt-modified .
   ```
2. Build the baseline stack solver by switching the build argument:
   ```bash
   docker build --build-arg SRC_FOLDER=synthesis-original -t dtpaynt-original .
   ```
3. (Optional) Rebuild after editing native dependencies in `payntbind/`:
   ```bash
   docker build --no-cache -t dtpaynt-modified-dev .
   ```

Each image exposes `/opt/synthesis-{modified,original}` inside the container with Storm, pycarl, Boost, and matplotlib ready to use.

## Heuristic Options

The modified synthesizer accepts a priority heuristic via `--heuristic` (wired through `experiments-dts.py` to `paynt.py`).

| Flag | Description |
|------|-------------|
| `value_only` | Greedy best-first queue based solely on the latest improving value (matches the first prototype). |
| `value_size` + `--heuristic-alpha <α>` | Penalises wide families: priority = value − α·size. Start with α = 0.1. |
| `bounds_gap` | Uses the ratio lower_bound / (upper_bound − lower_bound + ε) to emphasise families that reduce the residual gap. |
| `upper_bound` | Alias for `bounds_gap`; maintained for backwards compatibility. |

Heuristic selections and α-coefficients are recorded in the progress metadata so that downstream analysis can group runs automatically.

## Run Experiments in Docker

Mount a persistent results directory from the host and call the Click runner inside the desired image.

```bash
HOST_RESULTS="$(pwd)/results"
mkdir -p "$HOST_RESULTS/logs"

# Modified solver – value-only heuristic (default presets)
docker run --rm \
  -v "$HOST_RESULTS/logs":/results \
  dtpaynt-modified \
  bash -lc "cd /opt/synthesis-modified && python3 experiments-dts.py \\
    --timeout 1800 \\
    --output-root /results/logs \\
    --benchmark csma-3-4 --benchmark consensus-4-2 --benchmark obstacles \\
    --heuristic value_only"

# Modified solver – value_size heuristic with α = 0.1
docker run --rm \
  -v "$HOST_RESULTS/logs":/results \
  dtpaynt-modified \
  bash -lc "cd /opt/synthesis-modified && python3 experiments-dts.py \\
    --timeout 1800 \\
    --output-root /results/logs \\
    --benchmark csma-3-4 --benchmark consensus-4-2 --benchmark obstacles \\
    --benchmark models/dtmc/maze/concise \\
    --heuristic value_size --heuristic-alpha 0.1"

# Baseline solver for comparison
docker run --rm \
  -v "$HOST_RESULTS/logs":/results \
  dtpaynt-original \
  bash -lc "cd /opt/synthesis-original && python3 experiments-dts.py \\
    --timeout 1800 \\
    --output-root /results/logs \\
    --benchmark csma-3-4 --benchmark consensus-4-2 --benchmark obstacles"
```

Use `python experiments-dts.py --list` inside either tree to see all predefined presets. Pass a path (relative to the tree) via `--benchmark` to run custom models; the script infers sketch/props filenames when possible.

## Results and Post-Processing

Every run produces a timestamped folder under `results/logs/<algorithm_variant>/<benchmark>/` containing:
- `progress.csv` – structured progress log with timestamped metrics.
- `stdout.txt` – full console output from PAYNT.
- `run-info.json` – command-line parameters and metadata used for that run.

Aggregate the latest runs across algorithms with the pandas-based helper:

```bash
python -m pip install --upgrade pandas matplotlib  # once on the host
python process_results.py \
  --algo-root original=results/logs/original \
  --algo-root modified_value_only=results/logs/modified_value_only \
  --algo-root modified_value_size_alpha0.1=results/logs/modified_value_size_alpha0.1 \
  --algo-root modified_bounds_gap=results/logs/modified_bounds_gap \
  --output-dir results/analysis
```

Key artefacts:
- `results/analysis/run_summary.csv` – per-run statistics (finish time, tree metrics, bounds events).
- `results/final_results_summary.csv` – wide table suitable for publication.
- `results/analysis/figures/*.png` – time-series plots (value, frontier size, lower bounds, families evaluated).
- `results/plots/Final_Value_vs_Size_Scatter.png` and `Final_Value_vs_Depth_Scatter.png` – cross-algorithm scatter plots.

Update `results/analysis/priority_queue_benchmark.md` with highlights drawn from these outputs before sharing results.

### Stress Test (Depth-7) Reproduction

To run the 1-hour “Stress Test” on csma-3-4 and consensus-4-2 with a fixed depth-7 target and generate the paper-style plots/tables:

1) Launch all runs (Docker required). This executes the 5 configurations:
  - original (DFS)
  - modified value_only (BFS)
  - modified value_size with α ∈ {0.01, 0.1, 0.5}

  Optional environment overrides: `TIMEOUT` (default 3600), `TREE_DEPTH` (default 7).

  ```bash
  bash scripts/run_stress_test.sh
  ```

2) Produce the report artefacts (anytime plots, tables, combined scatter, strategy analysis):

  ```bash
  python3 scripts/plot_stress_test.py --logs-root results/logs --out-dir results/analysis/stress_test
  ```

Outputs are written under `results/analysis/stress_test/`:
- `anytime_csma-3-4_depth7.png`, `anytime_consensus-4-2_depth7.png`
- `table_final_csma-3-4.csv`, `table_final_consensus-4-2.csv`
- `value_vs_size_combined.png`
- `strategy_csma-3-4.png`

Notes:
- The runners forward `--add-dont-care-action` and `--tree-depth <k>` so all solvers race on the same depth-k problem.
- Progress logs include families evaluated and frontier size for the strategy plot.

## Automated Campaigns

- `./scripts/run_all_experiments.sh` builds images on demand, launches all solver variants in parallel, migrates any legacy `logs/logs` layout, and regenerates the analysis artefacts.
- `./scripts/run_all_large_benchmarks.sh` targets deeper search trees by default (`csma-3-4-depth3`, `maze-concise`, and `grid-hard`) while delegating to the same orchestrator. Override `BENCHMARK_ARGS`, `TIMEOUT`, or `HEURISTIC_ALPHA` in the environment to tune the workload.
- Set `PROGRESS_INTERVAL` (seconds) if you want coarser progress logging from the runners.

## Tests

- `./run_tests_docker.sh` runs the priority-search comparison tests inside Docker.
- `./run_simple_test_docker.sh` executes a single benchmark smoke test.
- `cd synthesis-modified && pytest tests/test_priority_search_comparison.py -v -s` verifies the heuristics locally once dependencies are installed.

## Workflow Checklist

- Build both Docker images and ensure the host `results/` directory is writable.
- Execute benchmarks for the original solver and each heuristic variant (value_only, value_size, bounds_gap).
- Run `process_results.py` to regenerate CSVs and plots after each campaign.
- Populate the summary tables in `results/analysis/priority_queue_benchmark.md` with fresh numbers.
- Amend `BENCHMARKS.md` and the README if new presets or workflows are introduced.

## Latest results

- Final capped 10-way parallel run (depth 4): see `results/final_capped_run/FINAL_REPORT.md` for the integrated report with all required plots and tables.