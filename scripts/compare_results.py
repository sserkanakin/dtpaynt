#!/usr/bin/env python3
"""Compare two paynt-final.csv files and report per-model and aggregate stats.

Usage:
    ./scripts/compare_results.py --base results_original_subset/logs/paynt-final.csv \
        --modified results_modified_subset/logs/paynt-final.csv [--out out.csv]

Output:
 - Prints summary to stdout
 - Writes a CSV with per-row comparisons if --out is provided (default: compare-output.csv)

Matching key: model + max_depth + depth (these appear to uniquely identify runs in the sample files).

Metrics compared:
 - best (float) -> higher is better
 - best relative (float) -> higher is better
 - time (best) (float seconds) -> lower is better
 - time (all) (float seconds) -> lower is better
 - tree nodes (int) -> lower is better (smaller search)
 - tree depth (int) -> lower may be considered better (shallower)

The script gracefully handles 'N/A' and missing rows.
"""
import csv
import argparse
from collections import namedtuple, defaultdict
from math import isnan

KEY_FIELDS = ['model', 'max_depth', 'depth']
NUMERIC_FIELDS = ['best', 'best relative', 'time (best)', 'time (all)', 'tree nodes', 'tree depth']


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


def read_csv(path):
    rows = []
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        for r in reader:
            # Normalize keys: strip and lower-case some
            # Keep original header names; assume sample headers present.
            row = {k.strip(): v.strip() for k, v in r.items()}
            # Extract key
            key = tuple(row.get(k, '').strip() for k in ['model', 'max_depth', 'depth'])
            # parse numeric fields
            parsed = {}
            for nf in NUMERIC_FIELDS:
                parsed[nf] = safe_float(row.get(nf))
            parsed['raw'] = row
            parsed['key'] = key
            rows.append(parsed)
    return rows


def make_index(rows):
    idx = {}
    for r in rows:
        idx[r['key']] = r
    return idx


def compare_pair(base, mod):
    # returns dict of comparisons
    out = {}
    for nf in NUMERIC_FIELDS:
        b = base.get(nf)
        m = mod.get(nf)
        out[nf] = {'base': b, 'mod': m}
        if b is None and m is None:
            out[nf]['better'] = 'tie'
        elif b is None:
            out[nf]['better'] = 'mod'  # mod has data, base doesn't
        elif m is None:
            out[nf]['better'] = 'base'
        else:
            # determine direction: for 'best' and 'best relative' higher is better.
            if nf in ('best', 'best relative'):
                if m > b:
                    out[nf]['better'] = 'mod'
                elif m < b:
                    out[nf]['better'] = 'base'
                else:
                    out[nf]['better'] = 'tie'
            else:
                # for times and sizes lower is better
                if m < b:
                    out[nf]['better'] = 'mod'
                elif m > b:
                    out[nf]['better'] = 'base'
                else:
                    out[nf]['better'] = 'tie'
    return out


def summarize(comparisons):
    stats = defaultdict(int)
    diffs = defaultdict(list)
    for c in comparisons:
        key = c['key']
        comp = c['comparison']
        # primary metric: 'best' deciding winner
        primary = comp['best']['better']
        stats['total'] += 1
        if primary == 'mod':
            stats['mod_better'] += 1
        elif primary == 'base':
            stats['base_better'] += 1
        else:
            stats['tie'] += 1
        # record numeric deltas where available
        b = comp['best']['base']
        m = comp['best']['mod']
        if b is not None and m is not None:
            diffs['best'].append(m - b)
        tb = comp['time (best)']['base']
        tm = comp['time (best)']['mod']
        if tb is not None and tm is not None:
            diffs['time_best'].append(tm - tb)
    # compute averages
    avgs = {}
    for k, lst in diffs.items():
        if lst:
            avgs[k] = sum(lst) / len(lst)
        else:
            avgs[k] = None
    return stats, avgs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True, help='base CSV (original)')
    ap.add_argument('--modified', required=True, help='modified CSV')
    ap.add_argument('--out', default='compare-output.csv', help='output CSV with comparisons')
    args = ap.parse_args()

    base_rows = read_csv(args.base)
    mod_rows = read_csv(args.modified)
    base_idx = make_index(base_rows)
    mod_idx = make_index(mod_rows)

    keys = set(base_idx.keys()) | set(mod_idx.keys())
    comparisons = []
    for k in sorted(keys):
        b = base_idx.get(k)
        m = mod_idx.get(k)
        if b is None:
            # base missing
            comp = compare_pair({'best': None, 'best relative': None, 'time (best)': None, 'time (all)': None, 'tree nodes': None, 'tree depth': None}, m)
        elif m is None:
            comp = compare_pair(b, {'best': None, 'best relative': None, 'time (best)': None, 'time (all)': None, 'tree nodes': None, 'tree depth': None})
        else:
            comp = compare_pair(b, m)
        comparisons.append({'key': k, 'base': b, 'mod': m, 'comparison': comp})

    stats, avgs = summarize(comparisons)

    # Write per-row CSV
    with open(args.out, 'w', newline='') as f:
        fieldnames = ['model', 'max_depth', 'depth'] + [f'base_{nf}' for nf in NUMERIC_FIELDS] + [f'mod_{nf}' for nf in NUMERIC_FIELDS] + [f'better_{nf}' for nf in NUMERIC_FIELDS]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for c in comparisons:
            k = c['key']
            row = {'model': k[0], 'max_depth': k[1], 'depth': k[2]}
            comp = c['comparison']
            for nf in NUMERIC_FIELDS:
                row[f'base_{nf}'] = comp[nf]['base']
                row[f'mod_{nf}'] = comp[nf]['mod']
                row[f'better_{nf}'] = comp[nf]['better']
            writer.writerow(row)

    # Print summary
    print('Summary:')
    print(f"Total comparisons: {stats.get('total',0)}")
    print(f"Modified better (by 'best'): {stats.get('mod_better',0)}")
    print(f"Base better (by 'best'): {stats.get('base_better',0)}")
    print(f"Ties: {stats.get('tie',0)}")
    print('Average deltas (mod - base):')
    for k,v in avgs.items():
        print(f'  {k}: {v}')


if __name__ == '__main__':
    main()
