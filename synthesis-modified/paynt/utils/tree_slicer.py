from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Union

import logging

from paynt.quotient.mdp import DecisionTree, DecisionTreeNode

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PathConstraint:
    variable: str
    operator: str
    value: Union[int, str]


@dataclass
class SubProblem:
    root_identifier: int
    subtree: DecisionTree
    path_condition: List[PathConstraint]
    original_nonterminal_count: int


@dataclass
class SubProblemTemplate:
    max_depth: int
    path_condition: List[PathConstraint]


def extract_subproblems(
    tree: DecisionTree,
    max_depth: int,
    *,
    min_subtree_depth: int = 2,
) -> List[SubProblem]:
    candidates: List[SubProblem] = []
    queue: List[tuple[DecisionTreeNode, int]] = [(tree.root, 0)]
    while queue:
        node, depth = queue.pop(0)
        if node.is_terminal:
            continue
        subtree_depth = node.get_depth()
        if depth < max_depth and subtree_depth >= min_subtree_depth:
            subtree = DecisionTree(tree.quotient, tree.variables)
            subtree.root = node.copy(None)
            subtree.root.assign_identifiers()
            constraints = [_parse_branch_expression(expr) for expr in node.path_expression(tree.variables)]
            nonterminals = len(subtree.collect_nonterminals())
            candidates.append(
                SubProblem(
                    root_identifier=node.identifier,
                    subtree=subtree,
                    path_condition=constraints,
                    original_nonterminal_count=nonterminals,
                )
            )
        queue.append((node.child_true, depth + 1))
        queue.append((node.child_false, depth + 1))
    return candidates


def generate_constrained_template(subproblem: SubProblem, max_depth: int) -> SubProblemTemplate:
    target_depth = max(1, min(max_depth, subproblem.subtree.get_depth()))
    return SubProblemTemplate(max_depth=target_depth, path_condition=subproblem.path_condition.copy())


def replace_subtree(
    main_tree: DecisionTree,
    original_sub_tree: SubProblem,
    new_sub_tree: DecisionTree,
) -> DecisionTree:
    if original_sub_tree.root_identifier == main_tree.root.identifier:
        replacement_root = new_sub_tree.root.copy(None)
        replacement_root.fix_with_respect_to_quotient(
            new_sub_tree.quotient,
            main_tree.quotient,
        )
        main_tree.root = replacement_root
    else:
        main_tree.append_tree_as_subtree(
            new_sub_tree,
            original_sub_tree.root_identifier,
            new_sub_tree.quotient,
        )
    main_tree.root.assign_identifiers()
    return main_tree


def optimise_subproblem_structure(
    subproblem: SubProblem,
    template: SubProblemTemplate,
) -> DecisionTree:
    optimised = DecisionTree(subproblem.subtree.quotient, subproblem.subtree.variables)
    optimised.root = _prune_node(subproblem.subtree.root, template.max_depth, current_depth=0)
    optimised.root.assign_identifiers()
    return optimised


def estimate_policy_loss(reference: DecisionTree, candidate: DecisionTree) -> float:
    reference_actions = _collect_leaf_actions(reference.root, reference.variables)
    candidate_actions = _collect_leaf_actions(candidate.root, candidate.variables)
    all_paths = set(reference_actions) | set(candidate_actions)
    if not all_paths:
        return 0.0

    changed = 0
    for path in all_paths:
        reference_action = reference_actions.get(path)
        candidate_action = candidate_actions.get(path)
        if reference_action is None:
            reference_action = _evaluate_action_for_path(reference.root, path, reference.variables)
        if candidate_action is None:
            candidate_action = _evaluate_action_for_path(candidate.root, path, candidate.variables)
        if reference_action != candidate_action:
            changed += 1
    return changed / len(all_paths)


# --- helpers -----------------------------------------------------------------


def _parse_branch_expression(expression: str) -> PathConstraint:
    cleaned = expression.replace(" ", "")
    if "<=" in cleaned:
        variable, value = cleaned.split("<=", 1)
        op = "<="
    elif ">" in cleaned:
        variable, value = cleaned.split(">", 1)
        op = ">"
    else:  # pragma: no cover - defensive
        raise ValueError(f"Unsupported branch expression '{expression}'.")
    try:
        numeric: Union[int, str] = int(float(value))
    except ValueError:
        numeric = value
    return PathConstraint(variable=variable, operator=op, value=numeric)


def _prune_node(node: DecisionTreeNode, max_depth: int, current_depth: int) -> DecisionTreeNode:
    if node.is_terminal:
        leaf = DecisionTreeNode(None)
        leaf.action = node.action
        return leaf

    if current_depth >= max_depth:
        leaf = DecisionTreeNode(None)
        leaf.action = _majority_action(node)
        return leaf

    true_child = _prune_node(node.child_true, max_depth, current_depth + 1)
    false_child = _prune_node(node.child_false, max_depth, current_depth + 1)

    if true_child.is_terminal and false_child.is_terminal and true_child.action == false_child.action:
        merged = DecisionTreeNode(None)
        merged.action = true_child.action
        return merged

    branch = DecisionTreeNode(None)
    branch.variable = node.variable
    branch.variable_bound = node.variable_bound
    branch.child_true = true_child
    branch.child_false = false_child
    true_child.parent = branch
    false_child.parent = branch
    return branch


def _majority_action(node: DecisionTreeNode) -> int:
    actions = _collect_actions(node)
    if not actions:  # pragma: no cover - defensive
        logger.debug("No actions found in subtree; defaulting to zero.")
        return 0
    histogram: Dict[int, int] = {}
    for action in actions:
        histogram[action] = histogram.get(action, 0) + 1
    majority = max(histogram.items(), key=lambda item: item[1])[0]
    return majority


def _collect_actions(node: DecisionTreeNode) -> List[int]:
    if node.is_terminal:
        return [node.action]
    return _collect_actions(node.child_true) + _collect_actions(node.child_false)


def _collect_leaf_actions(node: DecisionTreeNode, variables) -> Dict[tuple[str, ...], int]:
    mapping: Dict[tuple[str, ...], int] = {}

    def _collect(current: DecisionTreeNode):
        if current.is_terminal:
            path = tuple(current.path_expression(variables))
            mapping[path] = current.action
            return
        _collect(current.child_true)
        _collect(current.child_false)

    _collect(node)
    return mapping


def _evaluate_action_for_path(
    node: DecisionTreeNode,
    path: tuple[str, ...],
    variables,
) -> int:
    current = node
    for expr in path:
        if current.is_terminal:
            return current.action
        constraint = _parse_branch_expression(expr)
        if current.variable is None:
            break
        var_name = variables[current.variable].name
        if constraint.variable != var_name:
            break
        if constraint.operator == "<=":
            current = current.child_true
        else:
            current = current.child_false
    if current.is_terminal:
        return current.action
    return _majority_action(current)
