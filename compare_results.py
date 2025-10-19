#!/usr/bin/env python3
"""
Compare results between original and symbiotic DTPAYNT versions.

Analyzes synthesis logs to extract metrics and show improvements.

Usage:
  python3 compare_results.py --original ./results-original --symbiotic ./results-symbiotic
  python3 compare_results.py --original ./results-original --symbiotic ./results-symbiotic --output report.txt
"""

import json
import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class SynthesisMetrics:
    """Metrics extracted from a single synthesis run"""
    method: str  # 'original' or 'symbiotic'
    model_name: str
    synthesis_time: float  # seconds
    tree_nodes: int  # number of decision nodes
    tree_depth: int  # tree height
    optimum_value: float  # objective value
    raw_log: str = field(default="")


@dataclass
class ComparisonResult:
    """Comparison between original and symbiotic for one model"""
    model_name: str
    original: Optional[SynthesisMetrics] = None
    symbiotic: Optional[SynthesisMetrics] = None
    
    def has_both(self) -> bool:
        return self.original is not None and self.symbiotic is not None
    
    def time_speedup(self) -> float:
        """Return (symbiotic_time / original_time). > 1 means slower."""
        if not self.has_both():
            return None
        if self.original.synthesis_time == 0:
            return float('inf')
        return self.symbiotic.synthesis_time / self.original.synthesis_time
    
    def value_improvement(self) -> float:
        """Return percentage improvement. > 0 means better."""
        if not self.has_both():
            return None
        orig = self.original.optimum_value
        symb = self.symbiotic.optimum_value
        if orig == 0:
            return 0
        return ((symb - orig) / abs(orig)) * 100
    
    def tree_size_reduction(self) -> float:
        """Return percentage reduction. > 0 means smaller tree."""
        if not self.has_both():
            return None
        orig_size = self.original.tree_nodes
        symb_size = self.symbiotic.tree_nodes
        if orig_size == 0:
            return 0
        return ((orig_size - symb_size) / orig_size) * 100


class LogParser:
    """Parse synthesis logs from stdout.txt files"""
    
    @staticmethod
    def parse_stdout(log_path: Path) -> Optional[SynthesisMetrics]:
        """Extract metrics from a stdout.txt file"""
        if not log_path.exists():
            return None
        
        content = log_path.read_text()
        
        # Extract model name from directory path
        # Expected: .../logs/paynt-smoke-test/1/model_name/stdout.txt
        parts = log_path.parts
        try:
            model_idx = parts.index('paynt-smoke-test') + 2  # Skip 'paynt-smoke-test' and '1'
            model_name = parts[model_idx]
        except (ValueError, IndexError):
            model_name = "unknown"
        
        metrics = SynthesisMetrics(
            method="unknown",
            model_name=model_name,
            synthesis_time=0.0,
            tree_nodes=0,
            tree_depth=0,
            optimum_value=0.0,
            raw_log=content
        )
        
        # Detect method
        if "symbiotic" in content.lower():
            metrics.method = "symbiotic"
        elif "ar_multicore" in content:
            metrics.method = "ar_multicore"
        elif "method ar" in content or "Abstraction-Refinement" in content:
            metrics.method = "ar"
        else:
            metrics.method = "unknown"
        
        # Extract synthesis time (in seconds)
        # Pattern: "synthesis time: X.XXs" or "Total time: X.XXs"
        time_patterns = [
            r'synthesis time:\s*([\d.]+)\s*s',
            r'Total time:\s*([\d.]+)\s*s',
            r'Time:\s*([\d.]+)\s*s',
        ]
        for pattern in time_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                metrics.synthesis_time = float(match.group(1))
                break
        
        # Extract optimum value
        # Pattern: "optimum: -XX.XXXXXX" or "objective: -XX.XXXXXX"
        value_patterns = [
            r'optimum:\s*([-\d.]+)',
            r'objective:\s*([-\d.]+)',
            r'value:\s*([-\d.]+)',
        ]
        for pattern in value_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                # Take the last value (final result)
                metrics.optimum_value = float(matches[-1])
                break
        
        # Extract tree size (decision nodes)
        # Pattern: "with X decision nodes" or "X decision nodes"
        node_patterns = [
            r'with\s+(\d+)\s+decision nodes',
            r'(\d+)\s+decision nodes',
            r'Nodes:\s+(\d+)',
        ]
        for pattern in node_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                # Take the last value (final tree)
                metrics.tree_nodes = max(int(m) for m in matches)
                break
        
        # Extract tree depth
        # Pattern: "depth: X" or "Depth: X"
        depth_patterns = [
            r'(?:tree\s+)?depth:\s*(\d+)',
            r'Depth:\s*(\d+)',
        ]
        for pattern in depth_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                metrics.tree_depth = max(int(m) for m in matches)
                break
        
        return metrics
    
    @staticmethod
    def find_all_logs(result_dir: Path) -> Dict[str, Path]:
        """Find all stdout.txt files in result directory"""
        logs = {}
        
        # Look for pattern: logs/paynt-smoke-test/1/model_name/stdout.txt
        target_pattern = result_dir / "logs" / "paynt-smoke-test" / "1"
        
        if target_pattern.exists():
            for model_dir in target_pattern.iterdir():
                stdout = model_dir / "stdout.txt"
                if stdout.exists():
                    logs[model_dir.name] = stdout
        
        return logs


