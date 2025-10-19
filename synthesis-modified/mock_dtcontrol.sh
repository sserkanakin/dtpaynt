#!/bin/bash

# Mock dtcontrol script for testing the symbiotic synthesis
# This script generates a simple pre-defined .dot file

# Extract output path from arguments
OUTPUT_PATH="$1"

# Create a simple decision tree in .dot format
cat > "$OUTPUT_PATH" << 'EOF'
digraph DecisionTree {
    node [shape=box];
    rankdir=TB;
    
    0 [label="x > 5"];
    1 [label="y > 3"];
    2 [label="z > 1"];
    3 [label="Action: a0", shape=ellipse];
    4 [label="Action: a1", shape=ellipse];
    5 [label="Action: a2", shape=ellipse];
    6 [label="Action: a3", shape=ellipse];
    
    0 -> 1 [label="yes"];
    0 -> 2 [label="no"];
    1 -> 3 [label="yes"];
    1 -> 4 [label="no"];
    2 -> 5 [label="yes"];
    2 -> 6 [label="no"];
}
EOF

echo "Mock dtcontrol generated tree at $OUTPUT_PATH"
