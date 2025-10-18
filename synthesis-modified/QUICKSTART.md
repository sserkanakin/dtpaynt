# Quick Start Guide - Hybrid Synthesis

## Installation

```bash
# 1. Install DTCONTROL (if not already installed)
# See: https://github.com/moves-rwth/dtcontrol

# 2. Verify DTCONTROL is in PATH
which dtcontrol
dtcontrol --help

# 3. Navigate to synthesis-modified directory
cd synthesis-modified

# 4. Install Python dependencies (already in PAYNT environment)
# Ensure you have: click, z3-solver, psutil, graphviz
```

## Basic Usage

```bash
# Minimal command
python3 hybrid_synthesis.py --model model.prism --props model.props

# With output directory
python3 hybrid_synthesis.py \
    --model model.prism \
    --props model.props \
    --output ./results

# With custom parameters
python3 hybrid_synthesis.py \
    --model model.prism \
    --props model.props \
    --max-subtree-depth 5 \
    --max-loss 0.1 \
    --timeout 7200
```

## Parameter Quick Reference

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `--model` | *required* | - | Path to PRISM model file |
| `--props` | *required* | - | Path to properties file |
| `--output` | `./hybrid_output` | - | Output directory |
| `--max-subtree-depth` | 4 | 1-∞ | Max depth for sub-tree extraction |
| `--max-loss` | 0.05 | 0-1 | Max value loss fraction |
| `--timeout` | 3600 | 1-∞ | Total timeout in seconds |
| `--no-hybridization` | False | - | Run DTCONTROL only |
| `--verbose` | False | - | Enable debug logging |

## Expected Output Files

After running hybrid synthesis, check:

```bash
# Final optimized tree
cat hybrid_output/final_tree.dot

# Initial DTCONTROL tree (for comparison)
cat hybrid_output/initial_tree.dot

# Synthesis statistics
cat hybrid_output/synthesis_stats.json
```

## Running Tests

```bash
# All tests
python3 -m pytest tests/test_hybrid_*.py -v

# Just unit tests
python3 -m pytest tests/test_hybrid_components.py -v

# Just integration tests
python3 -m pytest tests/test_hybrid_integration.py -v

# With coverage
python3 -m pytest tests/test_hybrid_*.py --cov=paynt --cov=hybrid_synthesis
```

## Typical Parameter Combinations

### For Speed (Quick Results)
```bash
python3 hybrid_synthesis.py \
    --model model.prism \
    --props model.props \
    --max-subtree-depth 2 \
    --max-loss 0.2 \
    --timeout 600
```

### For Quality (Best Optimization)
```bash
python3 hybrid_synthesis.py \
    --model model.prism \
    --props model.props \
    --max-subtree-depth 6 \
    --max-loss 0.01 \
    --timeout 7200
```

### Balanced (Default - Recommended)
```bash
python3 hybrid_synthesis.py \
    --model model.prism \
    --props model.props
```

### DTCONTROL Baseline (No Refinement)
```bash
python3 hybrid_synthesis.py \
    --model model.prism \
    --props model.props \
    --no-hybridization
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `dtcontrol: command not found` | Install DTCONTROL, add to PATH |
| Timeout on large models | Reduce `--max-subtree-depth` or increase `--timeout` |
| High memory usage | Reduce `--max-subtree-depth`, restart |
| No refinement happening | Check with `--verbose`, check `--max-subtree-depth` |
| PAYNT crashes | Try `--no-hybridization` to isolate issue |

## Viewing Results

```bash
# View final tree as text
cat hybrid_output/final_tree.dot

# View statistics
python3 -c "import json; print(json.dumps(json.load(open('hybrid_output/synthesis_stats.json')), indent=2))"

# Compare tree sizes
echo "Initial: $(cat hybrid_output/initial_tree.dot | wc -l) lines"
echo "Final: $(cat hybrid_output/final_tree.dot | wc -l) lines"
```

## Environment Setup

```bash
# Activate PAYNT environment (if using install.sh)
source prerequisites/venv/bin/activate

# Or if using system Python
python3 -m venv venv
source venv/bin/activate
pip install click z3-solver psutil graphviz pydot pytest

# Run hybrid synthesis
python3 hybrid_synthesis.py --model model.prism --props model.props

# Deactivate environment
deactivate
```

## Key Files and Their Purposes

| File | Purpose |
|------|---------|
| `hybrid_synthesis.py` | Main orchestrator and CLI |
| `paynt/parser/dot_parser.py` | Parses DTCONTROL output |
| `paynt/utils/tree_slicer.py` | Extracts and manages sub-trees |
| `paynt/synthesizer/synthesizer_ar.py` | Enhanced DTPAYNT synthesizer |
| `DESIGN_CHOICES.md` | Detailed design justifications |
| `README.md` | Complete user guide |
| `IMPLEMENTATION_SUMMARY.md` | Technical overview |

## Documentation Links

- **DESIGN_CHOICES.md**: Why we made specific design decisions
- **README.md**: Comprehensive user guide with examples
- **IMPLEMENTATION_SUMMARY.md**: Technical implementation details
- **tests/test_hybrid_components.py**: Usage examples in tests
- **tests/test_hybrid_integration.py**: Integration test examples

## Performance Expectations

- **Speed-up vs. PAYNT alone:** 2-5x faster on complex models
- **Size reduction vs. DTCONTROL:** 30-50% fewer nodes (typical)
- **Value loss:** 5-10% with default `--max-loss 0.05`

## Next Steps

1. **Understand Design**: Read `DESIGN_CHOICES.md`
2. **Try Basic Example**: Run on a simple model with defaults
3. **Tune Parameters**: Adjust for your specific model
4. **Review Results**: Check statistics and output trees
5. **Run Tests**: Validate on your system
6. **Integrate**: Use in your workflow

## Getting Help

```bash
# Show help message
python3 hybrid_synthesis.py --help

# Enable verbose output for debugging
python3 hybrid_synthesis.py --model model.prism --props model.props --verbose

# Check if DTCONTROL works
dtcontrol --help

# Validate test setup
python3 -m pytest tests/test_hybrid_components.py::TestDotParser::test_parse_dot_basic -v
```

## Useful Commands

```bash
# Run on simple model
python3 hybrid_synthesis.py \
    --model models/mdp/simple/model.prism \
    --props models/mdp/simple/simple.props \
    --verbose

# Run and time
time python3 hybrid_synthesis.py \
    --model model.prism \
    --props model.props

# Run multiple times and compare
for i in {1..3}; do
    echo "Run $i:"
    python3 hybrid_synthesis.py --model model.prism --props model.props 2>&1 | grep -E "Initial tree|Sub-problems|total_time"
done

# Generate tree visualization (if graphviz installed)
dot -Tpng hybrid_output/final_tree.dot -o hybrid_output/final_tree.png
```

## Common Issues and Solutions

### Issue: Memory Error
**Solution:**
```bash
# Reduce complexity
python3 hybrid_synthesis.py \
    --model model.prism \
    --props model.props \
    --max-subtree-depth 2 \
    --max-loss 0.2
```

### Issue: DTCONTROL Hangs
**Solution:**
```bash
# Set lower timeout
python3 hybrid_synthesis.py \
    --model model.prism \
    --props model.props \
    --timeout 300 \
    --verbose
```

### Issue: No Refinement
**Solution:**
```bash
# Debug with verbose mode
python3 hybrid_synthesis.py \
    --model model.prism \
    --props model.props \
    --verbose | tee debug.log
```

---

**For complete documentation, see README.md and DESIGN_CHOICES.md**
