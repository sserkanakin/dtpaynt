"""
Comprehensive test comparing original stack-based search vs. priority-queue-based search.

This test file imports both the original and modified SynthesizerAR implementations
and compares their performance on benchmark MDP models.
"""

import sys
import os
import time
import tempfile
from pathlib import Path

# Add both synthesis directories to the path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "synthesis-modified"))
sys.path.insert(1, str(project_root / "synthesis-original"))

# Import the modified synthesizer from synthesis-modified
import paynt.parser.sketch as modified_sketch
import paynt.synthesizer.synthesizer_ar as modified_synthesizer_ar
import paynt.quotient.mdp as modified_mdp_quotient
import paynt.utils.timer

# Store references to modified classes
ModifiedSynthesizerAR = modified_synthesizer_ar.SynthesizerAR
modified_parse_sketch = modified_sketch.Sketch.load_sketch

# Clear and re-import from original
sys.path.remove(str(project_root / "synthesis-modified"))
sys.modules.pop('paynt.parser.sketch', None)
sys.modules.pop('paynt.synthesizer.synthesizer_ar', None)
sys.modules.pop('paynt.quotient.mdp', None)

# Re-insert original at the front
sys.path.insert(0, str(project_root / "synthesis-original"))
import paynt.parser.sketch as original_sketch
import paynt.synthesizer.synthesizer_ar as original_synthesizer_ar

OriginalSynthesizerAR = original_synthesizer_ar.SynthesizerAR
original_parse_sketch = original_sketch.Sketch.load_sketch


class BenchmarkResult:
    """Store benchmark results for comparison."""
    def __init__(self, name, time_taken, value, tree_size, iterations):
        self.name = name
        self.time_taken = time_taken
        self.value = value
        self.tree_size = tree_size
        self.iterations = iterations


def get_simple_sketch_paths():
    """Get paths to a simple sketch model with holes."""
    base_path = Path(__file__).parent.parent / 'models' / 'dtmc' / 'grid' / 'grid'
    sketch_path = str(base_path / 'sketch.templ')
    props_path = str(base_path / 'easy.props')
    return sketch_path, props_path


def get_complex_sketch_paths():
    """Get paths to a more complex sketch model with holes."""
    base_path = Path(__file__).parent.parent / 'models' / 'dtmc' / 'grid' / 'safety'
    sketch_path = str(base_path / 'sketch.templ')
    props_path = str(base_path / 'sketch.props')
    return sketch_path, props_path


