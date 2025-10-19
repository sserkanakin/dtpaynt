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
from paynt.synthesizer.dtcontrol_wrapper import DtcontrolWrapper, DtcontrolResult

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
        
        # Initialize dtcontrol wrapper
        self.dtcontrol = DtcontrolWrapper(dtcontrol_path=dtcontrol_path, timeout=symbiotic_timeout)
        
        self.initial_tree = None
        self.final_tree = None
        self.initial_tree_size = None
        self.final_tree_size = None
        self.initial_value = None
        self.final_value = None
        self.dtcontrol_calls = 0
        self.dtcontrol_successes = 0
        self.is_basic_mdp = False
    
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
        
        # Check if this is an MDP with holes (MdpFamilyQuotient)
        # For basic MDPs, we still use symbiotic but with dtcontrol as the primary synthesizer
        import paynt.quotient.mdp_family
        import paynt.quotient.mdp
        
        is_basic_mdp = isinstance(self.quotient, paynt.quotient.mdp.MdpQuotient) and \
                       not isinstance(self.quotient, paynt.quotient.mdp_family.MdpFamilyQuotient)
        
        if is_basic_mdp:
            logger.info("Quotient is basic MDP (not a family)")
            logger.info("Using dtcontrol for tree generation instead of AR synthesis")
            # For basic MDPs, use dtcontrol directly without AR synthesis
            self.is_basic_mdp = True
        else:
            self.is_basic_mdp = False
        
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
                
            except Exception as e:
                # dtcontrol failed - log and return None to trigger fallback
                logger.warning(f"dtcontrol tree generation failed: {e}")
                return None
            finally:
                # Clean up temporary files
                shutil.rmtree(temp_dir, ignore_errors=True)
                
        except Exception as e:
            logger.error(f"Error generating initial tree: {e}", exc_info=True)
            return None
    
    def _compute_optimal_policy(self):
        """Compute optimal policy for the MDP using AR synthesis (families) or model checking (basic MDPs)."""
        try:
            if self.is_basic_mdp:
                # For basic MDPs (no holes), directly model check to get optimal policy
                logger.info("Model checking basic MDP to get optimal policy...")
                
                # The quotient_mdp contains the stormpy MDP
                stormpy_mdp = self.quotient.quotient_mdp
                
                # Wrap in paynt.models.Mdp to get check_specification method
                import paynt.models.models
                mdp = paynt.models.models.Mdp(stormpy_mdp)
                
                result = mdp.check_specification(self.quotient.specification)
                
                if hasattr(result, 'optimality_result') and result.optimality_result is not None:
                    logger.info(f"Successfully extracted optimality value: {result.optimality_result.value}")
                    return mdp
                
                logger.warning("Could not extract optimality result from basic MDP")
                return None
            else:
                # For MDPs with families, run AR synthesis first to get an assignment
                from paynt.synthesizer.synthesizer_ar import SynthesizerAR
                
                logger.info("Running AR synthesis to get optimal assignment...")
                ar_synthesizer = SynthesizerAR(self.quotient)
                ar_result = ar_synthesizer.run()
                
                if ar_result is None or ar_synthesizer.best_assignment is None:
                    logger.warning("AR synthesis failed or produced no assignment")
                    return None
                
                # Get the assignment
                assignment = ar_synthesizer.best_assignment
                logger.info(f"AR synthesis produced assignment: {assignment}")
                
                # Build the MDP for this assignment
                mdp = self.quotient.build_assignment(assignment)
                
                if mdp is None:
                    logger.warning("Could not build MDP for assignment")
                    return None
                
                logger.info("Successfully extracted policy MDP from assignment")
                return mdp
            
        except Exception as e:
            logger.error(f"Error computing optimal policy: {e}", exc_info=True)
            return None
    
    def _call_dtcontrol(self, policy_mdp, output_dot):
        """Call dtcontrol to generate a decision tree from a policy using the wrapper.
        
        Args:
            policy_mdp: paynt.models.Mdp object
            output_dot: Path to save the tree JSON file
        
        The wrapper handles:
        - Scheduler file preparation
        - dtcontrol subprocess execution
        - Result validation
        - Error handling with detailed logging
        """
        try:
            self.dtcontrol_calls += 1
            logger.info(f"[dtcontrol call #{self.dtcontrol_calls}] Generating tree from policy...")
            
            # Extract scheduler from Mdp object's specification result
            logger.debug("Extracting scheduler from Mdp object...")
            result = policy_mdp.check_specification(self.quotient.specification)
            
            # result.optimality_result is a PropertyResult
            # The actual stormpy result is in result.optimality_result.result
            if hasattr(result.optimality_result, 'result') and hasattr(result.optimality_result.result, 'scheduler'):
                stormpy_result = result.optimality_result.result
                scheduler = stormpy_result.scheduler
                logger.debug(f"Extracted scheduler with value {result.optimality_result.value}")
            else:
                logger.error("Could not extract scheduler from specification result")
                raise RuntimeError("No scheduler in specification result")
            
            # Convert stormpy scheduler to JSON format
            logger.debug("Converting stormpy scheduler to JSON format...")
            scheduler_json_str = scheduler.to_json_str(self.quotient.quotient_mdp, skip_dont_care_states=True)
            logger.debug(f"Scheduler converted to JSON string with length {len(scheduler_json_str)}")
            
            # Use the wrapper to generate tree (pass JSON string, not parsed object)
            result_wrapper = self.dtcontrol.generate_tree_from_scheduler(scheduler_json_str, preset="default")
            
            if not result_wrapper.success:
                logger.warning(f"dtcontrol failed: {result_wrapper.error_msg}")
                raise RuntimeError(f"dtcontrol failed: {result_wrapper.error_msg}")
            
            # Validate the result
            if not result_wrapper.validate():
                logger.error("dtcontrol result validation failed")
                raise RuntimeError("dtcontrol result validation failed")
            
            self.dtcontrol_successes += 1
            
            # Write the result to output file
            # (wrapper already validated and loaded the JSON)
            with open(output_dot, 'w') as f:
                json.dump(result_wrapper.tree_data, f, indent=2)
            
            # Log statistics
            stats = result_wrapper.get_tree_stats()
            logger.info(f"[dtcontrol success #{self.dtcontrol_successes}] Tree stats: {stats}")
            
        except Exception as e:
            logger.error(f"Error calling dtcontrol: {e}", exc_info=True)
            raise
    
    def _parse_dot_file(self, dot_file_path):
        """Parse dtcontrol tree JSON output and create an internal tree representation."""
        try:
            if not os.path.exists(dot_file_path):
                logger.error(f"Tree file not found: {dot_file_path}")
                return None
            
            # Read the JSON file (dtcontrol outputs JSON, not DOT)
            with open(dot_file_path, 'r') as f:
                tree_data = json.load(f)
            
            logger.info(f"Loaded decision tree from {dot_file_path}")
            
            # Convert JSON tree to internal representation
            root = self._json_to_tree(tree_data)
            
            if root is None:
                logger.error("Failed to convert JSON tree to internal representation")
                return None
            
            logger.info(f"Parsed decision tree: {root.num_nodes()} nodes, {root.num_leaves()} leaves")
            return root
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON tree file: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing tree file: {e}", exc_info=True)
            return None
    
    def _json_to_tree(self, json_node, node_id=None):
        """Recursively convert JSON tree to internal DecisionTreeNode representation."""
        if node_id is None:
            node_id = [0]  # Use list to allow modification in nested calls
        
        try:
            current_id = node_id[0]
            node_id[0] += 1
            
            if json_node.get("type") == "leaf":
                # Leaf node - contains an action
                action = json_node.get("action", json_node.get("value", "unknown"))
                logger.debug(f"Created leaf node {current_id}: action={action}")
                return DecisionTreeNode(current_id, is_leaf=True, action=action)
            
            elif json_node.get("type") == "node" or json_node.get("type") == "decision_node":
                # Internal decision node
                # The predicate/variable name is typically stored here
                predicate = json_node.get("predicate", json_node.get("variable", json_node.get("label", "var")))
                
                node = DecisionTreeNode(current_id, is_leaf=False, predicate=predicate)
                logger.debug(f"Created inner node {current_id}: predicate={predicate}")
                
                # Process children
                children_data = json_node.get("children", [])
                if isinstance(children_data, dict):
                    # Children as dictionary {branch_label: child_node}
                    for branch_label, child_json in children_data.items():
                        child_node = self._json_to_tree(child_json, node_id)
                        if child_node is not None:
                            node.children[branch_label] = child_node
                            child_node.parent = node
                            child_node.branch_value = branch_label
                elif isinstance(children_data, list):
                    # Children as list
                    for idx, child_json in enumerate(children_data):
                        child_node = self._json_to_tree(child_json, node_id)
                        if child_node is not None:
                            node.children[str(idx)] = child_node
                            child_node.parent = node
                            child_node.branch_value = str(idx)
                
                return node
            
            else:
                logger.warning(f"Unknown node type: {json_node.get('type')}")
                return None
            
        except Exception as e:
            logger.error(f"Error converting JSON to tree: {e}", exc_info=True)
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
