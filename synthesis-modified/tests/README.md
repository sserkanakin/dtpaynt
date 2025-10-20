# Test Suite for Priority Queue vs Stack-based Search

This directory contains comprehensive tests comparing the priority queue implementation against the original stack-based DFS in DTPAYNT.

## Test Files

### 1. `test_simple_priority_search.py`
**Purpose**: Basic functionality validation

- **Model**: `models/dtmc/dice/5` (9 holes, 125k family size)
- **Validates**: 
  - Priority queue implementation runs without crashes
  - GlobalTimer properly initialized
  - Synthesis explores design space correctly
- **Run**: `../run_simple_test_docker.sh`

### 2. `test_comprehensive_comparison.py` ⭐ **RECOMMENDED**
**Purpose**: Comprehensive comparison suite with strategic test cases

#### Test 1: Basic Coin Model
- **Model**: `models/dtmc/coin/` (6 holes)
- **Property**: Multi-objective (minimize steps, satisfy P>=0.49 for heads/tails)
- **Purpose**: Validate both algorithms find solutions
- **Expected**: Both succeed with similar performance

#### Test 2: Maze Model - Priority Queue Advantage
- **Model**: `models/dtmc/maze/concise/` (24 holes)
- **Property**: Optimization (R{"steps"}min=? [F goal])
- **Purpose**: Show priority queue advantage on optimization problems
- **Expected**: Priority queue finds optimal faster (best-first search excels)
- **Why**: Heuristic guides search toward better solutions

#### Test 3: Grid Model - Satisfiability
- **Model**: `models/dtmc/grid/grid/` with `easy.props`
- **Property**: Reachability (P>=0.928 [F "goal" & c<CMAX])
- **Purpose**: Validate both correctly determine satisfiability
- **Expected**: Both agree on whether solution exists

**Run**: `../run_comprehensive_tests.sh`

### 3. `test_priority_search_comparison_docker.py`
**Purpose**: Original comparison test (kept for backwards compatibility)

- **Models**: Grid models (both variations)
- **Note**: Some specifications may be unsatisfiable
- **Status**: Use comprehensive test suite instead
- **Run**: `../run_tests_docker.sh`

## Running Tests

### Quick Start (Recommended)
```bash
cd /Users/serkan/Projects/FML
./dtpaynt/run_comprehensive_tests.sh
```

This runs all three strategic tests and provides a summary.

### Individual Tests
```bash
# Simple functionality test
./dtpaynt/run_simple_test_docker.sh

# Specific comprehensive test
docker run --platform linux/amd64 --rm dtpaynt-test \
    pytest -v -s /opt/synthesis-modified/tests/test_comprehensive_comparison.py::test_basic_coin_model
```

## Expected Output

### Successful Test Run
```
================================================================================
TEST 1: Basic Coin Model (6 holes)
================================================================================
Expected: Both find solution, similar performance

[1/2] Running ORIGINAL (Stack-based DFS)...
[2/2] Running MODIFIED (Priority Queue)...

--------------------------------------------------------------------------------
RESULTS:
--------------------------------------------------------------------------------
Method               Time (s)     Solution   Value           Iterations
--------------------------------------------------------------------------------
Original (Stack)     0.05         True       3.5             250
Modified (PQueue)    0.04         True       3.5             250
--------------------------------------------------------------------------------
✅ TEST 1 PASSED: Both algorithms found solutions
```

### Performance Comparison
Look for these key metrics:
- **Time**: Which is faster?
- **Iterations**: Which explores fewer families?
- **Value**: Do both find the same optimal value?

For optimization problems (Test 2), expect:
- Priority queue may find optimal faster
- Fewer iterations to reach optimum
- Same final optimal value

## Understanding Results

### When Priority Queue Excels
- **Optimization problems**: Best-first search finds optimal faster
- **Shallow optimal solutions**: Heuristic guides directly to goal
- **Large search spaces**: Better pruning with value estimates

### When Stack DFS Excels  
- **Satisfiability only**: When any solution works, DFS is simple
- **Deep-first solutions**: When solutions are at leaves
- **Small search spaces**: Overhead not worth it

### Both Should Agree On
- **Satisfiability**: Same answer on whether solution exists
- **Optimal values**: Same final value for optimization problems
- **Correctness**: All specifications satisfied

## Troubleshooting

### "No solution found" for all tests
- Check if models/properties are correct
- Verify specifications are satisfiable
- Try simpler models first

### Different values found
- Check for bugs in implementation
- Verify both use same property file
- Compare exploration strategies

### Crashes or errors
- Check GlobalTimer initialization
- Verify module isolation
- Check Docker build succeeded

## Test Design Philosophy

Tests are designed to:
1. ✅ **Validate correctness** - Both find solutions when they exist
2. 📊 **Compare performance** - Show when each excels
3. 🎯 **Strategic selection** - Models with known solutions
4. 📈 **Clear metrics** - Time, iterations, values

Each test has:
- Clear expected behavior
- Known solvable models
- Specific performance characteristics
- Validation assertions

## Adding New Tests

To add a new test:

1. Choose a model with known solution
2. Identify what characteristic you're testing
3. Add test function to `test_comprehensive_comparison.py`
4. Document expected behavior
5. Add assertions for correctness

Example:
```python
def test_new_model():
    """
    Test: Description
    - Model characteristics
    - Expected behavior
    - What this validates
    """
    # Implementation
```

## Files Modified

All tests use these implementations:
- `synthesis-modified/paynt/synthesizer/synthesizer_ar.py` - Priority queue
- `synthesis-original/paynt/synthesizer/synthesizer_ar.py` - Stack DFS

Both have GlobalTimer fixes applied.
