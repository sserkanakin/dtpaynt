#!/usr/bin/env python3
"""Produce the required stress-test plots and tables from logs.

Inputs: results/logs structure produced by experiments-dts.py via the runner scripts.
Outputs under results/analysis/stress_test/.

Generates:
- Plot 1/2: Anytime performance (value vs time) for csma-3-4 and consensus-4-2 comparing original vs modified_value_only.
- Tables 1/2: Final results summaries per benchmark across 5 configs.
- Plot 3: Value vs Size scatter (combined benchmarks) with markers per heuristic and colors per benchmark.
- Plot 4: Strategy analysis (families vs time, frontier vs time) on csma-3-4 for 5 configs.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import pandas as pd
except ImportError as exc:
    print("Error: pandas is required for plotting. Install it with 'pip install pandas matplotlib'.", file=sys.stderr)
    sys.exit(1)

try:
    import matplotlib.pyplot as plt
except Exception:
    plt = None


LOGS_ROOT = Path("results/logs").resolve()
OUT_ROOT = Path("results/analysis/stress_test").resolve()

BENCHMARKS = ["csma-3-4", "consensus-4-2"]
ALGORITHMS_ALL = [
    "original",
    "modified_value_only",
    "modified_value_size_alpha0.01",
    "modified_value_size_alpha0.1",
    "modified_value_size_alpha0.5",
]
ALGORITHMS_ANYTIME = ["original", "modified_value_only"]


@dataclass
class Run:
    algorithm: str
    benchmark: str
    run_dir: Path
    progress: pd.DataFrame


def find_latest_run_dir(root: Path) -> Optional[Path]:
    if not root.exists():
        return None
    candidates = [p for p in root.iterdir() if p.is_dir()]
    if not candidates:
        return None
    return sorted(candidates)[-1]


def read_progress(csv_path: Path) -> pd.DataFrame:
    try:
        df = pd.read_csv(csv_path)
        # Normalise expected columns
        columns = [
            "timestamp",
            "best_value",
            "tree_size",
            "tree_depth",
            "frontier_size",
            "families_evaluated",
            "improvement_count",
            "lower_bound",
            "event",
        ]
        for c in columns:
            if c not in df.columns:
                df[c] = pd.NA
        return df
    except Exception:
        return pd.DataFrame()


def load_runs(logs_root: Path, algorithms: Sequence[str], benchmarks: Sequence[str]) -> List[Run]:
    runs: List[Run] = []
    for alg in algorithms:
        for bench in benchmarks:
            bench_root = logs_root / alg / bench
            latest = find_latest_run_dir(bench_root)
            if latest is None:
                continue
            progress_csv = latest / "progress.csv"
            if not progress_csv.is_file():
                continue
            df = read_progress(progress_csv)
            if df.empty:
                continue
            runs.append(Run(alg, bench, latest, df))
    return runs


def plot_anytime(runs: List[Run], out_dir: Path, xlim: Optional[Tuple[float, float]] = (0, 3600)) -> None:
    if plt is None:
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    for bench in BENCHMARKS:
        subset = [r for r in runs if r.benchmark == bench and r.algorithm in ALGORITHMS_ANYTIME]
        if len(subset) < 1:
            continue
        fig, ax = plt.subplots()
        for run in subset:
            df = run.progress.dropna(subset=["timestamp", "best_value"])  # type: ignore[arg-type]
            if df.empty:
                continue
            ax.step(df["timestamp"], df["best_value"], where="post", label=run.algorithm)
        title = f"Anytime Performance on {bench} (Depth 7)"
        ax.set_title(title)
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Best Value Found")
        if xlim:
            ax.set_xlim(*xlim)
        ax.grid(True, linestyle="--", linewidth=0.4)
        ax.legend()
        fig.tight_layout()
        fig.savefig(out_dir / f"anytime_{bench}_depth7.png", dpi=150)
        plt.close(fig)


def summarise_final(df: pd.DataFrame) -> Tuple[Optional[float], Optional[int], Optional[int], Optional[float]]:
    if df.empty:
        return None, None, None, None
    last = df.dropna(subset=["timestamp"]).iloc[-1]
    final_value = pd.to_numeric(df["best_value"], errors="coerce").dropna()
    v = float(final_value.iloc[-1]) if not final_value.empty else None
    size = df["tree_size"].dropna()
    depth = df["tree_depth"].dropna()
    finish_time = float(last["timestamp"]) if "timestamp" in last else None
    return v, (int(size.iloc[-1]) if not size.empty else None), (int(depth.iloc[-1]) if not depth.empty else None), finish_time


def make_tables(runs: List[Run], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    config_rows: Dict[str, List[Dict[str, object]]] = {bench: [] for bench in BENCHMARKS}
    def decode(alg: str) -> Tuple[str, str, Optional[float]]:
        if alg == "original":
            return "Original (DFS)", "-", None
        if alg == "modified_value_only":
            return "Modified (BFS)", "value_only", None
        if alg.startswith("modified_value_size_alpha"):
            token = alg.rsplit("alpha", 1)[-1]
            try:
                alpha = float(token)
            except Exception:
                alpha = None
            return "Modified (BFS)", "value_size", alpha
        return alg, "-", None

    for run in runs:
        v, size, depth, tfinish = summarise_final(run.progress)
        algo, heuristic, alpha = decode(run.algorithm)
        config_rows[run.benchmark].append(
            {
                "Algorithm": algo,
                "Heuristic": heuristic,
                "Alpha": (None if alpha is None else alpha),
                "Final V_best": v,
                "Tree Size (Nodes)": size,
                "Tree Depth": depth,
                "Time to Final (s)": tfinish,
                "AlgorithmLabel": run.algorithm,
            }
        )

    for bench, rows in config_rows.items():
        if not rows:
            continue
        df = pd.DataFrame(rows)
        # Ensure consistent ordering: Original, value_only, value_size alphas
        order = [
            "Original (DFS)",
            "Modified (BFS)",
        ]
        # sort by Algorithm then Heuristic then Alpha
        df["Alpha"] = pd.to_numeric(df["Alpha"], errors="coerce")
        df = df.sort_values(by=["Algorithm", "Heuristic", "Alpha"], na_position="first")
        df.drop(columns=["AlgorithmLabel"], inplace=True)
        df.to_csv(out_dir / f"table_final_{bench}.csv", index=False)


def plot_value_vs_size_combined(runs: List[Run], out_dir: Path) -> None:
    if plt is None:
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    # Build records
    records: List[Dict[str, object]] = []
    for run in runs:
        v, size, depth, _ = summarise_final(run.progress)
        if v is None or size is None:
            continue
        if run.algorithm == "original":
            marker = "x"; label = "Original (DFS)"; heuristic = "original"
        elif run.algorithm == "modified_value_only":
            marker = "o"; label = "value_only"; heuristic = "value_only"
        else:
            marker = "+"; label = "value_size"; heuristic = "value_size"
        records.append({
            "benchmark": run.benchmark,
            "algorithm": run.algorithm,
            "heuristic": heuristic,
            "label": label,
            "TreeSize": size,
            "Value": v,
            "marker": marker,
        })
    if not records:
        return
    df = pd.DataFrame.from_records(records)
    if df.empty:
        return
    fig, ax = plt.subplots()
    colors = {"csma-3-4": "tab:blue", "consensus-4-2": "tab:red"}
    markers = {"original": "x", "value_only": "o", "value_size": "+"}
    for (bench, heuristic), group in df.groupby(["benchmark", "heuristic"]):
        color = colors.get(bench, "gray")
        marker = markers.get(heuristic, "o")
        ax.scatter(group["TreeSize"].astype(float), group["Value"].astype(float),
                   label=f"{bench} · {group['label'].iloc[0]}", marker=marker, color=color, alpha=0.9)
    ax.set_title("Value vs. Size Trade-off (Combined Benchmarks)")
    ax.set_xlabel("Tree Size (Nodes) [lower is better]")
    ax.set_ylabel("Final V_best [higher is better]")
    ax.grid(True, linestyle="--", linewidth=0.4)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "value_vs_size_combined.png", dpi=150)
    plt.close(fig)


def plot_strategy_csma(runs: List[Run], out_dir: Path, xlim: Optional[Tuple[float, float]] = (0, 3600)) -> None:
    if plt is None:
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    subset = [r for r in runs if r.benchmark == "csma-3-4"]
    if not subset:
        return
    # ensure only the 5 desired configs
    desired = set(ALGORITHMS_ALL)
    subset = [r for r in subset if r.algorithm in desired]
    if not subset:
        return
    fig, axes = plt.subplots(2, 1, figsize=(7.5, 7.0), sharex=True)
    ax_eff, ax_mem = axes
    for run in subset:
        df = run.progress
        t = pd.to_numeric(df["timestamp"], errors="coerce").dropna()
        fam = pd.to_numeric(df["families_evaluated"], errors="coerce").dropna()
        fr = pd.to_numeric(df["frontier_size"], errors="coerce").dropna()
        # Align indexes
        if not t.empty and not fam.empty:
            ax_eff.step(t.iloc[: len(fam)], fam, where="post", label=run.algorithm)
        if not t.empty and not fr.empty:
            ax_mem.step(t.iloc[: len(fr)], fr, where="post", label=run.algorithm)
    ax_eff.set_title("Search Strategy Analysis on csma-3-4")
    ax_eff.set_ylabel("Families Evaluated")
    ax_eff.grid(True, linestyle="--", linewidth=0.4)
    ax_mem.set_ylabel("Frontier Size")
    ax_mem.set_xlabel("Time (s)")
    ax_mem.grid(True, linestyle="--", linewidth=0.4)
    if xlim:
        ax_eff.set_xlim(*xlim)
        ax_mem.set_xlim(*xlim)
    ax_eff.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "strategy_csma-3-4.png", dpi=150)
    plt.close(fig)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate stress-test plots and tables from results/logs.")
    p.add_argument("--logs-root", type=Path, default=LOGS_ROOT, help="Root directory with algorithm logs.")
    p.add_argument("--out-dir", type=Path, default=OUT_ROOT, help="Output directory for artefacts.")
    return p.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    logs_root: Path = args.logs_root
    out_dir: Path = args.out_dir
    runs = load_runs(logs_root, ALGORITHMS_ALL, BENCHMARKS)
    if not runs:
        print("No runs found under", logs_root)
        return 1

    # Plots
    plot_anytime([r for r in runs if r.algorithm in ALGORITHMS_ANYTIME], out_dir)
    plot_value_vs_size_combined(runs, out_dir)
    plot_strategy_csma(runs, out_dir)

    # Tables
    make_tables(runs, out_dir)

    print(f"Wrote artefacts to {out_dir}")
    if plt is None:
        print("matplotlib not available; plots were skipped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
