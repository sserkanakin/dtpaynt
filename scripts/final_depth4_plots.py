#!/usr/bin/env python3
"""
Clean depth-4 plot generation: 4 essential plots + best trees.
"""
import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import MaxNLocator
from pathlib import Path
import shutil

OUTPUT_DIR = Path("/root/dtpaynt/depth4-analysis")
OUTPUT_DIR.mkdir(exist_ok=True)

# Read metrics
metrics_file = OUTPUT_DIR / "aggregated_metrics.csv"
df = pd.read_csv(metrics_file)

# Filter valid runs (non-empty)
df = df.dropna(subset=['final_best_value'])
print(f"[info] Processing {len(df)} valid depth-4 runs")

# Setup plotting style
plt.rcParams['figure.figsize'] = (12, 5)
plt.rcParams['font.size'] = 10

# Color map
variants = sorted(df['variant'].unique())
color_map = {
    'original': '#1f77b4',
    'modified_value_only': '#ff7f0e',
    'modified_bounds_gap': '#2ca02c',
    'modified_value_size_alpha0.01': '#d62728',
    'modified_value_size_alpha0.1': '#9467bd',
    'modified_value_size_alpha0.25': '#8c564b',
    'modified_value_size_alpha0.5': '#e377c2',
    'modified_value_size_alpha0.75': '#7f7f7f',
    'modified_value_size_alpha0.9': '#bcbd22',
    'modified_value_size_alpha0.99': '#17becf',
}

# ============================================================================
# PLOT 1: Best Value by Variant (Bar Chart)
# ============================================================================
fig, ax = plt.subplots(figsize=(14, 6))
df_sorted = df.sort_values('final_best_value', ascending=False)
colors = [color_map.get(v, '#000000') for v in df_sorted['variant']]
bars = ax.bar(range(len(df_sorted)), df_sorted['final_best_value'], color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)
ax.set_xticks(range(len(df_sorted)))
ax.set_xticklabels(df_sorted['variant'], rotation=45, ha='right', fontsize=9)
ax.set_ylabel('Best Value Found', fontsize=12, fontweight='bold')
ax.set_title('Depth-4: Best Value by Variant', fontsize=14, fontweight='bold')
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "best_value_by_variant.png", dpi=150, bbox_inches='tight')
plt.close()
print("[done] Saved: best_value_by_variant.png")

# ============================================================================
# PLOT 2: Time to Best Value (Bar Chart)
# ============================================================================
fig, ax = plt.subplots(figsize=(14, 6))
df_sorted = df.sort_values('time_to_best', ascending=True)
colors = [color_map.get(v, '#000000') for v in df_sorted['variant']]
bars = ax.bar(range(len(df_sorted)), df_sorted['time_to_best'], color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)
ax.set_xticks(range(len(df_sorted)))
ax.set_xticklabels(df_sorted['variant'], rotation=45, ha='right', fontsize=9)
ax.set_ylabel('Time to Best Value (seconds)', fontsize=12, fontweight='bold')
ax.set_title('Depth-4: Time to Achieve Best Value', fontsize=14, fontweight='bold')
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "time_to_best_by_variant.png", dpi=150, bbox_inches='tight')
plt.close()
print("[done] Saved: time_to_best_by_variant.png")

# ============================================================================
# PLOT 3: Exported Tree Nodes vs Best Value (Scatter)
# ============================================================================
fig, ax = plt.subplots(figsize=(12, 6))
for variant in variants:
    variant_data = df[df['variant'] == variant]
    ax.scatter(variant_data['exported_tree_nodes'], variant_data['final_best_value'], 
               s=200, label=variant, color=color_map.get(variant, '#000000'), 
               alpha=0.7, edgecolors='black', linewidth=1.5)
ax.set_xlabel('Exported Tree Nodes', fontsize=12, fontweight='bold')
ax.set_ylabel('Best Value', fontsize=12, fontweight='bold')
ax.set_title('Depth-4: Tree Size vs Quality', fontsize=14, fontweight='bold')
ax.grid(True, alpha=0.3)
ax.legend(fontsize=8, loc='best', ncol=2)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "tree_nodes_vs_value.png", dpi=150, bbox_inches='tight')
plt.close()
print("[done] Saved: tree_nodes_vs_value.png")

# ============================================================================
# PLOT 4: Best Value vs Time to Best (Scatter - Quality vs Speed)
# ============================================================================
fig, ax = plt.subplots(figsize=(12, 6))
for variant in variants:
    variant_data = df[df['variant'] == variant]
    ax.scatter(variant_data['time_to_best'], variant_data['final_best_value'], 
               s=200, label=variant, color=color_map.get(variant, '#000000'), 
               alpha=0.7, edgecolors='black', linewidth=1.5)
ax.set_xlabel('Time to Best Value (seconds)', fontsize=12, fontweight='bold')
ax.set_ylabel('Best Value', fontsize=12, fontweight='bold')
ax.set_title('Depth-4: Quality vs Speed Trade-off', fontsize=14, fontweight='bold')
ax.grid(True, alpha=0.3)
ax.legend(fontsize=8, loc='best', ncol=2)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "quality_vs_speed.png", dpi=150, bbox_inches='tight')
plt.close()
print("[done] Saved: quality_vs_speed.png")

# ============================================================================
# Create best trees directory and copy best trees
# ============================================================================
trees_dir = OUTPUT_DIR / "best_trees"
if trees_dir.exists():
    shutil.rmtree(trees_dir)
trees_dir.mkdir()

for idx, row in df.iterrows():
    if pd.notna(row['tree_png']) and os.path.exists(row['tree_png']):
        variant_name = row['variant'].replace('/', '_')
        dest = trees_dir / f"{variant_name}.png"
        shutil.copy(row['tree_png'], dest)
        print(f"[copy] {variant_name} -> best_trees/")

print(f"\n[done] All artifacts saved to {OUTPUT_DIR}")
print(f"[summary] Plots generated: 4 (best_value, time_to_best, tree_nodes_vs_value, quality_vs_speed)")
print(f"[summary] Best trees: {len(list(trees_dir.glob('*.png')))} variants")
