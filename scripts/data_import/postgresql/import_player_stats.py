"""Import player-map statistics from overview.csv into Neon.

Process all six seasons with --all-years, or select one with --year YEAR.
Only Side=both records for real maps are used. Missing metrics remain NULL.
Shared ID matching and source corrections follow import_agents.py.

Requires schema 005_player_game_stats.sql. Only player_game_stats is written;
raw CSVs, shared tables and existing statistics are never overwritten.
--dry-run validates against Neon through a read-only connection.
"""

import argparse
import csv
import os
from collections import Counter, defaultdict
from contextlib import closing
from decimal import Decimal, InvalidOperation
from pathlib import Path

from import_core import ROOT, read_csv, valid_id
from import_agents import (
    ISSUE_FIELDS, MAP_FIELDS, MATCH_FIELDS, exact_key, label_key, log_issue,
    lookup_ids, lookup_exact_ids, normal, nrg_reconciliation_keys,
)


STAT_FIELDS = {
    "acs": "Average Combat Score",
    "kills": "Kills",
    "deaths": "Deaths",
    "assists": "Assists",
}


def parse_stat(value, field):
    """Keep missing values; reject negatives, overflow and lossy rounding."""
    if not value:
        return None
    try:
        number = Decimal(value)
        if not number.is_finite() or number < 0:
            raise ValueError("Must be a finite non-negative number")
        if field == "acs":
            if number > Decimal("999999.99") or number != number.quantize(Decimal("0.01")):
                raise ValueError("ACS must fit NUMERIC(8, 2) without rounding")
            return number
        if number > 32767 or number != number.to_integral_value():
            raise ValueError("Counter must be a whole number within SMALLINT range")
        return int(number)
    except InvalidOperation as error:
        raise ValueError("Not a valid number") from error


def prepare(data_dir, year, issues, reconcile_nrg=False):
    """Resolve each player-map row without inventing IDs or statistics."""
    season = data_dir / f"vct_{year}"
    ids_dir = season / "ids"
    team_ids = lookup_ids(ids_dir / "teams_ids.csv", "Team", "Team ID")
    player_ids = lookup_ids(ids_dir / "players_ids.csv", "Player", "Player ID")
    exact_players = lookup_exact_ids(ids_dir / "players_ids.csv", "Player", "Player ID")

    games = defaultdict(set)
    mapping = ids_dir / "tournaments_stages_matches_games_ids.csv"
    for _, row in read_csv(mapping, (*MAP_FIELDS, "Game ID", "Match ID")):
        game_id, match_id = valid_id(row["Game ID"]), valid_id(row["Match ID"])
        if game_id and match_id and row["Map"] and normal(row["Map"]) != "all maps":
            games[exact_key(row, MAP_FIELDS)].add((game_id, match_id))

    nrg_keys = set()
    if reconcile_nrg and year in (2025, 2026):
        nrg_keys = nrg_reconciliation_keys(season / "matches/scores.csv", team_ids)

    candidates, blocked = {}, set()
    metrics = Counter()
    path = season / "matches/overview.csv"
    required = (*MAP_FIELDS, "Player", "Team", "Agents", "Side", *STAT_FIELDS.values())
    for line, row in read_csv(path, required):
        metrics["overview_rows"] += 1
        if normal(row["Side"]) != "both" or not row["Map"] or normal(row["Map"]) == "all maps":
            continue
        metrics["map_both_rows"] += 1

        game_matches = games.get(exact_key(row, MAP_FIELDS), set())
        if len(game_matches) != 1:
            log_issue(issues, year, path, line, "unmatched_or_ambiguous_game", row,
                      f"Possible (Game ID, Match ID) pairs={sorted(game_matches)}")
            continue
        game_id, match_id = next(iter(game_matches))

        team_name = normal(row["Team"])
        if team_name == "mega minors" and label_key(row, MATCH_FIELDS) in nrg_keys:
            team_name = "nrg"
            log_issue(issues, year, path, line, "source_label_reconciled", row,
                      "Used shared importer's verified NRG context and Team ID 1034; CSV unchanged")
        teams = team_ids.get(team_name, set())
        players = player_ids.get(normal(row["Player"]), set())
        if len(players) > 1:
            exact = exact_players.get(row["Player"], set())
            if len(exact) == 1:
                players = exact
                log_issue(issues, year, path, line, "player_id_disambiguated_exact_case", row,
                          f"Exact source name identifies Player ID {next(iter(exact))}")
        if len(teams) != 1 or len(players) != 1:
            log_issue(issues, year, path, line, "unresolved_player_or_team", row,
                      f"Player IDs={sorted(players)}; Team IDs={sorted(teams)}")
            continue

        agent = normal(row["Agents"])
        if not agent or any(separator in agent for separator in (",", "/", ";", "|")):
            log_issue(issues, year, path, line, "unresolved_single_agent", row,
                      "Cannot verify one source agent against the existing scoreboard selection")
            continue

        stats = []
        for field, source in STAT_FIELDS.items():
            try:
                value = parse_stat(row[source], field)
            except ValueError as error:
                value = None
                metrics[f"invalid_{field}"] += 1
                log_issue(issues, year, path, line, "invalid_statistic", row,
                          f"{source}={row[source]!r}: {error}; kept other metrics, stored this one as NULL")
            if value is None:
                metrics[f"null_{field}"] += 1
            stats.append(value)

        key = (game_id, next(iter(players)))
        payload = (match_id, normal(row["Map"]), next(iter(teams)), agent, *stats)
        if key in blocked:
            continue
        if key in candidates:
            previous = candidates[key][0]
            if previous != payload:
                candidates.pop(key)
                blocked.add(key)
                log_issue(issues, year, path, line, "conflicting_player_game_stats", row,
                          f"Game/Player={key}; differing source records excluded: {previous!r} vs {payload!r}")
            else:
                log_issue(issues, year, path, line, "duplicate_source_row", row,
                          f"Identical Game/Player={key}; included once")
            continue
        context = {name: row[name] for name in ("Match Name", "Map", "Player", "Team")}
        candidates[key] = (payload, line, context)
    return candidates, metrics


