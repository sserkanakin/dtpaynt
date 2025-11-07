#!/usr/bin/env python3
"""
Scan results/logs for consensus-4-2 runs and report status by variant and depth.

Status rules:
- finished: progress.csv contains a row with event == 'finished'.
- running: no 'finished' and progress.csv mtime < 5 minutes ago (still updating).
- stalled/ended: no 'finished' and progress.csv older than 5 minutes.

Outputs:
- prints a compact summary to stdout
- writes results/analysis/run_status.csv with details
"""

from __future__ import annotations

import csv
import json
import os
import time
from glob import glob
from typing import Dict, List, Tuple


def extract_depth(args: List[str]) -> int | None:
    try:
        for i, a in enumerate(args):
            if a == "--tree-depth":
                return int(args[i + 1])
    except Exception:
        return None
    return None


def read_run_info(path: str) -> Dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            info = json.load(f)
        depth = extract_depth(info.get("cli_extra_args", [])) or extract_depth(info.get("extra_args", []))
        info["tree_depth"] = depth
        return info
    except Exception:
        return {}


def progress_has_finished(prog_path: str) -> bool:
    try:
        with open(prog_path, "r", encoding="utf-8") as f:
            # light scan for ',finished,'
            for line in f:
                if ",finished," in line:
                    return True
    except Exception:
        return False
    return False


def progress_mtime_seconds(prog_path: str) -> float:
    try:
        return time.time() - os.path.getmtime(prog_path)
    except Exception:
        return float("inf")


def main():
    base = os.path.join("results", "logs")
    pattern = os.path.join(base, "*", "consensus-4-2", "*", "run-info.json")
    run_infos = glob(pattern)
    rows = []
    for run_info_path in run_infos:
        info = read_run_info(run_info_path)
        if not info or info.get("benchmark_id") != "consensus-4-2":
            continue
        algo = info.get("algorithm_version", "unknown")
        timeout = info.get("timeout")
        depth = info.get("tree_depth")
        run_dir = os.path.dirname(run_info_path)
        run_id = os.path.basename(run_dir)
        progress = os.path.join(run_dir, "progress.csv")
        tree_png = os.path.join(run_dir, "tree.png")

        finished = progress_has_finished(progress)
        m_age = progress_mtime_seconds(progress)
        if finished:
            status = "finished"
        else:
            # consider running if recently updated (< 300s)
            status = "running" if m_age < 300 else "stalled/ended"

        rows.append({
            "variant": algo,
            "depth": depth,
            "timeout": timeout,
            "run_id": run_id,
            "status": status,
            "progress_age_sec": round(m_age if m_age != float("inf") else -1, 1),
            "tree_png_exists": os.path.exists(tree_png),
            "progress_exists": os.path.exists(progress),
            "run_dir": run_dir,
        })

    # write CSV
    out_dir = os.path.join("results", "analysis")
    os.makedirs(out_dir, exist_ok=True)
    out_csv = os.path.join(out_dir, "run_status.csv")
    if rows:
        keys = list(rows[0].keys())
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)

    # print compact summary by (variant, depth)
    summary: Dict[Tuple[str, int], Dict[str, int]] = {}
    for r in rows:
        k = (r["variant"], r["depth"])
        d = summary.setdefault(k, {"finished": 0, "running": 0, "stalled/ended": 0})
        d[r["status"]] += 1

    # Order by depth then variant
    ordered = sorted(summary.items(), key=lambda kv: (kv[0][1] or 0, kv[0][0]))
    print("Variant/Depth status summary (finished | running | stalled):")
    for (variant, depth), counts in ordered:
        print(f"- depth {depth:<2} :: {variant:<28}  {counts['finished']:>2} | {counts['running']:>2} | {counts['stalled/ended']:>2}")
    if rows:
        print(f"\nDetails written to {out_csv}")
    else:
        print("No runs found under results/logs.")


if __name__ == "__main__":
    main()
