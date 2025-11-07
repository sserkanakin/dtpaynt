#!/usr/bin/env python3
"""
Analyze 30-minute depth-4 runs for consensus-4-2 and generate aggregates and plots.

Inputs (discovered automatically):
- results/logs/**/consensus-4-2/*/run-info.json with timeout==1800 and tree-depth==4

Outputs:
- depth4-analysis/aggregated_metrics.csv (per-run)
- depth4-analysis/summary_by_variant.csv (per-variant aggregates)
- depth4-analysis/value_vs_time.png (median per variant, shaded IQR)
- depth4-analysis/tree_size_vs_time.png (median per variant)
- depth4-analysis/families_evaluated_vs_time.png (median per variant)
- depth4-analysis/comparison_tables.md (human-readable summary)
- depth4-analysis/trees/<variant>.png (best run tree snapshot, if available)

Assumptions:
- All relevant runs recorded progress.csv with columns:
  timestamp,best_value,tree_size,tree_depth,frontier_size,families_evaluated,improvement_count,lower_bound,event,algorithm_version,benchmark_name,run_id
"""

from __future__ import annotations

import json
import math
import os
import sys
from glob import glob
from typing import Dict, List, Tuple


def ensure_deps():
    """Install required Python packages if missing.

    We need: pandas, matplotlib, tabulate (for DataFrame.to_markdown).
    """
    try:
        import pandas as pd  # noqa: F401
        import matplotlib  # noqa: F401
        import tabulate  # noqa: F401
    except Exception:
        print("[info] Installing required Python packages (pandas, matplotlib, tabulate)...", flush=True)
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas", "matplotlib", "tabulate"], stdout=subprocess.DEVNULL)


def discover_runs(base: str = "results/logs") -> List[Dict]:
    runs = []
    # pattern: results/logs/<variant>/<benchmark>/<run_id>/run-info.json
    for run_info_path in glob(os.path.join(base, "*", "consensus-4-2", "*", "run-info.json")):
        try:
            with open(run_info_path, "r", encoding="utf-8") as f:
                info = json.load(f)
        except Exception:
            continue

        # We want timeout==1800 and tree-depth==4 (from cli_extra_args or extra_args)
        timeout = info.get("timeout")
        cli_args = info.get("cli_extra_args", [])
        extra_args = info.get("extra_args", [])
        algo = info.get("algorithm_version", "unknown")
        benchmark = info.get("benchmark_id")
        if benchmark != "consensus-4-2":
            continue

        def extract_depth(args: List[str]) -> int | None:
            try:
                for i, a in enumerate(args):
                    if a == "--tree-depth":
                        return int(args[i + 1])
            except Exception:
                return None
            return None

        depth = extract_depth(cli_args) or extract_depth(extra_args)
        if timeout == 1800 and depth == 4:
            run_dir = os.path.dirname(run_info_path)
            progress_path = os.path.join(run_dir, "progress.csv")
            stdout_path = os.path.join(run_dir, "stdout.txt")
            tree_png = os.path.join(run_dir, "tree.png")
            runs.append({
                "variant": algo,
                "run_dir": run_dir,
                "progress": progress_path,
                "stdout": stdout_path,
                "tree_png": tree_png,
                "run_id": os.path.basename(run_dir),
            })
    return runs


def load_progress(path: str):
    import pandas as pd
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    # Ensure expected columns exist
    expected = {
        "timestamp", "best_value", "tree_size", "tree_depth", "frontier_size",
        "families_evaluated", "improvement_count", "event", "algorithm_version",
        "benchmark_name", "run_id"
    }
    missing = expected.difference(set(df.columns))
    if missing:
        # Try to coerce older schema by adding missing columns with NaN
        for col in missing:
            df[col] = math.nan
    # filter to depth 4 only
    if "tree_depth" in df.columns:
        df = df[df["tree_depth"] == 4]
    # coerce best_value numeric
    df["best_value"] = pd.to_numeric(df["best_value"], errors="coerce")
    df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
    df = df.sort_values("timestamp").reset_index(drop=True)
    # forward-fill best_value to form a step function curve
    df["best_value_ffill"] = df["best_value"].ffill()
    return df


