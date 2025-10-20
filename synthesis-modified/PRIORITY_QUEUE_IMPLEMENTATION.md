# Priority Queue Implementation - Quick Reference

## Overview
This document provides a quick reference for the heuristic-guided priority queue search implementation in DTPAYNT.

## Files Changed

### 1. `paynt/synthesizer/synthesizer_ar.py`
**What changed:** Replaced stack-based search with priority queue
**Key changes:**
- Added `import heapq`
- Modified `synthesize_one()` method to use `heapq.heappush()` and `heapq.heappop()`
- Priority = `-family.analysis_result.improving_value` (negated for max-heap)
- Added iteration counter and enhanced logging

### 2. `tests/test_priority_search_comparison.py`
**What it does:** Compares original vs. modified synthesizer performance
**Features:**
- Imports both synthesizers from parallel directories
- Creates benchmark MDP models programmatically
- Measures time, value, tree size, iterations
- Prints formatted comparison tables
- Validates correctness with assertions

### 3. `README.md`
**What changed:** Added "Comparing Search Strategies" section
**Content:**
- Explains priority queue modification
- Provides test command
- Shows sample log output
- Describes expected benefits

## Running Tests

### Docker (Recommended)
```bash
cd /Users/serkan/Projects/FML/dtpaynt
./run_tests_docker.sh
```

### Local
```bash
cd /Users/serkan/Projects/FML/dtpaynt/synthesis-modified
pytest tests/test_priority_search_comparison.py -v -s
```

## Docker Compatibility

No changes needed! The `heapq` module is part of Python's standard library.

```bash
docker build -t dtpaynt-better-value .
```

## Key Algorithm Details

**Priority Assignment:**
```python
if family.analysis_result.improving_value is not None:
    priority = -family.analysis_result.improving_value  # Negate for max-heap
else:
    priority = 0  # Default for initial/unknown families
```

**Heap Structure:**
```python
# (priority, counter, family)
# - priority: negated improving_value (lower = better)
# - counter: ensures FIFO for equal priorities
# - family: the actual family object
heapq.heappush(families, (priority, counter, family))
```

## Log Output Pattern

```
[Priority-Queue Search] Iteration 0, Processing family with priority 0
[Priority-Queue Search] Iteration 1, Processing family with priority -0.85
[Priority-Queue Search] Iteration 2, Processing family with priority -0.92
[Priority-Queue Search] Iteration 3, Processing family with priority -0.95
```

Higher absolute priority values (more negative) = better/higher optimal values = processed first

## Expected Benefits

1. **Faster Convergence:** Explores high-value families first
2. **Better Anytime Performance:** Finds good solutions quickly under time constraints
3. **Efficient Search:** Reduces wasted effort on low-value branches

## Validation

The test suite ensures:
- Modified algorithm finds solutions with value ≥ original algorithm
- Both algorithms explore the same search space
- Priority queue ordering is correct
- Performance metrics are captured accurately
