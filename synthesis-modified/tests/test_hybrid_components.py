import math
from dataclasses import dataclass

import pytest

from paynt.parser.dot_parser import parse_dot
from paynt.utils.tree_slicer import (
    SubProblem,
    estimate_policy_loss,
    extract_subproblems,
    generate_constrained_template,
    optimise_subproblem_structure,
    replace_subtree,
)

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


def build_dummy_quotient() -> DummyQuotient:
    return DummyQuotient(
        variables=[DummyVariable("x", [0, 1, 2])],
        action_labels=["stay", "move"],
    )


def build_sample_tree(quotient):
    from paynt.quotient.mdp import DecisionTree

    tree = DecisionTree(quotient, quotient.variables)
    root = tree.root
    root.add_children()
    root.variable = 0
    root.variable_bound = 0
    root.child_true.action = 0
    root.child_false.add_children()
    root.child_false.variable = 0
    root.child_false.variable_bound = 1
    root.child_false.child_true.action = 0
    root.child_false.child_false.action = 1
    tree.root.assign_identifiers()
    return tree


@pytest.mark.skipif(pydot is None, reason="pydot not available")
def test_parse_dot_builds_expected_tree_structure():
    quotient = build_dummy_quotient()
    dot = """
    digraph Tree {
        0 [label="x <= 1"];
        1 [label="action: stay"];
        2 [label="move"];
        0 -> 1 [label="True"];
        0 -> 2 [label="False"];
    }
    """
    tree = parse_dot(dot, quotient)
    assert tree.root.variable == 0
    assert tree.root.child_true.action == 0
    assert tree.root.child_false.action == 1


def test_extract_subproblems_and_replace_subtree():
    quotient = build_dummy_quotient()
    tree = build_sample_tree(quotient)

    subproblems = extract_subproblems(tree, max_depth=1, min_subtree_depth=2)
    assert len(subproblems) == 1
    sub = subproblems[0]
    assert isinstance(sub.path_condition, list)
    assert sub.path_condition == []

    from paynt.quotient.mdp import DecisionTree

    replacement = DecisionTree(quotient, quotient.variables)
    replacement.root.action = 0

    replace_subtree(tree, sub, replacement)
    assert tree.root.is_terminal
    assert tree.root.action == 0


def test_optimise_subproblem_structure_reduces_tree_depth():
    quotient = build_dummy_quotient()
    tree = build_sample_tree(quotient)
    subproblem = extract_subproblems(tree, max_depth=1, min_subtree_depth=2)[0]
    from paynt.utils.tree_slicer import SubProblemTemplate

    template = SubProblemTemplate(max_depth=0, path_condition=subproblem.path_condition)

    candidate = optimise_subproblem_structure(subproblem, template)
    assert candidate.get_depth() == template.max_depth
    loss = estimate_policy_loss(subproblem.subtree, candidate)
    assert math.isclose(loss, 0.25, rel_tol=1e-6)
