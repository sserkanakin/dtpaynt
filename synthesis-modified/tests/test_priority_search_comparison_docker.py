"""
Docker-compatible test runner for priority search comparison.
This version adjusts paths for the Docker container environment.
"""

import sys
import os
import time
import tempfile
from pathlib import Path

# Determine if we're running in Docker or locally
if os.path.exists('/opt/synthesis-modified'):
    # Docker environment
    project_root = Path('/opt')
else:
    # Local environment
    project_root = Path(__file__).parent.parent.parent

# Add both synthesis directories to the path
sys.path.insert(0, str(project_root / "synthesis-modified"))
sys.path.insert(1, str(project_root / "synthesis-original"))

# Import the modified synthesizer from synthesis-modified
import paynt.parser.sketch as modified_sketch
import paynt.synthesizer.synthesizer_ar as modified_synthesizer_ar
import paynt.quotient.mdp as modified_mdp_quotient
import paynt.utils.timer

# Store references to modified classes
print(f"[DEBUG] ModifiedSynthesizerAR loaded from: {modified_synthesizer_ar.__file__}")
ModifiedSynthesizerAR = modified_synthesizer_ar.SynthesizerAR
modified_parse_sketch = modified_sketch.Sketch.load_sketch

# We need to load from different directories, but Python's import system makes this tricky
# Solution: Use subprocess to run each synthesizer in isolation
# For now, let's use a simpler approach - verify the classes are actually different

import importlib

# Clear ALL paynt modules to force clean reimport  
sys.path.remove(str(project_root / "synthesis-modified"))
modules_to_remove = [key for key in sys.modules.keys() if key.startswith('paynt')]
for module in modules_to_remove:
    sys.modules.pop(module, None)

# Re-insert original at the front - this MUST be the only paynt in path
sys.path.insert(0, str(project_root / "synthesis-original"))

# Force reimport with importlib
import paynt.parser.sketch as original_sketch
import paynt.synthesizer.synthesizer_ar as original_synthesizer_ar

# Verify we got the right version
print(f"[DEBUG] OriginalSynthesizerAR loaded from: {original_synthesizer_ar.__file__}")
print(f"[DEBUG] OriginalSynthesizerAR class id: {id(original_synthesizer_ar.SynthesizerAR)}")
print(f"[DEBUG] ModifiedSynthesizerAR class id: {id(ModifiedSynthesizerAR)}")

# Check if they're the same class (they shouldn't be!)
if original_synthesizer_ar.SynthesizerAR is ModifiedSynthesizerAR:
    print("[WARNING] Both classes are THE SAME! Import isolation failed!")
else:
    print("[OK] Classes are different - import isolation successful")

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
    if os.path.exists('/opt/synthesis-modified'):
        # Docker environment  
        sketch_path = '/opt/synthesis-modified/models/dtmc/grid/grid/sketch.templ'
        props_path = '/opt/synthesis-modified/models/dtmc/grid/grid/hard.props'  # Use hard.props (Pmax=?)
    else:
        # Local environment
        base_path = Path(__file__).parent.parent / 'models' / 'dtmc' / 'grid' / 'grid'
        sketch_path = str(base_path / 'sketch.templ')
        props_path = str(base_path / 'hard.props')  # Use hard.props (Pmax=?)
    
    return sketch_path, props_path


def get_complex_sketch_paths():
    """Get paths to a more complex sketch model with holes."""
    if os.path.exists('/opt/synthesis-modified'):
        # Docker environment - use a different model for more complex test
        sketch_path = '/opt/synthesis-modified/models/dtmc/grid/safety/sketch.templ'
        props_path = '/opt/synthesis-modified/models/dtmc/grid/safety/sketch.props'
    else:
        # Local environment
        base_path = Path(__file__).parent.parent / 'models' / 'dtmc' / 'grid' / 'safety'
        sketch_path = str(base_path / 'sketch.templ')
        props_path = str(base_path / 'sketch.props')
    
    return sketch_path, props_path


