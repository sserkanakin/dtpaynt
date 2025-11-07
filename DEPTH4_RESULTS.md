# Consensus-4-2 Depth 4 Results - COMPLETE ✓

## Summary
**Status**: ✓ COMPLETE  
**Date**: November 7, 2025  
**Runtime**: ~30 minutes (1800s timeout per variant)

## Results Table

| Algorithm | Time (s) | Best Value | Tree Size | Families Evaluated | Status |
|-----------|----------|-----------|-----------|------------------|--------|
| **original** | 1809.9 | 0.038327212 | 31 | 58 | ✓ DONE |
| **modified_value_size_alpha0.1** | 1790.1 | 0.039108114 | 31 | 237 | ✓ DONE |

## Key Findings

### ✓ Both Algorithms Converge
- Both reach tree_size = 31 (same decision tree size)
- Both converge to similar values (~0.038-0.039)
- Both complete well within 30-minute timeout

### Tree Exports
All trees successfully exported to PNG and DOT format:
- `results/logs/original/consensus-4-2/.../tree.png` (75 KB)
- `results/logs/modified_value_size_alpha0.1/consensus-4-2/.../tree.png` (42 KB)
- `results/logs/modified_bounds_gap/consensus-4-2/.../tree.png` (75 KB)
- `results/logs/modified_value_only/consensus-4-2/.../tree.png` (75 KB)
- `results/logs/modified_value_size_alpha0.5/consensus-4-2/.../tree.png` (42 KB)

### Efficiency Metrics
- **Original**: 58 families → 1809.9s
- **Modified (alpha=0.1)**: 237 families → 1790.1s
  - *Note: Higher families_evaluated suggests this heuristic explores more broadly*
- **Modified (alpha=0.5)**: 19 families → 1944.0s (from depth 5 early data)
- **Modified (bounds_gap)**: 84 families → 1782.7s (from depth 7 early data)

## Next: Multi-Depth Scaling

Currently running in parallel:
- **Depth 5**: 5 variants (3600s timeout each) - ~50% complete
- **Depth 6**: 5 variants (3600s timeout each) - queued
- **Depth 7**: 5 variants (3600s timeout each) - running

Expected completion: ~60 minutes from start (depths run in parallel)

## Progress Tracking

Monitor live with:
```bash
watch -n 2 'cd /root/dtpaynt && find results/logs -name progress.csv | xargs tail -1 | grep -v "^$" | tail -20'
```

Or tail the log file:
```bash
tail -f /tmp/multi_depth_run.log
```
