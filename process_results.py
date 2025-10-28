#!/usr/bin/env python3
"""Aggregate PAYNT progress logs into comparison tables and plots."""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import matplotlib.pyplot as plt  # type: ignore
except Exception:  # pragma: no cover - matplotlib is optional
    plt = None  # type: ignore


@dataclass
class ProgressEntry:
    timestamp: Optional[float]
    best_value: Optional[float]
    tree_size: Optional[int]
    tree_depth: Optional[int]
    frontier_size: Optional[int]
    families_evaluated: Optional[int]
    improvement_count: Optional[int]
    lower_bound: Optional[float]
    event: str


@dataclass
class RunSummary:
    algorithm_version: str
    benchmark_name: str
    run_id: str
    timestamp_utc: Optional[str]
    timestamp_dt: Optional[datetime]
    timeout_seconds: Optional[float]
    progress: List[ProgressEntry]
    final_best_value: Optional[float]
    time_to_best: Optional[float]
    finish_time: Optional[float]
    final_tree_size: Optional[int]
    final_tree_depth: Optional[int]
    final_frontier_size: Optional[int]
    max_frontier_size: Optional[int]
    final_families_evaluated: Optional[int]
    final_improvement_count: Optional[int]
    final_lower_bound: Optional[float]
    improvement_events: int
    lower_bound_events: int
    total_events: int
    run_dir: Path


FloatPair = Tuple[float, float]


def parse_float(value: str) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_int(value: str) -> Optional[int]:
    parsed = parse_float(value)
    if parsed is None:
        return None
    try:
        return int(round(parsed))
    except (TypeError, ValueError):
        return None


