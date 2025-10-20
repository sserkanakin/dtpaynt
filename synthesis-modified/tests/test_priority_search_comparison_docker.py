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


def create_simple_mdp_model():
    """Create a simple MDP model for testing."""
    model_content = """mdp

module simple
    s : [0..5] init 0;
    
    [act1] s=0 -> 0.7:(s'=1) + 0.3:(s'=2);
    [act2] s=0 -> 0.5:(s'=1) + 0.5:(s'=2);
    
    [act1] s=1 -> 0.8:(s'=3) + 0.2:(s'=4);
    [act2] s=1 -> 0.6:(s'=3) + 0.4:(s'=4);
    
    [act1] s=2 -> 0.9:(s'=3) + 0.1:(s'=5);
    [act2] s=2 -> 0.4:(s'=4) + 0.6:(s'=5);
    
    [done] s=3 -> true;
    [done] s=4 -> true;
    [done] s=5 -> true;
endmodule

formula goal = s=3;

rewards "reward"
    s=3 : 10;
    s=4 : 5;
    s=5 : 1;
endrewards
"""
    
    properties_content = """Rmax=? [F goal]"""
    
    return model_content, properties_content


def create_grid_mdp_model():
    """Create a more complex grid-based MDP model."""
    model_content = """mdp

module grid
    x : [0..4] init 0;
    y : [0..4] init 0;
    
    // Movement from start position
    [north] x=0 & y=0 -> 0.8:(y'=1) + 0.2:(x'=1);
    [south] x=0 & y=0 -> true;
    [east]  x=0 & y=0 -> 0.8:(x'=1) + 0.2:(y'=1);
    [west]  x=0 & y=0 -> true;
    
    // General movement rules (simplified for demonstration)
    [north] x>0 & y<4 & !(x=4 & y=4) -> 0.8:(y'=min(y+1,4)) + 0.1:(x'=max(x-1,0)) + 0.1:(x'=min(x+1,4));
    [south] x>0 & y>0 & !(x=4 & y=4) -> 0.8:(y'=max(y-1,0)) + 0.1:(x'=max(x-1,0)) + 0.1:(x'=min(x+1,4));
    [east]  x<4 & y>0 & !(x=4 & y=4) -> 0.8:(x'=min(x+1,4)) + 0.1:(y'=max(y-1,0)) + 0.1:(y'=min(y+1,4));
    [west]  x>0 & y>0 & !(x=4 & y=4) -> 0.8:(x'=max(x-1,0)) + 0.1:(y'=max(y-1,0)) + 0.1:(y'=min(y+1,4));
    
    // Goal state
    [done] x=4 & y=4 -> true;
endmodule

formula goal = x=4 & y=4;

rewards "steps"
    !(x=4 & y=4) : 1;
endrewards

rewards "goal_reward"
    x=4 & y=4 : 100;
endrewards
"""
    
    properties_content = """Rmax=? [F goal]"""
    
    return model_content, properties_content


def run_synthesis(synthesizer_class, sketch_path, props_path, max_timeout=30):
    """Run synthesis with the given synthesizer class."""
    try:
        # Reset the global timer
        paynt.utils.timer.GlobalTimer.reset()
        
        # Load the sketch
        if synthesizer_class == OriginalSynthesizerAR:
            sketch = original_parse_sketch(sketch_path, props_path)
        else:
            sketch = modified_parse_sketch(sketch_path, props_path)
        
        # Create quotient and synthesizer
        quotient = sketch.quotient
        synthesizer = synthesizer_class.choose_synthesizer(quotient)
        
        # Set timeout
        synthesizer.timeout = max_timeout
        
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
    """Test and compare both synthesizers on a simple MDP model."""
    print("\n" + "="*80)
    print("TEST 1: Simple MDP Model Comparison")
    print("="*80)
    
    # Create temporary files for the model
    with tempfile.TemporaryDirectory() as tmpdir:
        sketch_path = os.path.join(tmpdir, "sketch.templ")
        props_path = os.path.join(tmpdir, "sketch.props")
        
        model_content, props_content = create_simple_mdp_model()
        
        with open(sketch_path, 'w') as f:
            f.write(model_content)
        with open(props_path, 'w') as f:
            f.write(props_content)
        
        # Run original synthesizer
        print("\nRunning ORIGINAL (Stack-Based) Synthesizer...")
        original_result = run_synthesis(OriginalSynthesizerAR, sketch_path, props_path)
        
        # Run modified synthesizer
        print("\nRunning MODIFIED (Priority-Queue-Based) Synthesizer...")
        modified_result = run_synthesis(ModifiedSynthesizerAR, sketch_path, props_path)
        
        # Print comparison
        print_comparison_table([original_result, modified_result], "Simple MDP")
        
        # Assertions
        if original_result and modified_result:
            assert modified_result.value is not None, "Modified synthesizer should find a solution"
            if original_result.value is not None:
                assert modified_result.value >= original_result.value * 0.99, \
                    f"Modified value {modified_result.value} should be >= original value {original_result.value}"


def test_grid_mdp_comparison():
    """Test and compare both synthesizers on a grid MDP model."""
    print("\n" + "="*80)
    print("TEST 2: Grid MDP Model Comparison")
    print("="*80)
    
    # Create temporary files for the model
    with tempfile.TemporaryDirectory() as tmpdir:
        sketch_path = os.path.join(tmpdir, "sketch.templ")
        props_path = os.path.join(tmpdir, "sketch.props")
        
        model_content, props_content = create_grid_mdp_model()
        
        with open(sketch_path, 'w') as f:
            f.write(model_content)
        with open(props_path, 'w') as f:
            f.write(props_content)
        
        # Run original synthesizer
        print("\nRunning ORIGINAL (Stack-Based) Synthesizer...")
        original_result = run_synthesis(OriginalSynthesizerAR, sketch_path, props_path, max_timeout=60)
        
        # Run modified synthesizer
        print("\nRunning MODIFIED (Priority-Queue-Based) Synthesizer...")
        modified_result = run_synthesis(ModifiedSynthesizerAR, sketch_path, props_path, max_timeout=60)
        
        # Print comparison
        print_comparison_table([original_result, modified_result], "Grid MDP")
        
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
