# Results Directory Structure Explained

## Overview
Your results are organized in a **4-level hierarchy** designed to keep all variants, benchmarks, and runs organized:

```
results/
├── logs/                              ← All run logs and data
│   ├── original/
│   ├── modified_bounds_gap/
│   ├── modified_value_only/
│   └── modified_value_size_alpha{0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99}/
│       └── consensus-4-2/            ← Benchmark name
│           └── consensus-4-2-{TIMESTAMP}/
│               ├── progress.csv      ← **MAIN DATA FILE** (time series)
│               ├── stdout.txt        ← PAYNT logs
│               ├── run-info.json     ← Run metadata (depth, timeout, etc)
│               ├── tree.png          ← Decision tree visualization
│               ├── tree.dot          ← Decision tree in GraphViz format
│               └── tree/             ← Tree data files
└── analysis/                          ← Generated analysis plots
    └── consensus-4-2_depth{4,5,6,7}/
        ├── value_vs_time.png
        ├── tree_size_vs_time.png
        └── families_evaluated_vs_time.png
```

## Directory Levels Explained

### Level 1: Algorithm Variant
```
results/logs/
├── original                          ← DFS-based synthesis
├── modified_bounds_gap               ← Best-first + bounds gap heuristic
├── modified_value_only               ← Best-first + greedy value heuristic
└── modified_value_size_alpha{...}    ← Best-first + size-penalized heuristic
    └── 7 different alpha parameters
```

**Why**: To compare different algorithms/heuristics side-by-side

### Level 2: Benchmark Name
```
results/logs/modified_value_size_alpha0.5/
└── consensus-4-2/                   ← The model being synthesized
    └── Other benchmarks can go here (csma-3-4, etc)
```

**Why**: To support running multiple models. Currently only `consensus-4-2`

### Level 3: Run ID (Timestamp)
```
results/logs/modified_value_size_alpha0.5/consensus-4-2/
├── consensus-4-2-20251107-135113/   ← Depth 4 run
├── consensus-4-2-20251107-135114/   ← Depth 5 run
├── consensus-4-2-20251107-135115/   ← Depth 6 run
└── consensus-4-2-20251107-135116/   ← Depth 7 run
```

**Why**: Each depth is a separate run with unique timestamp. Multiple runs can exist per algorithm/benchmark.

### Level 4: Output Files (In Each Run Directory)

#### Critical Files:
| File | Purpose | Format |
|------|---------|--------|
| `progress.csv` | **Main data** - time series of convergence | CSV (timestamp, value, tree_size, etc) |
| `run-info.json` | Metadata - what parameters were used | JSON |
| `tree.png` | Decision tree visualization | PNG image |

#### Supporting Files:
| File | Purpose | Format |
|------|---------|--------|
| `stdout.txt` | Raw PAYNT output/logs | Text |
| `tree.dot` | Decision tree in GraphViz format | DOT (can render with Graphviz) |
| `tree/` folder | Additional tree export files | Various |

---

## Current Run Structure (40 variants)

### Timestamps Encoded in Run ID:
- `...135113` → Depth 4 (first to start)
- `...135114` → Depth 5 (started after depth 4)
- `...135115` → Depth 6 (started after depth 5)
- `...135116` → Depth 7 (started in parallel with others)

### Algorithm × Alpha Combinations:
```
10 Variants per depth × 4 depths = 40 total runs

Variants (per depth):
1. original
2. modified_value_only
3. modified_value_size_alpha0.01
4. modified_value_size_alpha0.1
5. modified_value_size_alpha0.25
6. modified_value_size_alpha0.5
7. modified_value_size_alpha0.75
8. modified_value_size_alpha0.9
9. modified_value_size_alpha0.99
10. modified_bounds_gap
```

---

## How to Use This Structure

### 1. Find a Specific Run
```bash
# Find all depth-4 runs
find results/logs -path "*135113*" -name progress.csv

# Find all value_size runs
find results/logs/modified_value_size_alpha* -name progress.csv

# Find all runs for a specific alpha
find results/logs/modified_value_size_alpha0.5 -name progress.csv
```

### 2. View Run Metadata
```bash
# See what parameters were used in a run
cat results/logs/modified_value_size_alpha0.5/consensus-4-2/consensus-4-2-20251107-135115/run-info.json

# Output shows:
# - heuristic: "value_size"
# - heuristic_alpha: 0.5
# - timeout: 3600
# - extra_args: ["--tree-depth", "5", ...]
```

### 3. Extract Results
```bash
# See convergence data for a run
head results/logs/original/consensus-4-2/consensus-4-2-20251107-135113/progress.csv

# Output columns: timestamp, best_value, tree_size, depth_reached, families_evaluated, ...
```

### 4. View Trees
```bash
# Open a decision tree visualization
open results/logs/modified_value_size_alpha0.5/consensus-4-2/consensus-4-2-20251107-135115/tree.png

# Or view the DOT file
cat results/logs/.../tree.dot  # Can be rendered with Graphviz
```

---

## Analysis Output Structure

Once runs complete, analysis plots are generated in:
```
results/analysis/
├── consensus-4-2_depth4/
│   ├── value_vs_time.png           ← All 10 variants on one plot
│   ├── tree_size_vs_time.png
│   └── families_evaluated_vs_time.png
├── consensus-4-2_depth5/
├── consensus-4-2_depth6/
└── consensus-4-2_depth7/
```

**Why**: Separate plots per depth allows easy comparison of algorithm performance at each complexity level.

---

## Key Insights from Structure

✓ **Modular**: Variants isolated from each other  
✓ **Traceable**: Every run has timestamp and metadata  
✓ **Scalable**: Easy to add new benchmarks or depths  
✓ **Comparable**: Same structure for all variants makes diff analysis simple  
✓ **Complete**: Trees + progress data + metadata in one place per run  

---

## Quick Command Reference

```bash
# Count total runs
find results/logs -name progress.csv | wc -l

# List all algorithms
ls -1 results/logs | grep -v "^analysis"

# Check which runs completed (have non-empty best_value)
for csv in $(find results/logs -name progress.csv); do 
  val=$(tail -1 "$csv" | cut -d',' -f2)
  [ -n "$val" ] && echo "DONE: $csv"
done

# Extract summary for all runs
python3 << 'EOF'
import json
from pathlib import Path

for info_file in sorted(Path("results/logs").rglob("run-info.json")):
    with open(info_file) as f:
        info = json.load(f)
    algo = info["algorithm_version"]
    depth = info["extra_args"][info["extra_args"].index("--tree-depth") + 1]
    timeout = info["timeout"]
    print(f"  {algo:40s} | Depth {depth} | {timeout}s timeout")
EOF
```
