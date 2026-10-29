"""Import score-sheet match participants into PostgreSQL with strict ID checks.
Run from repository root:
 python scripts/data_import/postgresql/import_participants.py --year 2023 --dry-run
 python scripts/data_import/postgresql/import_participants.py --year 2023
"""
import argparse
import csv
import getpass
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

from import_core import ROOT, read_csv, valid_id

FIELDS = ("year", "file", "row", "issue", "match", "detail")
MATCH_COLS = ("Tournament", "Stage", "Match Type", "Match Name")


def normal(text):
    return " ".join(text.casefold().split())


def match_key(row):
    return tuple(normal(row[c]) for c in MATCH_COLS)


def issue(issues, year, file, line, kind, match, detail):
    issues.append(dict(year=year, file=file.name, row=line,
                       issue=kind, match=match, detail=str(detail)[:500]))


def prepare(year, reconcile_nrg=False):
    season = ROOT / "data" / "raw" / f"vct_{year}"
    team_file = season / "ids" / "teams_ids.csv"
    mapping_file = season / "ids" / "tournaments_stages_matches_games_ids.csv"
    scores_file = season / "matches" / "scores.csv"
    issues = []

    # A team name must resolve to exactly one ID within the source season.
    team_ids = defaultdict(set)
    for line, row in read_csv(team_file, ("Team", "Team ID")):
        tid = valid_id(row["Team ID"])
        if tid is not None and row["Team"]:
            team_ids[normal(row["Team"])].add(tid)

    # Each natural match key must resolve to exactly one Match ID.
    match_ids = defaultdict(set)
    for line, row in read_csv(mapping_file, (*MATCH_COLS, "Match ID")):
        mid = valid_id(row["Match ID"])
        if mid is not None:
            match_ids[match_key(row)].add(mid)

    pairs = {}  # match_id -> (team_a_id, team_b_id)
    blocked = set()  # do not recover from contradictory score rows by chance
    score_rows = 0
    for line, row in read_csv(scores_file, (*MATCH_COLS, "Team A", "Team B")):
        score_rows += 1
        key = match_key(row)
        matches = match_ids.get(key, set())
        if len(matches) != 1:
            issue(issues, year, scores_file, line, "unmatched_or_ambiguous_match",
                  row["Match Name"], f"Match IDs found: {sorted(matches)}")
            continue

        a, b = row["Team A"], row["Team B"]

        # Narrowly scoped, opt-in correction for a known source inconsistency.
        # Never convert "Mega Minors" to NRG based on that name alone.
        # Require: 2025/2026, NRG's verified source ID (1034), missing
        # "Mega Minors" ID, match title agrees in the corresponding slot,
        # and the opposite team matches exactly between the title and score.
        if reconcile_nrg and year in (2025, 2026):
            title_sides = re.split(r"\s+vs\.?\s+", row["Match Name"],
                                   maxsplit=1, flags=re.I)
            score_sides = [a, b]
            if len(title_sides) == 2 and team_ids.get("nrg") == {1034} \
                    and len(team_ids.get("mega minors", set())) == 0:
                for slot in (0, 1):
                    if (normal(score_sides[slot]) == "mega minors"
                            and normal(title_sides[slot]) == "nrg"
                            and normal(score_sides[1-slot]) == normal(title_sides[1-slot])):
                        score_sides[slot] = title_sides[slot]
                        issue(issues, year, scores_file, line,
                              "source_label_reconciled", row["Match Name"],
                              "scores.csv used Mega Minors; match title and unique "
                              "NRG Team ID 1034 identify NRG; original CSV unchanged")
                a, b = score_sides

        ids_a, ids_b = team_ids.get(normal(a), set()), team_ids.get(normal(b), set())
        if len(ids_a) != 1 or len(ids_b) != 1:
            issue(issues, year, scores_file, line, "unresolved_team_id",
                  row["Match Name"], f"Team A={a!r} IDs={sorted(ids_a)}; Team B={b!r} IDs={sorted(ids_b)}")
            continue
        a_id, b_id = next(iter(ids_a)), next(iter(ids_b))
        if a_id == b_id:
            issue(issues, year, scores_file, line, "same_team_on_both_sides",
                  row["Match Name"], f"Both teams resolve to ID {a_id}")
            continue

        # Check obvious contradictions with 'Team A vs Team B' match titles.
        title_parts = re.split(r"\s+vs\.?\s+", row["Match Name"], maxsplit=1, flags=re.I)
        if len(title_parts) == 2 and {normal(v) for v in title_parts} != {normal(a), normal(b)}:
            issue(issues, year, scores_file, line, "match_title_team_mismatch",
                  row["Match Name"], f"Score teams: {a!r} and {b!r}; skipped, not guessed")
            continue

        mid = next(iter(matches))
        if mid in blocked:
            continue
        if mid in pairs and pairs[mid] != (a_id, b_id):
            issue(issues, year, scores_file, line, "conflicting_score_rows",
                  row["Match Name"], f"Existing={pairs[mid]}; new={(a_id, b_id)}")
            pairs.pop(mid, None)
            blocked.add(mid)
            continue
        pairs[mid] = (a_id, b_id)

    return pairs, issues, score_rows


