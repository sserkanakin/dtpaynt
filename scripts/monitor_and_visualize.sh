#!/bin/bash
# Monitor depth 4 run and generate all visualizations once complete

RESULTS_DIR="/root/dtpaynt/results/depth4_final_20251106-140747"
LOGS_DIR="$RESULTS_DIR/logs"

echo "=== Monitoring Depth 4 Run ==="
echo "Results directory: $RESULTS_DIR"
echo ""

# Wait for all progress files to stop updating (experiments finished or timed out)
echo "Waiting for experiments to finish..."
while true; do
    # Check if any progress file was modified in last 60 seconds
    recent=$(find "$LOGS_DIR" -name "progress.csv" -mmin -1 2>/dev/null | wc -l)
    
    if [ "$recent" -eq 0 ]; then
        echo "No updates in last minute - experiments appear finished!"
        break
    fi
    
    count=$(find "$LOGS_DIR" -name "progress.csv" 2>/dev/null | wc -l)
    echo "$(date): $count progress files, $recent updated in last minute..."
    sleep 60
done

sleep 30  # Extra buffer

echo ""
echo "=== Checking Results ==="
progress_count=$(find "$LOGS_DIR" -name "progress.csv" 2>/dev/null | wc -l)
dot_count=$(find "$LOGS_DIR" -name "*.dot" 2>/dev/null | wc -l)
png_count=$(find "$LOGS_DIR" -name "tree*.png" 2>/dev/null | wc -l)
json_count=$(find "$LOGS_DIR" -name "*.json" 2>/dev/null | wc -l)

echo "Progress CSV files: $progress_count"
echo "Decision tree .dot files: $dot_count"
echo "Decision tree .png files: $png_count"
echo "Policy JSON files: $json_count"

# List tree files if any exist
if [ "$dot_count" -gt 0 ]; then
    echo ""
    echo "=== Tree Files Found ==="
    find "$LOGS_DIR" -name "*.dot" -o -name "tree*.png"
fi

echo ""
echo "=== Generating Visualizations ==="
python3 /root/dtpaynt/scripts/create_better_visualizations.py \
    --logs-root "$LOGS_DIR" \
    --output-dir "$RESULTS_DIR/better_viz"

echo ""
echo "=== Running Standard Analysis ==="
python3 /root/dtpaynt/scripts/plot_stress_test.py \
    --logs-root "$LOGS_DIR" \
    --out-dir "$RESULTS_DIR/analysis"

echo ""
echo "=== Summary ==="
echo "All visualizations complete!"
echo "View results in:"
echo "  - $RESULTS_DIR/better_viz/"
echo "  - $RESULTS_DIR/analysis/"
echo ""
echo "Decision trees (if exported):"
find "$LOGS_DIR" -name "*.dot" -o -name "tree*.png" 2>/dev/null | head -10

echo ""
echo "=== Done at $(date) ==="
