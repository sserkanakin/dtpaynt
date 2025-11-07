#!/usr/bin/env python3
"""Regenerate depth-4 plots with clearer step curves and improvement markers.

Reads:
- depth4-analysis/best_per_variant.csv
- per-run progress.csv files discovered via aggregated_metrics.csv

Outputs (written into depth4-analysis/):
- value_vs_time_best_improved.png
- tree_size_vs_time_best_improved.png
- families_evaluated_vs_time_best_improved.png

Enhancements:
- Step curves (drawn with where='post') for best_value.
- Markers at improvement points (triangles).
- If series empty -> annotate 'NO DATA'.
- Consistent color palette.
"""

from __future__ import annotations

import os
import sys
from typing import Dict


def ensure_deps():
    try:
        import pandas  # noqa: F401
        import matplotlib  # noqa: F401
    except Exception:
        import subprocess
        print("[info] Installing pandas/matplotlib...", flush=True)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas", "matplotlib"], stdout=subprocess.DEVNULL)


def load_best(out_dir: str):
    import pandas as pd
    return pd.read_csv(os.path.join(out_dir, "best_per_variant.csv"))


def progress_df(path: str):
    import pandas as pd
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    if "timestamp" not in df.columns:
        return None
    if "tree_depth" in df.columns:
        df = df[df["tree_depth"] == 4]
    df = df.sort_values("timestamp")
    df["best_value_ffill"] = df["best_value"].ffill() if "best_value" in df.columns else float('nan')
    return df.reset_index(drop=True)


def regenerate(out_dir: str):
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt

    best = load_best(out_dir)
    agg = pd.read_csv(os.path.join(out_dir, "aggregated_metrics.csv"))
    merged = best.merge(agg[["variant", "run_id", "progress_path"]], on=["variant", "run_id"], how="left")

    palette = plt.get_cmap("tab10")

    def plot_metric(metric: str, fname: str, ylabel: str, ytransform=None):
        plt.figure(figsize=(11, 6))
        for idx, row in merged.iterrows():
            df = progress_df(row.get("progress_path"))
            if df is None or df.empty or metric not in df.columns:
                continue
            color = palette(idx % 10)
            t = df["timestamp"].to_numpy()
            y = df[metric].to_numpy()
            if metric == "best_value_ffill" and np.all(np.isnan(y)):
                continue
            if ytransform:
                y = ytransform(y)
            # Build step curve
            plt.step(t, y, where='post', label=row['variant'], linewidth=2.0, color=color)
            # Mark improvement events
            if metric == "best_value_ffill" and "best_value" in df.columns:
                impro_mask = df["best_value"].diff() > 0
                t_impr = df.loc[impro_mask, "timestamp"].to_numpy()
                y_impr = df.loc[impro_mask, "best_value"].to_numpy()
                if len(t_impr):
                    plt.scatter(t_impr, y_impr, color=color, marker='^', s=50, edgecolors='black', linewidths=0.5, zorder=5)
        ax = plt.gca()
        if all(len(line.get_xdata()) == 0 for line in ax.get_lines()):
            plt.text(0.5, 0.5, 'NO DATA', ha='center', va='center', transform=ax.transAxes, fontsize=18, color='red')
        plt.xlabel('time (s)')
        plt.ylabel(ylabel)
        plt.title(f'Depth-4 (30 min) {ylabel} — best runs (step curves)')
        plt.grid(True, alpha=0.35)
        plt.legend(loc='best', fontsize=8, ncol=2)
        plt.tight_layout()
        out_path = os.path.join(out_dir, fname)
        plt.savefig(out_path)
        plt.close()

    # Ensure best_value_ffill column for values plotting
    for _, row in merged.iterrows():
        df = progress_df(row.get("progress_path"))
        if df is not None and "best_value_ffill" not in df.columns and "best_value" in df.columns:
            df["best_value_ffill"] = df["best_value"].ffill()

    plot_metric("best_value_ffill", "value_vs_time_best_improved.png", "best value")
    plot_metric("tree_size", "tree_size_vs_time_best_improved.png", "tree size")
    plot_metric("families_evaluated", "families_evaluated_vs_time_best_improved.png", "families evaluated")

    print("[done] Improved best-run plots generated.")


def main():
    ensure_deps()
    out_dir = os.path.join(os.getcwd(), "depth4-analysis")
    if not os.path.isdir(out_dir):
        print("[error] depth4-analysis missing. Run analysis first.")
        sys.exit(1)
    regenerate(out_dir)


if __name__ == "__main__":
    main()
