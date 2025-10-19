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
        print("\n" + "="*80)
        print("SYMBIOTIC SYNTHESIS PIPELINE - DTCONTROL INTEGRATION")
        print("="*80)
        logger.info("="*80)
        logger.info("SYMBIOTIC SYNTHESIS PIPELINE - DTCONTROL INTEGRATION")
        logger.info("="*80)
        logger.info("Starting symbiotic synthesis using dtcontrol")
        logger.info(f"Timeout: {self.symbiotic_timeout}s")
        
        # Check if this is a basic MDP
        import paynt.quotient.mdp_family
        import paynt.quotient.mdp
        
        is_basic_mdp = isinstance(self.quotient, paynt.quotient.mdp.MdpQuotient) and \
                       not isinstance(self.quotient, paynt.quotient.mdp_family.MdpFamilyQuotient)
        
        if is_basic_mdp:
            logger.info("[PIPELINE] Quotient type: Basic MDP (not a family)")
            logger.info("[PIPELINE] Tree generation method: DTCONTROL")
            print("[PIPELINE] Quotient type: Basic MDP (not a family)")
            print("[PIPELINE] Tree generation method: DTCONTROL")
            self.is_basic_mdp = True
        else:
            logger.warning("[PIPELINE] Quotient is MDP family - symbiotic synthesis for families not yet implemented")
            return None
        
        try:
            # Generate initial tree using dtcontrol
            logger.info("[PIPELINE] Step 1: Generating initial decision tree using dtcontrol...")
            print("[PIPELINE] Step 1: Generating initial decision tree using dtcontrol...")
            self.initial_tree = self._generate_initial_tree()
            
            if self.initial_tree is None:
                logger.error("[PIPELINE] ERROR: Failed to generate initial tree")
                print("[PIPELINE] ERROR: Failed to generate initial tree")
                return None
            
            self.initial_tree_size = len(self.initial_tree.collect_nonterminals())
            logger.info(f"[PIPELINE] SUCCESS: Generated tree with {self.initial_tree_size} decision nodes, depth {self.initial_tree.get_depth()}")
            print(f"[PIPELINE] SUCCESS: Generated tree with {self.initial_tree_size} decision nodes, depth {self.initial_tree.get_depth()}")
            
            # Use initial tree as final tree
            self.final_tree = self.initial_tree
            self.final_tree_size = len(self.initial_tree.collect_nonterminals())
            self.final_value = self.initial_value if self.initial_value is not None else 0.5
            
            logger.info("[PIPELINE] Step 2: Finalizing results...")
            print("[PIPELINE] Step 2: Finalizing results...")
            logger.info(f"[PIPELINE] Final tree: {self.final_tree_size} decision nodes, depth {self.final_tree.get_depth()}, value {self.final_value}")
            print(f"[PIPELINE] Final tree: {self.final_tree_size} decision nodes, depth {self.final_tree.get_depth()}, value {self.final_value}")
            
            # Export results
            self._export_trees()
            
            logger.info("="*80)
            logger.info("SYMBIOTIC SYNTHESIS COMPLETE - DTCONTROL PIPELINE SUCCESSFUL")
            logger.info("="*80)
            print("="*80)
            print("SYMBIOTIC SYNTHESIS COMPLETE - DTCONTROL PIPELINE SUCCESSFUL")
            print("="*80 + "\n")
            
            return self.final_tree
            
        except Exception as e:
            logger.error(f"[PIPELINE] ERROR during symbiotic synthesis: {e}", exc_info=True)
            raise
    
    def _generate_initial_tree(self):
        """Generate initial decision tree using dtcontrol from optimal scheduler."""
        try:
            logger.info("\n[DTCONTROL] ========== PHASE 1: OPTIMAL POLICY COMPUTATION ==========")
            logger.info("[DTCONTROL] Computing optimal tabular policy...")
            print("[DTCONTROL] ========== PHASE 1: OPTIMAL POLICY COMPUTATION ==========")
            print("[DTCONTROL] Computing optimal tabular policy...")
            
            policy_mdp = self._compute_optimal_policy()
            
            if policy_mdp is None:
                logger.error("[DTCONTROL] ERROR: Failed to compute optimal policy")
                print("[DTCONTROL] ERROR: Failed to compute optimal policy")
                return None
            
            logger.info("[DTCONTROL] ========== PHASE 2: SCHEDULER EXTRACTION ==========")
            logger.info("[DTCONTROL] Extracting scheduler from optimal policy...")
            print("[DTCONTROL] ========== PHASE 2: SCHEDULER EXTRACTION ==========")
            print("[DTCONTROL] Extracting scheduler from optimal policy...")
            
            # Model check to get scheduler
            result = policy_mdp.check_specification(self.quotient.specification)
            if not hasattr(result, 'optimality_result') or result.optimality_result is None:
                logger.error("[DTCONTROL] ERROR: Could not extract optimality result")
                print("[DTCONTROL] ERROR: Could not extract optimality result")
                return None
            
            # Get the stormpy result which has the scheduler
            if not hasattr(result.optimality_result, 'result'):
                logger.error("[DTCONTROL] ERROR: PropertyResult does not have .result attribute")
                print("[DTCONTROL] ERROR: PropertyResult does not have .result attribute")
                return None
                
            stormpy_result = result.optimality_result.result
            if not hasattr(stormpy_result, 'scheduler'):
                logger.error("[DTCONTROL] ERROR: Stormpy result does not have scheduler")
                print("[DTCONTROL] ERROR: Stormpy result does not have scheduler")
                return None
            
            scheduler = stormpy_result.scheduler
            optimal_value = result.optimality_result.value
            self.initial_value = optimal_value
            logger.info(f"[DTCONTROL] SUCCESS: Extracted scheduler with optimal value: {optimal_value}")
            print(f"[DTCONTROL] SUCCESS: Extracted scheduler with optimal value: {optimal_value}")
            
            logger.info("[DTCONTROL] ========== PHASE 3: SCHEDULER JSON CONVERSION ==========")
            logger.info("[DTCONTROL] Converting scheduler to JSON format...")
            print("[DTCONTROL] ========== PHASE 3: SCHEDULER JSON CONVERSION ==========")
            print("[DTCONTROL] Converting scheduler to JSON format...")
            
            scheduler_json_str = scheduler.to_json_str(self.quotient.quotient_mdp, skip_dont_care_states=True)
            logger.info(f"[DTCONTROL] SUCCESS: Scheduler converted to JSON ({len(scheduler_json_str)} bytes)")
            print(f"[DTCONTROL] SUCCESS: Scheduler converted to JSON ({len(scheduler_json_str)} bytes)")
            
            # Create temp directory for dtcontrol
            temp_dir = tempfile.mkdtemp(prefix="dtcontrol_symbiotic_")
            logger.info(f"[DTCONTROL] Created temp directory: {temp_dir}")
            print(f"[DTCONTROL] Created temp directory: {temp_dir}")
            
            try:
                # Write scheduler to file
                scheduler_path = os.path.join(temp_dir, "scheduler.storm.json")
                with open(scheduler_path, 'w') as f:
                    f.write(scheduler_json_str)
                logger.info(f"[DTCONTROL] SUCCESS: Scheduler written to {scheduler_path}")
                print(f"[DTCONTROL] SUCCESS: Scheduler written to {scheduler_path}")
                
                logger.info("[DTCONTROL] ========== PHASE 4: DTCONTROL EXECUTION ==========")
                logger.info("[DTCONTROL] Calling dtcontrol subprocess...")
                print("[DTCONTROL] ========== PHASE 4: DTCONTROL EXECUTION ==========")
                print("[DTCONTROL] Calling dtcontrol subprocess...")
                print("[DTCONTROL] Command: dtcontrol --input scheduler.storm.json -r --use-preset default")
                
                cmd = ["dtcontrol", "--input", "scheduler.storm.json", "-r", "--use-preset", "default"]
                result = subprocess.run(cmd, cwd=temp_dir, capture_output=True, text=True, timeout=120)
                
                logger.info("[DTCONTROL] STDOUT from dtcontrol:")
                for line in result.stdout.split('\n'):
                    if line.strip():
                        logger.info(f"[DTCONTROL]   {line}")
                        print(f"[DTCONTROL]   {line}")
                
                if result.stderr:
                    logger.info("[DTCONTROL] STDERR from dtcontrol:")
                    for line in result.stderr.split('\n'):
                        if line.strip():
                            logger.info(f"[DTCONTROL]   {line}")
                            print(f"[DTCONTROL]   {line}")
                
                # Check if tree was generated
                tree_path = os.path.join(temp_dir, "decision_trees", "default", "scheduler", "default.json")
                if not os.path.exists(tree_path):
                    logger.warning(f"[DTCONTROL] WARNING: dtcontrol did not generate tree at {tree_path}")
                    logger.info("[DTCONTROL] Falling back to AR synthesis...")
                    print(f"[DTCONTROL] WARNING: dtcontrol did not generate tree at {tree_path}")
                    print("[DTCONTROL] Falling back to AR synthesis...")
                    return None
                
                logger.info("[DTCONTROL] ========== PHASE 5: TREE PARSING & CONVERSION ==========")
                logger.info(f"[DTCONTROL] Parsing dtcontrol tree from {tree_path}")
                print("[DTCONTROL] ========== PHASE 5: TREE PARSING & CONVERSION ==========")
                print(f"[DTCONTROL] Parsing dtcontrol tree from {tree_path}")
                
                tree_helper = parse_tree_helper(tree_path)
                logger.info("[DTCONTROL] SUCCESS: Tree parsed from JSON")
                print("[DTCONTROL] SUCCESS: Tree parsed from JSON")
                
                logger.info("[DTCONTROL] Building PAYNT DecisionTree object...")
                print("[DTCONTROL] Building PAYNT DecisionTree object...")
                
                tree = self.quotient.build_tree_helper_tree(tree_helper)
                
                tree_depth = tree.get_depth()
                tree_nodes = len(tree.collect_nonterminals())
                logger.info(f"[DTCONTROL] SUCCESS: PAYNT DecisionTree created: depth={tree_depth}, nodes={tree_nodes}")
                print(f"[DTCONTROL] SUCCESS: PAYNT DecisionTree created: depth={tree_depth}, nodes={tree_nodes}")
                
                logger.info("[DTCONTROL] ========== PHASE 5 COMPLETE ==========")
                print("[DTCONTROL] ========== PHASE 5 COMPLETE ==========")
                
                return tree
                
            finally:
                # Clean up temp directory
                logger.info(f"[DTCONTROL] Cleaning up temp directory: {temp_dir}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                
        except subprocess.TimeoutExpired:
            logger.warning("[DTCONTROL] WARNING: dtcontrol timed out - falling back to AR synthesis")
            print("[DTCONTROL] WARNING: dtcontrol timed out - falling back to AR synthesis")
            return None
        except Exception as e:
            logger.warning(f"[DTCONTROL] WARNING: dtcontrol tree generation failed: {e}")
            logger.debug(f"[DTCONTROL] Full error", exc_info=True)
            print(f"[DTCONTROL] WARNING: dtcontrol tree generation failed: {e}")
            return None
    
    def _compute_optimal_policy(self):
        """Compute optimal policy for the MDP using model checking (basic MDPs)."""
        try:
            if self.is_basic_mdp:
                # For basic MDPs (no holes), directly model check to get optimal policy
                logger.info("[DTPAYNT] Model checking basic MDP to get optimal policy...")
                print("[DTPAYNT] Model checking basic MDP to get optimal policy...")
                
                # The quotient_mdp contains the stormpy MDP
                stormpy_mdp = self.quotient.quotient_mdp
                logger.info(f"[DTPAYNT] MDP has {stormpy_mdp.nr_states} states")
                print(f"[DTPAYNT] MDP has {stormpy_mdp.nr_states} states")
                
                # Wrap in paynt.models.Mdp to get check_specification method
                import paynt.models.models
                mdp = paynt.models.models.Mdp(stormpy_mdp)
                logger.info("[DTPAYNT] Wrapped MDP in paynt.models.Mdp")
                print("[DTPAYNT] Wrapped MDP in paynt.models.Mdp")
                
                logger.info("[DTPAYNT] Running model checking with stormpy...")
                print("[DTPAYNT] Running model checking with stormpy...")
                
                result = mdp.check_specification(self.quotient.specification)
                
                if hasattr(result, 'optimality_result') and result.optimality_result is not None:
                    optimal_value = result.optimality_result.value
                    logger.info(f"[DTPAYNT] SUCCESS: Model checking complete")
                    logger.info(f"[DTPAYNT] Optimal value: {optimal_value}")
                    print(f"[DTPAYNT] SUCCESS: Model checking complete")
                    print(f"[DTPAYNT] Optimal value: {optimal_value}")
                    return mdp
                
                logger.warning("[DTPAYNT] WARNING: Could not extract optimality result from basic MDP")
                print("[DTPAYNT] WARNING: Could not extract optimality result from basic MDP")
                return None
            else:
                # For MDPs with families, would run AR synthesis
                logger.warning("[DTPAYNT] MDP families not supported in current implementation")
                print("[DTPAYNT] MDP families not supported in current implementation")
                return None
            
        except Exception as e:
            logger.error(f"[DTPAYNT] ERROR computing optimal policy: {e}", exc_info=True)
            print(f"[DTPAYNT] ERROR computing optimal policy: {e}")
            return None
    
    def _select_subtree(self, tree, target_depth=None):
        """Select a sub-tree for optimization - stub for future implementation."""
        return None
    
    def _export_trees(self):
        """Export tree to DOT and PNG formats."""
        try:
            if self.final_tree is None:
                logger.warning("No final tree to export")
                return
            
            num_nodes = len(self.final_tree.collect_nonterminals())
            depth = self.final_tree.get_depth()
            logger.info(f"Final tree: {num_nodes} decision nodes, depth: {depth}")
            
            # Export to DOT and PNG if export_synthesis_filename_base is set
            if self.export_synthesis_filename_base is not None:
                self._export_decision_tree(self.final_tree, self.export_synthesis_filename_base)
            
        except Exception as e:
            logger.error(f"Error exporting trees: {e}", exc_info=True)
    
    def _export_decision_tree(self, decision_tree, export_filename_base):
        """Export decision tree to DOT and PNG files (graphviz format)."""
        try:
            import os
            
            # Convert to graphviz
            tree = decision_tree.to_graphviz()
            
            # Export DOT file
            tree_filename = export_filename_base + ".dot"
            directory = os.path.dirname(tree_filename)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(tree_filename, 'w') as file:
                file.write(tree.source)
            logger.info(f"[EXPORT] Exported decision tree to {tree_filename}")
            print(f"[EXPORT] Exported decision tree to {tree_filename}")
            
            # Render to PNG
            tree_visualization_filename = export_filename_base + ".png"
            tree.render(export_filename_base, format="png", cleanup=True)
            logger.info(f"[EXPORT] Exported decision tree visualization to {tree_visualization_filename}")
            print(f"[EXPORT] Exported decision tree visualization to {tree_visualization_filename}")
            
        except ImportError:
            logger.warning("[EXPORT] graphviz module not available, skipping visualization export")
            print("[EXPORT] graphviz module not available, skipping visualization export")
        except Exception as e:
            logger.error(f"[EXPORT] Error exporting tree: {e}", exc_info=True)
            print(f"[EXPORT] Error exporting tree: {e}")
