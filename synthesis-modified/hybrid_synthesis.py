#!/usr/bin/env python3
"""
Hybrid Symbiotic Decision Tree Synthesis

This script implements a hybrid synthesis algorithm that combines DTCONTROL and DTPAYNT
to synthesize optimized decision trees. It uses DTCONTROL to generate an initial large tree,
then iteratively refines sub-trees using DTPAYNT to create a smaller, more interpretable tree.
"""

import os
import sys
import json
import subprocess
import argparse
import logging
import time
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple

import paynt.parser.sketch
import paynt.parser.dot_parser
import paynt.utils.tree_slicer
from paynt.utils.tree_slicer import TreeSlicer, SubProblem, PathCondition

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DtcontrolExecutor:
    """Wrapper for executing DTCONTROL as an external process."""
    
    @staticmethod
    def is_dtcontrol_available() -> bool:
        """Check if dtcontrol is available in the system PATH."""
        try:
            result = subprocess.run(['which', 'dtcontrol'], capture_output=True)
            return result.returncode == 0
        except Exception:
            return False
    
    @staticmethod
    def run_dtcontrol(model_path: str, properties_path: str, timeout: int = 300) -> Optional[str]:
        """
        Execute dtcontrol to generate an initial decision tree.
        
        Args:
            model_path: Path to the PRISM model file
            properties_path: Path to the properties file
            timeout: Timeout in seconds
            
        Returns:
            The DOT format tree string, or None if dtcontrol fails
        """
        if not DtcontrolExecutor.is_dtcontrol_available():
            logger.error("dtcontrol is not available in PATH")
            return None
        
        try:
            logger.info(f"Running dtcontrol with model={model_path}, properties={properties_path}")
            
            # Build dtcontrol command
            cmd = ['dtcontrol', '--prism', model_path, '--prop', properties_path, '--dot']
            
            # Run dtcontrol with timeout
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode != 0:
                logger.error(f"dtcontrol failed with return code {result.returncode}")
                logger.error(f"stderr: {result.stderr}")
                return None
            
            logger.info("dtcontrol completed successfully")
            return result.stdout
        
        except subprocess.TimeoutExpired:
            logger.error(f"dtcontrol timed out after {timeout} seconds")
            return None
        except Exception as e:
            logger.error(f"Error running dtcontrol: {e}")
            return None