def compute_run_metrics(df) -> Dict:
    import numpy as np
    if df is None or df.empty:
        return {
            "final_best_value": math.nan,
            "time_to_best": math.nan,
            "tree_size_at_best": math.nan,
            "final_tree_size": math.nan,
            "families_evaluated_at_best": math.nan,
            "n_improvements": 0,
            "duration": math.nan,
            "tree_depth": 4,
        }
    # Final best and time
    best = df["best_value_ffill"].max()
    if np.isnan(best):
        final_best = math.nan
        t_best = math.nan
        ts = math.nan
        fam = math.nan
    else:
        final_best = float(best)
        first_best_idx = df.index[df["best_value_ffill"] == best][0]
        t_best = float(df.loc[first_best_idx, "timestamp"]) if "timestamp" in df.columns else math.nan
        # Closest matching row to that time for tree_size and families_evaluated
        ts = float(df.loc[first_best_idx, "tree_size"]) if "tree_size" in df.columns else math.nan
        fam = float(df.loc[first_best_idx, "families_evaluated"]) if "families_evaluated" in df.columns else math.nan

    # number of improvements seen (count event==improvement or positive deltas)
    n_impr = int((df["best_value"].diff() > 0).fillna(False).sum())
    duration = float(df["timestamp"].max()) if "timestamp" in df.columns else math.nan
    # final tree size at last timestamp (depth 4 rows)
    final_ts = float(df["tree_size"].ffill().iloc[-1]) if "tree_size" in df.columns and not df["tree_size"].empty else math.nan
    return {
        "final_best_value": final_best,
        "time_to_best": t_best,
        "tree_size_at_best": ts,
        "final_tree_size": final_ts,
        "families_evaluated_at_best": fam,
        "n_improvements": n_impr,
        "duration": duration,
        "tree_depth": 4,
    }


