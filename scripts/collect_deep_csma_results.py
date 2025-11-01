#!/usr/bin/env python3
"""Collect and plot results for the deep CSMA experiment suite.

Usage:
  python3 scripts/collect_deep_csma_results.py --results-root results

This script expects the runs to be present under:
  <results_root>/logs/<algorithm_label>/csma-3-4/<run-id>/progress.csv

Algorithm labels expected (matching experiments-dts.py naming):
  original
  modified_value_only
  modified_value_size_alpha0.01
  modified_value_size_alpha0.1
  modified_value_size_alpha0.5

Outputs:
  - CSV summary: results/analysis/deep_csma_summary.csv
  - Figures: results/analysis/figures/deep_csma_time_series.png
             results/analysis/figures/deep_csma_value_vs_size.png

"""
import argparse
import csv
import os
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import pandas as pd

ALGO_LABELS = [
    ("original", "Original (DFS)") ,
    ("modified_value_only", "Modified (BFS, value_only)"),
    ("modified_value_size_alpha0.01", "Modified (value_size, alpha=0.01)"),
    ("modified_value_size_alpha0.1", "Modified (value_size, alpha=0.1)"),
    ("modified_value_size_alpha0.5", "Modified (value_size, alpha=0.5)"),
]

FIG_DIR = Path("results/analysis/figures/deep_csma")
FIG_DIR.mkdir(parents=True, exist_ok=True)


def find_latest_run(progress_root: Path, algo_label: str, benchmark: str = "csma-3-4") -> Optional[Path]:
    base = progress_root / algo_label / benchmark
    if not base.exists():
        return None
    runs = [d for d in base.iterdir() if d.is_dir()]
    if not runs:
        return None
    # choose the lexicographically largest (timestamped run id)
    runs_sorted = sorted(runs, key=lambda p: p.name)
    return runs_sorted[-1]


def read_progress_csv(csv_path: Path) -> pd.DataFrame:
    try:
        df = pd.read_csv(csv_path)
        return df
    except Exception:
        return pd.DataFrame()


