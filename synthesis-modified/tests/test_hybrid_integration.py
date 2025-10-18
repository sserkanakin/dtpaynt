import shutil
from dataclasses import dataclass

import pytest

from hybrid_synthesis import HybridConfig, execute_hybrid
from paynt.parser.dot_parser import parse_dot
from paynt.utils.tree_slicer import estimate_policy_loss

try:
    import pydot  # type: ignore
except ImportError:  # pragma: no cover
    pydot = None


@dataclass
class DummyVariable:
    name: str
    domain: list[int]


@dataclass
class DummyQuotient:
    variables: list[DummyVariable]
    action_labels: list[str]


def build_test_quotient():
    return DummyQuotient(
        variables=[
            DummyVariable("x", [0, 1]),
            DummyVariable("y", [0, 1, 2]),
        ],
        action_labels=["stay", "move"],
    )


@pytest.mark.skipif(pydot is None, reason="pydot not available")
def test_execute_hybrid_reduces_tree_size():
    quotient = build_test_quotient()
    dot = """
    digraph Tree {
        0 [label="x <= 0"];
        1 [label="stay"];
        2 [label="y <= 1"];
        3 [label="move"];
        4 [label="move"];
        0 -> 1 [label="True"];
        0 -> 2 [label="False"];
        2 -> 3 [label="True"];
        2 -> 4 [label="False"];
    }
    """
    initial_tree = parse_dot(dot, quotient)
    config = HybridConfig(hybrid_enabled=True, max_subtree_depth=2, min_subtree_depth=1, max_loss=0.1)
    optimised_tree, replacements = execute_hybrid(quotient, dot, config)

    assert len(replacements) == 2
    root_ids = {sub.root_identifier for sub, _, _ in replacements}
    assert root_ids == {0, 2}
    assert len(optimised_tree.collect_nonterminals()) < len(initial_tree.collect_nonterminals())
    assert estimate_policy_loss(initial_tree, optimised_tree) <= config.max_loss


@pytest.mark.skipif(pydot is None, reason="pydot not available")
@pytest.mark.skipif(shutil.which("dtcontrol") is None, reason="dtcontrol binary not found")
def test_full_pipeline_with_dtcontrol(tmp_path, monkeypatch):
    from hybrid_synthesis import main

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "model.prism").write_text("// dummy model", encoding="utf-8")
    (project_dir / "model.props").write_text("// dummy props", encoding="utf-8")

    dummy_quotient = build_test_quotient()
    dummy_dot = """
    digraph Tree {
        0 [label="x <= 0"];
        1 [label="stay"];
        2 [label="move"];
        0 -> 1 [label="True"];
        0 -> 2 [label="False"];
    }
    """

    monkeypatch.setattr("hybrid_synthesis.Sketch.load_sketch", lambda *_, **__: dummy_quotient)
    monkeypatch.setattr("hybrid_synthesis.run_dtcontrol", lambda *_, **__: dummy_dot)

    args = [
        str(project_dir),
        "--prism",
        "model.prism",
        "--prop",
        "model.props",
        "--output",
        str(project_dir / "out.dot"),
    ]
    exit_code = main(args)
    assert exit_code == 0
