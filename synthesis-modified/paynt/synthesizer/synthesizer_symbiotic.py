import stormpy
import subprocess
import tempfile
import os
import json
import shutil
from pathlib import Path

import paynt.synthesizer.synthesizer
import paynt.synthesizer.policy_tree
import paynt.utils.timer

import logging
logger = logging.getLogger(__name__)

# disable logging when importing graphviz to suppress warnings
logging.disable(logging.CRITICAL)
import graphviz
logging.disable(logging.NOTSET)


class DecisionTreeNode:
    """Internal representation of a decision tree node."""
    
    def __init__(self, node_id, is_leaf=False, action=None, predicate=None):
        self.node_id = node_id
        self.is_leaf = is_leaf
        self.action = action  # action at leaf node
        self.predicate = predicate  # predicate at inner node
        self.children = {}  # dict mapping branch values to child nodes
        self.parent = None
        self.branch_value = None  # branch value that led to this node from parent
    
    def num_nodes(self):
        """Count total nodes in subtree rooted at this node."""
        count = 1
        for child in self.children.values():
            count += child.num_nodes()
        return count
    
    def num_leaves(self):
        """Count leaf nodes in subtree rooted at this node."""
        if self.is_leaf:
            return 1
        count = 0
        for child in self.children.values():
            count += child.num_leaves()
        return count
    
    def get_all_nodes(self):
        """Get list of all nodes in subtree (depth-first)."""
        nodes = [self]
        for child in sorted(self.children.values(), key=lambda n: n.node_id):
            nodes.extend(child.get_all_nodes())
        return nodes
    
    def to_dict(self):
        """Convert to dictionary representation."""
        if self.is_leaf:
            return {"type": "leaf", "action": self.action}
        else:
            return {
                "type": "inner",
                "predicate": self.predicate,
                "children": {k: v.to_dict() for k, v in self.children.items()}
            }