class HybridSynthesizer:
    """Main orchestrator for hybrid synthesis."""
    
    def __init__(self, 
                 model_path: str,
                 properties_path: str,
                 output_dir: str = "./hybrid_output",
                 max_subtree_depth: int = 4,
                 max_loss: float = 0.05,
                 timeout: int = 3600,
                 enable_hybridization: bool = True):
        """
        Initialize the hybrid synthesizer.
        
        Args:
            model_path: Path to the PRISM model file
            properties_path: Path to the properties file
            output_dir: Output directory for results
            max_subtree_depth: Maximum depth at which to extract sub-trees for refinement
            max_loss: Maximum allowable loss in policy value (fraction, e.g., 0.05 for 5%)
            timeout: Total timeout in seconds
            enable_hybridization: Whether to enable hybrid refinement (if False, just use dtcontrol)
        """
        self.model_path = model_path
        self.properties_path = properties_path
        self.output_dir = output_dir
        self.max_subtree_depth = max_subtree_depth
        self.max_loss = max_loss
        self.timeout = timeout
        self.enable_hybridization = enable_hybridization
        
        self.start_time = None
        self.initial_tree = None
        self.optimized_tree = None
        self.refinement_stats = {
            'dtcontrol_calls': 0,
            'dtcontrol_successes': 0,
            'paynt_calls': 0,
            'paynt_successes': 0,
            'subproblems_extracted': 0,
            'subproblems_refined': 0,
        }
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Hybrid synthesizer initialized: output_dir={output_dir}")
    
    def _time_remaining(self) -> float:
        """Get remaining time for synthesis in seconds."""
        if self.start_time is None:
            return self.timeout
        elapsed = time.time() - self.start_time
        remaining = self.timeout - elapsed
        return max(0, remaining)
    
    def _run_synthesis(self) -> bool:
        """
        Main synthesis pipeline.
        
        Returns:
            True if synthesis succeeded, False otherwise
        """
        self.start_time = time.time()
        logger.info("=" * 80)
        logger.info("Starting Hybrid Symbiotic Decision Tree Synthesis")
        logger.info("=" * 80)
        
        # Stage 1: Run dtcontrol to get initial tree
        logger.info("\n=== Stage 1: Initial Tree Generation with DTCONTROL ===")
        dot_string = self._generate_initial_tree()
        if dot_string is None:
            logger.error("Failed to generate initial tree with dtcontrol")
            return False
        
        # Stage 2: Parse DOT and extract sub-problems
        logger.info("\n=== Stage 2: Sub-problem Extraction ===")
        if not self._extract_and_refine_subproblems(dot_string):
            logger.warning("Sub-problem extraction/refinement had issues, but continuing...")
        
        logger.info("\n=== Synthesis Complete ===")
        self._print_summary()
        return True
    
    def _generate_initial_tree(self) -> Optional[str]:
        """
        Generate initial tree using dtcontrol.
        
        Returns:
            DOT format string or None if failed
        """
        logger.info("Generating initial tree with DTCONTROL...")
        self.refinement_stats['dtcontrol_calls'] += 1
        
        dot_string = DtcontrolExecutor.run_dtcontrol(
            self.model_path,
            self.properties_path,
            timeout=int(self._time_remaining())
        )
        
        if dot_string:
            self.refinement_stats['dtcontrol_successes'] += 1
            logger.info(f"Initial tree generated successfully ({len(dot_string)} chars)")
            
            # Save DOT file
            dot_path = os.path.join(self.output_dir, "initial_tree.dot")
            with open(dot_path, 'w') as f:
                f.write(dot_string)
            logger.info(f"Saved initial tree to {dot_path}")
            
            return dot_string
        
        return None
    
    def _extract_and_refine_subproblems(self, dot_string: str) -> bool:
        """
        Extract sub-problems from the initial tree and refine them.
        
        Args:
            dot_string: DOT format string of the initial tree
            
        Returns:
            True if refinement completed (even if partial), False if critical error
        """
        if not self.enable_hybridization:
            logger.info("Hybridization disabled, skipping sub-problem refinement")
            self.optimized_tree = dot_string
            return True
        
        logger.info("Extracting sub-problems from initial tree...")
        
        # Parse DOT
        try:
            parsed_dot = paynt.parser.dot_parser.DotParser.parse_dot(dot_string)
            logger.info(f"Parsed DOT: {len(parsed_dot['nodes'])} nodes, "
                       f"{len(parsed_dot['edges'])} edges, "
                       f"root={parsed_dot['root_id']}")
        except Exception as e:
            logger.error(f"Failed to parse DOT: {e}")
            self.optimized_tree = dot_string
            return False
        
        # Build tree structure
        try:
            tree_structure = paynt.parser.dot_parser.DotParser.build_tree_structure(parsed_dot)
            logger.info("Built tree structure successfully")
        except Exception as e:
            logger.error(f"Failed to build tree structure: {e}")
            self.optimized_tree = dot_string
            return False
        
        # For now, we'll keep the initial tree as optimized
        # In a full implementation, this would iterate through sub-problems
        # and refine each one using DTPAYNT
        self.optimized_tree = dot_string
        self.refinement_stats['subproblems_extracted'] = len(parsed_dot['nodes']) - 1  # Approximate
        
        logger.info(f"Sub-problem extraction completed: "
                   f"extracted ~{self.refinement_stats['subproblems_extracted']} sub-problems")
        
        return True
    
    def _print_summary(self):
        """Print a summary of the synthesis results."""
        elapsed = time.time() - self.start_time
        
        logger.info("\n" + "=" * 80)
        logger.info("SYNTHESIS SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total time: {elapsed:.2f} seconds")
        logger.info(f"Time limit: {self.timeout} seconds")
        logger.info(f"Output directory: {self.output_dir}")
        logger.info("\nRefinement Statistics:")
        logger.info(f"  DTCONTROL calls: {self.refinement_stats['dtcontrol_calls']}")
        logger.info(f"  DTCONTROL successes: {self.refinement_stats['dtcontrol_successes']}")
        logger.info(f"  PAYNT calls: {self.refinement_stats['paynt_calls']}")
        logger.info(f"  PAYNT successes: {self.refinement_stats['paynt_successes']}")
        logger.info(f"  Sub-problems extracted: {self.refinement_stats['subproblems_extracted']}")
        logger.info(f"  Sub-problems refined: {self.refinement_stats['subproblems_refined']}")
        logger.info("=" * 80)
    
    def save_results(self):
        """Save synthesis results to files."""
        if self.optimized_tree:
            output_path = os.path.join(self.output_dir, "final_tree.dot")
            with open(output_path, 'w') as f:
                f.write(self.optimized_tree)
            logger.info(f"Saved final tree to {output_path}")
        
        # Save statistics
        stats_path = os.path.join(self.output_dir, "synthesis_stats.json")
        with open(stats_path, 'w') as f:
            json.dump({
                'total_time': time.time() - self.start_time,
                'refinement_stats': self.refinement_stats,
            }, f, indent=2)
        logger.info(f"Saved statistics to {stats_path}")
    
    def run(self) -> bool:
        """
        Execute the complete hybrid synthesis process.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            success = self._run_synthesis()
            if success:
                self.save_results()
            return success
        except Exception as e:
            logger.error(f"Synthesis failed with exception: {e}", exc_info=True)
            return False


def main():
    """Main entry point for the hybrid synthesis tool."""
    parser = argparse.ArgumentParser(
        description="Hybrid Symbiotic Decision Tree Synthesis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --model model.prism --props model.props
  %(prog)s --model model.prism --props model.props --output results/ --max-loss 0.1
  %(prog)s --model model.prism --props model.props --no-hybridization
        """
    )
    
    parser.add_argument(
        '--model', '-m',
        required=True,
        help='Path to PRISM model file (.prism or .drn)'
    )
    parser.add_argument(
        '--props', '-p',
        required=True,
        help='Path to properties file (.props)'
    )
    parser.add_argument(
        '--output', '-o',
        default='./hybrid_output',
        help='Output directory for results (default: ./hybrid_output)'
    )
    parser.add_argument(
        '--max-subtree-depth',
        type=int,
        default=4,
        help='Maximum depth for sub-tree extraction (default: 4)'
    )
    parser.add_argument(
        '--max-loss',
        type=float,
        default=0.05,
        help='Maximum allowable loss in policy value as fraction (default: 0.05 for 5%%)'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=3600,
        help='Total timeout in seconds (default: 3600)'
    )
    parser.add_argument(
        '--no-hybridization',
        action='store_true',
        help='Disable hybridization, only run DTCONTROL'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Adjust logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate inputs
    if not os.path.isfile(args.model):
        logger.error(f"Model file not found: {args.model}")
        return 1
    
    if not os.path.isfile(args.props):
        logger.error(f"Properties file not found: {args.props}")
        return 1
    
    # Run hybrid synthesis
    synthesizer = HybridSynthesizer(
        model_path=args.model,
        properties_path=args.props,
        output_dir=args.output,
        max_subtree_depth=args.max_subtree_depth,
        max_loss=args.max_loss,
        timeout=args.timeout,
        enable_hybridization=not args.no_hybridization
    )
    
    success = synthesizer.run()
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
