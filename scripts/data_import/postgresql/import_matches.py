"""Import match and map scores into the existing Neon database.

Run from the repository root, starting with a preview:
    python scripts/data_import/postgresql/import_matches.py --year 2023 --data-dir "PATH/TO/vct_dataset" --dry-run

For all seasons, import each score table separately:
    python scripts/data_import/postgresql/import_matches.py --all-years --table match_scores --data-dir "PATH/TO/vct_dataset" --reconcile-nrg
    python scripts/data_import/postgresql/import_matches.py --all-years --table map_scores --data-dir "PATH/TO/vct_dataset" --reconcile-nrg

Requires schema 004_match_scores.sql. A dry run reads Neon but writes no data.
Only match_scores and map_scores receive inserts. Existing scores are checked,
never overwritten. Source CSVs and shared core tables are left unchanged.
One-map round scores are converted to maps won only when the sole mapped
game's score confirms them. Every conversion and excluded row is reported.
"""

import argparse
import csv
import os
from collections import Counter, defaultdict
from contextlib import closing
from pathlib import Path

from import_core import ROOT, read_csv, valid_id
from import_participants import MATCH_COLS, match_key, normal


ISSUE_FIELDS = ("year", "file", "row", "issue", "match", "map", "detail")
SCORE_TABLES = {
    "match_scores": ("match_id", "team_a_score", "team_b_score", "match_result"),
    "map_scores": ("game_id", "team_a_score", "team_b_score"),
}


def add_issue(issues, year, path, line, kind, row, detail):
    issues.append(dict(
        year=year, file=path.name, row=line, issue=kind,
        match=row.get("Match Name", ""), map=row.get("Map", ""),
        detail=str(detail),
    ))


def parse_score(value):
    """Accept zero; reject missing, negative and non-integer scores."""
    if not value.isascii() or not value.isdecimal():
        raise ValueError("Score must be a non-negative integer")
    score = int(value)
    if score > 32767:
        raise ValueError("Score exceeds PostgreSQL SMALLINT range")
    return score


def source_team_names(row, nrg_keys):
    """Normalise names, using only the shared importer's verified NRG contexts."""
    names = [normal(row["Team A"]), normal(row["Team B"])]
    if match_key(row) in nrg_keys:
        names = ["nrg" if name == "mega minors" else name for name in names]
    return names


def score_signature(names, scores):
    """Compare map evidence without depending on which team was listed first."""
    return tuple(sorted(zip(names, scores)))