def read_progress_csv(csv_path: Path) -> List[ProgressEntry]:
    entries: List[ProgressEntry] = []
    with csv_path.open("r", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            entries.append(
                ProgressEntry(
                    timestamp=parse_float(row.get("timestamp", "")),
                    best_value=parse_float(row.get("best_value", "")),
                    tree_size=parse_int(row.get("tree_size", "")),
                    tree_depth=parse_int(row.get("tree_depth", "")),
                    frontier_size=parse_int(row.get("frontier_size", "")),
                    families_evaluated=parse_int(row.get("families_evaluated", "")),
                    improvement_count=parse_int(row.get("improvement_count", "")),
                    lower_bound=parse_float(row.get("lower_bound", "")),
                    event=row.get("event", "").strip(),
                )
            )
    return entries


def last_non_none(entries: Sequence[ProgressEntry], attr: str) -> Optional[float]:
    for entry in reversed(entries):
        value = getattr(entry, attr)
        if value is not None:
            return value
    return None


def first_time_for_value(events: Sequence[Tuple[float, float]], target: float) -> Optional[float]:
    for timestamp, value in events:
        if math.isclose(value, target, rel_tol=1e-9, abs_tol=1e-9):
            return timestamp
    return None


def summarise_run(algorithm_version: str, benchmark: str, run_dir: Path) -> Optional[RunSummary]:
    progress_path = run_dir / "progress.csv"
    info_path = run_dir / "run-info.json"
    if not progress_path.is_file():
        return None
    progress = read_progress_csv(progress_path)
    if not progress:
        return None

    run_info: Dict[str, object] = {}
    timestamp_utc: Optional[str] = None
    timeout_seconds: Optional[float] = None
    if info_path.is_file():
        with info_path.open("r") as handle:
            run_info = json.load(handle)
            timestamp_utc = run_info.get("timestamp_utc")  # type: ignore[assignment]
            timeout_value = run_info.get("timeout")
            if isinstance(timeout_value, (int, float)):
                timeout_seconds = float(timeout_value)

    timestamp_dt: Optional[datetime] = None
    if isinstance(timestamp_utc, str):
        try:
            timestamp_dt = datetime.strptime(timestamp_utc, "%Y%m%d-%H%M%S")
        except ValueError:
            timestamp_dt = None

    best_events: List[Tuple[float, float]] = []
    for entry in progress:
        if entry.best_value is None:
            continue
        timestamp = entry.timestamp if entry.timestamp is not None else 0.0
        best_events.append((timestamp, entry.best_value))

    final_best_value: Optional[float] = best_events[-1][1] if best_events else None
    time_to_best: Optional[float] = None
    if final_best_value is not None:
        time_to_best = first_time_for_value(best_events, final_best_value)

    finish_time: Optional[float] = None
    for entry in progress:
        if entry.event == "finished":
            finish_time = entry.timestamp
            break

    frontier_values = [value for value in (entry.frontier_size for entry in progress) if value is not None]
    max_frontier_size = max(frontier_values) if frontier_values else None

    summary = RunSummary(
        algorithm_version=algorithm_version,
        benchmark_name=benchmark,
        run_id=run_dir.name,
        timestamp_utc=timestamp_utc,
        timestamp_dt=timestamp_dt,
        timeout_seconds=timeout_seconds,
        progress=progress,
        final_best_value=final_best_value,
        time_to_best=time_to_best,
        finish_time=finish_time,
        final_tree_size=last_non_none(progress, "tree_size"),
        final_tree_depth=last_non_none(progress, "tree_depth"),
        final_frontier_size=last_non_none(progress, "frontier_size"),
        max_frontier_size=max_frontier_size,
        final_families_evaluated=last_non_none(progress, "families_evaluated"),
        final_improvement_count=last_non_none(progress, "improvement_count"),
        final_lower_bound=last_non_none(progress, "lower_bound"),
        improvement_events=sum(1 for entry in progress if entry.event == "improvement"),
        lower_bound_events=sum(1 for entry in progress if entry.event == "lower_bound"),
        total_events=len(progress),
        run_dir=run_dir,
    )
    return summary


def collect_runs(
    algorithm_version: str,
    algorithm_root: Path,
    selected: Optional[Iterable[str]],
) -> List[RunSummary]:
    benchmarks_filter = {name for name in selected} if selected else None
    summaries: List[RunSummary] = []
    if not algorithm_root.exists():
        return summaries
    for bench_dir in sorted(p for p in algorithm_root.iterdir() if p.is_dir()):
        benchmark = bench_dir.name
        if benchmarks_filter and benchmark not in benchmarks_filter:
            continue
        for run_dir in sorted(p for p in bench_dir.iterdir() if p.is_dir()):
            summary = summarise_run(algorithm_version, benchmark, run_dir)
            if summary is not None:
                summaries.append(summary)
    return summaries


def fmt(value: Optional[float]) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def fmt_int(value: Optional[int]) -> str:
    return "" if value is None else str(value)


def safe_delta(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return a - b


def select_latest_runs(summaries: Sequence[RunSummary]) -> Dict[Tuple[str, str], RunSummary]:
    latest: Dict[Tuple[str, str], RunSummary] = {}
    for summary in summaries:
        key = (summary.algorithm_version, summary.benchmark_name)
        current = latest.get(key)
        if current is None:
            latest[key] = summary
            continue
        if summary.timestamp_dt and current.timestamp_dt:
            if summary.timestamp_dt > current.timestamp_dt:
                latest[key] = summary
        elif summary.timestamp_dt and not current.timestamp_dt:
            latest[key] = summary
        elif not summary.timestamp_dt and current.timestamp_dt:
            continue
        else:
            if summary.run_id > current.run_id:
                latest[key] = summary
    return latest


def build_series(progress: Sequence[ProgressEntry], field: str) -> List[FloatPair]:
    series: List[FloatPair] = []
    for entry in progress:
        timestamp = entry.timestamp
        value = getattr(entry, field)
        if timestamp is None or value is None:
            continue
        series.append((timestamp, float(value)))
    return series


def plot_series(
    figure_name: Path,
    benchmark: str,
    ylabel: str,
    series_data: Dict[str, List[FloatPair]],
    step: bool,
) -> None:
    if plt is None:
        return
    if not any(series_data.values()):
        return
    figure_name.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots()
    for label, data in sorted(series_data.items()):
        if not data:
            continue
        data.sort(key=lambda item: item[0])
        xs, ys = zip(*data)
        if step:
            ax.step(xs, ys, where="post", label=label)
        else:
            ax.plot(xs, ys, label=label)
    ax.set_title(f"{benchmark} — {ylabel}")
    ax.set_xlabel("time (s)")
    ax.set_ylabel(ylabel)
    ax.legend()
    ax.grid(True, linestyle="--", linewidth=0.4)
    fig.tight_layout()
    fig.savefig(figure_name, dpi=150)
    plt.close(fig)


def write_run_summary(rows: Sequence[RunSummary], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "algorithm_version",
                "benchmark_name",
                "run_id",
                "timestamp_utc",
                "timeout_seconds",
                "finish_time",
                "final_best_value",
                "final_lower_bound",
                "time_to_best",
                "final_tree_size",
                "final_tree_depth",
                "final_frontier_size",
                "max_frontier_size",
                "final_families_evaluated",
                "final_improvement_count",
                "improvement_events",
                "lower_bound_events",
                "total_events",
                "run_dir",
            ]
        )
        for summary in sorted(rows, key=lambda s: (s.algorithm_version, s.benchmark_name, s.run_id)):
            writer.writerow(
                [
                    summary.algorithm_version,
                    summary.benchmark_name,
                    summary.run_id,
                    summary.timestamp_utc or "",
                    fmt(summary.timeout_seconds),
                    fmt(summary.finish_time),
                    fmt(summary.final_best_value),
                    fmt(summary.final_lower_bound),
                    fmt(summary.time_to_best),
                    fmt_int(summary.final_tree_size),
                    fmt_int(summary.final_tree_depth),
                    fmt_int(summary.final_frontier_size),
                    fmt_int(summary.max_frontier_size),
                    fmt_int(summary.final_families_evaluated),
                    fmt_int(summary.final_improvement_count),
                    summary.improvement_events,
                    summary.lower_bound_events,
                    summary.total_events,
                    str(summary.run_dir),
                ]
            )


def write_comparison(
    latest_runs: Dict[Tuple[str, str], RunSummary],
    output_path: Path,
    algorithm_pair: Tuple[str, str],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    first_alg, second_alg = algorithm_pair
    with output_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "benchmark_name",
                f"{first_alg}_run_id",
                f"{second_alg}_run_id",
                f"{first_alg}_best_value",
                f"{second_alg}_best_value",
                "best_value_delta",
                f"{first_alg}_lower_bound",
                f"{second_alg}_lower_bound",
                "lower_bound_delta",
                f"{first_alg}_finish_time",
                f"{second_alg}_finish_time",
                "finish_time_delta",
                f"{first_alg}_time_to_best",
                f"{second_alg}_time_to_best",
                "time_to_best_delta",
                f"{first_alg}_tree_size",
                f"{second_alg}_tree_size",
                "tree_size_delta",
                f"{first_alg}_tree_depth",
                f"{second_alg}_tree_depth",
                "tree_depth_delta",
                f"{first_alg}_max_frontier",
                f"{second_alg}_max_frontier",
                "max_frontier_delta",
                f"{first_alg}_families_evaluated",
                f"{second_alg}_families_evaluated",
                "families_evaluated_delta",
                f"{first_alg}_improvement_count",
                f"{second_alg}_improvement_count",
                f"{first_alg}_improvements",
                f"{second_alg}_improvements",
                f"{first_alg}_lower_bound_events",
                f"{second_alg}_lower_bound_events",
            ]
        )
        benchmarks = sorted({key[1] for key in latest_runs})
        for benchmark in benchmarks:
            first = latest_runs.get((first_alg, benchmark))
            second = latest_runs.get((second_alg, benchmark))
            if first is None or second is None:
                continue
            writer.writerow(
                [
                    benchmark,
                    first.run_id,
                    second.run_id,
                    fmt(first.final_best_value),
                    fmt(second.final_best_value),
                    fmt(safe_delta(second.final_best_value, first.final_best_value)),
                    fmt(first.final_lower_bound),
                    fmt(second.final_lower_bound),
                    fmt(safe_delta(second.final_lower_bound, first.final_lower_bound)),
                    fmt(first.finish_time),
                    fmt(second.finish_time),
                    fmt(safe_delta(second.finish_time, first.finish_time)),
                    fmt(first.time_to_best),
                    fmt(second.time_to_best),
                    fmt(safe_delta(second.time_to_best, first.time_to_best)),
                    fmt_int(first.final_tree_size),
                    fmt_int(second.final_tree_size),
                    fmt(safe_delta(
                        float(second.final_tree_size) if second.final_tree_size is not None else None,
                        float(first.final_tree_size) if first.final_tree_size is not None else None,
                    )),
                    fmt_int(first.final_tree_depth),
                    fmt_int(second.final_tree_depth),
                    fmt(safe_delta(
                        float(second.final_tree_depth) if second.final_tree_depth is not None else None,
                        float(first.final_tree_depth) if first.final_tree_depth is not None else None,
                    )),
                    fmt_int(first.max_frontier_size),
                    fmt_int(second.max_frontier_size),
                    fmt(safe_delta(
                        float(second.max_frontier_size) if second.max_frontier_size is not None else None,
                        float(first.max_frontier_size) if first.max_frontier_size is not None else None,
                    )),
                    fmt_int(first.final_families_evaluated),
                    fmt_int(second.final_families_evaluated),
                    fmt(safe_delta(
                        float(second.final_families_evaluated) if second.final_families_evaluated is not None else None,
                        float(first.final_families_evaluated) if first.final_families_evaluated is not None else None,
                    )),
                    fmt_int(first.final_improvement_count),
                    fmt_int(second.final_improvement_count),
                    first.improvement_events,
                    second.improvement_events,
                    first.lower_bound_events,
                    second.lower_bound_events,
                ]
            )