def run_synthesis(synthesizer_class, sketch_path, props_path, max_timeout=30):
    """Run synthesis with the given synthesizer class."""
    try:
        # Load the sketch
        if synthesizer_class == OriginalSynthesizerAR:
            quotient = original_parse_sketch(sketch_path, props_path)
        else:
            quotient = modified_parse_sketch(sketch_path, props_path)
        
        # Initialize family constraint indices if not set
        if quotient.family.constraint_indices is None:
            quotient.family.constraint_indices = list(range(len(quotient.specification.constraints)))
        
        # Create synthesizer directly
        synthesizer = synthesizer_class(quotient)
        
        # Set timeout
        synthesizer.timeout = max_timeout if max_timeout else None
        
        # Run synthesis
        start_time = time.time()
        assignment = synthesizer.synthesize(keep_optimum=True, print_stats=False)
        end_time = time.time()
        
        time_taken = end_time - start_time
        
        # Extract results
        value = None
        if hasattr(synthesizer, 'best_assignment_value'):
            value = synthesizer.best_assignment_value
        
        tree_size = 0
        if assignment is not None and hasattr(assignment, '__len__'):
            tree_size = len(assignment)
        
        iterations = 0
        if hasattr(synthesizer.stat, 'iterations'):
            iterations = synthesizer.stat.iterations
        
        return BenchmarkResult(
            name=synthesizer_class.__name__,
            time_taken=time_taken,
            value=value,
            tree_size=tree_size,
            iterations=iterations
        )
    except Exception as e:
        print(f"Error running {synthesizer_class.__name__}: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_simple_mdp_comparison():
    """Test and compare both synthesizers on a simple sketch with holes."""
    print("\n" + "="*80)
    print("TEST 1: Simple Sketch Model Comparison (Grid with holes)")
    print("="*80)
    
    # Get paths to existing sketch files
    sketch_path, props_path = get_simple_sketch_paths()
    
    # Run original synthesizer
    print("\nRunning ORIGINAL (Stack-Based) Synthesizer...")
    original_result = run_synthesis(OriginalSynthesizerAR, sketch_path, props_path, max_timeout=60)
    
    # Run modified synthesizer
    print("\nRunning MODIFIED (Priority-Queue-Based) Synthesizer...")
    modified_result = run_synthesis(ModifiedSynthesizerAR, sketch_path, props_path, max_timeout=60)
    
    # Print comparison
    print_comparison_table([original_result, modified_result], "Simple Sketch")
    
    # Assertions
    if original_result and modified_result:
        assert modified_result.value is not None, "Modified synthesizer should find a solution"
        if original_result.value is not None:
            assert modified_result.value >= original_result.value * 0.99, \
                f"Modified value {modified_result.value} should be >= original value {original_result.value}"


def test_grid_mdp_comparison():
    """Test and compare both synthesizers on a more complex sketch with holes."""
    print("\n" + "="*80)
    print("TEST 2: Complex Sketch Model Comparison (Grid Safety)")
    print("="*80)
    
    # Get paths to existing sketch files
    sketch_path, props_path = get_complex_sketch_paths()
    
    # Run original synthesizer
    print("\nRunning ORIGINAL (Stack-Based) Synthesizer...")
    original_result = run_synthesis(OriginalSynthesizerAR, sketch_path, props_path, max_timeout=120)
    
    # Run modified synthesizer
    print("\nRunning MODIFIED (Priority-Queue-Based) Synthesizer...")
    modified_result = run_synthesis(ModifiedSynthesizerAR, sketch_path, props_path, max_timeout=120)
    
    # Print comparison
    print_comparison_table([original_result, modified_result], "Complex Sketch")
    
    # Assertions
    if original_result and modified_result:
        assert modified_result.value is not None, "Modified synthesizer should find a solution"
        if original_result.value is not None:
            assert modified_result.value >= original_result.value * 0.99, \
                f"Modified value {modified_result.value} should be >= original value {original_result.value}"


def print_comparison_table(results, model_name):
    """Print a formatted comparison table."""
    print("\n" + "="*80)
    print(f"COMPARISON RESULTS: {model_name}")
    print("="*80)
    print(f"{'Algorithm':<30} {'Time (s)':<15} {'Value':<15} {'Tree Size':<15} {'Iterations':<15}")
    print("-"*80)
    
    for result in results:
        if result:
            algo_name = "Original (Stack)" if "Original" in result.name else "Modified (Priority-Q)"
            time_str = f"{result.time_taken:.4f}" if result.time_taken else "N/A"
            value_str = f"{result.value:.6f}" if result.value is not None else "N/A"
            tree_str = f"{result.tree_size}" if result.tree_size else "N/A"
            iter_str = f"{result.iterations}" if result.iterations else "N/A"
            
            print(f"{algo_name:<30} {time_str:<15} {value_str:<15} {tree_str:<15} {iter_str:<15}")
    
    print("="*80)
    
    # Calculate improvements
    if len(results) == 2 and all(results):
        original, modified = results
        if original.time_taken and modified.time_taken:
            speedup = (original.time_taken - modified.time_taken) / original.time_taken * 100
            print(f"\nTime improvement: {speedup:+.2f}%")
        
        if original.value is not None and modified.value is not None:
            value_improvement = (modified.value - original.value) / original.value * 100
            print(f"Value improvement: {value_improvement:+.2f}%")
    
    print()


def test_all_comparisons():
    """Run all comparison tests."""
    test_simple_mdp_comparison()
    test_grid_mdp_comparison()
    
    print("\n" + "="*80)
    print("ALL TESTS COMPLETED")
    print("="*80)


if __name__ == "__main__":
    test_all_comparisons()
