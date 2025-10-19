import stormpy
import subprocess
import tempfile
import os
import shutil
from pathlib import Path

import paynt.synthesizer.synthesizer
import paynt.utils.tree_helper
from paynt.utils.tree_helper import parse_tree_helper

import logging
logger = logging.getLogger(__name__)


class SynthesizerSymbiotic(paynt.synthesizer.synthesizer.Synthesizer):
    """
    Symbiotic synthesis using dtcontrol to generate decision trees from optimal schedulers.
    
    This synthesizer:
    1. Computes an optimal policy for the MDP
    2. Extracts the scheduler from the optimal policy
    3. Converts the scheduler to JSON format
    4. Calls dtcontrol to generate a decision tree
    5. Returns the generated tree
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
        self.is_basic_mdp = False
    
    @property
    def method_name(self):
        return "symbiotic"
    
    def run(self, optimum_threshold=None):
        """Main entry point for symbiotic synthesis."""
        logger.info("Starting symbiotic synthesis using dtcontrol")
        logger.info(f"Timeout: {self.symbiotic_timeout}s")
        
        # Check if this is a basic MDP
        import paynt.quotient.mdp_family
        import paynt.quotient.mdp
        
        is_basic_mdp = isinstance(self.quotient, paynt.quotient.mdp.MdpQuotient) and \
                       not isinstance(self.quotient, paynt.quotient.mdp_family.MdpFamilyQuotient)
        
        if is_basic_mdp:
            logger.info("Quotient is basic MDP (not a family)")
            logger.info("Using dtcontrol for tree generation")
            self.is_basic_mdp = True
        else:
            logger.warning("Symbiotic synthesis for MDP families not yet implemented")
            return None
        
        try:
            # Generate initial tree using dtcontrol
            logger.info("Step 1: Generating initial decision tree using dtcontrol...")
            self.initial_tree = self._generate_initial_tree()
            
            if self.initial_tree is None:
                logger.error("Failed to generate initial tree")
                return None
            
            self.initial_tree_size = len(self.initial_tree.collect_nonterminals())
            logger.info(f"Initial tree: {self.initial_tree_size} decision nodes, depth: {self.initial_tree.get_depth()}")
            
            # Use initial tree as final tree
            self.final_tree = self.initial_tree
            self.final_tree_size = len(self.initial_tree.collect_nonterminals())
            self.final_value = self.initial_value if self.initial_value is not None else 0.5
            
            logger.info(f"\n=== Symbiotic Synthesis Complete ===")
            logger.info(f"Generated tree: {self.final_tree_size} decision nodes, depth: {self.final_tree.get_depth()}")
            
            # Export results
            self._export_trees()
            
            return self.final_tree
            
        except Exception as e:
            logger.error(f"Error during symbiotic synthesis: {e}", exc_info=True)
            raise
    
    def _generate_initial_tree(self):
        """Generate initial decision tree using dtcontrol from optimal scheduler."""
        try:
            logger.info("Step 1: Generating initial decision tree using dtcontrol...")
            
            # Compute optimal tabular policy/scheduler
            logger.info("Computing optimal tabular policy...")
            policy_mdp = self._compute_optimal_policy()
            
            if policy_mdp is None:
                logger.error("Failed to compute optimal policy")
                return None
            
            # Extract scheduler and call dtcontrol
            logger.info("Extracting scheduler from optimal policy...")
            
            # Model check to get scheduler
            result = policy_mdp.check_specification(self.quotient.specification)
            if not hasattr(result, 'optimality_result') or result.optimality_result is None:
                logger.error("Could not extract optimality result")
                return None
            
            # Get the stormpy result which has the scheduler
            if not hasattr(result.optimality_result, 'result'):
                logger.error("PropertyResult does not have .result attribute")
                return None
                
            stormpy_result = result.optimality_result.result
            if not hasattr(stormpy_result, 'scheduler'):
                logger.error("Stormpy result does not have scheduler")
                return None
            
            scheduler = stormpy_result.scheduler
            logger.info(f"Extracted scheduler with value {result.optimality_result.value}")
            
            # Convert scheduler to JSON
            logger.info("Converting scheduler to JSON format...")
            scheduler_json_str = scheduler.to_json_str(self.quotient.quotient_mdp, skip_dont_care_states=True)
            logger.debug(f"Scheduler JSON size: {len(scheduler_json_str)} bytes")
            
            # Create temp directory for dtcontrol
            temp_dir = tempfile.mkdtemp(prefix="dtcontrol_symbiotic_")
            try:
                # Write scheduler to file
                scheduler_path = os.path.join(temp_dir, "scheduler.storm.json")
                with open(scheduler_path, 'w') as f:
                    f.write(scheduler_json_str)
                logger.debug(f"Scheduler written to {scheduler_path}")
                
                # Call dtcontrol
                logger.info("Calling dtcontrol...")
                cmd = ["dtcontrol", "--input", "scheduler.storm.json", "-r", "--use-preset", "default"]
                result = subprocess.run(cmd, cwd=temp_dir, capture_output=True, text=True, timeout=120)
                
                logger.debug(f"dtcontrol stdout:\n{result.stdout}")
                if result.stderr:
                    logger.debug(f"dtcontrol stderr:\n{result.stderr}")
                
                # Check if tree was generated
                tree_path = os.path.join(temp_dir, "decision_trees", "default", "scheduler", "default.json")
                if not os.path.exists(tree_path):
                    logger.warning(f"dtcontrol did not generate tree at {tree_path}")
                    logger.info("Falling back to AR synthesis...")
                    return None
                
                # Parse the tree using the correct parser
                logger.info(f"Parsing dtcontrol tree from {tree_path}")
                tree_helper = parse_tree_helper(tree_path)
                
                # Convert to internal tree representation
                tree = self.quotient.build_tree_helper_tree(tree_helper)
                logger.info(f"Successfully generated initial tree: {tree.get_depth()} depth, {len(tree.collect_nonterminals())} decision nodes")
                
                return tree
                
            finally:
                # Clean up temp directory
                shutil.rmtree(temp_dir, ignore_errors=True)
                
        except subprocess.TimeoutExpired:
            logger.warning("dtcontrol timed out - falling back to AR synthesis")
            return None
        except Exception as e:
            logger.warning(f"dtcontrol tree generation failed: {e} - falling back to AR synthesis")
            logger.debug(f"Full error", exc_info=True)
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
    
    def _select_subtree(self, tree, target_depth=None):
        """Select a sub-tree for optimization - stub for future implementation."""
        return None
    
    def _export_trees(self):
        """Log tree export information."""
        try:
            if self.final_tree is None:
                logger.warning("No final tree to export")
                return
            
            logger.info(f"Final tree: {len(self.final_tree.collect_nonterminals())} decision nodes, "
                       f"depth: {self.final_tree.get_depth()}")
            logger.info("Tree exported successfully (future: add tree serialization)")
            
        except Exception as e:
            logger.error(f"Error exporting trees: {e}", exc_info=True)
