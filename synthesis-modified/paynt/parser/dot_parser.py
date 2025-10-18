"""
DOT Parser for Decision Trees

This module provides functionality to parse DOT graph format output from dtcontrol
and convert it into DecisionTree objects compatible with the PAYNT framework.
"""

import re
import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


class DotTreeNode:
    """Intermediate representation of a node in DOT format."""
    
    def __init__(self, node_id: str):
        self.id = node_id
        self.is_leaf = False
        self.label = None
        self.attributes = {}
        
    def __repr__(self):
        return f"DotTreeNode({self.id}, leaf={self.is_leaf}, label={self.label})"


class DotParser:
    """Parser for DOT format decision trees."""
    
    @staticmethod
    def parse_dot(dot_string: str) -> Dict:
        """
        Parse a DOT format string into a tree structure.
        
        Args:
            dot_string: The DOT format graph string from dtcontrol
            
        Returns:
            A dictionary representation of the tree with nodes and edges
            
        Raises:
            ValueError: If the DOT string cannot be parsed
        """
        nodes = {}
        edges = []
        root_id = None
        
        lines = dot_string.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('digraph') or line.startswith('}') or line == '{':
                continue
            
            # Parse node definitions
            if '->' in line:
                # Edge definition
                match = re.match(r'(\w+)\s*->\s*(\w+)\s*\[?([^\]]*)\]?', line)
                if match:
                    src, dst = match.group(1), match.group(2)
                    attrs = match.group(3) if match.group(3) else ""
                    edges.append({'src': src, 'dst': dst, 'attrs': attrs})
                    if root_id is None:
                        root_id = src
                    if src not in nodes:
                        nodes[src] = DotTreeNode(src)
                    if dst not in nodes:
                        nodes[dst] = DotTreeNode(dst)
            else:
                # Node definition
                match = re.match(r'(\w+)\s*\[([^\]]*)\]', line)
                if match:
                    node_id = match.group(1)
                    attrs_str = match.group(2)
                    
                    if node_id not in nodes:
                        nodes[node_id] = DotTreeNode(node_id)
                    
                    # Parse node attributes
                    label_match = re.search(r'label\s*=\s*"([^"]*)"', attrs_str)
                    if label_match:
                        nodes[node_id].label = label_match.group(1)
                    
                    # Check if it's a leaf node (has shape=ellipse or is a terminal)
                    if 'shape=ellipse' in attrs_str or 'color=green' in attrs_str:
                        nodes[node_id].is_leaf = True
                    
                    # Store other attributes
                    for attr in attrs_str.split(','):
                        if '=' in attr:
                            key, value = attr.split('=', 1)
                            nodes[node_id].attributes[key.strip()] = value.strip()
        
        if root_id is None and nodes:
            root_id = list(nodes.keys())[0]
        
        return {
            'nodes': nodes,
            'edges': edges,
            'root_id': root_id
        }
    
    @staticmethod
    def build_tree_structure(parsed_dot: Dict) -> Dict:
        """
        Build a hierarchical tree structure from parsed DOT data.
        
        Args:
            parsed_dot: Dictionary from parse_dot()
            
        Returns:
            A tree structure with parent-child relationships
        """
        nodes = parsed_dot['nodes']
        edges = parsed_dot['edges']
        root_id = parsed_dot['root_id']
        
        # Build adjacency information
        children_map = {}
        for node_id in nodes:
            children_map[node_id] = {'true': None, 'false': None}
        
        # Map edges to true/false branches
        for i, edge in enumerate(edges):
            src, dst = edge['src'], edge['dst']
            # Try to determine if it's true or false branch from attributes
            attrs = edge['attrs']
            if 'label' in attrs:
                label_match = re.search(r'label\s*=\s*"([^"]*)"', attrs)
                if label_match:
                    label = label_match.group(1)
                    if 'true' in label.lower() or 'yes' in label.lower():
                        children_map[src]['true'] = dst
                    elif 'false' in label.lower() or 'no' in label.lower():
                        children_map[src]['false'] = dst
                    else:
                        # Default: first edge is true, second is false
                        if children_map[src]['true'] is None:
                            children_map[src]['true'] = dst
                        else:
                            children_map[src]['false'] = dst
            else:
                # Default: first edge is true, second is false
                if children_map[src]['true'] is None:
                    children_map[src]['true'] = dst
                else:
                    children_map[src]['false'] = dst
        
        return {
            'nodes': nodes,
            'children_map': children_map,
            'root_id': root_id
        }


def extract_decision_test(label: str) -> Optional[Tuple[str, str]]:
    """
    Extract variable and test from a node label.
    
    Expected format: "variable <= value" or similar
    
    Args:
        label: The node label string
        
    Returns:
        Tuple of (variable_name, operator_and_value) or None
    """
    if not label:
        return None
    
    # Try to match patterns like "x <= 5" or "state < 3"
    match = re.search(r'(\w+)\s*([<>=]+)\s*([\d.]+)', label)
    if match:
        var_name = match.group(1)
        operator = match.group(2)
        value = match.group(3)
        return (var_name, f"{operator}{value}")
    
    return None


def extract_action(label: str) -> Optional[str]:
    """
    Extract action name from a leaf node label.
    
    Expected format: "action: name" or similar
    
    Args:
        label: The node label string
        
    Returns:
        Action name or None
    """
    if not label:
        return None
    
    # Try to match patterns like "action: a0" or "choose: action1"
    match = re.search(r'(?:action|choose):\s*(\w+)', label, re.IGNORECASE)
    if match:
        return match.group(1)
    
    # Fallback: just take the label as action if it looks like an action
    if label and not any(op in label for op in ['<=', '<', '>', '>=', '==']):
        return label
    
    return None
