#!/usr/bin/env python3

"""Utility script to run DTPAYNT experiments with structured logging."""

import json
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import click


REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_DIR = Path(__file__).resolve().parent
PAYNT_ENTRYPOINT = BASE_DIR / "paynt.py"


DEFAULT_BENCHMARKS: Dict[str, Dict[str, str]] = {
    "csma-3-4": {
        "path": "models/dts-q4/csma-3-4",
        "sketch": "model.prism",
        "props": "model.props",
        "extra_args": "--add-dont-care-action",
    },
    "consensus-4-2": {
        "path": "models/dts-q4/consensus-4-2",
        "sketch": "model.prism",
        "props": "model.props",
        "extra_args": "--add-dont-care-action",
    },
    "obstacles": {
        "path": "models/mdp/obstacles",
        "sketch": "sketch.templ",
        "props": "sketch.props",
        "extra_args": "--add-dont-care-action",
    },
    "csma-3-4-depth3": {
        "path": "models/dts-q4/csma-3-4",
        "sketch": "model.prism",
        "props": "model.props",
        "extra_args": "--add-dont-care-action --tree-depth 3",
    },
}

DEFAULT_PRESETS: List[str] = ["csma-3-4", "consensus-4-2", "obstacles"]


def detect_algorithm_version() -> str:
    parts = Path(__file__).resolve().parts
    if "synthesis-modified" in parts:
        return "modified"
    if "synthesis-original" in parts:
        return "original"
    return "unknown"


def default_output_root() -> Path:
    return REPO_ROOT / "results" / "logs"


def infer_files(benchmark_path: Path) -> Dict[str, str]:
    candidates = [
        ("model.prism", "model.props"),
        ("model.drn", "model.props"),
        ("model-random.drn", "discounted.props"),
        ("sketch.templ", "sketch.props"),
    ]
    for sketch_name, props_name in candidates:
        if (benchmark_path / sketch_name).exists() and (benchmark_path / props_name).exists():
            return {"sketch": sketch_name, "props": props_name}

    prism_files = list(benchmark_path.glob("*.prism"))
    templ_files = list(benchmark_path.glob("*.templ"))
    props_files = list(benchmark_path.glob("*.props"))

    if len(props_files) == 1:
        props_name = props_files[0].name
        if len(prism_files) == 1:
            return {"sketch": prism_files[0].name, "props": props_name}
        if len(templ_files) == 1:
            return {"sketch": templ_files[0].name, "props": props_name}

    raise click.ClickException(
        f"Unable to infer sketch/props files in {benchmark_path}. "
        "Please specify a predefined benchmark id or ensure standard filenames exist."
    )


@dataclass
class Benchmark:
    identifier: str
    path: Path
    sketch: str
    props: str
    extra_args: List[str]


def resolve_benchmark(identifier: str) -> Benchmark:
    if identifier in DEFAULT_BENCHMARKS:
        config = DEFAULT_BENCHMARKS[identifier]
        bench_path = (BASE_DIR / config["path"]).resolve()
        extra = shlex.split(config.get("extra_args", ""))
        return Benchmark(identifier, bench_path, config["sketch"], config["props"], extra)

    raw_path = Path(identifier)
    bench_path = raw_path if raw_path.is_absolute() else (BASE_DIR / raw_path)
    bench_path = bench_path.resolve()
    if not bench_path.exists():
        raise click.BadParameter(f"Benchmark path does not exist: {bench_path}")

    inferred = infer_files(bench_path)
    return Benchmark(bench_path.name, bench_path, inferred["sketch"], inferred["props"], [])


def stream_subprocess(command: List[str], cwd: Path, logfile: Path) -> int:
    logfile.parent.mkdir(parents=True, exist_ok=True)
    with logfile.open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="")
            stream.write(line)
        return process.wait()


def build_metadata_string(metadata: Dict[str, str]) -> Optional[str]:
    if not metadata:
        return None
    parts = [f"{key}={value}" for key, value in metadata.items()]
    return ",".join(parts)