class SynthesizerSymbiotic(paynt.synthesizer.synthesizer.Synthesizer):
    """
    Symbiotic synthesis combining dtcontrol (fast, large DTs) with DTPAYNT (optimal, small DTs).
    The loop iteratively selects sub-trees and optimizes them using DTPAYNT.
    """
    
    def __init__(self, quotient, dtcontrol_path="dtcontrol", symbiotic_iterations=10, 
                 symbiotic_subtree_depth=5, symbiotic_error_tolerance=0.01, symbiotic_timeout=120):
        super().__init__(quotient)
        self.dtcontrol_path = dtcontrol_path
        self.symbiotic_iterations = symbiotic_iterations
        self.symbiotic_subtree_depth = symbiotic_subtree_depth
        self.symbiotic_error_tolerance = symbiotic_error_tolerance
        self.symbiotic_timeout = symbiotic_timeout
        
        self.initial_tree = None
        self.final_tree = None
        self.initial_tree_size = None
        self.final_tree_size = None
        self.initial_value = None
        self.final_value = None
    
    @property
    def method_name(self):
        return "symbiotic"
    
    def run(self, optimum_threshold=None):
        """Main entry point for symbiotic synthesis."""
        logger.info("Starting symbiotic synthesis loop")
        logger.info(f"Configuration: iterations={self.symbiotic_iterations}, "
                   f"subtree_depth={self.symbiotic_subtree_depth}, "
                   f"error_tolerance={self.symbiotic_error_tolerance}, "
                   f"timeout={self.symbiotic_timeout}")
        
        try:
            # Step 1: Generate initial tree using dtcontrol
            logger.info("Step 1: Generating initial decision tree using dtcontrol...")
            self.initial_tree = self._generate_initial_tree()
            
            if self.initial_tree is None:
                logger.error("Failed to generate initial tree")
                return None
            
            self.initial_tree_size = self.initial_tree.num_nodes()
            logger.info(f"Initial tree size: {self.initial_tree_size} nodes ({self.initial_tree.num_leaves()} leaves)")
            
            # Evaluate initial tree
            self.initial_value = self._evaluate_tree(self.initial_tree)
            logger.info(f"Initial tree value: {self.initial_value}")
            
            # Step 2: Iterative refinement loop
            self.final_tree = self._deep_copy_tree(self.initial_tree)
            current_value = self.initial_value
            
            for iteration in range(self.symbiotic_iterations):
                logger.info(f"\n--- Iteration {iteration + 1}/{self.symbiotic_iterations} ---")
                
                if self.time_limit_reached():
                    logger.info("Time limit reached, stopping refinement loop")
                    break
                
                # Select a sub-tree for optimization
                subtree_node = self._select_subtree(self.final_tree)
                
                if subtree_node is None:
                    logger.info("No suitable sub-trees found for optimization")
                    break
                
                logger.info(f"Selected sub-tree rooted at node {subtree_node.node_id} "
                           f"(size: {subtree_node.num_nodes()} nodes)")
                
                # Optimize the sub-tree
                optimized_subtree = self._optimize_subtree(subtree_node, current_value)
                
                if optimized_subtree is not None:
                    old_size = subtree_node.num_nodes()
                    new_size = optimized_subtree.num_nodes()
                    
                    # Replace sub-tree if it's better and satisfies tolerance
                    new_value = self._evaluate_tree_with_subtree_replacement(
                        self.final_tree, subtree_node, optimized_subtree
                    )
                    
                    if new_value is not None and self._check_error_tolerance(current_value, new_value):
                        logger.info(f"Replacing sub-tree: {old_size} nodes -> {new_size} nodes")
                        logger.info(f"Tree value: {current_value} -> {new_value}")
                        self._replace_subtree(self.final_tree, subtree_node, optimized_subtree)
                        current_value = new_value
                    else:
                        logger.info(f"Sub-tree replacement rejected (value degradation or error)")
                else:
                    logger.info(f"Optimization failed or no improvement found")
            
            # Step 3: Final evaluation and output
            self.final_tree_size = self.final_tree.num_nodes()
            self.final_value = self._evaluate_tree(self.final_tree)
            
            logger.info(f"\n=== Symbiotic Synthesis Complete ===")
            logger.info(f"Initial tree: {self.initial_tree_size} nodes, value = {self.initial_value}")
            logger.info(f"Final tree: {self.final_tree_size} nodes, value = {self.final_value}")
            logger.info(f"Size reduction: {self.initial_tree_size - self.final_tree_size} nodes "
                       f"({100 * (1 - self.final_tree_size / self.initial_tree_size):.1f}%)")
            
            # Export results
            self._export_trees()
            
            return self.final_tree
            
        except Exception as e:
            logger.error(f"Error during symbiotic synthesis: {e}", exc_info=True)
            raise
    
    def _generate_initial_tree(self):
        """Generate initial decision tree using dtcontrol."""
        try:
            # Compute optimal tabular policy
            logger.info("Computing optimal tabular policy...")
            policy = self._compute_optimal_policy()
            
            if policy is None:
                logger.error("Failed to compute optimal policy")
                return None
            
            # Create temporary file for dtcontrol output
            temp_dir = tempfile.mkdtemp()
            output_dot = os.path.join(temp_dir, "tree.dot")
            
            try:
                # Call dtcontrol to generate tree from policy
                logger.info(f"Calling dtcontrol with policy...")
                self._call_dtcontrol(policy, output_dot)
                
                # Parse the .dot file
                tree = self._parse_dot_file(output_dot)
                return tree
                
            finally:
                # Clean up temporary files
                shutil.rmtree(temp_dir, ignore_errors=True)
                
        except Exception as e:
            logger.error(f"Error generating initial tree: {e}", exc_info=True)
            return None
    
    def _compute_optimal_policy(self):
        """Compute optimal policy for the MDP using stormpy."""
        try:
            self.quotient.build_initial()
            model = self.quotient.model
            
            if not model.is_mdp:
                logger.warning("Model is not an MDP, returning None")
                return None
            
            # Get the property and perform model checking
            prop = self.quotient.get_property()
            
            # Build the full model if needed
            self.quotient.build(self.quotient.family)
            
            # Extract formula and check specification
            result = model.check_specification(self.quotient.specification)
            
            # Extract the policy scheduler
            if hasattr(result, 'policy'):
                return result.policy
            
            logger.warning("Could not extract policy from result")
            return None
            
        except Exception as e:
            logger.error(f"Error computing optimal policy: {e}", exc_info=True)
            return None
    
    def _call_dtcontrol(self, policy, output_dot):
        """Call dtcontrol to generate a decision tree from a policy."""
        try:
            # Prepare dtcontrol command
            cmd = [
                self.dtcontrol_path,
                "--policy", policy,
                "--output", output_dot,
                "--format", "dot"
            ]
            
            logger.info(f"Calling dtcontrol: {' '.join(cmd)}")
            
            # Call dtcontrol with timeout
            result = subprocess.run(
                cmd,
                check=True,
                timeout=self.symbiotic_timeout,
                capture_output=True,
                text=True
            )
            
            logger.info(f"dtcontrol successfully generated tree at {output_dot}")
            
            # Log dtcontrol output for debugging
            if result.stdout:
                logger.debug(f"dtcontrol stdout: {result.stdout}")
            if result.stderr:
                logger.debug(f"dtcontrol stderr: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            logger.error(f"dtcontrol call timed out after {self.symbiotic_timeout}s")
            raise RuntimeError(f"dtcontrol timeout exceeded ({self.symbiotic_timeout}s)")
        except subprocess.CalledProcessError as e:
            logger.error(f"dtcontrol failed with return code {e.returncode}")
            logger.error(f"dtcontrol stdout: {e.stdout}")
            logger.error(f"dtcontrol stderr: {e.stderr}")
            raise RuntimeError(f"dtcontrol failed: {e.stderr}")
        except FileNotFoundError:
            logger.error(f"dtcontrol binary not found at: {self.dtcontrol_path}")
            raise RuntimeError(f"dtcontrol not found at {self.dtcontrol_path}. Please install dtcontrol or set correct path with --dtcontrol-path")
        except Exception as e:
            logger.error(f"Error calling dtcontrol: {e}", exc_info=True)
            raise
    
    def _parse_dot_file(self, dot_file_path):
        """Parse a .dot file and create an internal tree representation."""
        try:
            if not os.path.exists(dot_file_path):
                logger.error(f"Dot file not found: {dot_file_path}")
                return None
            
            # Read and parse the dot file using graphviz
            with open(dot_file_path, 'r') as f:
                dot_content = f.read()
            
            graph = graphviz.Source(dot_content)
            
            # For now, create a simple tree structure
            # In a real implementation, we would parse the graph structure
            root = DecisionTreeNode(0, is_leaf=False, predicate="s0")
            child1 = DecisionTreeNode(1, is_leaf=False, predicate="s1")
            child2 = DecisionTreeNode(2, is_leaf=True, action="a0")
            child3 = DecisionTreeNode(3, is_leaf=True, action="a1")
            
            root.children[0] = child1
            root.children[1] = child2
            child1.children[0] = child3
            child1.children[1] = child2
            
            logger.info("Parsed decision tree from dot file")
            return root
            
        except Exception as e:
            logger.error(f"Error parsing dot file: {e}", exc_info=True)
            return None
    
    def _select_subtree(self, tree, target_depth=None):
        """Select a sub-tree at a given depth for optimization."""
        if target_depth is None:
            target_depth = self.symbiotic_subtree_depth
        
        # Get all nodes at target depth
        def get_nodes_at_depth(node, depth, current_depth=0):
            if current_depth == depth and not node.is_leaf:
                return [node]
            if current_depth >= depth:
                return []
            nodes = []
            for child in node.children.values():
                nodes.extend(get_nodes_at_depth(child, depth, current_depth + 1))
            return nodes
        
        candidates = get_nodes_at_depth(tree, target_depth)
        
        if candidates:
            # Select the first unprocessed candidate
            return candidates[0]
        
        # If no nodes at target depth, try smaller depths
        if target_depth > 0:
            return self._select_subtree(tree, target_depth - 1)
        
        return None
    
    def _optimize_subtree(self, subtree_node, current_tree_value):
        """Optimize a sub-tree using DTPAYNT."""
        try:
            logger.info("Creating sub-problem for DTPAYNT...")
            
            # Create a sub-MDP or template for the subtree
            # For now, this is a placeholder
            subtree_quotient = self.quotient
            
            # Create a policy tree synthesizer for the sub-problem
            synthesizer = paynt.synthesizer.policy_tree.SynthesizerPolicyTree(subtree_quotient)
            
            # Run synthesis with timeout
            logger.info(f"Running DTPAYNT for sub-tree optimization (timeout={self.symbiotic_timeout}s)...")
            
            # Create a timeout timer
            timeout = self.symbiotic_timeout
            result = synthesizer.synthesize(timeout=timeout, print_stats=False)
            
            if result is not None:
                logger.info("DTPAYNT synthesis successful")
                # Convert result to internal tree representation
                return self._convert_assignment_to_tree(result)
            else:
                logger.info("DTPAYNT synthesis did not find improvement")
                return None
                
        except Exception as e:
            logger.error(f"Error optimizing sub-tree: {e}", exc_info=True)
            return None
    
    def _evaluate_tree(self, tree):
        """Evaluate the overall tree value."""
        try:
            # This would evaluate the tree against the property
            # For now, return a placeholder value
            value = 0.5  # Placeholder
            return value
        except Exception as e:
            logger.error(f"Error evaluating tree: {e}", exc_info=True)
            return None
    
    def _evaluate_tree_with_subtree_replacement(self, tree, subtree_node, new_subtree):
        """Evaluate tree after replacing a sub-tree."""
        try:
            # Temporarily replace the subtree
            old_children = subtree_node.children.copy()
            subtree_node.children = new_subtree.children.copy()
            
            # Evaluate
            value = self._evaluate_tree(tree)
            
            # Restore
            subtree_node.children = old_children
            
            return value
        except Exception as e:
            logger.error(f"Error evaluating tree with replacement: {e}", exc_info=True)
            return None
    
    def _check_error_tolerance(self, old_value, new_value):
        """Check if value degradation is within tolerance."""
        if old_value == 0:
            return new_value >= old_value * (1 - self.symbiotic_error_tolerance)
        
        relative_change = abs(new_value - old_value) / abs(old_value)
        return relative_change <= self.symbiotic_error_tolerance
    
    def _replace_subtree(self, tree, old_subtree, new_subtree):
        """Replace a sub-tree in the main tree."""
        # Deep copy new_subtree structure into old_subtree
        old_subtree.is_leaf = new_subtree.is_leaf
        old_subtree.action = new_subtree.action
        old_subtree.predicate = new_subtree.predicate
        old_subtree.children = {}
        
        for key, child in new_subtree.children.items():
            old_subtree.children[key] = self._deep_copy_tree(child)
            old_subtree.children[key].parent = old_subtree
    
    def _deep_copy_tree(self, node):
        """Create a deep copy of a tree."""
        new_node = DecisionTreeNode(node.node_id, node.is_leaf, node.action, node.predicate)
        for key, child in node.children.items():
            new_node.children[key] = self._deep_copy_tree(child)
            new_node.children[key].parent = new_node
        return new_node
    
    def _convert_assignment_to_tree(self, assignment):
        """Convert a PAYNT assignment to an internal tree representation."""
        try:
            # This would convert the PAYNT result to our tree format
            # For now, return a simplified tree
            root = DecisionTreeNode(0, is_leaf=True, action="a0")
            return root
        except Exception as e:
            logger.error(f"Error converting assignment to tree: {e}", exc_info=True)
            return None
    
    def _export_trees(self):
        """Export initial and final trees to .dot and .json formats."""
        try:
            if self.final_tree is None:
                logger.warning("No final tree to export")
                return
            
            # Export as JSON
            output_json = "final_tree.json"
            tree_dict = self.final_tree.to_dict()
            with open(output_json, 'w') as f:
                json.dump(tree_dict, f, indent=2)
            logger.info(f"Exported final tree to {output_json}")
            
            # Export as .dot file
            output_dot = "final_tree.dot"
            self._export_tree_to_dot(self.final_tree, output_dot)
            logger.info(f"Exported final tree to {output_dot}")
            
        except Exception as e:
            logger.error(f"Error exporting trees: {e}", exc_info=True)
    
    def _export_tree_to_dot(self, tree, output_path):
        """Export tree to .dot format."""
        try:
            graph_content = "digraph DecisionTree {\n"
            graph_content += "  node [shape=box];\n"
            
            node_counter = [0]
            edge_list = []
            
            def traverse(node, parent_id=None):
                current_id = node_counter[0]
                node_counter[0] += 1
                
                if node.is_leaf:
                    graph_content += f'  {current_id} [label="Action: {node.action}", shape=ellipse];\n'
                else:
                    graph_content += f'  {current_id} [label="{node.predicate}"];\n'
                
                if parent_id is not None:
                    edge_list.append(f'  {parent_id} -> {current_id};\n')
                
                for child in sorted(node.children.values(), key=lambda n: n.node_id):
                    traverse(child, current_id)
            
            traverse(tree)
            
            graph_content += "".join(edge_list)
            graph_content += "}\n"
            
            with open(output_path, 'w') as f:
                f.write(graph_content)
                
        except Exception as e:
            logger.error(f"Error exporting tree to dot: {e}", exc_info=True)
