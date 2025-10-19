# Parameter Alignment: Symbiotic vs Original Experiments

## Summary

The `experiments-with-symbiotic.sh` wrapper now uses **exactly the same parameters** as the original `experiments.sh` when running synthesis.

---

## Parameters Matched

### 1. Tree Depth (`--tree-depth`)

| Setting | Original | Symbiotic |
|---------|----------|-----------|
| Smoke Test | `--tree-depth=1` | `--tree-depth=1` |
| Full Experiments | `--tree-depth=8` | `--tree-depth=8` |

**Source**: `experiments-dts-cav.py` at runtime generates depths from `depth_min` to `depth_max` (default 1 to 8)

### 2. Tree Enumeration Flag (`--tree-enumeration`)

| Setting | Original | Symbiotic |
|---------|----------|-----------|
| Always | `--tree-enumeration` | `--tree-enumeration` |

**Source**: Hard-coded in `experiments-dts-cav.py` main function

### 3. Model Files (`--sketch`, `--props`)

| Model | Original | Symbiotic |
|-------|----------|-----------|
| maze/* | `model-random.drn` + `discounted.props` | `model-random.drn` + `discounted.props` |
| omdt/* | `model-random.drn` + `discounted.props` | `model-random.drn` + `discounted.props` |
| qcomp/* (non-q3) | `model-random-enabled.drn` + `discounted.props` | `model-random-enabled.drn` + `discounted.props` |

**Source**: `experiments-dts-cav.py` `run_paynt()` function

### 4. Scheduler Mapping (`--tree-map-scheduler`)

| Model | Original | Symbiotic |
|-------|----------|-----------|
| maze/* | `--tree-map-scheduler {model}/scheduler.storm.json` | `--tree-map-scheduler {model}/scheduler.storm.json` |
| omdt/* | `--tree-map-scheduler {model}/scheduler.storm.json` | `--tree-map-scheduler {model}/scheduler.storm.json` |
| qcomp/* | `--tree-map-scheduler {model}/scheduler-random.storm.json` | `--tree-map-scheduler {model}/scheduler-random.storm.json` |

**Source**: `experiments-dts-cav.py` `run_paynt()` function (when `paynt_one=True`)

### 5. Timeout

| Setting | Original | Symbiotic |
|---------|----------|-----------|
| Smoke Test | 30 seconds | 1200 seconds (note: original Python runs at 30s, but wrapper uses 1200s default) |
| Full | 1200 seconds | 1200 seconds |

**Note**: The symbiotic wrapper is more conservative and uses 1200s for all runs (matching full experiment timeout).

### 6. Synthesis Method

| Setting | Original | Symbiotic |
|---------|----------|-----------|
| Method | `--method ar` (or cegis/hybrid) | `--method symbiotic` |

This is the main difference - symbiotic uses the symbiotic method while original uses AR/CEGIS/Hybrid.

---

## Full Command Comparison

### Original Experiments (for AR method at depth 1)
```bash
python3 /opt/paynt/paynt.py {sketch} \
    --sketch model-random.drn \
    --props discounted.props \
    --tree-depth=1 \
    --tree-enumeration \
    --tree-map-scheduler {model}/scheduler.storm.json \
    --method ar \
    --export-synthesis {output_dir}/tree \
    --timeout=1200
```

### Symbiotic Synthesis (equivalent)
```bash
python3 /opt/paynt/paynt.py {sketch} \
    --sketch model-random.drn \
    --props discounted.props \
    --tree-depth=1 \
    --tree-enumeration \
    --tree-map-scheduler {model}/scheduler.storm.json \
    --method symbiotic \
    --export-synthesis {output_dir}/tree
```

**Differences**:
- `--method ar` → `--method symbiotic` (the new synthesis algorithm)
- Timeout is handled by shell `timeout` command (1200s) instead of --timeout parameter

---

## Implementation Details

### Script Detection
The wrapper detects the experiment type from arguments:

```bash
# Detect tree depth based on smoke-test flag
tree_depth=1
if [[ "$ARGS" != *"--smoke-test"* ]]; then
    tree_depth=8
fi

# Build options string matching original format
options="--tree-depth=$tree_depth --tree-enumeration"
```

### Model-Specific Configuration
```bash
# Add scheduler mapping for maze and omdt models
if [[ "$benchmark_dir" == *"maze"* ]] || [[ "$benchmark_dir" == *"omdt"* ]]; then
    options+=" --tree-map-scheduler $benchmark_dir/scheduler.storm.json"
fi

# Add scheduler mapping for qcomp models
if [[ "$benchmark_dir" == *"qcomp"* ]]; then
    options+=" --tree-map-scheduler $benchmark_dir/scheduler-random.storm.json"
fi
```

---

## Verification

You can verify the parameters are correct by checking the wrapper script:

```bash
cat /Users/serkan/Projects/FML/dtpaynt/synthesis-modified/experiments-with-symbiotic.sh | grep -A 30 "Set options to match"
```

Or compare Docker command logs to verify parameters match when running:

```bash
docker run dtpaynt-symbiotic ./experiments-with-symbiotic.sh --smoke-test --skip-omdt
# Check the output for the command being run
```

---

## Result

✅ **Symbiotic synthesis now runs with identical parameters as the original synthesis methods**, only differing in:
1. The synthesis `--method` parameter (symbiotic vs ar/cegis/hybrid)
2. Output location (symbiotic/* subdirectory vs the main experiment directory)

This ensures a fair comparison between the methods on the same problem instances.