@click.command()
@click.option(
    "--benchmark",
    "benchmarks",
    multiple=True,
    help="Benchmark identifier or path. If omitted, all defaults are executed.",
)
@click.option("--timeout", type=int, default=600, show_default=True, help="Timeout per run in seconds.")
@click.option(
    "--output-root",
    type=click.Path(file_okay=False, dir_okay=True, resolve_path=True),
    default=None,
    help="Directory in which experiment artefacts will be stored.",
)
@click.option(
    "--progress-interval",
    type=float,
    default=5.0,
    show_default=True,
    help="Seconds between periodic progress log rows.",
)
@click.option(
    "--extra-args",
    type=str,
    default="",
    help="Additional arguments forwarded to paynt.py (quoted string).",
)
@click.option("--force", is_flag=True, help="Do not skip runs if a destination folder already exists.")
@click.option("--list", "list_defaults", is_flag=True, help="List available default benchmarks and exit.")
def main(
    benchmarks: Iterable[str],
    timeout: int,
    output_root: Optional[str],
    progress_interval: float,
    extra_args: str,
    force: bool,
    list_defaults: bool,
):
    """Execute PAYNT experiments with structured progress logging."""

    algorithm_version = detect_algorithm_version()

    if list_defaults:
        click.echo("Available benchmark presets:")
        for key, info in DEFAULT_BENCHMARKS.items():
            extra = info.get("extra_args")
            suffix = f", extra_args=\"{extra}\"" if extra else ""
            default_tag = " (default)" if key in DEFAULT_PRESETS else ""
            click.echo(
                f"  - {key}: {info['path']} (sketch={info['sketch']}, props={info['props']}{suffix}){default_tag}"
            )
        return

    benchmarks_to_run: List[Benchmark] = []
    if benchmarks:
        for identifier in benchmarks:
            benchmarks_to_run.append(resolve_benchmark(identifier))
    else:
        for identifier in DEFAULT_PRESETS:
            benchmarks_to_run.append(resolve_benchmark(identifier))

    output_directory = Path(output_root) if output_root else default_output_root()
    target_root = output_directory / algorithm_version
    target_root.mkdir(parents=True, exist_ok=True)

    extra_args_list = shlex.split(extra_args)

    summary: List[Dict[str, str]] = []

    for benchmark in benchmarks_to_run:
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        run_id = f"{benchmark.identifier}-{timestamp}"
        run_dir = target_root / benchmark.identifier / run_id

        if run_dir.exists():
            if force:
                click.echo(f"Removing existing directory {run_dir} due to --force flag.")
                shutil.rmtree(run_dir)
            else:
                click.echo(f"Skipping {benchmark.identifier}: destination {run_dir} already exists.")
                continue

        progress_log = run_dir / "progress.csv"
        stdout_log = run_dir / "stdout.txt"

        metadata = {
            "algorithm_version": algorithm_version,
            "benchmark_name": benchmark.identifier,
            "run_id": run_id,
        }
        metadata_string = build_metadata_string(metadata)

        command: List[str] = [
            str(PAYNT_ENTRYPOINT),
            str(benchmark.path),
            "--sketch",
            benchmark.sketch,
            "--props",
            benchmark.props,
            "--timeout",
            str(timeout),
            "--progress-log",
            str(progress_log),
            "--progress-interval",
            str(progress_interval),
        ]
        if metadata_string:
            command.extend(["--progress-metadata", metadata_string])

        combined_extra_args = benchmark.extra_args + extra_args_list
        command.extend(combined_extra_args)

        # ensure run directory exists before command execution
        run_dir.mkdir(parents=True, exist_ok=True)

        run_info = {
            "benchmark_id": benchmark.identifier,
            "benchmark_path": str(benchmark.path),
            "sketch": benchmark.sketch,
            "props": benchmark.props,
            "timeout": timeout,
            "progress_interval": progress_interval,
            "algorithm_version": algorithm_version,
            "progress_log": str(progress_log),
            "stdout_log": str(stdout_log),
            "benchmark_extra_args": benchmark.extra_args,
            "cli_extra_args": extra_args_list,
            "extra_args": combined_extra_args,
            "command": command,
            "timestamp_utc": timestamp,
        }

        with (run_dir / "run-info.json").open("w", encoding="utf-8") as info_file:
            json.dump(run_info, info_file, indent=2)

        click.echo("")
        click.echo(f"Running {benchmark.identifier} (timeout={timeout}s)...")
        exit_code = stream_subprocess(["python3"] + command, BASE_DIR, stdout_log)
        if exit_code != 0:
            raise click.ClickException(
                f"PAYNT execution failed for {benchmark.identifier} with exit code {exit_code}."
            )

        summary.append(
            {
                "benchmark": benchmark.identifier,
                "run_dir": str(run_dir),
                "progress_log": str(progress_log),
                "extra_args": " ".join(combined_extra_args),
            }
        )

    if summary:
        click.echo("\nCompleted runs:")
        for record in summary:
            click.echo(
                f"  - {record['benchmark']}: progress={record['progress_log']} (artefacts in {record['run_dir']})"
                + (f" extra_args={record['extra_args']}" if record.get("extra_args") else "")
            )
    else:
        click.echo("No experiments were executed.")


if __name__ == "__main__":
    main()