def generate_plots(
    latest_runs: Dict[Tuple[str, str], RunSummary],
    output_dir: Path,
    algorithms: Sequence[str],
) -> None:
    if plt is None:
        return
    for benchmark in sorted({key[1] for key in latest_runs}):
        figure_dir = output_dir / benchmark
        value_series: Dict[str, List[FloatPair]] = {}
        size_series: Dict[str, List[FloatPair]] = {}
        depth_series: Dict[str, List[FloatPair]] = {}
        frontier_series: Dict[str, List[FloatPair]] = {}
        families_series: Dict[str, List[FloatPair]] = {}
        lower_bound_series: Dict[str, List[FloatPair]] = {}
        for algorithm in algorithms:
            run = latest_runs.get((algorithm, benchmark))
            if run is None:
                continue
            value_series[algorithm] = build_series(run.progress, "best_value")
            size_series[algorithm] = build_series(run.progress, "tree_size")
            depth_series[algorithm] = build_series(run.progress, "tree_depth")
            frontier_series[algorithm] = build_series(run.progress, "frontier_size")
            families_series[algorithm] = build_series(run.progress, "families_evaluated")
            lower_bound_series[algorithm] = build_series(run.progress, "lower_bound")
        if not value_series:
            continue
        plot_series(
            figure_dir / "value_vs_time.png",
            benchmark,
            "best value",
            value_series,
            step=True,
        )
        plot_series(
            figure_dir / "tree_size_vs_time.png",
            benchmark,
            "tree size",
            size_series,
            step=True,
        )
        plot_series(
            figure_dir / "tree_depth_vs_time.png",
            benchmark,
            "tree depth",
            depth_series,
            step=True,
        )
        plot_series(
            figure_dir / "frontier_size_vs_time.png",
            benchmark,
            "frontier size",
            frontier_series,
            step=True,
        )
        plot_series(
            figure_dir / "families_evaluated_vs_time.png",
            benchmark,
            "families evaluated",
            families_series,
            step=True,
        )
        plot_series(
            figure_dir / "lower_bound_vs_time.png",
            benchmark,
            "best lower bound",
            lower_bound_series,
            step=True,
        )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process PAYNT experiment logs.")
    parser.add_argument(
        "--logs-root",
        type=Path,
        default=Path("results/logs"),
        help="Root directory containing per-algorithm experiment logs.",
    )
    parser.add_argument(
        "--algo-root",
        action="append",
        dest="algorithm_roots",
        help="Optional explicit mapping in the form label=path. May be repeated.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/analysis"),
        help="Directory for generated tables and plots.",
    )
    parser.add_argument(
        "--benchmark",
        action="append",
        dest="benchmarks",
        help="Restrict processing to the specified benchmark (repeatable).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    selected = args.benchmarks

    algorithm_entries: List[Tuple[str, Path]] = []
    if args.algorithm_roots:
        for entry in args.algorithm_roots:
            if "=" not in entry:
                raise argparse.ArgumentTypeError(
                    f"Invalid --algo-root value '{entry}'. Expected format label=path."
                )
            label, path_str = entry.split("=", 1)
            label = label.strip()
            path = Path(path_str.strip())
            algorithm_entries.append((label, path))
    else:
        logs_root = args.logs_root
        if logs_root.exists():
            for candidate in sorted(p for p in logs_root.iterdir() if p.is_dir()):
                algorithm_entries.append((candidate.name, candidate))

    summaries: List[RunSummary] = []
    for label, path in algorithm_entries:
        summaries.extend(collect_runs(label, path, selected))

    if not summaries:
        print("No runs found. Check the input directories, --logs-root value, and benchmark filters.")
        return 1

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    write_run_summary(summaries, output_dir / "run_summary.csv")

    latest_runs = select_latest_runs(summaries)
    algorithm_labels = [
        label
        for label in (label for label, _ in algorithm_entries)
        if any(key[0] == label for key in latest_runs)
    ]
    comparison_pair: Optional[Tuple[str, str]] = None
    if {"original", "modified"}.issubset(set(algorithm_labels)):
        comparison_pair = ("original", "modified")
    elif len(algorithm_labels) >= 2:
        comparison_pair = (algorithm_labels[0], algorithm_labels[1])
    if comparison_pair is not None:
        write_comparison(latest_runs, output_dir / "comparison_latest.csv", comparison_pair)
    else:
        print("Skipping comparison table because fewer than two algorithms were detected.")

    generate_plots(latest_runs, output_dir / "figures", algorithm_labels)

    print(f"Processed {len(summaries)} runs. Outputs written to {output_dir}.")
    if plt is None:
        print("matplotlib not available; plots were skipped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
