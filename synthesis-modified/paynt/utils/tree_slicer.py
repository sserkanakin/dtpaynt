"""
Tree Slicer Utility for Hybrid Synthesis

This module provides functions to extract sub-problems from large decision trees,
generate constrained tree templates for DTPAYNT synthesis, and reconstruct trees
with optimized sub-trees.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PathCondition:
    """Represents the path taken to reach a node in the tree."""
    
    decisions: List[Dict[str, Any]]  # List of {'variable': str, 'operator': str, 'value': Any}
    
    def __repr__(self):
        return f"PathCondition({len(self.decisions)} decisions)"
    
    def to_string(self) -> str:
        """Convert path condition to human-readable string."""
        if not self.decisions:
            return "root"
        parts = []
        for decision in self.decisions:
            parts.append(f"{decision['variable']}{decision['operator']}{decision['value']}")
        return " AND ".join(parts)


@dataclass
class SubProblem:
    """Represents a sub-tree optimization task."""
    
    sub_tree_node: Any  # Reference to the sub-tree root node in DecisionTree
    path_condition: PathCondition  # Path from main tree root to this sub-tree
    depth: int  # Depth of the sub-tree
    node_count: int  # Number of non-terminal nodes in the sub-tree
    tree_path: List[Any]  # Path of node identifiers from root to this sub-tree
    
    def __repr__(self):
        return f"SubProblem(depth={self.depth}, nodes={self.node_count}, path={self.path_condition.to_string()})"


class TreeSlicer:
    """Utility for slicing and managing decision tree sub-problems."""
    
    @staticmethod
    def extract_subproblems(tree: Any, max_depth: int, min_depth: int = 3, 
                           node_count_threshold: int = 2) -> List[SubProblem]:
        """
        Extract sub-problems from a decision tree.
        
        This function traverses the tree and identifies all sub-trees whose root
        is at a depth less than max_depth, but which have depth >= min_depth.
        These are good candidates for optimization.
        
        Args:
            tree: The DecisionTree object to slice
            max_depth: Maximum depth at which to look for sub-tree roots
            min_depth: Minimum depth of sub-trees to consider (default: 3)
            node_count_threshold: Minimum number of nodes for a sub-tree (default: 2)
            
        Returns:
            List of SubProblem objects ready for synthesis
        """
        subproblems = []
        
        def traverse(node, current_depth, path_conditions, path_ids):
            """Recursively traverse the tree and identify sub-problems."""
            
            if node is None or node.is_terminal:
                return
            
            # Calculate sub-tree properties
            subtree_depth = node.get_depth() if hasattr(node, 'get_depth') else 0
            subtree_node_count = node.get_number_of_descendants() if hasattr(node, 'get_number_of_descendants') else 0
            
            # Check if this node is a good candidate for sub-problem extraction
            if (current_depth < max_depth and 
                subtree_depth >= min_depth and 
                subtree_node_count >= node_count_threshold):
                
                path_cond = PathCondition(decisions=path_conditions.copy())
                subproblem = SubProblem(
                    sub_tree_node=node,
                    path_condition=path_cond,
                    depth=subtree_depth,
                    node_count=subtree_node_count,
                    tree_path=path_ids.copy()
                )
                subproblems.append(subproblem)
                logger.debug(f"Extracted sub-problem: {subproblem}")
            
            # Continue traversal if we haven't exceeded max_depth
            if current_depth < max_depth:
                if hasattr(node, 'child_true') and node.child_true is not None:
                    # Add true branch decision
                    new_conditions = path_conditions.copy()
                    if hasattr(node, 'variable') and hasattr(node, 'variable_bound'):
                        new_conditions.append({
                            'variable': f'var_{node.variable}',
                            'operator': '<=',
                            'value': node.variable_bound
                        })
                    traverse(node.child_true, current_depth + 1, new_conditions, path_ids + [node.identifier if hasattr(node, 'identifier') else 'unknown'])
                
                if hasattr(node, 'child_false') and node.child_false is not None:
                    # Add false branch decision
                    new_conditions = path_conditions.copy()
                    if hasattr(node, 'variable') and hasattr(node, 'variable_bound'):
                        new_conditions.append({
                            'variable': f'var_{node.variable}',
                            'operator': '>',
                            'value': node.variable_bound
                        })
                    traverse(node.child_false, current_depth + 1, new_conditions, path_ids + [node.identifier if hasattr(node, 'identifier') else 'unknown'])
        
        # Start traversal from root
        if hasattr(tree, 'root'):
            traverse(tree.root, depth=0, path_conditions=[], path_ids=[])
        else:
            logger.warning("Tree object does not have 'root' attribute")
        
        # Sort sub-problems by depth (deeper first) for more targeted optimization
        subproblems.sort(key=lambda sp: sp.depth, reverse=True)
        
        logger.info(f"Extracted {len(subproblems)} sub-problems from tree")
        return subproblems
    
    @staticmethod
    def replace_subtree(main_tree: Any, original_subtree_path: List[Any], 
                       new_subtree: Any) -> Any:
        """
        Replace a sub-tree in the main tree with an optimized version.
        
        Args:
            main_tree: The main DecisionTree object
            original_subtree_path: List of node identifiers from root to the subtree
            new_subtree: The new optimized sub-tree to insert
            
        Returns:
            The modified main_tree with the replacement made
        """
        if not original_subtree_path:
            logger.warning("Empty path provided for subtree replacement")
            return main_tree
        
        # Navigate to the parent of the subtree to replace
        current_node = main_tree.root if hasattr(main_tree, 'root') else main_tree
        
        # If path has only one element, we're replacing the root
        if len(original_subtree_path) == 1:
            logger.info("Replacing entire tree root")
            main_tree.root = new_subtree
            return main_tree
        
        # Navigate to parent
        for i, node_id in enumerate(original_subtree_path[:-1]):
            if hasattr(current_node, 'child_true') and hasattr(current_node.child_true, 'identifier'):
                if current_node.child_true.identifier == original_subtree_path[i + 1]:
                    current_node = current_node.child_true
                    continue
            if hasattr(current_node, 'child_false') and hasattr(current_node.child_false, 'identifier'):
                if current_node.child_false.identifier == original_subtree_path[i + 1]:
                    current_node = current_node.child_false
                    continue
            
            logger.warning(f"Could not navigate to node in replacement path: {node_id}")
            return main_tree
        
        # Determine if we're replacing true or false child
        parent_node = current_node
        target_id = original_subtree_path[-1]
        
        if (hasattr(parent_node, 'child_true') and parent_node.child_true is not None and 
            hasattr(parent_node.child_true, 'identifier') and parent_node.child_true.identifier == target_id):
            logger.debug(f"Replacing true child at path {original_subtree_path}")
            parent_node.child_true = new_subtree
            return main_tree
        elif (hasattr(parent_node, 'child_false') and parent_node.child_false is not None and 
              hasattr(parent_node.child_false, 'identifier') and parent_node.child_false.identifier == target_id):
            logger.debug(f"Replacing false child at path {original_subtree_path}")
            parent_node.child_false = new_subtree
            return main_tree
        else:
            logger.warning(f"Could not find target node {target_id} in children of parent")
            return main_tree
    
    @staticmethod
    def get_tree_statistics(tree: Any) -> Dict[str, Any]:
        """
        Compute statistics about a decision tree.
        
        Args:
            tree: The DecisionTree object
            
        Returns:
            Dictionary with statistics (depth, node_count, leaf_count, etc.)
        """
        stats = {
            'depth': None,
            'node_count': None,
            'leaf_count': None,
            'avg_branch_depth': None,
        }
        
        if not hasattr(tree, 'root') or tree.root is None:
            return stats
        
        root = tree.root
        
        if hasattr(root, 'get_depth'):
            stats['depth'] = root.get_depth()
        
        if hasattr(root, 'get_number_of_descendants'):
            # Number of descendants is the number of non-leaf nodes
            stats['node_count'] = root.get_number_of_descendants()
        
        # Count leaves by traversing
        def count_leaves(node):
            if node is None:
                return 0
            if hasattr(node, 'is_terminal') and node.is_terminal:
                return 1
            left_count = count_leaves(node.child_true if hasattr(node, 'child_true') else None)
            right_count = count_leaves(node.child_false if hasattr(node, 'child_false') else None)
            return left_count + right_count
        
        stats['leaf_count'] = count_leaves(root)
        
        return stats
    
    @staticmethod
    def copy_subtree(node: Any) -> Any:
        """
        Create a deep copy of a sub-tree rooted at node.
        
        Args:
            node: The root node to copy
            
        Returns:
            A deep copy of the sub-tree
        """
        if node is None:
            return None
        
        # Use the node's copy method if available
        if hasattr(node, 'copy'):
            return node.copy(parent=None)
        
        # Otherwise, perform a simple copy
        node_copy = type(node)(parent=None)
        
        # Copy attributes
        for attr in ['identifier', 'action', 'variable', 'variable_bound', 'holes']:
            if hasattr(node, attr):
                setattr(node_copy, attr, getattr(node, attr))
        
        # Recursively copy children
        if hasattr(node, 'child_true') and node.child_true is not None:
            node_copy.child_true = TreeSlicer.copy_subtree(node.child_true)
            node_copy.child_true.parent = node_copy
        
        if hasattr(node, 'child_false') and node.child_false is not None:
            node_copy.child_false = TreeSlicer.copy_subtree(node.child_false)
            node_copy.child_false.parent = node_copy
        
        return node_copy