def summarize_run(progress_df: pd.DataFrame) -> Dict:
    # expects fields: timestamp,best_value,tree_size,tree_depth,time_to_best maybe
    if progress_df.empty:
        return {"finish_time": None, "best_value": None, "tree_size": None, "tree_depth": None, "time_to_best": None}
    # take last non-null best_value
    best_vals = progress_df[progress_df["best_value"].notnull()]
    last_best = None
    if not best_vals.empty:
        last_best = float(best_vals["best_value"].iloc[-1])
    finish_time = None
    try:
        finish_time = float(progress_df["timestamp"].iloc[-1])
    except Exception:
        finish_time = None
    # tree_size/tree_depth from last row if present
    tree_size = None
    tree_depth = None
    try:
        tree_size = int(progress_df["tree_size"].dropna().iloc[-1])
    except Exception:
        tree_size = None
    try:
        tree_depth = int(progress_df["tree_depth"].dropna().iloc[-1])
    except Exception:
        tree_depth = None
    # time_to_best could be present as column; if not, try to infer from last improvement event
    ttb = None
    if "time_to_best" in progress_df.columns:
        try:
            ttb = float(progress_df["time_to_best"].dropna().iloc[-1])
        except Exception:
            ttb = None
    else:
        # find last row with event==improvement and take its timestamp
        if "event" in progress_df.columns:
            improvements = progress_df[progress_df["event"] == "improvement"]
            if not improvements.empty:
                try:
                    ttb = float(improvements["timestamp"].iloc[-1])
                except Exception:
                    ttb = None
    return {"finish_time": finish_time, "best_value": last_best, "tree_size": tree_size, "tree_depth": tree_depth, "time_to_best": ttb}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--results-root", type=str, default="results", help="Root folder where logs/analysis/plots are stored")
    p.add_argument(
        "--benchmarks",
        type=str,
        default="csma-3-4",
        help="Comma-separated list of benchmark ids to collect (default: csma-3-4)",
    )
    args = p.parse_args()
    results_root = Path(args.results_root)
    benchmarks = [b.strip() for b in args.benchmarks.split(",") if b.strip()]
    progress_root = results_root / "logs"
    analysis_dir = results_root / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = []

    # For each benchmark requested, collect per-algorithm results and produce plots
    for bm in benchmarks:
        print(f"Collecting results for benchmark: {bm}")
        # For time series plot, collect progress dfs for original and modified_value_only for this benchmark
        ts_dfs: Dict[str, pd.DataFrame] = {}

        for algo_dir, pretty in ALGO_LABELS:
            run_dir = find_latest_run(progress_root, algo_dir, bm)
            if run_dir is None:
                print(f"No run found for {algo_dir} / {bm}")
                summary_rows.append({"benchmark": bm, "algorithm": pretty, "finish_time": None, "best_value": None, "tree_size": None, "tree_depth": None, "time_to_best": None, "run_dir": None})
                continue
            progress_csv = run_dir / "progress.csv"
            if not progress_csv.exists():
                print(f"Missing progress.csv for {algo_dir} at {run_dir}")
                summary_rows.append({"benchmark": bm, "algorithm": pretty, "finish_time": None, "best_value": None, "tree_size": None, "tree_depth": None, "time_to_best": None, "run_dir": str(run_dir)})
                continue
            df = read_progress_csv(progress_csv)
            s = summarize_run(df)
            s.update({"benchmark": bm, "algorithm": pretty, "run_dir": str(run_dir)})
            summary_rows.append(s)
            if algo_dir in ("original", "modified_value_only"):
                # keep full time series
                ts = df[["timestamp", "best_value"]].copy() if not df.empty else pd.DataFrame()
                ts = ts.dropna(subset=["timestamp"]).reset_index(drop=True)
                ts["timestamp"] = pd.to_numeric(ts["timestamp"], errors="coerce")
                ts["best_value"] = pd.to_numeric(ts["best_value"], errors="coerce")
                ts_dfs[pretty] = ts

        # write per-benchmark summary CSV
        per_summary_df = pd.DataFrame([r for r in summary_rows if r.get("benchmark") == bm])
        per_csv = analysis_dir / f"deep_{bm}_summary.csv"
        if not per_summary_df.empty:
            per_summary_df.to_csv(per_csv, index=False)
            print(f"Wrote per-benchmark summary CSV to {per_csv}")

        # Deliverable 1: Anytime Performance Plot (original vs modified_value_only) for this benchmark
        if ts_dfs:
            plt.figure(figsize=(10,6))
            for label, df in ts_dfs.items():
                if df.empty:
                    continue
                df = df.sort_values("timestamp").reset_index(drop=True)
                df["best_value_ffill"] = df["best_value"].ffill()
                plt.step(df["timestamp"], df["best_value_ffill"], where='post', label=label)
            plt.xlim(0, 1800)
            plt.ylim(bottom=0)
            plt.xlabel("Time (s)")
            plt.ylabel("Best value found")
            plt.title(f"Anytime performance: Original vs Modified (value_only) — {bm}")
            plt.legend()
            out1 = FIG_DIR / f"deep_{bm}_time_series.png"
            plt.savefig(out1, bbox_inches='tight')
            plt.close()
            print(f"Saved time-series plot to {out1}")

        # Deliverable 3: Value vs Size Trade-off (scatter) for this benchmark
        per_scatter_df = per_summary_df.dropna(subset=["best_value","tree_size"]).copy() if not per_summary_df.empty else pd.DataFrame()
        if not per_scatter_df.empty:
            plt.figure(figsize=(8,6))
            plt.scatter(per_scatter_df["tree_size"], per_scatter_df["best_value"], s=100)
            for i,row in per_scatter_df.iterrows():
                plt.annotate(row["algorithm"], (row["tree_size"], row["best_value"]), textcoords="offset points", xytext=(5,5))
            plt.xlabel("Tree size (nodes)")
            plt.ylabel("Final V_best")
            plt.title(f"Value vs Size trade-off — {bm}")
            out2 = FIG_DIR / f"deep_{bm}_value_vs_size.png"
            plt.savefig(out2, bbox_inches='tight')
            plt.close()
            print(f"Saved value-vs-size scatter to {out2}")

    # write aggregated summary CSV for all benchmarks
    summary_df = pd.DataFrame(summary_rows)[["benchmark","algorithm","best_value","tree_size","tree_depth","time_to_best","finish_time","run_dir"]]
    summary_csv = analysis_dir / "deep_benchmarks_summary.csv"
    summary_df.to_csv(summary_csv, index=False)
    print(f"Wrote aggregated summary CSV to {summary_csv}")

    # write summary CSV
    print("Done. Summary and figures are in results/analysis and results/analysis/figures/deep_csma")

if __name__ == '__main__':
    main()
