"""Compare old Python substring search with the current PostgreSQL fuzzy search.
Run from the repository root. Read-only; no schema changes.
"""
import argparse
from pathlib import Path
from statistics import median
import sys
from time import perf_counter

ROOT = Path.cwd()
if not (ROOT / 'backend' / 'matches').is_dir():
    raise SystemExit('Run this script from the Valorant repository root folder.')
sys.path.insert(0, str(ROOT))
from frontend.services import teams_players_matches_service as service


def benchmark_once(season, search, method):
    start = perf_counter()
    seasons = service.get_match_seasons()
    if season not in seasons:
        raise ValueError(f'Season {season} unavailable. Available: {seasons}')
    if method == 'old':
        data = service.get_match_records(season)
    else:
        data = service.get_match_records(season, search=search)
    loaded = perf_counter()
    rows = data['matches']
    if method == 'old':
        term = search.strip().casefold()
        rows = [m for m in rows if term in (
            ' '.join(m['team_names']) + ' ' + m['tournament'] + ' ' + m['id']
        ).casefold()]
        rows.sort(key=lambda m: int(m['id']), reverse=True)
    visible = rows[:8]
    finished = perf_counter()
    return dict(load_ms=(loaded-start)*1000, python_ms=(finished-loaded)*1000,
                total_ms=(finished-start)*1000, loaded=len(data['matches']),
                found=len(rows), visible=len(visible),
                ids=tuple(m['id'] for m in rows))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--season', type=int, default=2026)
    p.add_argument('--search', nargs='+', default=['FNATIC', 'Fnatc'])
    p.add_argument('--runs', type=int, default=20)
    p.add_argument('--warmups', type=int, default=2)
    p.add_argument('--method', choices=['old', 'new', 'both'], default='both')
    args = p.parse_args()
    if args.runs < 1 or args.warmups < 0:
        p.error('Runs must be positive; warmups must be nonnegative.')
    methods = ['old', 'new'] if args.method == 'both' else [args.method]
    print(f'Season {args.season} | {args.runs} runs per method/term | {args.warmups} warmups')
    print('All filters cleared. Includes season loading, DB connections, transfer, adapter and top 8 selection.')
    print('Excludes UI rendering. Times in ms; Load, Python and Total are medians.')
    print('Old = baseline logic on current schema; New = current SQL search.\n', flush=True)
    for term in args.search:
        samples = {m: [] for m in methods}
        for i in range(args.warmups + args.runs):
            order = methods if i % 2 == 0 else methods[::-1]
            for m in order:
                result = benchmark_once(args.season, term, m)
                if i >= args.warmups:
                    samples[m].append(result)
        print(f'Search: {term!r}')
        print(f"{'Method':<8} {'Loaded':>7} {'Found':>7} {'Visible':>7} {'Load':>10} {'Python':>10} {'Total':>10} {'Min':>10} {'Max':>10}")
        totals = {}
        for m in methods:
            s = samples[m]
            times = [r['total_ms'] for r in s]
            totals[m] = median(times)
            print(f"{m:<8} {s[-1]['loaded']:>7} {s[-1]['found']:>7} {s[-1]['visible']:>7} "
                  f"{median(r['load_ms'] for r in s):>10.2f} {median(r['python_ms'] for r in s):>10.2f} "
                  f"{totals[m]:>10.2f} {min(times):>10.2f} {max(times):>10.2f}")
            if any(r['ids'] != s[0]['ids'] for r in s):
                print(f'Warning: {m} results changed between measured runs.')
        if args.method == 'both':
            old, new = totals['old'], totals['new']
            if old > 0 and new > 0:
                print(f'Latency reduction: {(old-new)/old*100:.2f}% | Speedup: {old/new:.2f}x')
            old_ids = set(samples['old'][-1]['ids'])
            new_ids = set(samples['new'][-1]['ids'])
            print(f'Common matches: {len(old_ids & new_ids)} | New-only: {len(new_ids-old_ids)} | Old-only: {len(old_ids-new_ids)}')
            print('Different result sets measure different search behavior, not identical workloads.')
        print(flush=True)


if __name__ == '__main__':
    try:
        main()
    except (service.DataServiceError, ValueError) as error:
        raise SystemExit(str(error)) from None
