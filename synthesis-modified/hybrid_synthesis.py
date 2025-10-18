#!/usr/bin/env python3

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Tuple

from paynt.parser.dot_parser import parse_dot
from paynt.parser.sketch import Sketch
from paynt.quotient.mdp import DecisionTree
from paynt.synthesizer.synthesizer_ar import SynthesizerAR
from paynt.utils.tree_slicer import (
    SubProblem,
    SubProblemTemplate,
    extract_subproblems,
    generate_constrained_template,
    replace_subtree,
)

logger = logging.getLogger(__name__)


@dataclass
class HybridConfig:
    hybrid_enabled: bool = True
    max_subtree_depth: int = 3
    min_subtree_depth: int = 2
    max_loss: float = 0.05


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


def run_dtcontrol(
    dtcontrol_bin: str,
    prism_model: str,
    properties: str,
    *,
    timeout: int | None = None,
) -> str:
    command = [
        dtcontrol_bin,
        "--prism",
        prism_model,
        "--prop",
        properties,
        "--export-dot",
        "-",
    ]
    logger.info("Running dtcontrol: %s", " ".join(command))
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.CalledProcessError as exc:  # pragma: no cover - defensive
        logger.error("dtcontrol execution failed: %s", exc.stderr)
        raise RuntimeError("dtcontrol execution failed") from exc
    except subprocess.TimeoutExpired as exc:  # pragma: no cover
        logger.error("dtcontrol timed out after %s seconds", timeout)
        raise RuntimeError("dtcontrol timed out") from exc
    return result.stdout


def execute_hybrid(
    quotient,
    dot_string: str,
    config: HybridConfig,

) -> Tuple[DecisionTree, List[Tuple[SubProblem, SubProblemTemplate, float]]]:

    initial_tree = parse_dot(dot_string, quotient)
    logger.info(
        "Initial dtcontrol tree depth=%s nonterminals=%s",
        initial_tree.get_depth(),
        len(initial_tree.collect_nonterminals()),
    )
    if not config.hybrid_enabled:
        return initial_tree, []

    subproblems = extract_subproblems(
        initial_tree,
        config.max_subtree_depth,
        min_subtree_depth=config.min_subtree_depth,
    )
    logger.info("Identified %d candidate sub-problems.", len(subproblems))

    replacements: List[Tuple[SubProblem, SubProblemTemplate, float]] = []
    for subproblem in subproblems:
        template = generate_constrained_template(subproblem, config.max_subtree_depth)
        synthesizer = SynthesizerAR(quotient, path_condition=template.path_condition)
        candidate, loss, improved = synthesizer.optimize_subtree(
            subproblem, template, config.max_loss
        )
        if improved:
            replace_subtree(initial_tree, subproblem, candidate)
            replacements.append((subproblem, template, loss))
            logger.info(
                "Replaced subtree @%s -> depth=%s nodes=%s loss=%.4f",
                subproblem.root_identifier,
                candidate.get_depth(),
                len(candidate.collect_nonterminals()),
                loss,
            )
        else:
            logger.debug(
                "Skipped subtree @%s (loss %.4f, improved=%s)",
                subproblem.root_identifier,
                loss,
                improved,
            )

    initial_tree.root.assign_identifiers()
    logger.info(
        "Hybrid tree depth=%s nonterminals=%s",
        initial_tree.get_depth(),
        len(initial_tree.collect_nonterminals()),
    )
    return initial_tree, replacements


def save_tree(tree, output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    graph = tree.to_graphviz()
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(graph.source)
    logger.info("Saved final decision tree to %s", output_path)


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hybrid Paynt + dtcontrol synthesis")
    parser.add_argument("project", help="Project directory containing the model and properties.")
    parser.add_argument("--prism", default="model.prism", help="Relative path to the PRISM model.")
    parser.add_argument("--prop", default="model.props", help="Relative path to PRISM properties.")
    parser.add_argument("--dtcontrol-bin", default="dtcontrol", help="dtcontrol executable.")
    parser.add_argument("--initial-dot", help="Path to a pre-computed dtcontrol DOT file.")
    parser.add_argument("--output", default="hybrid_tree.dot", help="Output path for the DOT tree.")
    parser.add_argument(
        "--hybrid-enabled",
        action="store_true",
        default=True,
        help="Enable hybrid refinement.",
    )
    parser.add_argument(
        "--no-hybrid",
        action="store_false",
        dest="hybrid_enabled",
        help="Disable hybrid refinement and keep the dtcontrol tree.",
    )
    parser.add_argument(
        "--max-subtree-depth",
        type=int,
        default=3,
        help="Maximum depth of subtrees considered for optimisation.",
    )
    parser.add_argument(
        "--min-subtree-depth",
        type=int,
        default=2,
        help="Minimum depth a subtree must have to be considered for optimisation.",
    )
    parser.add_argument(
        "--max-loss",
        type=float,
        default=0.05,
        help="Maximum tolerated relative loss when replacing a subtree.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging verbosity level.",
    )
    parser.add_argument(
        "--dtcontrol-timeout",
        type=int,
        default=None,
        help="Timeout (seconds) for dtcontrol execution.",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    configure_logging(args.log_level)

    prism_model = os.path.join(args.project, args.prism)
    properties = os.path.join(args.project, args.prop)

    if not os.path.exists(prism_model):
        raise FileNotFoundError(f"PRISM model not found: {prism_model}")
    if not os.path.exists(properties):
        raise FileNotFoundError(f"Properties file not found: {properties}")

    quotient = Sketch.load_sketch(prism_model, properties)

    if args.initial_dot:
        with open(args.initial_dot, "r", encoding="utf-8") as handle:
            dot_string = handle.read()
    else:
        dot_string = run_dtcontrol(
            args.dtcontrol_bin,
            prism_model,
            properties,
            timeout=args.dtcontrol_timeout,
        )

    config = HybridConfig(
        hybrid_enabled=args.hybrid_enabled,
        max_subtree_depth=args.max_subtree_depth,
        min_subtree_depth=args.min_subtree_depth,
        max_loss=args.max_loss,
    )

    tree, _ = execute_hybrid(quotient, dot_string, config)
    save_tree(tree, args.output)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