def prepare(data_dir, year, issues, tables=None, reconcile_nrg=False):
    """Resolve source IDs and reject ambiguous or contradictory records."""
    season = data_dir / f"vct_{year}"
    teams = defaultdict(set)
    for _, row in read_csv(season / "ids/teams_ids.csv", ("Team", "Team ID")):
        team_id = valid_id(row["Team ID"])
        if team_id and row["Team"]:
            teams[normal(row["Team"])].add(team_id)

    # Reuse the narrowly scoped source correction from the shared importer.
    # No general Mega Minors -> NRG alias is assumed.
    nrg_keys = set()
    if reconcile_nrg and year in (2025, 2026):
        from import_agents import nrg_reconciliation_keys

        nrg_keys = nrg_reconciliation_keys(season / "matches/scores.csv", teams)

    matches, games = defaultdict(set), defaultdict(set)
    match_game_ids = defaultdict(set)
    mapping = season / "ids/tournaments_stages_matches_games_ids.csv"
    for _, row in read_csv(mapping, (*MATCH_COLS, "Match ID", "Game ID", "Map")):
        match_id, game_id = valid_id(row["Match ID"]), valid_id(row["Game ID"])
        if match_id:
            matches[match_key(row)].add((match_id, match_id))
        if match_id and game_id and row["Map"] and normal(row["Map"]) != "all maps":
            games[(*match_key(row), normal(row["Map"]))].add((game_id, match_id))
            match_game_ids[match_id].add(game_id)
        elif match_id:
            # A missing map ID prevents proving this is a one-map match.
            match_game_ids[match_id].add(None)

    # Older seasons sometimes put a one-map match's ROUND score in scores.csv.
    # Convert it to maps won only when the sole mapped game's score agrees.
    map_evidence = defaultdict(set)
    if tables is None or "match_scores" in tables:
        evidence_file = season / "matches/maps_scores.csv"
        evidence_fields = (*MATCH_COLS, "Map", "Team A", "Team B", "Team A Score", "Team B Score")
        for _, row in read_csv(evidence_file, evidence_fields):
            ids = games.get((*match_key(row), normal(row["Map"])), set())
            if len(ids) != 1:
                continue
            game_id, _ = next(iter(ids))
            try:
                scores = (parse_score(row["Team A Score"]), parse_score(row["Team B Score"]))
                signature = score_signature(source_team_names(row, nrg_keys), scores)
            except ValueError:
                # Invalid or conflicting map evidence must not permit conversion.
                signature = None
            map_evidence[game_id].add(signature)

    prepared = {}
    counts = {}
    for table, filename, lookup in (
        ("match_scores", "scores.csv", matches),
        ("map_scores", "maps_scores.csv", games),
    ):
        if tables is not None and table not in tables:
            continue
        path = season / "matches" / filename
        required = (*MATCH_COLS, "Team A", "Team B", "Team A Score", "Team B Score")
        required += ("Match Result",) if table == "match_scores" else ("Map",)
        candidates, blocked = {}, set()
        count = 0
        for line, row in read_csv(path, required):
            count += 1
            key = match_key(row)
            if table == "map_scores":
                key = (*key, normal(row["Map"]))
            ids = lookup.get(key, set())
            if len(ids) != 1:
                add_issue(issues, year, path, line, "unmatched_or_ambiguous_id", row,
                          f"Possible IDs: {sorted(ids)}")
                continue
            identifier, match_id = next(iter(ids))
            team_names = source_team_names(row, nrg_keys)
            if match_key(row) in nrg_keys:
                for slot in (0, 1):
                    if normal(row["Team A" if slot == 0 else "Team B"]) == "mega minors":
                        add_issue(issues, year, path, line, "source_label_reconciled", row,
                                  "Used the shared importer's verified NRG context and Team ID 1034; CSV unchanged")
            team_a, team_b = teams[team_names[0]], teams[team_names[1]]
            if len(team_a) != 1 or len(team_b) != 1 or team_a == team_b:
                add_issue(issues, year, path, line, "unresolved_team_ids", row,
                          f"A={sorted(team_a)}, B={sorted(team_b)}; no aliases guessed")
                continue
            try:
                scores = (parse_score(row["Team A Score"]), parse_score(row["Team B Score"]))
            except ValueError as error:
                add_issue(issues, year, path, line, "invalid_score", row, error)
                continue
            if table == "match_scores" and max(scores) > 5:
                game_ids = match_game_ids[match_id]
                signature = score_signature(team_names, scores)
                if (len(game_ids) != 1 or None in game_ids
                        or map_evidence[next(iter(game_ids))] != {signature}):
                    add_issue(issues, year, path, line, "unsupported_series_score", row,
                              f"Round scores {scores} not confirmed by one unambiguous map; review required")
                    continue
                round_scores = scores
                scores = (int(scores[0] > scores[1]), int(scores[1] > scores[0]))
                add_issue(issues, year, path, line, "single_map_round_score_normalized", row,
                          f"Round scores {round_scores} confirmed by the sole map; stored maps won={scores}")
            result = row.get("Match Result") or None
            payload = (match_id, next(iter(team_a)), next(iter(team_b)),
                       scores, result, normal(row.get("Map", "")))
            if identifier in blocked:
                continue
            if identifier in candidates:
                previous = candidates[identifier][0]
                if previous != payload:
                    candidates.pop(identifier)
                    blocked.add(identifier)
                    add_issue(issues, year, path, line, "conflicting_source_rows", row,
                              f"Different records for ID {identifier}; all excluded")
                else:
                    add_issue(issues, year, path, line, "duplicate_source_row", row,
                              f"Identical record for ID {identifier}; included once")
                continue
            candidates[identifier] = (payload, line, row)
        prepared[table] = candidates
        counts[filename] = count
    return prepared, counts


def align_scores(scores, source_teams, stored_slots):
    """Return scores in the A/B order used by match_participants."""
    if stored_slots == {"A": source_teams[0], "B": source_teams[1]}:
        return scores
    if stored_slots == {"A": source_teams[1], "B": source_teams[0]}:
        return scores[::-1]
    raise ValueError("Source teams do not match the two stored participant slots")


def validate_database(cursor, year, prepared, issues):
    """Validate parents and team slots before preparing any inserts."""
    cursor.execute("""
        SELECT m.match_id, p.team_slot, p.team_id
        FROM match_series m
        LEFT JOIN match_participants p ON p.match_id = m.match_id
        WHERE m.season = %s
    """, (year,))
    participants = defaultdict(dict)
    for match_id, slot, team_id in cursor.fetchall():
        participants[match_id][slot] = team_id

    cursor.execute("""
        SELECT g.game_id, g.match_id, g.map_name
        FROM map_games g JOIN match_series m ON m.match_id = g.match_id
        WHERE m.season = %s
    """, (year,))
    games = {gid: (mid, normal(name)) for gid, mid, name in cursor.fetchall()}

    rows = {table: [] for table in prepared}
    for table, candidates in prepared.items():
        filename = "scores.csv" if table == "match_scores" else "maps_scores.csv"
        for identifier, (payload, line, source) in sorted(candidates.items()):
            match_id, team_a, team_b, scores, result, map_name = payload
            try:
                if table == "map_scores" and games.get(identifier) != (match_id, map_name):
                    raise ValueError("Game ID, Match ID or map differs from the stored season")
                scores = align_scores(scores, (team_a, team_b), participants.get(match_id, {}))
            except ValueError as error:
                add_issue(issues, year, Path(filename), line, "database_relationship_mismatch",
                          source, error)
                continue
            values = (identifier, *scores)
            rows[table].append((*values, result) if table == "match_scores" else values)
    return rows


