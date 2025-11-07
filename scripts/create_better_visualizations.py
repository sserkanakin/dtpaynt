#!/usr/bin/env python3
"""
Create better visualizations for DTPAYNT results.
Focuses on metrics that actually vary and uses appropriate chart types.
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional

try:
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np
except ImportError as e:
    print(f"Error: Missing required package: {e}")
    print("Install with: pip install pandas matplotlib numpy")
    sys.exit(1)

# Color schemes
ALGO_COLORS = {
    'original': '#1f77b4',
    'modified_value_only': '#ff7f0e',
    'modified_value_size_alpha0.01': '#2ca02c',
    'modified_value_size_alpha0.1': '#d62728',
    'modified_value_size_alpha0.5': '#9467bd',
}

ALGO_LABELS = {
    'original': 'Original (DFS)',
    'modified_value_only': 'Modified value_only',
    'modified_value_size_alpha0.01': 'Modified value_size α=0.01',
    'modified_value_size_alpha0.1': 'Modified value_size α=0.1',
    'modified_value_size_alpha0.5': 'Modified value_size α=0.5',
}


def load_all_runs(logs_root: Path) -> Dict[str, Dict[str, pd.DataFrame]]:
    """Load all progress CSVs organized by algorithm and benchmark."""
    data = {}
    
    for algo_dir in logs_root.iterdir():
        if not algo_dir.is_dir():
            continue
        algo = algo_dir.name
        data[algo] = {}
        
        for bench_dir in algo_dir.iterdir():
            if not bench_dir.is_dir():
                continue
            bench = bench_dir.name
            
            # Find latest run
            run_dirs = sorted([d for d in bench_dir.iterdir() if d.is_dir()])
            if not run_dirs:
                continue
            
            latest_run = run_dirs[-1]
            csv_path = latest_run / "progress.csv"
            
            if csv_path.exists():
                try:
                    df = pd.read_csv(csv_path)
                    data[algo][bench] = df
                except Exception as e:
                    print(f"Warning: Could not read {csv_path}: {e}")
    
    return data


def plot_comparative_bar_chart(data: Dict[str, Dict[str, pd.DataFrame]], 
                                 output_dir: Path,
                                 metric: str,
                                 title: str,
                                 ylabel: str):
    """Create comparative bar chart for a specific metric across algorithms and benchmarks."""
    
    benchmarks = set()
    for algo_data in data.values():
        benchmarks.update(algo_data.keys())
    benchmarks = sorted(benchmarks)
    
    if not benchmarks:
        return
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    x = np.arange(len(benchmarks))
    width = 0.15
    algos = sorted(data.keys())
    
    for i, algo in enumerate(algos):
        values = []
        for bench in benchmarks:
            if bench in data[algo]:
                df = data[algo][bench]
                # Get last non-null value for this metric
                series = df[metric].dropna()
                if not series.empty:
                    if metric in ['best_value', 'time_to_best', 'finish_time']:
                        values.append(float(series.iloc[-1]))
                    else:
                        values.append(int(series.iloc[-1]))
                else:
                    values.append(0)
            else:
                values.append(0)
        
        offset = (i - len(algos)/2) * width
        color = ALGO_COLORS.get(algo, f'C{i}')
        label = ALGO_LABELS.get(algo, algo)
        ax.bar(x + offset, values, width, label=label, color=color, alpha=0.8)
    
    ax.set_xlabel('Benchmark', fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(benchmarks, rotation=0)
    ax.legend(loc='best', fontsize=9)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    
    plt.tight_layout()
    output_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_dir / f'bar_{metric}.png', dpi=150, bbox_inches='tight')
    plt.close(fig)


def plot_timeline_comparison(data: Dict[str, Dict[str, pd.DataFrame]], 
                               output_dir: Path,
                               benchmark: str,
                               metric: str,
                               ylabel: str):
    """Plot timeline showing how a metric evolves over time for all algorithms on one benchmark."""
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    for algo in sorted(data.keys()):
        if benchmark not in data[algo]:
            continue
        
        df = data[algo][benchmark]
        ts = pd.to_numeric(df['timestamp'], errors='coerce').dropna()
        vals = pd.to_numeric(df[metric], errors='coerce')
        
        # Align with timestamps
        valid_idx = ts.index.intersection(vals.dropna().index)
        if valid_idx.empty:
            continue
        
        ts_aligned = ts.loc[valid_idx]
        vals_aligned = vals.loc[valid_idx]
        
        color = ALGO_COLORS.get(algo, None)
        label = ALGO_LABELS.get(algo, algo)
        ax.step(ts_aligned, vals_aligned, where='post', label=label, 
                linewidth=2, alpha=0.8, color=color)
    
    ax.set_xlabel('Time (seconds)', fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(f'{ylabel} over Time - {benchmark}', fontsize=14, fontweight='bold')
    ax.legend(loc='best', fontsize=9)
    ax.grid(True, alpha=0.3, linestyle='--')
    
    plt.tight_layout()
    output_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_dir / f'timeline_{benchmark}_{metric}.png', dpi=150, bbox_inches='tight')
    plt.close(fig)


def plot_best_value_timelines(data: Dict[str, Dict[str, pd.DataFrame]],
                               output_dir: Path) -> None:
    """Plot Best Value (V_best) vs Time for all algorithms per benchmark."""
    benchmarks = set()
    for algo_data in data.values():
        benchmarks.update(algo_data.keys())
    if not benchmarks:
        return

    for benchmark in sorted(benchmarks):
        fig, ax = plt.subplots(figsize=(10, 6))
        found_any = False
        for algo in sorted(data.keys()):
            if benchmark not in data[algo]:
                continue
            df = data[algo][benchmark]
            ts = pd.to_numeric(df['timestamp'], errors='coerce')
            vals = pd.to_numeric(df['best_value'], errors='coerce')
            valid_idx = ts.dropna().index.intersection(vals.dropna().index)
            if valid_idx.empty:
                continue
            found_any = True
            ts_aligned = ts.loc[valid_idx]
            vals_aligned = vals.loc[valid_idx]
            color = ALGO_COLORS.get(algo, None)
            label = ALGO_LABELS.get(algo, algo)
            ax.step(ts_aligned, vals_aligned, where='post', label=label,
                    linewidth=2, alpha=0.9, color=color)

        if not found_any:
            plt.close(fig)
            continue
        ax.set_xlabel('Time (seconds)', fontsize=12)
        ax.set_ylabel('Best Value (V_best)', fontsize=12)
        ax.set_title(f'Anytime Performance: Best Value vs Time — {benchmark}', fontsize=14, fontweight='bold')
        ax.legend(loc='best', fontsize=9)
        ax.grid(True, alpha=0.3, linestyle='--')
        plt.tight_layout()
        output_dir.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_dir / f'timeline_{benchmark}_best_value.png', dpi=150, bbox_inches='tight')
        plt.close(fig)


def create_summary_table(data: Dict[str, Dict[str, pd.DataFrame]], output_dir: Path):
    """Create a comprehensive summary table with key metrics."""
    
    rows = []
    
    for algo in sorted(data.keys()):
        for bench in sorted(data[algo].keys()):
            df = data[algo][bench]
            
            # Extract final values
            best_value = df['best_value'].dropna()
            final_best = float(best_value.iloc[-1]) if not best_value.empty else None
            
            # Time to best value
            if final_best is not None and not best_value.empty:
                best_rows = df[df['best_value'] == final_best]
                time_to_best = best_rows['timestamp'].min() if not best_rows.empty else None
            else:
                time_to_best = None
            
            # Total time
            total_time = df['timestamp'].max()
            
            # Families evaluated
            families = df['families_evaluated'].dropna()
            final_families = int(families.iloc[-1]) if not families.empty else None
            
            # Max frontier
            frontier = df['frontier_size'].dropna()
            max_frontier = int(frontier.max()) if not frontier.empty else None
            final_frontier = int(frontier.iloc[-1]) if not frontier.empty else None
            
            # Tree size (should be constant)
            tree_size = df['tree_size'].dropna()
            final_tree_size = int(tree_size.iloc[-1]) if not tree_size.empty else None
            
            # Tree depth
            tree_depth = df['tree_depth'].dropna()
            final_tree_depth = int(tree_depth.iloc[-1]) if not tree_depth.empty else None
            
            rows.append({
                'Algorithm': ALGO_LABELS.get(algo, algo),
                'Benchmark': bench,
                'Best Value': f'{final_best:.6f}' if final_best is not None else 'N/A',
                'Time to Best (s)': f'{time_to_best:.2f}' if time_to_best is not None else 'N/A',
                'Total Time (s)': f'{total_time:.2f}' if total_time is not None else 'N/A',
                'Families Evaluated': final_families if final_families is not None else 'N/A',
                'Max Frontier Size': max_frontier if max_frontier is not None else 'N/A',
                'Final Frontier': final_frontier if final_frontier is not None else 'N/A',
                'Tree Size': final_tree_size if final_tree_size is not None else 'N/A',
                'Tree Depth': final_tree_depth if final_tree_depth is not None else 'N/A',
            })
    
    if rows:
        summary_df = pd.DataFrame(rows)
        output_dir.mkdir(parents=True, exist_ok=True)
        summary_df.to_csv(output_dir / 'comprehensive_summary.csv', index=False)
        print(f"Created summary table: {output_dir / 'comprehensive_summary.csv'}")


def generate_scatter_plots(data: Dict[str, Dict[str, pd.DataFrame]], output_dir: Path):
    """Generate scatter plots comparing algorithms."""
    if plt is None:
        return
    
    # Collect data for scatter plots
    records = []
    for algo in data.keys():
        for bench in data[algo].keys():
            df = data[algo][bench]
            
            best_value = df['best_value'].dropna()
            final_best = float(best_value.iloc[-1]) if not best_value.empty else None
            
            # Time to best
            if final_best is not None:
                best_rows = df[df['best_value'] == final_best]
                time_to_best = float(best_rows['timestamp'].min()) if not best_rows.empty else None
            else:
                time_to_best = None
            
            families = df['families_evaluated'].dropna()
            final_families = int(families.iloc[-1]) if not families.empty else None
            
            frontier = df['frontier_size'].dropna()
            max_frontier = int(frontier.max()) if not frontier.empty else None
            
            if time_to_best and final_families and max_frontier:
                records.append({
                    'algorithm': algo,
                    'benchmark': bench,
                    'time_to_best': time_to_best,
                    'families': final_families,
                    'max_frontier': max_frontier,
                    'best_value': final_best
                })
    
    if not records:
        return
    
    scatter_df = pd.DataFrame(records)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Plot 1: Time vs Families Evaluated
    fig, ax = plt.subplots(figsize=(10, 6))
    for algo in sorted(scatter_df['algorithm'].unique()):
        subset = scatter_df[scatter_df['algorithm'] == algo]
        color = ALGO_COLORS.get(algo, None)
        label = ALGO_LABELS.get(algo, algo)
        ax.scatter(subset['families'], subset['time_to_best'], 
                  label=label, color=color, s=100, alpha=0.7, edgecolors='black')
    
    ax.set_xlabel('Families Evaluated', fontsize=12)
    ax.set_ylabel('Time to Best Solution (s)', fontsize=12)
    ax.set_title('Efficiency: Families Evaluated vs Time', fontsize=14, fontweight='bold')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3, linestyle='--')
    plt.tight_layout()
    fig.savefig(output_dir / 'scatter_families_vs_time.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  Created scatter plot: families vs time")
    
    # Plot 2: Memory (frontier) vs Time
    fig, ax = plt.subplots(figsize=(10, 6))
    for algo in sorted(scatter_df['algorithm'].unique()):
        subset = scatter_df[scatter_df['algorithm'] == algo]
        color = ALGO_COLORS.get(algo, None)
        label = ALGO_LABELS.get(algo, algo)
        ax.scatter(subset['max_frontier'], subset['time_to_best'],
                  label=label, color=color, s=100, alpha=0.7, edgecolors='black')
    
    ax.set_xlabel('Max Frontier Size (Memory)', fontsize=12)
    ax.set_ylabel('Time to Best Solution (s)', fontsize=12)
    ax.set_title('Memory vs Time Trade-off', fontsize=14, fontweight='bold')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3, linestyle='--')
    plt.tight_layout()
    fig.savefig(output_dir / 'scatter_frontier_vs_time.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  Created scatter plot: frontier vs time")


def plot_value_vs_size_scatter(data: Dict[str, Dict[str, pd.DataFrame]], output_dir: Path) -> None:
    """Scatter plot of Tree Size (X) vs Best Value (Y) across algorithms/benchmarks."""
    records = []
    for algo in data.keys():
        for bench in data[algo].keys():
            df = data[algo][bench]
            best_value = pd.to_numeric(df['best_value'], errors='coerce').dropna()
            tree_size = pd.to_numeric(df['tree_size'], errors='coerce').dropna()
            if best_value.empty or tree_size.empty:
                continue
            records.append({
                'algorithm': algo,
                'benchmark': bench,
                'best_value': float(best_value.iloc[-1]),
                'tree_size': int(tree_size.iloc[-1]),
            })

    if not records:
        return

    dfp = pd.DataFrame(records)
    fig, ax = plt.subplots(figsize=(10, 6))
    for (bench, algo), group in dfp.groupby(['benchmark', 'algorithm']):
        color = ALGO_COLORS.get(algo, None)
        label = f"{ALGO_LABELS.get(algo, algo)} · {bench}"
        ax.scatter(group['tree_size'], group['best_value'], s=120, alpha=0.85,
                   edgecolors='black', color=color, label=label)

    ax.set_xlabel('Tree Size (nodes) — lower is better', fontsize=12)
    ax.set_ylabel('Best Value (V_best) — higher is better', fontsize=12)
    ax.set_title('Value vs Size Trade-off (All benchmarks)', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.legend(loc='best', fontsize=9)
    plt.tight_layout()
    output_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_dir / 'scatter_tree_size_vs_value.png', dpi=150, bbox_inches='tight')
    plt.close(fig)


def create_comparison_matrix(data: Dict[str, Dict[str, pd.DataFrame]], output_dir: Path):
    """Create a comparison matrix showing which algorithm is best for each metric."""
    
    benchmarks = set()
    for algo_data in data.values():
        benchmarks.update(algo_data.keys())
    
    if not benchmarks:
        return
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_dir / 'winner_analysis.txt', 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("ALGORITHM PERFORMANCE WINNERS BY METRIC\n")
        f.write("=" * 80 + "\n\n")
        
        for bench in sorted(benchmarks):
            f.write(f"\n{'='*80}\n")
            f.write(f"BENCHMARK: {bench}\n")
            f.write(f"{'='*80}\n\n")
            
            # Collect metrics for this benchmark
            results = {}
            for algo in data.keys():
                if bench not in data[algo]:
                    continue
                df = data[algo][bench]
                
                best_value = df['best_value'].dropna()
                final_best = float(best_value.iloc[-1]) if not best_value.empty else None
                
                if final_best:
                    best_rows = df[df['best_value'] == final_best]
                    time_to_best = float(best_rows['timestamp'].min())
                else:
                    time_to_best = float('inf')
                
                families = df['families_evaluated'].dropna()
                final_families = int(families.iloc[-1]) if not families.empty else float('inf')
                
                frontier = df['frontier_size'].dropna()
                max_frontier = int(frontier.max()) if not frontier.empty else float('inf')
                
                results[algo] = {
                    'time': time_to_best,
                    'families': final_families,
                    'frontier': max_frontier,
                    'value': final_best if final_best else 0
                }
            
            if not results:
                continue
            
            # Find winners
            fastest = min(results.items(), key=lambda x: x[1]['time'])
            fewest_families = min(results.items(), key=lambda x: x[1]['families'])
            smallest_frontier = min(results.items(), key=lambda x: x[1]['frontier'])
            best_value = max(results.items(), key=lambda x: x[1]['value'])
            
            f.write(f"🏆 FASTEST (Time to Solution):\n")
            f.write(f"   {ALGO_LABELS.get(fastest[0], fastest[0])}: {fastest[1]['time']:.2f}s\n\n")
            
            f.write(f"🏆 MOST EFFICIENT (Fewest Family Evaluations):\n")
            f.write(f"   {ALGO_LABELS.get(fewest_families[0], fewest_families[0])}: {fewest_families[1]['families']} families\n\n")
            
            f.write(f"🏆 LOWEST MEMORY (Smallest Frontier):\n")
            f.write(f"   {ALGO_LABELS.get(smallest_frontier[0], smallest_frontier[0])}: {smallest_frontier[1]['frontier']} nodes\n\n")
            
            f.write(f"🏆 BEST VALUE:\n")
            f.write(f"   {ALGO_LABELS.get(best_value[0], best_value[0])}: {best_value[1]['value']:.6f}\n\n")
            
            # Full rankings
            f.write(f"\nFULL RANKINGS:\n")
            f.write(f"-" * 80 + "\n")
            f.write(f"{'Algorithm':<40} {'Time (s)':<12} {'Families':<12} {'Frontier':<12}\n")
            f.write(f"-" * 80 + "\n")
            for algo in sorted(results.keys()):
                label = ALGO_LABELS.get(algo, algo)
                time_val = f"{results[algo]['time']:.2f}" if results[algo]['time'] != float('inf') else "N/A"
                families_val = f"{results[algo]['families']}" if results[algo]['families'] != float('inf') else "N/A"
                frontier_val = f"{results[algo]['frontier']}" if results[algo]['frontier'] != float('inf') else "N/A"
                f.write(f"{label:<40} {time_val:<12} {families_val:<12} {frontier_val:<12}\n")
    
    print(f"Created winner analysis: {output_dir / 'winner_analysis.txt'}")


def main():
    parser = argparse.ArgumentParser(description='Create enhanced visualizations for DTPAYNT results')
    parser.add_argument('--logs-root', type=Path, required=True,
                        help='Root directory containing algorithm logs')
    parser.add_argument('--output-dir', type=Path, required=True,
                        help='Output directory for visualizations')
    
    args = parser.parse_args()
    
    print(f"Loading data from {args.logs_root}...")
    data = load_all_runs(args.logs_root)
    
    if not data:
        print("No data found!")
        return 1
    
    print(f"Loaded data for {len(data)} algorithms")
    
    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate summary table
    print("Creating summary table...")
    create_summary_table(data, args.output_dir)
    
    # Generate comparison matrix and winner analysis
    print("Creating winner analysis...")
    create_comparison_matrix(data, args.output_dir)
    
    # Generate bar charts for key metrics
    print("Creating bar charts...")
    metrics_to_plot = [
        ('families_evaluated', 'Families Evaluated (Final)', 'Families Evaluated'),
        ('frontier_size', 'Frontier Size (Final)', 'Frontier Size (nodes)'),
    ]
    
    for metric, title, ylabel in metrics_to_plot:
        plot_comparative_bar_chart(data, args.output_dir, metric, title, ylabel)
        print(f"  Created bar chart for {metric}")
    
    # Generate scatter plots
    print("Creating scatter plots...")
    generate_scatter_plots(data, args.output_dir)
    # RQ2: Value vs Size (money plot)
    plot_value_vs_size_scatter(data, args.output_dir)
    
    # Generate timeline plots for each benchmark
    print("Creating timeline plots...")
    benchmarks = set()
    for algo_data in data.values():
        benchmarks.update(algo_data.keys())
    
    timeline_metrics = [
        ('frontier_size', 'Frontier Size'),
        ('families_evaluated', 'Families Evaluated'),
    ]
    
    for benchmark in sorted(benchmarks):
        for metric, ylabel in timeline_metrics:
            plot_timeline_comparison(data, args.output_dir, benchmark, metric, ylabel)
            print(f"  Created timeline for {benchmark} - {metric}")
    # RQ1: Best value vs time timelines
    plot_best_value_timelines(data, args.output_dir)
    print("  Created best value (anytime) timelines")
    
    print(f"\n✅ All visualizations created in {args.output_dir}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
