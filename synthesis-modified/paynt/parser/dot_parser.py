import logging
from typing import Dict, List, Optional, Tuple

from paynt.quotient.mdp import DecisionTree, DecisionTreeNode

logger = logging.getLogger(__name__)

try:
    import pydot  # type: ignore
except ImportError:  # pragma: no cover - handled in tests
    pydot = None  # type: ignore


TRUE_EDGE_LABELS = {"true", "True", "TRUE", "t", "T", "1"}
FALSE_EDGE_LABELS = {"false", "False", "FALSE", "f", "F", "0"}


def parse_dot(dot_string: str, quotient=None) -> DecisionTree:
    """
    Parse a DOT-formatted decision tree produced by dtcontrol into a DecisionTree instance.

    Args:
        dot_string: DOT representation of the tree.
        quotient: Quotient object providing variable and action metadata.
    """
    if pydot is None:
        raise ImportError(
            "pydot is required to parse DOT decision trees. "
            "Install it via `pip install pydot`."
        )
    if quotient is None:
        raise ValueError("A quotient instance must be supplied to rebuild the decision tree.")

    graphs = pydot.graph_from_dot_data(dot_string)
    if not graphs:  # pragma: no cover - defensive
        raise ValueError("Unable to parse DOT data into a graph.")

    graph = graphs[0]
    raw_nodes = {
        node.get_name().strip('"'): node
        for node in graph.get_nodes()
        if node.get_name() not in {"node", "graph", "edge"}
    }
    if not raw_nodes:
        raise ValueError("DOT graph contains no decision nodes.")

    edges: Dict[str, List[Tuple[str, Optional[str]]]] = {}
    destinations = set()
    for edge in graph.get_edges():
        src = edge.get_source().strip('"')
        dst = edge.get_destination().strip('"')
        label = edge.get_attributes().get("label")
        edges.setdefault(src, []).append((dst, label))
        destinations.add(dst)

    # assume a single root (node without an incoming edge)
    root_candidates = [node_id for node_id in raw_nodes.keys() if node_id not in destinations]
    if not root_candidates:
        raise ValueError("DOT graph does not expose a root node (no node without incoming edges).")
    root_id = root_candidates[0]

    decision_tree = DecisionTree(quotient, quotient.variables)
    decision_tree.root = _build_tree(
        node_id=root_id,
        parent=None,
        raw_nodes=raw_nodes,
        edges=edges,
        quotient=quotient,
    )
    decision_tree.root.assign_identifiers()
    return decision_tree


def _build_tree(
    node_id: str,
    parent: Optional[DecisionTreeNode],
    raw_nodes: Dict[str, "pydot.Node"],
    edges: Dict[str, List[Tuple[str, Optional[str]]]],
    quotient,
) -> DecisionTreeNode:
    dot_node = raw_nodes[node_id]
    label = dot_node.get_attributes().get("label", "")
    label = label.strip('"')

    dt_node = DecisionTreeNode(parent)

    if _is_leaf_label(label, quotient.action_labels):
        action_name = _normalise_leaf_label(label)
        dt_node.action = _resolve_action_index(action_name, quotient.action_labels)
        return dt_node

    variable_name, bound_value = _parse_split_label(label)
    dt_node.variable = _resolve_variable_index(variable_name, quotient.variables)
    dt_node.variable_bound = _resolve_bound_index(
        dt_node.variable, bound_value, quotient.variables
    )

    children = edges.get(node_id, [])
    if len(children) != 2:
        raise ValueError(
            f"Node '{node_id}' does not have exactly two children; got {len(children)}."
        )

    true_child_id = _pick_child(children, prefer_true=True)
    false_child_id = _pick_child(children, prefer_true=False)

    dt_node.child_true = _build_tree(true_child_id, dt_node, raw_nodes, edges, quotient)
    dt_node.child_false = _build_tree(false_child_id, dt_node, raw_nodes, edges, quotient)
    return dt_node


def _pick_child(children: List[Tuple[str, Optional[str]]], prefer_true: bool) -> str:
    fallback = children[0 if prefer_true else 1][0]
    for candidate, label in children:
        if label is None:
            continue
        clean_label = label.strip('"').strip()
        if prefer_true and clean_label in TRUE_EDGE_LABELS:
            return candidate
        if not prefer_true and clean_label in FALSE_EDGE_LABELS:
            return candidate
    return fallback


def _is_leaf_label(label: str, action_labels: List[str]) -> bool:
    cleaned = label.replace('"', "").strip()
    if cleaned in action_labels:
        return True
    return cleaned.lower().startswith("action:")


def _normalise_leaf_label(label: str) -> str:
    cleaned = label.replace('"', "").strip()
    if cleaned.lower().startswith("action:"):
        return cleaned.split(":", 1)[1].strip()
    return cleaned


def _resolve_action_index(action_name: str, action_labels: List[str]) -> int:
    if action_name not in action_labels:
        raise ValueError(f"Leaf action '{action_name}' not found in quotient action labels.")
    return action_labels.index(action_name)


def _parse_split_label(label: str) -> Tuple[str, str]:
    primary_line = label.splitlines()[0]
    cleaned = primary_line.replace(" ", "")
    if "<=" in cleaned:
        variable, value = cleaned.split("<=", 1)
    elif ">" in cleaned:
        variable, value = cleaned.split(">", 1)
    else:
        raise ValueError(f"Cannot parse internal node label '{label}'.")
    return variable, value


def _resolve_variable_index(variable_name: str, variables) -> int:
    for index, variable in enumerate(variables):
        if variable.name == variable_name:
            return index
    raise ValueError(f"Variable '{variable_name}' referenced in DOT tree is unknown.")


def _resolve_bound_index(variable_index: int, bound_value: str, variables) -> int:
    domain = variables[variable_index].domain
    try:
        numeric_bound = type(domain[0])(float(bound_value))  # type: ignore[arg-type]
    except (ValueError, TypeError):
        numeric_bound = bound_value
    for index, candidate in enumerate(domain):
        if str(candidate) == str(numeric_bound):
            return index
    # fallback: try integer conversion if domain stores ints
    try:
        as_int = int(float(bound_value))
        return domain.index(as_int)
    except (ValueError, TypeError):
        pass
    raise ValueError(
        f"Bound '{bound_value}' for variable '{variables[variable_index].name}' is not in the domain."
    )