class ResultsAnalyzer:
    """Analyze and compare synthesis results"""
    
    def __init__(self, original_dir: Path, symbiotic_dir: Path):
        self.original_dir = original_dir
        self.symbiotic_dir = symbiotic_dir
        self.comparisons: List[ComparisonResult] = []
        self._load_results()
    
    def _load_results(self):
        """Load and parse results from both directories"""
        parser = LogParser()
        
        # Find all logs
        original_logs = parser.find_all_logs(self.original_dir)
        symbiotic_logs = parser.find_all_logs(self.symbiotic_dir)
        
        # Get all model names
        all_models = set(original_logs.keys()) | set(symbiotic_logs.keys())
        
        # Parse and compare
        for model_name in sorted(all_models):
            comparison = ComparisonResult(model_name=model_name)
            
            # Parse original
            if model_name in original_logs:
                comparison.original = parser.parse_stdout(original_logs[model_name])
                if comparison.original:
                    comparison.original.method = "original"
            
            # Parse symbiotic
            if model_name in symbiotic_logs:
                comparison.symbiotic = parser.parse_stdout(symbiotic_logs[model_name])
                if comparison.symbiotic:
                    comparison.symbiotic.method = "symbiotic"
            
            self.comparisons.append(comparison)
    
    def generate_report(self) -> str:
        """Generate human-readable comparison report"""
        lines = []
        
        lines.append("=" * 80)
        lines.append("DTPAYNT Synthesis Results: Original vs Symbiotic")
        lines.append("=" * 80)
        lines.append("")
        
        # Summary statistics
        lines.append("SUMMARY")
        lines.append("-" * 80)
        
        comparable = [c for c in self.comparisons if c.has_both()]
        lines.append(f"Models analyzed: {len(comparable)}/{len(self.comparisons)}")
        
        if comparable:
            avg_speedup = sum(c.time_speedup() for c in comparable) / len(comparable)
            avg_improvement = sum(c.value_improvement() for c in comparable) / len(comparable)
            avg_size_reduction = sum(c.tree_size_reduction() for c in comparable) / len(comparable)
            
            lines.append(f"Average time factor: {avg_speedup:.2f}x")
            lines.append(f"Average value improvement: {avg_improvement:+.2f}%")
            lines.append(f"Average tree size reduction: {avg_size_reduction:+.2f}%")
            
            # Count improvements
            time_worse = sum(1 for c in comparable if c.time_speedup() > 1.0)
            value_better = sum(1 for c in comparable if c.value_improvement() > 0)
            size_smaller = sum(1 for c in comparable if c.tree_size_reduction() > 0)
            
            lines.append(f"Models where symbiotic is slower: {time_worse}/{len(comparable)}")
            lines.append(f"Models where symbiotic is better quality: {value_better}/{len(comparable)}")
            lines.append(f"Models where symbiotic has smaller tree: {size_smaller}/{len(comparable)}")
        
        lines.append("")
        lines.append("")
        
        # Per-model details
        lines.append("DETAILED RESULTS")
        lines.append("-" * 80)
        lines.append("")
        
        for comparison in self.comparisons:
            lines.append(f"Model: {comparison.model_name}")
            lines.append("  " + "-" * 76)
            
            if not comparison.has_both():
                if comparison.original:
                    lines.append(f"  ✓ Original only: {comparison.original.synthesis_time:.2f}s")
                if comparison.symbiotic:
                    lines.append(f"  ✓ Symbiotic only: {comparison.symbiotic.synthesis_time:.2f}s")
                lines.append("")
                continue
            
            # Side-by-side comparison
            orig = comparison.original
            symb = comparison.symbiotic
            
            # Time
            time_factor = comparison.time_speedup()
            time_symbol = "↑" if time_factor > 1 else "↓"
            lines.append(f"  Time:     {orig.synthesis_time:7.2f}s → {symb.synthesis_time:7.2f}s ({time_symbol} {abs(1-time_factor):.2f}x)")
            
            # Value
            value_improv = comparison.value_improvement()
            value_symbol = "↑" if value_improv > 0 else "↓"
            lines.append(f"  Value:    {orig.optimum_value:9.6f} → {symb.optimum_value:9.6f} ({value_symbol} {abs(value_improv):+.2f}%)")
            
            # Tree size
            size_reduction = comparison.tree_size_reduction()
            size_symbol = "↓" if size_reduction > 0 else "↑"
            lines.append(f"  Nodes:    {orig.tree_nodes:3d} → {symb.tree_nodes:3d} ({size_symbol} {abs(size_reduction):+.1f}%)")
            
            # Depth
            lines.append(f"  Depth:    {orig.tree_depth:3d} → {symb.tree_depth:3d}")
            
            # Verdict
            if value_improv > 0 or size_reduction > 0:
                if time_factor > 2.0:
                    verdict = "Mixed: Better quality but 2x+ slower"
                else:
                    verdict = "✓ Better quality (worth the time)"
            else:
                if time_factor < 0.5:
                    verdict = "✓ Better speed"
                else:
                    verdict = "Trade-off: Slower but not better"
            
            lines.append(f"  Verdict:  {verdict}")
            lines.append("")
        
        lines.append("")
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def generate_json_report(self) -> str:
        """Generate JSON format report"""
        data = {
            "timestamp": "comparison",
            "original_dir": str(self.original_dir),
            "symbiotic_dir": str(self.symbiotic_dir),
            "models": []
        }
        
        for comparison in self.comparisons:
            model_data = {
                "name": comparison.model_name,
                "original": None,
                "symbiotic": None,
                "comparison": {
                    "speedup_factor": comparison.time_speedup(),
                    "value_improvement_percent": comparison.value_improvement(),
                    "tree_size_reduction_percent": comparison.tree_size_reduction(),
                }
            }
            
            if comparison.original:
                model_data["original"] = {
                    "synthesis_time": comparison.original.synthesis_time,
                    "tree_nodes": comparison.original.tree_nodes,
                    "tree_depth": comparison.original.tree_depth,
                    "optimum_value": comparison.original.optimum_value,
                }
            
            if comparison.symbiotic:
                model_data["symbiotic"] = {
                    "synthesis_time": comparison.symbiotic.synthesis_time,
                    "tree_nodes": comparison.symbiotic.tree_nodes,
                    "tree_depth": comparison.symbiotic.tree_depth,
                    "optimum_value": comparison.symbiotic.optimum_value,
                }
            
            data["models"].append(model_data)
        
        return json.dumps(data, indent=2)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Compare DTPAYNT synthesis results between original and symbiotic versions"
    )
    parser.add_argument("--original", type=Path, required=True,
                       help="Path to original version results directory")
    parser.add_argument("--symbiotic", type=Path, required=True,
                       help="Path to symbiotic version results directory")
    parser.add_argument("--output", type=Path, default=None,
                       help="Output file for report (default: stdout)")
    parser.add_argument("--json", action="store_true",
                       help="Output as JSON instead of human-readable")
    
    args = parser.parse_args()
    
    # Validate directories
    if not args.original.exists():
        print(f"Error: Original results directory not found: {args.original}", file=sys.stderr)
        sys.exit(1)
    if not args.symbiotic.exists():
        print(f"Error: Symbiotic results directory not found: {args.symbiotic}", file=sys.stderr)
        sys.exit(1)
    
    # Analyze
    print("Analyzing results...", file=sys.stderr)
    analyzer = ResultsAnalyzer(args.original, args.symbiotic)
    
    # Generate report
    if args.json:
        report = analyzer.generate_json_report()
    else:
        report = analyzer.generate_report()
    
    # Output
    if args.output:
        args.output.write_text(report)
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(report)


if __name__ == "__main__":
    main()