def check_existing(cursor, table, rows):
    """An existing score must agree exactly; reruns never overwrite data."""
    if not rows:
        return
    columns = SCORE_TABLES[table]
    # Identifiers come only from SCORE_TABLES, never from user input.
    cursor.execute(
        f"SELECT {', '.join(columns)} FROM {table} WHERE {columns[0]} = ANY(%s)",
        ([row[0] for row in rows],),
    )
    expected = {row[0]: row for row in rows}
    for current in cursor.fetchall():
        if current != expected[current[0]]:
            raise ValueError(f"Existing {table} ID {current[0]} has different scores; import cancelled")


def run_database(year, prepared, issues, dry_run):
    import psycopg2
    from psycopg2.extras import execute_values
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is missing from the repository .env file")
    with closing(psycopg2.connect(database_url, connect_timeout=20)) as conn:
        conn.set_session(readonly=dry_run)
        with conn:
            with conn.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout = '30s'")
                rows = validate_database(cursor, year, prepared, issues)
                if not any(rows.values()):
                    raise ValueError("No scores passed validation; database unchanged")
                added = {}
                for table in rows:
                    check_existing(cursor, table, rows[table])
                if not dry_run:
                    for table in rows:
                        columns = SCORE_TABLES[table]
                        inserted = execute_values(
                            cursor,
                            f"INSERT INTO {table} ({', '.join(columns)}) VALUES %s "
                            f"ON CONFLICT ({columns[0]}) DO NOTHING RETURNING {columns[0]}",
                            rows[table], page_size=500, fetch=True,
                        ) if rows[table] else []
                        added[table] = len(inserted)
                    # Also catch conflicting records inserted concurrently.
                    for table in rows:
                        check_existing(cursor, table, rows[table])
                return {table: len(values) for table, values in rows.items()}, added


def save_report(folder, year, issues, table=None):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{table or 'matches'}_import_issues_{year}.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ISSUE_FIELDS)
        writer.writeheader()
        writer.writerows(issues)
    return path


def main():
    parser = argparse.ArgumentParser(description="Import validated match and map scores into Neon")
    year_options = parser.add_mutually_exclusive_group()
    year_options.add_argument("--year", type=int, choices=range(2021, 2027), default=2023)
    year_options.add_argument("--all-years", action="store_true",
                              help="Process every season, from 2021 through 2026")
    parser.add_argument("--table", choices=tuple(SCORE_TABLES),
                        help="Import only this table; omit to process both")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/raw",
                        help="Dataset folder containing vct_2021 through vct_2026")
    parser.add_argument("--dry-run", action="store_true",
                        help="Read CSVs and validate against Neon using a read-only connection")
    parser.add_argument("--report-dir", type=Path, default=ROOT / "docs/shared")
    parser.add_argument("--reconcile-nrg", action="store_true",
                        help="Reuse the shared importer's verified 2025/2026 NRG label correction")
    args = parser.parse_args()
    years = range(2021, 2027) if args.all_years else (args.year,)
    tables = (args.table,) if args.table else tuple(SCORE_TABLES)
    for year in years:
        issues = []
        try:
            prepared, counts = prepare(args.data_dir, year, issues, tables, args.reconcile_nrg)
            print(f"Season {year}")
            for filename, count in counts.items():
                print(f"  {filename}: {count:,} source rows")
            accepted, added = run_database(year, prepared, issues, args.dry_run)
            for table, count in accepted.items():
                source_count = counts["scores.csv" if table == "match_scores" else "maps_scores.csv"]
                print(f"  {table}: {count:,} validated records")
                print(f"  Skipped or duplicate source rows: {source_count - count:,}")
            if args.dry_run:
                print("PREVIEW ONLY: no database data was changed.")
            else:
                for table, count in added.items():
                    print(f"  {table}: {count:,} new records committed")
        finally:
            for kind, count in sorted(Counter(item["issue"] for item in issues).items()):
                print(f"  {kind}: {count:,}")
            print(f"Diagnostic report: {save_report(args.report_dir, year, issues, args.table)}")


if __name__ == "__main__":
    try:
        import psycopg2

        main()
    except (OSError, ValueError, ImportError) as error:
        raise SystemExit(f"ERROR: {error}") from error
    except psycopg2.Error as error:
        message = error.diag.message_primary or type(error).__name__
        raise SystemExit(f"ERROR: Neon operation failed: {message}") from None