def validate_database(cursor, year, candidates, issues):
    """Require agreement with the actual map, player, team and agent selection."""
    cursor.execute("""
        SELECT g.game_id, s.player_id, g.match_id, g.map_name, s.team_id, a.agent_name
        FROM agent_selections s
        JOIN map_games g ON g.game_id = s.game_id
        JOIN match_series m ON m.match_id = g.match_id
        JOIN agents a ON a.agent_id = s.agent_id
        JOIN match_participants p ON p.match_id = m.match_id AND p.team_id = s.team_id
        WHERE m.season = %s
    """, (year,))
    selections = defaultdict(set)
    for gid, pid, mid, map_name, tid, agent in cursor.fetchall():
        selections[(gid, pid)].add((mid, normal(map_name), tid, normal(agent)))

    rows = []
    for (gid, pid), (payload, line, context) in sorted(candidates.items()):
        match_id, map_name, team_id, agent, *stats = payload
        expected = (match_id, map_name, team_id, agent)
        if selections.get((gid, pid)) != {expected}:
            log_issue(issues, year, Path("overview.csv"), line, "unverified_database_selection", context,
                      f"Game {gid}, Player {pid}: source does not agree with one validated database selection")
            continue
        rows.append((gid, pid, *stats))
    return rows


def check_existing(cursor, year, rows):
    """Allow identical reruns; stop if any existing statistic would change."""
    cursor.execute("""
        SELECT s.game_id, s.player_id, s.acs, s.kills, s.deaths, s.assists
        FROM player_game_stats s
        JOIN map_games g ON g.game_id = s.game_id
        JOIN match_series m ON m.match_id = g.match_id
        WHERE m.season = %s
    """, (year,))
    expected = {row[:2]: row for row in rows}
    existing = 0
    for current in cursor.fetchall():
        wanted = expected.get(current[:2])
        if wanted is not None:
            if current != wanted:
                raise ValueError(f"Existing statistics differ for Game {current[0]}, Player {current[1]}; season cancelled")
            existing += 1
    return existing


def run_database(year, candidates, issues, dry_run):
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
                cursor.execute("SET LOCAL statement_timeout = '60s'")
                rows = validate_database(cursor, year, candidates, issues)
                if not rows:
                    raise ValueError("No player statistics passed validation; database unchanged")
                existing = check_existing(cursor, year, rows)
                added = 0
                if not dry_run:
                    inserted = execute_values(
                        cursor,
                        "INSERT INTO player_game_stats (game_id, player_id, acs, kills, deaths, assists) "
                        "VALUES %s ON CONFLICT (game_id, player_id) DO NOTHING RETURNING game_id",
                        rows, page_size=500, fetch=True,
                    )
                    added = len(inserted)
                    # Detect conflicting records inserted concurrently, too.
                    check_existing(cursor, year, rows)
                nulls = Counter(
                    field for row in rows for field, value in zip(STAT_FIELDS, row[2:]) if value is None
                )
                return len(rows), existing, added, nulls


def save_report(folder, year, issues):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"player_stats_import_issues_{year}.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ISSUE_FIELDS)
        writer.writeheader()
        writer.writerows(issues)
    return path


def main():
    parser = argparse.ArgumentParser(description="Import player-map ACS, kills, deaths and assists into Neon")
    years = parser.add_mutually_exclusive_group(required=True)
    years.add_argument("--year", type=int, choices=range(2021, 2027))
    years.add_argument("--all-years", action="store_true", help="Process all seasons, 2021 through 2026")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/raw")
    parser.add_argument("--report-dir", type=Path, default=ROOT / "docs/shared")
    parser.add_argument("--reconcile-nrg", action="store_true", help="Use shared importer's verified 2025/2026 NRG correction")
    parser.add_argument("--dry-run", action="store_true", help="Read-only preview; no database inserts")
    args = parser.parse_args()
    selected_years = range(2021, 2027) if args.all_years else (args.year,)
    for year in selected_years:
        issues = []
        try:
            candidates, metrics = prepare(args.data_dir, year, issues, args.reconcile_nrg)
            print(f"Season {year}")
            print(f"  overview.csv: {metrics['overview_rows']:,} source rows")
            print(f"  Side=both, real-map rows: {metrics['map_both_rows']:,}")
            accepted, existing, added, nulls = run_database(year, candidates, issues, args.dry_run)
            print(f"  player_game_stats: {accepted:,} validated records")
            print(f"  Skipped or duplicate eligible rows: {metrics['map_both_rows'] - accepted:,}")
            print(f"  Already stored and matching: {existing:,}")
            for field in STAT_FIELDS:
                print(f"  Missing {field} kept as NULL: {nulls[field]:,}")
            if args.dry_run:
                print("PREVIEW ONLY: no database data was changed.")
            else:
                print(f"  player_game_stats: {added:,} new records committed")
        finally:
            for kind, count in sorted(Counter(item['issue'] for item in issues).items()):
                print(f"  {kind}: {count:,}")
            print(f"Diagnostic report: {save_report(args.report_dir, year, issues)}")


if __name__ == "__main__":
    try:
        import psycopg2

        main()
    except (OSError, ValueError, ImportError) as error:
        raise SystemExit(f"ERROR: {error}") from error
    except psycopg2.Error as error:
        message = error.diag.message_primary or type(error).__name__
        raise SystemExit(f"ERROR: Neon operation failed: {message}") from None