def save_report(year, issues):
    folder = ROOT / "docs" / "shared"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"participants_issues_{year}.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(issues)
    return path


def insert(year, pairs):
    try:
        import psycopg2
        from psycopg2.extras import execute_values
    except ImportError as exc:
        raise RuntimeError("Install driver: python -m pip install psycopg2-binary") from exc

    host = os.getenv("PGHOST", "localhost")
    port = int(os.getenv("PGPORT", "5432"))
    dbname = os.getenv("PGDATABASE", "valorant_dev")
    user = os.getenv("PGUSER", "postgres")
    password = os.getenv("PGPASSWORD")
    print(f"Connecting to {dbname} at {host}:{port} as {user}")
    if password is None:
        password = getpass.getpass("PostgreSQL password (hidden): ")

    conn = psycopg2.connect(host=host, port=port, dbname=dbname,
                            user=user, password=password, connect_timeout=10)
    try:
        with conn:
            with conn.cursor() as cur:
                match_ids = list(pairs)
                cur.execute("SELECT match_id, season FROM match_series WHERE match_id = ANY(%s)", (match_ids,))
                db_matches = dict(cur.fetchall())
                invalid_matches = [mid for mid in match_ids if db_matches.get(mid) != year]
                if invalid_matches:
                    raise ValueError(f"Match IDs missing/wrong season in PostgreSQL: {invalid_matches[:10]}")

                team_ids = list({tid for sides in pairs.values() for tid in sides})
                cur.execute("SELECT team_id FROM teams WHERE team_id = ANY(%s)", (team_ids,))
                db_teams = {r[0] for r in cur.fetchall()}
                invalid_teams = sorted(set(team_ids) - db_teams)
                if invalid_teams:
                    raise ValueError(f"Team IDs missing in PostgreSQL: {invalid_teams[:10]}")

                cur.execute("SELECT match_id, team_id, team_slot FROM match_participants WHERE match_id = ANY(%s)", (match_ids,))
                current = cur.fetchall()
                expected = {(mid, tid, slot) for mid, (a, b) in pairs.items()
                            for tid, slot in ((a, "A"), (b, "B"))}
                unexpected = [row for row in current if row not in expected]
                if unexpected:
                    raise ValueError(f"Conflicting existing participants; transaction cancelled: {unexpected[:5]}")

                rows = sorted(expected)
                result = execute_values(
                    cur,
                    "INSERT INTO match_participants (match_id, team_id, team_slot) VALUES %s "
                    "ON CONFLICT DO NOTHING RETURNING match_id",
                    rows, page_size=500, fetch=True,
                ) if rows else []
                return len(result)
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, choices=range(2021, 2027), default=2023)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reconcile-nrg", action="store_true",
                        help="Opt-in, strictly verified 2025-2026 Mega Minors/NRG correction")
    args = parser.parse_args()
    pairs, issues, n_rows = prepare(args.year, reconcile_nrg=args.reconcile_nrg)
    print(f"Season {args.year}: {n_rows:,} score rows checked")
    print(f"  Valid distinct matches: {len(pairs):,}")
    print(f"  Participants prepared: {2 * len(pairs):,}")
    print(f"  Diagnostic issues: {len(issues):,}")
    for name, count in sorted(Counter(x['issue'] for x in issues).items()):
        print(f"    {name}: {count:,}")
    report = save_report(args.year, issues)
    print(f"  Report: {report}")
    if args.dry_run:
        print("DRY RUN: PostgreSQL was not modified.")
    else:
        added = insert(args.year, pairs)
        print(f"Import committed: {added:,} new match_participants rows")

if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
