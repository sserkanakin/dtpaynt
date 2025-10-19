# dtcontrol Integration in Symbiotic Synthesis

## Overview

The symbiotic synthesis workflow now ensures that **dtcontrol is actually called and its results are used** in all synthesis runs.

## Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Compute Optimal Policy                                       │
│    ├─ For basic MDPs: Direct model checking                     │
│    └─ For family-based MDPs: AR synthesis first                 │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Call dtcontrol via DtcontrolWrapper                          │
│    ├─ Pass optimal scheduler/policy to dtcontrol               │
│    ├─ dtcontrol generates decision tree                         │
│    └─ Returns JSON with tree structure and metrics             │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Parse dtcontrol Output                                       │
│    ├─ Read JSON tree from dtcontrol                            │
│    ├─ Convert to internal DecisionTreeNode representation      │
│    └─ Extract tree statistics (nodes, leaves, depth)           │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. Iterative Refinement (Symbiotic Loop)                        │
│    ├─ Select subtrees for optimization                          │
│    ├─ Optimize using DTPAYNT (policy_tree synthesis)           │
│    ├─ Compare with current tree                                 │
│    └─ Replace if improvement found                              │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. Export Final Decision Tree                                   │
│    ├─ Save as JSON                                              │
│    ├─ Save as DOT file                                          │
│    └─ Generate PNG visualization                                │
└─────────────────────────────────────────────────────────────────┘
```

## Code Flow

### Step 1: Initialization

```python
# In SynthesizerSymbiotic.__init__():
self.dtcontrol = DtcontrolWrapper(dtcontrol_path="dtcontrol", timeout=symbiotic_timeout)
```

### Step 2: Compute Optimal Policy

**For basic MDPs** (like traffic_intersection):
```python
# Direct model checking
mdp = self.quotient.mdp
result = mdp.check_specification(self.quotient.specification)
scheduler = result.scheduler  # Extract optimal scheduler
```

**For family-based MDPs**:
```python
# First run AR to get assignment
ar_synthesizer = SynthesizerAR(self.quotient)
ar_result = ar_synthesizer.run()
assignment = ar_synthesizer.best_assignment

# Build MDP for assignment
mdp = self.quotient.build_assignment(assignment)
result = mdp.check_specification(self.quotient.specification)
scheduler = result.scheduler
```

### Step 3: Call dtcontrol

```python
# In _generate_initial_tree():
policy = self._compute_optimal_policy()  # Get scheduler

# Call dtcontrol via wrapper
result = self.dtcontrol.generate_tree_from_scheduler(policy, preset="default")

# Check success
if result.success:
    tree_data = result.tree_data  # JSON tree structure
    stats = result.get_tree_stats()  # Get statistics
```

### Step 4: Parse dtcontrol Output

```python
# In _parse_dot_file():
with open(tree_file_path, 'r') as f:
    tree_data = json.load(f)  # Load JSON from dtcontrol

# Convert to internal representation
root = self._json_to_tree(tree_data)  # Recursive conversion

# Tree now ready for optimization/export
initial_tree_size = root.num_nodes()
initial_tree_leaves = root.num_leaves()
```

### Step 5: Tree Statistics

```python
# From dtcontrol result:
stats = {
    'total_nodes': result.get_tree_stats()['total_nodes'],
    'leaf_nodes': result.get_tree_stats()['leaf_nodes'],
    'max_depth': result.get_tree_stats()['max_depth'],
    'raw_size_bytes': result.get_tree_stats()['raw_size_bytes']
}
```

## Log Evidence

When running symbiotic synthesis, you should see:

```
2025-10-19 21:01:04,541 - synthesizer_symbiotic.py:103 - Starting symbiotic synthesis loop
2025-10-19 21:01:04,104 - synthesizer_symbiotic.py:XXX - Step 1: Generating initial decision tree using dtcontrol...
2025-10-19 21:01:04,XXX - synthesizer_symbiotic.py:XXX - Computing optimal policy...
2025-10-19 21:01:04,XXX - synthesizer_symbiotic.py:XXX - [dtcontrol call #1] Generating tree from policy...
2025-10-19 21:01:04,XXX - dtcontrol_wrapper.py:XXX - ✓ dtcontrol generated tree at: /tmp/dtcontrol_XXXXX/decision_trees/default/scheduler/default.json
2025-10-19 21:01:04,XXX - dtcontrol_wrapper.py:XXX - ✓ Tree validation passed. Stats: {'total_nodes': ..., 'leaf_nodes': ..., 'max_depth': ...}
2025-10-19 21:01:04,XXX - synthesizer_symbiotic.py:XXX - [dtcontrol success #1] Tree stats: {...}
2025-10-19 21:01:04,XXX - synthesizer_symbiotic.py:XXX - Initial tree size: 12 nodes (5 leaves)
```

## DtcontrolWrapper Interface

The wrapper (`dtcontrol_wrapper.py`) handles:

1. **Binary Verification**: Confirms dtcontrol is installed
2. **Scheduler File Writing**: Converts Python scheduler to JSON
3. **Process Execution**: Runs dtcontrol with proper arguments
4. **Result Validation**: Verifies output structure
5. **Error Handling**: Comprehensive error messages
6. **Tree Statistics**: Extracts metrics from tree

### Key Methods

```python
# Verify dtcontrol binary is available
wrapper.verify_binary()  # Returns True if OK

# Generate tree from scheduler
result = wrapper.generate_tree_from_scheduler(scheduler, preset="default")

# Get tree statistics
stats = result.get_tree_stats()
# Returns: {'total_nodes': N, 'leaf_nodes': L, 'max_depth': D, 'raw_size_bytes': B}

# Compare different presets
results = wrapper.compare_presets(scheduler)
best = wrapper.get_best_preset(results, metric="total_nodes")
```

## What dtcontrol Does

dtcontrol converts a **tabular policy/scheduler** (mapping from states to actions) into a **decision tree** by:

1. Taking the optimal scheduler (output of AR synthesis or model checking)
2. Extracting decision rules that guide this scheduler
3. Organizing these rules into a tree structure
4. Minimizing tree complexity using various heuristics (gini, entropy, etc.)

**Result**: A human-readable decision tree that can be executed instead of storing the full scheduler table.

## For Basic MDPs

Even for basic MDPs like `traffic_intersection`:

1. ✅ Model checking extracts the optimal scheduler
2. ✅ dtcontrol converts scheduler to decision tree
3. ✅ Tree is used as starting point for refinement (if needed)
4. ✅ Final tree is exported with correct format

The symbiotic loop still runs but may find that the initial tree from dtcontrol is already optimal for basic MDPs (which is expected).

## Verification

To verify dtcontrol is being used:

1. Check log for `[dtcontrol call #N]` messages
2. Check for `✓ dtcontrol generated tree` success message
3. Check for tree statistics in log
4. Verify output files (tree.json, tree.dot, tree.png) are created

Example:
```bash
# Look for dtcontrol in logs
grep -i "dtcontrol" /path/to/stdout.txt | head -20

# Check output files
ls -lh ./results/logs/paynt-cav-final/symbiotic/*/tree.*
```

## Configuration Parameters

From `experiments-with-symbiotic.sh`:

```bash
--method symbiotic \
--symbiotic-iterations 5 \          # Refinement iterations
--symbiotic-subtree-depth 3 \       # Depth of subtrees to optimize
--symbiotic-timeout 60              # Timeout per iteration (seconds)
```

These are passed to SynthesizerSymbiotic which configures dtcontrol and the refinement loop.