def parse_dot_tree(dot_path: str) -> Tuple[int, int, int]:
    """Parse a Graphviz DOT of the tree and return (nodes, edges, max_depth).

    Depth is measured in number of edges from root to deepest node. Root is
    inferred as the node with no incoming edges.
    """
    try:
        nodes = set()
        edges = []
        with open(dot_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "[label=" in line and "->" not in line:
                    # e.g., 0 [label="pc1<=2" ...]
                    nid = line.split(" ", 1)[0]
                    if nid.isdigit():
                        nodes.add(int(nid))
                elif "->" in line:
                    # e.g., 0 -> 1 [label=T]
                    parts = line.replace("[", " ").split()
                    if "->" in parts:
                        u = parts[0]
                        v = parts[2]
                        if u.isdigit() and v.isdigit():
                            edges.append((int(u), int(v)))
        if not nodes and not edges:
            return (0, 0, 0)
        incoming = {}
        for u, v in edges:
            incoming[v] = incoming.get(v, 0) + 1
        roots = [n for n in nodes if incoming.get(n, 0) == 0]
        root = roots[0] if roots else (min(nodes) if nodes else 0)
        # BFS for depth
        from collections import deque, defaultdict
        adj = defaultdict(list)
        for u, v in edges:
            adj[u].append(v)
        q = deque([(root, 0)])
        seen = {root}
        max_d = 0
        while q:
            n, d = q.popleft()
            max_d = max(max_d, d)
            for w in adj.get(n, []):
                if w not in seen:
                    seen.add(w)
                    q.append((w, d + 1))
        return (len(nodes), len(edges), max_d)
    except Exception:
        return (0, 0, 0)


def aggregate_and_plot(runs: List[Dict], out_dir: str):
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt

    per_run_rows = []
    variant_to_runs: Dict[str, List[Tuple[str, object]]] = {}

    for r in runs:
        df = load_progress(r["progress"])
        metrics = compute_run_metrics(df)
        # parse exported dot if available
        dot_path = os.path.join(r["run_dir"], "tree.dot")
        exp_nodes, exp_edges, exp_depth = (0, 0, 0)
        if os.path.exists(dot_path):
            exp_nodes, exp_edges, exp_depth = parse_dot_tree(dot_path)
        row = {
            "variant": r["variant"],
            "run_id": r["run_id"],
            **metrics,
            "progress_path": r["progress"],
            "tree_png": r["tree_png"],
            "exported_tree_nodes": exp_nodes,
            "exported_tree_edges": exp_edges,
            "exported_tree_depth": exp_depth,
        }
        per_run_rows.append(row)
        variant_to_runs.setdefault(r["variant"], []).append((r["run_id"], df))

    per_run_df = pd.DataFrame(per_run_rows).sort_values(["variant", "final_best_value"], ascending=[True, False])
    per_run_csv = os.path.join(out_dir, "aggregated_metrics.csv")
    per_run_df.to_csv(per_run_csv, index=False)

    # Export vs progress comparison
    cmp_cols = [
        "variant", "run_id", "tree_depth", "tree_size_at_best", "final_tree_size",
        "exported_tree_nodes", "exported_tree_depth"
    ]
    cmp_df = per_run_df[cmp_cols].copy()
    cmp_df["size_delta_export_minus_progress"] = cmp_df["exported_tree_nodes"] - cmp_df["final_tree_size"]
    cmp_df["depth_delta_export_minus_requested"] = cmp_df["exported_tree_depth"] - cmp_df["tree_depth"]
    cmp_df.to_csv(os.path.join(out_dir, "export_vs_progress.csv"), index=False)

    # Per-variant summary
    summary_rows = []
    for variant, group in per_run_df.groupby("variant"):
        vals = group["final_best_value"].dropna()
        times = group["time_to_best"].dropna()
        row = {
            "variant": variant,
            "runs": len(group),
            "final_best_mean": vals.mean() if not vals.empty else math.nan,
            "final_best_std": vals.std(ddof=0) if not vals.empty else math.nan,
            "final_best_max": vals.max() if not vals.empty else math.nan,
            "time_to_best_median": times.median() if not times.empty else math.nan,
        }
        summary_rows.append(row)
    summary_df = pd.DataFrame(summary_rows).sort_values("final_best_max", ascending=False)
    summary_csv = os.path.join(out_dir, "summary_by_variant.csv")
    summary_df.to_csv(summary_csv, index=False)

    # Best-per-variant table
    best_rows = []
    for variant, group in per_run_df.groupby("variant"):
        br = group.sort_values("final_best_value", ascending=False).head(1)
        if not br.empty:
            best_rows.append(br.iloc[0].to_dict())
    best_df = pd.DataFrame(best_rows)
    best_cols = [
        "variant", "final_best_value", "time_to_best", "tree_depth",
        "tree_size_at_best", "final_tree_size", "exported_tree_nodes", "exported_tree_depth", "families_evaluated_at_best",
        "n_improvements", "duration", "run_id"
    ]
    best_df = best_df[best_cols].sort_values("final_best_value", ascending=False)
    best_csv = os.path.join(out_dir, "best_per_variant.csv")
    best_df.to_csv(best_csv, index=False)

    # Plots: build a regular time grid and compute median per variant
    T_MAX = 1800
    GRID = np.arange(0, T_MAX + 1, 10)  # every 10s

    def build_curve(df):
        if df is None or df.empty:
            return pd.Series(index=GRID, data=np.nan)
        s = df.set_index("timestamp")["best_value_ffill"].reindex(GRID).ffill()
        return s

    # value_vs_time
    plt.figure(figsize=(10, 6))
    for variant, pairs in variant_to_runs.items():
        curves = [build_curve(df) for _, df in pairs]
        if not curves:
            continue
        mat = pd.concat(curves, axis=1)
        med = mat.median(axis=1)
        q25 = mat.quantile(0.25, axis=1)
        q75 = mat.quantile(0.75, axis=1)
        plt.plot(GRID, med, label=variant)
        plt.fill_between(GRID, q25, q75, alpha=0.12)
    plt.xlabel("time (s)")
    plt.ylabel("best_value (median, shaded IQR)")
    plt.title("Depth-4 (30 min) Value vs Time — consensus-4-2")
    plt.legend(loc="lower right", fontsize=8)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "value_vs_time.png"))
    plt.close()

    # tree_size_vs_time (median)
    plt.figure(figsize=(10, 6))
    for variant, pairs in variant_to_runs.items():
        curves = []
        for _, df in pairs:
            if df is None or df.empty:
                curves.append(pd.Series(index=GRID, data=np.nan))
                continue
            s = df.set_index("timestamp")["tree_size"].reindex(GRID).ffill()
            curves.append(s)
        if not curves:
            continue
        mat = pd.concat(curves, axis=1)
        med = mat.median(axis=1)
        plt.plot(GRID, med, label=variant)
    plt.xlabel("time (s)")
    plt.ylabel("tree_size (median)")
    plt.title("Depth-4 (30 min) Tree Size vs Time — consensus-4-2")
    plt.legend(loc="upper left", fontsize=8)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "tree_size_vs_time.png"))
    plt.close()

    # families_evaluated_vs_time (median)
    plt.figure(figsize=(10, 6))
    for variant, pairs in variant_to_runs.items():
        curves = []
        for _, df in pairs:
            if df is None or df.empty or "families_evaluated" not in df.columns:
                curves.append(pd.Series(index=GRID, data=np.nan))
                continue
            s = df.set_index("timestamp")["families_evaluated"].reindex(GRID).ffill()
            curves.append(s)
        if not curves:
            continue
        mat = pd.concat(curves, axis=1)
        med = mat.median(axis=1)
        plt.plot(GRID, med, label=variant)
    plt.xlabel("time (s)")
    plt.ylabel("families_evaluated (median)")
    plt.title("Depth-4 (30 min) Families Evaluated vs Time — consensus-4-2")
    plt.legend(loc="upper left", fontsize=8)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "families_evaluated_vs_time.png"))
    plt.close()

    # Write a simple markdown summary
    md_path = os.path.join(out_dir, "comparison_tables.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Depth-4 (30 min) — consensus-4-2\n\n")
        f.write("This report compares algorithms by best value reached within 1800s at tree depth 4. It also includes time-to-best and tree size statistics.\\n\\n")
        f.write("## Per-variant summary (sorted by best final value)\n\n")
        f.write(summary_df.to_markdown(index=False))
        f.write("\n\n## Per-run metrics\n\n")
        # Limit columns for readability
        cols = [
            "variant", "run_id", "final_best_value", "time_to_best",
            "tree_size_at_best", "families_evaluated_at_best", "n_improvements",
        ]
        f.write(per_run_df[cols].to_markdown(index=False))
        f.write("\n\n## Best per variant (with depth and node counts)\n\n")
        f.write(best_df.to_markdown(index=False))
        f.write("\n\n> Note: 'tree_size_at_best' and 'final_tree_size' come from the progress logs at requested depth (4). 'exported_tree_nodes'/'exported_tree_depth' come from the final exported DOT tree after pruning/merging; these can be smaller/shallower when some branches are unreachable or simplify to the same action.\n")