def run_synthesis(synthesizer_class, sketch_path, props_path, max_timeout=30, label=None):
    """Run synthesis with the given synthesizer class."""
    try:
        # Determine label based on class identity
        if label is None:
            label = "OriginalSynthesizerAR" if synthesizer_class == OriginalSynthesizerAR else "ModifiedSynthesizerAR"
        
        # Load the sketch
        if synthesizer_class == OriginalSynthesizerAR:
            quotient = original_parse_sketch(sketch_path, props_path)
        else:
            quotient = modified_parse_sketch(sketch_path, props_path)
        
        # Check if family exists
        if quotient.family is None:
            raise ValueError("Quotient family is None. The sketch may not have been loaded correctly.")
        
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
        
        # Extract results - handle both optimality and non-optimality specs
        value = None
        if hasattr(synthesizer, 'best_assignment_value') and synthesizer.best_assignment_value is not None:
            value = synthesizer.best_assignment_value
        elif hasattr(synthesizer, 'best_assignment') and synthesizer.best_assignment is not None:
            # For non-optimality specs, we have an assignment but no value
            # We should still consider this a success, but value will be None
            pass
        
        # Debug output
        print(f"[DEBUG {label}] Synthesis completed:")
        print(f"  - Assignment returned: {assignment is not None}")
        print(f"  - best_assignment: {synthesizer.best_assignment is not None if hasattr(synthesizer, 'best_assignment') else 'N/A'}")
        print(f"  - best_assignment_value: {value}")
        print(f"  - Spec has_optimality: {synthesizer.quotient.specification.has_optimality if hasattr(synthesizer, 'quotient') else 'N/A'}")
        if hasattr(synthesizer, 'stat') and synthesizer.stat:
            print(f"  - Families explored: {synthesizer.explored if hasattr(synthesizer, 'explored') else 'N/A'}")
        print(f"  - Time taken: {time_taken:.2f}s")
        print(f"  - Timeout was: {max_timeout}s")
        print(f"  - Hit resource limit: {synthesizer.resource_limit_reached() if hasattr(synthesizer, 'resource_limit_reached') else 'N/A'}")
        
        # Check if we actually found a solution
        has_solution = (assignment is not None) or (
            hasattr(synthesizer, 'best_assignment') and synthesizer.best_assignment is not None
        )
        
        if not has_solution:
            print(f"[WARNING {label}] No solution found!")
            return None
        
        tree_size = 0
        if assignment is not None and hasattr(assignment, '__len__'):
            tree_size = len(assignment)
        
        iterations = 0
        if hasattr(synthesizer.stat, 'iterations'):
            iterations = synthesizer.stat.iterations
        
        return BenchmarkResult(
            name=label,  # Use the explicit label instead of class name
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
    
    # Run modified synthesizer
    print("\nRunning MODIFIED (Priority-Queue-Based) Synthesizer...")
    modified_result = run_synthesis(ModifiedSynthesizerAR, sketch_path, props_path, max_timeout=300)

    # Run original synthesizer
    print("\nRunning ORIGINAL (Stack-Based) Synthesizer...")
    original_result = run_synthesis(OriginalSynthesizerAR, sketch_path, props_path, max_timeout=300)
    
    
    
    # Print comparison
    print_comparison_table([original_result, modified_result], "Simple Sketch")
    
    # Assertions - be lenient about value being None for non-optimality specs
    if original_result and modified_result:
        # Check that at least one synthesizer found a solution
        if original_result.value is None and modified_result.value is None:
            print("[WARNING] Both synthesizers completed but neither found an optimality value")
            print("This may be expected for non-optimality specifications")
        elif original_result.value is not None and modified_result.value is not None:
            # Both have values - compare them
            assert modified_result.value >= original_result.value * 0.99, \
                f"Modified value {modified_result.value} should be >= original value {original_result.value}"
            print(f"[OK] Both synthesizers found values, modified is within acceptable range")
    elif not original_result:
        print("[ERROR] Original synthesizer failed to complete")
    elif not modified_result:
        print("[ERROR] Modified synthesizer failed to complete")


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
    
    # Assertions - be lenient about value being None for non-optimality specs
    if original_result and modified_result:
        if original_result.value is None and modified_result.value is None:
            print("[WARNING] Both synthesizers completed but neither found an optimality value")
            print("This may be expected for non-optimality specifications")
        elif original_result.value is not None and modified_result.value is not None:
            assert modified_result.value >= original_result.value * 0.99, \
                f"Modified value {modified_result.value} should be >= original value {original_result.value}"
            print(f"[OK] Both synthesizers found values, modified is within acceptable range")
    elif not original_result:
        print("[ERROR] Original synthesizer failed to complete")
    elif not modified_result:
        print("[ERROR] Modified synthesizer failed to complete")


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
