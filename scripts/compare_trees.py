#!/usr/bin/env python3
"""Compare tree performance between two paynt-final.csv files.

This script focuses on tree metrics: 'tree nodes', 'tree depth', and times,
and relates them to solution quality ('best'). It produces per-row comparisons
and classifies outcomes into buckets such as:
 - improved_tree_same_quality: smaller nodes AND best >= base_best
 - improved_tree_better_quality: smaller nodes AND best > base_best
 - larger_tree_better_quality: larger nodes but better best
 - tradeoff: smaller nodes but slightly worse best (within tolerance)
 - worse: larger nodes and worse best

Usage:
    python3 scripts/compare_trees.py --base path/to/base.csv --modified path/to/mod.csv --out tree-compare.csv

Output:
 - CSV with per-row comparisons + classification
 - Printed aggregate counts
"""
import csv
import argparse
from collections import defaultdict

NUMERIC_FIELDS = ['best', 'time (best)', 'time (all)', 'tree nodes', 'tree depth']


def safe_float(s):
    if s is None:
        return None
    s = s.strip()
    if s == '' or s.upper() == 'N/A':
        return None
    try:
        return float(s)
    except Exception:
        return None


def read_index(path):
    idx = {}
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        for r in reader:
            model = r.get('model','').strip()
            max_depth = r.get('max_depth','').strip()
            depth = r.get('depth','').strip()
            key = (model, max_depth, depth)
            # parse numeric fields
            parsed = {f: safe_float(r.get(f)) for f in NUMERIC_FIELDS}
            parsed['raw'] = r
            idx[key] = parsed
    return idx


def classify(b, m, rel_tol=1e-6, small_rel_tol=1e-3):
    # b, m are parsed dicts; returns a classification string
    bn = b.get('tree nodes')
    mn = m.get('tree nodes')
    bd = b.get('tree depth')
    md = m.get('tree depth')
    bb = b.get('best')
    mb = m.get('best')

    # Helper checks
    def is_better_best():
        if bb is None or mb is None:
            return None
        if mb > bb + rel_tol:
            return True
        if mb < bb - rel_tol:
            return False
        return 'tie'

    best_cmp = is_better_best()

    # Node comparison
    if bn is None or mn is None:
        node_cmp = None
    else:
        if mn < bn:
            node_cmp = 'smaller'
        elif mn > bn:
            node_cmp = 'larger'
        else:
            node_cmp = 'equal'

    # Depth comparison
    if bd is None or md is None:
        depth_cmp = None
    else:
        if md < bd:
            depth_cmp = 'shallower'
        elif md > bd:
            depth_cmp = 'deeper'
        else:
            depth_cmp = 'equal'

    # Classification logic
    if best_cmp is True and node_cmp == 'smaller':
        return 'improved_tree_better_quality'
    if best_cmp in (True, 'tie') and node_cmp == 'smaller':
        return 'improved_tree_same_or_better_quality'
    if best_cmp is True and node_cmp in ('larger','equal'):
        return 'larger_tree_better_quality'
    if best_cmp is False and node_cmp == 'smaller':
        # tradeoff: smaller tree but worse quality
        # check relative degradation
        if bb is None or mb is None:
            return 'tradeoff'
        rel = (bb - mb) / abs(bb) if bb != 0 else (bb - mb)
        if abs(rel) <= small_rel_tol:
            return 'tradeoff_small_loss'
        return 'tradeoff'
    if best_cmp is False and node_cmp in ('larger','equal'):
        return 'worse'
    # Fallbacks
    if best_cmp == 'tie' and node_cmp == 'smaller':
        return 'improved_tree_same_quality'
    if best_cmp == 'tie' and node_cmp in ('equal','larger'):
        return 'tie'
    return 'unknown'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True)
    ap.add_argument('--modified', required=True)
    ap.add_argument('--out', default='tree-compare.csv')
    args = ap.parse_args()

    base = read_index(args.base)
    mod = read_index(args.modified)
    keys = set(base.keys()) | set(mod.keys())

    results = []
    counts = defaultdict(int)
    for k in sorted(keys):
        b = base.get(k, {f: None for f in NUMERIC_FIELDS})
        m = mod.get(k, {f: None for f in NUMERIC_FIELDS})
        cls = classify(b, m)
        counts[cls] += 1
        row = {'model': k[0], 'max_depth': k[1], 'depth': k[2], 'class': cls}
        for f in NUMERIC_FIELDS:
            row[f'base_{f}'] = b.get(f)
            row[f'mod_{f}'] = m.get(f)
        results.append(row)

    # Write CSV
    with open(args.out, 'w', newline='') as f:
        fieldnames = ['model','max_depth','depth','class'] + [f'base_{f}' for f in NUMERIC_FIELDS] + [f'mod_{f}' for f in NUMERIC_FIELDS]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(r)

    print('Tree comparison summary:')
    total = sum(counts.values())
    print(f'Total items: {total}')
    for cls, cnt in sorted(counts.items(), key=lambda x: -x[1]):
        print(f'  {cls}: {cnt}')

if __name__ == '__main__':
    main()