def copy_best_trees(per_run_csv: str, out_dir: str):
    import pandas as pd
    import shutil
    trees_dir = os.path.join(out_dir, "trees")
    os.makedirs(trees_dir, exist_ok=True)
    df = pd.read_csv(per_run_csv)
    for variant, group in df.groupby("variant"):
        best_row = group.sort_values("final_best_value", ascending=False).head(1)
        if best_row.empty:
            continue
        src = best_row.iloc[0].get("tree_png")
        if isinstance(src, str) and os.path.exists(src):
            dst = os.path.join(trees_dir, f"{variant}.png")
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass


def main():
    ensure_deps()
    out_dir = os.path.join(os.getcwd(), "depth4-analysis")
    os.makedirs(out_dir, exist_ok=True)
    runs = discover_runs()
    if not runs:
        print("[error] No depth-4 (1800s) consensus-4-2 runs found under results/logs.", flush=True)
        sys.exit(1)
    print(f"[info] Found {len(runs)} runs matching depth-4/1800s:")
    for r in runs:
        print(f"  - {r['variant']} :: {r['run_id']}")
    aggregate_and_plot(runs, out_dir)
    copy_best_trees(os.path.join(out_dir, "aggregated_metrics.csv"), out_dir)
    print(f"[done] Artifacts written to: {out_dir}")


if __name__ == "__main__":
    main()
