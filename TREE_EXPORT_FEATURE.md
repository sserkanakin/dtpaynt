# Tree Export Feature for Symbiotic Synthesis

## Overview
The symbiotic synthesizer now exports decision trees to both **DOT (Graphviz)** and **PNG** formats, just like the original synthesizer.

## How It Works

### When Trees Are Exported
Trees are automatically exported when you use the `--export-synthesis` flag:

```bash
python3 paynt.py <benchmark> --sketch model.drn --props spec.props \
  --method symbiotic --export-synthesis /path/to/tree
```

### Output Files
For `--export-synthesis /path/to/tree`, you get:

1. **tree.dot** - Graphviz DOT format (text-based tree representation)
2. **tree.png** - PNG visualization (rendered from DOT using graphviz)

### Example Usage in Docker

```bash
docker run -v $(pwd)/results:/results dtpaynt-symbiotic bash -c \
  "cd /opt/cav25-experiments && \
   python3 /opt/paynt/paynt.py ./benchmarks/smoketest/omdt/system_administrator_tree \
   --sketch model-random.drn --props discounted.props \
   --method symbiotic --export-synthesis /results/tree"
```

This will create:
- `/results/tree.dot` (2.4 KB for system_administrator_tree)
- `/results/tree.png` (125 KB for system_administrator_tree)

## Implementation Details

### New Methods Added to SynthesizerSymbiotic

**`_export_trees()`**
- Called at the end of synthesis
- Checks if `export_synthesis_filename_base` is set
- Calls `_export_decision_tree()` if export is enabled

**`_export_decision_tree(decision_tree, export_filename_base)`**
- Converts PAYNT DecisionTree to graphviz format
- Exports DOT file (text format)
- Renders PNG file using graphviz
- Logs all export operations with `[EXPORT]` prefix

### Logging
All tree export operations are logged with `[EXPORT]` prefix:

```
[EXPORT] Exported decision tree to /tmp/test_export/tree.dot
[EXPORT] Exported decision tree visualization to /tmp/test_export/tree.png
```

## Testing Results

### Test 1: system_administrator_tree
- Tree: 12 decision nodes, depth 7
- DOT file: 2.4 KB
- PNG file: 125 KB
- Status: ✅ SUCCESS

### Test 2: 3d_navigation
- Tree: 68 decision nodes, depth 10
- DOT file: 11 KB
- PNG file: 330 KB
- Status: ✅ SUCCESS

## DOT File Format Example

The generated DOT files follow the standard graphviz format:

```dot
// decision tree
digraph {
    0 [label="computer_0_running<=0" shape=box style=rounded]
    0 -> 1 [label=T]
    0 -> 2 [label=F]
    1 [label="(reboot_computer_0)" shape=box style=rounded]
    2 [label="computer_2_running<=0" shape=box style=rounded]
    ...
}
```

Internal nodes show test conditions (e.g., `computer_0_running<=0`)
Leaf nodes show action assignments (e.g., `(reboot_computer_0)`)

## Viewing Trees

### View PNG Directly
Simply open the PNG file in any image viewer to see the tree visualization.

### View/Edit DOT File
```bash
cat tree.dot
```

### Regenerate PNG from DOT (if graphviz is installed)
```bash
dot -Tpng tree.dot -o tree.png
```

## Feature Comparison with Original Synthesizer

| Feature | Original | Symbiotic |
|---------|----------|-----------|
| DOT export | ✅ Yes | ✅ Yes |
| PNG export | ✅ Yes | ✅ Yes |
| Auto-export with flag | ✅ Yes | ✅ Yes |
| Graphviz integration | ✅ Yes | ✅ Yes |

The symbiotic synthesizer now provides **complete feature parity** with the original synthesizer for tree export functionality.
