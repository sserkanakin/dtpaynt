#!/usr/bin/env python3
"""
Visualize best trees and best-run time series for depth-4 (30-min) consensus-4-2.

Inputs:
- depth4-analysis/best_per_variant.csv (variant, run_id, ...)
- depth4-analysis/aggregated_metrics.csv (includes progress_path, tree_png)
- depth4-analysis/trees/<variant>.png (best exported controller per variant)

Outputs in depth4-analysis/:
- tree_gallery.png (grid of best trees with labels)
- value_vs_time_best.png (overlay of best runs only)
- tree_size_vs_time_best.png
- families_evaluated_vs_time_best.png
"""

from __future__ import annotations

import os
import sys
from typing import List, Tuple


def ensure_deps():
    try:
        import pandas  # noqa: F401
        import matplotlib  # noqa: F401
        from PIL import Image, ImageDraw, ImageFont  # noqa: F401
    except Exception:
        import subprocess
        print("[info] Installing required packages (pandas, matplotlib, pillow)...", flush=True)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas", "matplotlib", "pillow"], stdout=subprocess.DEVNULL)


def read_best_and_agg(out_dir: str):
    import pandas as pd
    best = pd.read_csv(os.path.join(out_dir, "best_per_variant.csv"))
    agg = pd.read_csv(os.path.join(out_dir, "aggregated_metrics.csv"))
    # We'll need progress paths for the best rows
    merged = best.merge(agg[["variant", "run_id", "progress_path"]], on=["variant", "run_id"], how="left")
    return merged


def load_progress(path: str):
    import pandas as pd
    if not isinstance(path, str) or not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    if "timestamp" not in df.columns:
        return None
    # Use only depth 4 rows if present
    if "tree_depth" in df.columns:
        df = df[df["tree_depth"] == 4]
    df = df.sort_values("timestamp").reset_index(drop=True)
    # forward-fill best_value
    if "best_value" in df.columns:
        df["best_value_ffill"] = df["best_value"].ffill()
    return df


def plot_best_only(merged, out_dir: str):
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    # Build curves
    T_MAX = 1800
    GRID = np.arange(0, T_MAX + 1, 10)

    def regrid(series):
        s = series.set_index("timestamp").reindex(GRID).ffill()
        return s

    # Value vs time best-only
    plt.figure(figsize=(10, 6))
    for _, row in merged.iterrows():
        df = load_progress(row.get("progress_path"))
        if df is None or df.empty or "best_value_ffill" not in df:
            continue
        s = regrid(df[["timestamp", "best_value_ffill"]].rename(columns={"best_value_ffill": "y"}))
        plt.plot(GRID, s, label=row["variant"])
    plt.xlabel("time (s)")
    plt.ylabel("best_value (best run)")
    plt.title("Depth-4 (30 min) Value vs Time — best run per variant")
    plt.legend(loc="lower right", fontsize=8)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "value_vs_time_best.png"))
    plt.close()

    # Tree size vs time best-only
    plt.figure(figsize=(10, 6))
    for _, row in merged.iterrows():
        df = load_progress(row.get("progress_path"))
        if df is None or df.empty or "tree_size" not in df.columns:
            continue
        s = regrid(df[["timestamp", "tree_size"]].rename(columns={"tree_size": "y"}))
        plt.plot(GRID, s, label=row["variant"])
    plt.xlabel("time (s)")
    plt.ylabel("tree_size (best run)")
    plt.title("Depth-4 Tree Size vs Time — best run per variant")
    plt.legend(loc="upper left", fontsize=8)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "tree_size_vs_time_best.png"))
    plt.close()

    # Families evaluated vs time best-only
    plt.figure(figsize=(10, 6))
    for _, row in merged.iterrows():
        df = load_progress(row.get("progress_path"))
        if df is None or df.empty or "families_evaluated" not in df.columns:
            continue
        s = regrid(df[["timestamp", "families_evaluated"]].rename(columns={"families_evaluated": "y"}))
        plt.plot(GRID, s, label=row["variant"])
    plt.xlabel("time (s)")
    plt.ylabel("families_evaluated (best run)")
    plt.title("Depth-4 Families Evaluated vs Time — best run per variant")
    plt.legend(loc="upper left", fontsize=8)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "families_evaluated_vs_time_best.png"))
    plt.close()


def build_tree_gallery(variants: List[str], tree_dir: str, out_path: str, cols: int = 3, cell_size: Tuple[int, int] = (480, 360)):
    from PIL import Image, ImageDraw, ImageFont
    imgs = []
    labels = []
    for v in variants:
        p = os.path.join(tree_dir, f"{v}.png")
        if os.path.exists(p):
            try:
                im = Image.open(p).convert("RGB")
                imgs.append(im)
                labels.append(v)
            except Exception:
                pass
    if not imgs:
        return
    # Normalize sizes
    W, H = cell_size
    norm = [im.copy() for im in imgs]
    for i, im in enumerate(norm):
        im.thumbnail((W, H), Image.LANCZOS)
        # canvas with label area at top
        canvas = Image.new("RGB", (W, H + 30), color=(255, 255, 255))
        x = (W - im.width) // 2
        y = (H - im.height) // 2 + 30
        canvas.paste(im, (x, y))
        draw = ImageDraw.Draw(canvas)
        text = labels[i]
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
        draw.text((10, 8), text, fill=(0, 0, 0), font=font)
        norm[i] = canvas

    rows = (len(norm) + cols - 1) // cols
    grid = Image.new("RGB", (cols * W, rows * (H + 30)), color=(255, 255, 255))
    for idx, im in enumerate(norm):
        r = idx // cols
        c = idx % cols
        grid.paste(im, (c * W, r * (H + 30)))
    grid.save(out_path)


def main():
    ensure_deps()
    out_dir = os.path.join(os.getcwd(), "depth4-analysis")
    trees_dir = os.path.join(out_dir, "trees")
    if not os.path.exists(out_dir):
        print("[error] depth4-analysis not found; run analyze_depth4.py first.", flush=True)
        sys.exit(1)
    merged = read_best_and_agg(out_dir)
    plot_best_only(merged, out_dir)
    variants = list(merged["variant"].values)
    build_tree_gallery(variants, trees_dir, os.path.join(out_dir, "tree_gallery.png"))
    print("[done] Best-run figures and tree gallery written to depth4-analysis")


if __name__ == "__main__":
    main()
