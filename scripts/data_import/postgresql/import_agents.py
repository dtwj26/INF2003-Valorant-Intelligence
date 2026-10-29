"""Import validated VCT player-map agent selections into PostgreSQL.

Run from the repository root (after 001/002/003 schema and participants imports):
    python scripts/data_import/postgresql/import_agents.py --year 2023 --dry-run
    python scripts/data_import/postgresql/import_agents.py --year 2023

2025/2026 optional source correction after verifying participant imports:
    python scripts/data_import/postgresql/import_agents.py --year 2025 --dry-run --reconcile-nrg

Reads raw CSVs. Never modifies source data. PostgreSQL writes are atomic.
Unmatched, multi-agent, or ambiguous observations are reported and excluded;
no source identifier is invented.
"""

import argparse
import csv
import getpass
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

from import_core import ROOT, read_csv, valid_id

MATCH_FIELDS = ("Tournament", "Stage", "Match Type", "Match Name")
MAP_FIELDS = (*MATCH_FIELDS, "Map")
ISSUE_FIELDS = (
    "year", "file", "row", "issue", "match", "map", "player", "team", "detail"
)


def normal(value):
    return " ".join((value or "").casefold().split())


def exact_key(row, fields):
    return tuple((row.get(k) or "").strip() for k in fields)


def label_key(row, fields):
    return tuple(normal(row.get(k)) for k in fields)


def log_issue(issues, year, file, line, issue, row=None, detail=""):
    row = row or {}
    issues.append({
        "year": year, "file": file.name, "row": line, "issue": issue,
        "match": row.get("Match Name", ""), "map": row.get("Map", ""),
        "player": row.get("Player", ""), "team": row.get("Team", ""),
        "detail": str(detail)[:500],
    })


def lookup_ids(path, name_field, id_field):
    mapping = defaultdict(set)
    for _, row in read_csv(path, (name_field, id_field)):
        ident = valid_id(row[id_field])
        if ident is not None and row[name_field]:
            mapping[normal(row[name_field])].add(ident)
    return mapping


def lookup_exact_ids(path, name_field, id_field):
    """Retain the exact source spelling for case-sensitive ID disambiguation.

    Only used when the normalised name maps to multiple different IDs.
    Exact spelling must itself resolve to precisely one ID.
    """
    mapping = defaultdict(set)
    for _, row in read_csv(path, (name_field, id_field)):
        ident = valid_id(row[id_field])
        if ident is not None and row[name_field]:
            mapping[row[name_field].strip()].add(ident)
    return mapping


def nrg_reconciliation_keys(scores_path, team_ids):
    """Return match contexts where the score source demonstrably renames NRG.

    Requires match title sides to align with score sides, except Mega Minors
    in the NRG slot. This does NOT assume the names are universal aliases.
    """
    if team_ids.get("nrg", set()) != {1034} or team_ids.get("mega minors", set()):
        return set()

    valid = set()
    for _, row in read_csv(scores_path, (*MATCH_FIELDS, "Team A", "Team B")):
        parts = re.split(r"\s+vs\.?\s+", row["Match Name"], maxsplit=1, flags=re.I)
        if len(parts) != 2:
            continue
        title = [normal(x) for x in parts]
        score = [normal(row["Team A"]), normal(row["Team B"])]
        for slot in (0, 1):
            if (title[slot] == "nrg" and score[slot] == "mega minors"
                    and title[1-slot] == score[1-slot]):
                valid.add(label_key(row, MATCH_FIELDS))
    return valid


def prepare(year, reconcile_nrg=False):
    season = ROOT / "data" / "raw" / f"vct_{year}"
    ids = season / "ids"
    games_file = ids / "tournaments_stages_matches_games_ids.csv"
    teams_file = ids / "teams_ids.csv"
    players_file = ids / "players_ids.csv"
    scores_file = season / "matches" / "scores.csv"
    overview_file = season / "matches" / "overview.csv"

    team_ids = lookup_ids(teams_file, "Team", "Team ID")
    player_ids = lookup_ids(players_file, "Player", "Player ID")
    player_exact_ids = lookup_exact_ids(players_file, "Player", "Player ID")

    game_ids = defaultdict(set)
    for _, row in read_csv(games_file, (*MAP_FIELDS, "Game ID", "Match ID")):
        gid, mid = valid_id(row["Game ID"]), valid_id(row["Match ID"])
        if gid is not None and mid is not None and row["Map"]:
            game_ids[exact_key(row, MAP_FIELDS)].add((gid, mid))

    nrg_keys = set()
    if reconcile_nrg and year in (2025, 2026):
        nrg_keys = nrg_reconciliation_keys(scores_file, team_ids)

    issues = []
    metrics = Counter()
    # One player should have one well-defined agent/team within a single map.
    candidates = defaultdict(set)  # (game_id, player_id) -> {(team_id, agent, match_id)}
    sample_rows = {}

    required = (*MAP_FIELDS, "Player", "Team", "Agents", "Side")
    for line, row in read_csv(overview_file, required):
        metrics["overview_rows"] += 1
        if normal(row["Side"]) != "both":
            continue
        if not row["Map"] or normal(row["Map"]) == "all maps":
            continue
        metrics["map_both_rows"] += 1

        agent = normal(row["Agents"])
        if not agent:
            log_issue(issues, year, overview_file, line, "missing_agent", row)
            continue
        if any(sep in agent for sep in (",", "/", ";", "|")):
            log_issue(issues, year, overview_file, line, "multiple_agents_in_source", row,
                      f"Agents={row['Agents']!r}; cannot determine single pick")
            continue

        matches = game_ids.get(exact_key(row, MAP_FIELDS), set())
        if len(matches) != 1:
            log_issue(issues, year, overview_file, line,
                      "ambiguous_game_id" if matches else "missing_game_id",
                      row, f"Possible (Game ID, Match ID) pairs={sorted(matches)[:12]}")
            continue
        game_id, match_id = next(iter(matches))

        team_name = normal(row["Team"])
        if (reconcile_nrg and year in (2025, 2026)
                and team_name == "mega minors"
                and label_key(row, MATCH_FIELDS) in nrg_keys):
            team_name = "nrg"
            log_issue(issues, year, overview_file, line, "source_label_reconciled",
                      row, "2025/2026 score-sheet and match-title agree on NRG; "
                           "Team ID 1034; raw CSV unchanged")

        team_candidates = team_ids.get(team_name, set())
        player_candidates = player_ids.get(normal(row["Player"]), set())
        if len(player_candidates) > 1:
            # E.g. f0rsakeN (9801) vs f0rsaken (12088): distinct source IDs.
            # Only use the exact-case mapping when it has exactly one ID.
            exact_candidates = player_exact_ids.get(row["Player"].strip(), set())
            if len(exact_candidates) == 1:
                player_candidates = exact_candidates
                log_issue(
                    issues, year, overview_file, line,
                    "player_id_disambiguated_exact_case", row,
                    f"Case-insensitive possibilities={sorted(player_ids[normal(row['Player'])])}; "
                    f"exact-name Player ID={next(iter(exact_candidates))}"
                )
        if len(team_candidates) != 1:
            log_issue(issues, year, overview_file, line, "unresolved_team_id", row,
                      f"Matching Team IDs={sorted(team_candidates)}")
            continue
        if len(player_candidates) != 1:
            log_issue(issues, year, overview_file, line, "unresolved_player_id", row,
                      f"Matching Player IDs={sorted(player_candidates)}")
            continue

        team_id = next(iter(team_candidates))
        player_id = next(iter(player_candidates))
        key = (game_id, player_id)
        choice = (team_id, agent, match_id)
        if choice in candidates[key]:
            log_issue(issues, year, overview_file, line,
                      "duplicate_observation", row,
                      "Same game/player/team/agent appears more than once")
        candidates[key].add(choice)
        sample_rows.setdefault(key, (line, row))
        metrics["candidate_rows"] += 1

    prepared = []  # game_id, player_id, team_id, agent_name, match_id
    for (game_id, player_id), choices in sorted(candidates.items()):
        if len(choices) != 1:
            line, row = sample_rows[(game_id, player_id)]
            log_issue(issues, year, overview_file, line, "conflicting_player_game_agent",
                      row, f"Game ID {game_id}, Player ID {player_id}: {sorted(choices)}")
            continue
        team_id, agent, match_id = next(iter(choices))
        prepared.append((game_id, player_id, team_id, agent, match_id))

    return prepared, issues, metrics


def save_report(year, issues):
    report_dir = ROOT / "docs" / "shared"
    report_dir.mkdir(parents=True, exist_ok=True)
    dest = report_dir / f"agents_import_issues_{year}.csv"
    with dest.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ISSUE_FIELDS)
        writer.writeheader()
        writer.writerows(issues)
    return dest


def write_database(year, prepared, issues):
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
                # Validate against actual database IDs and match participation.
                cur.execute("""
                    SELECT g.game_id, g.match_id, g.map_name
                    FROM map_games g JOIN match_series m ON g.match_id = m.match_id
                    WHERE m.season = %s
                """, (year,))
                games_db = {gid: (mid, map_name) for gid, mid, map_name in cur.fetchall()}

                cur.execute("""
                    SELECT mp.match_id, mp.team_id
                    FROM match_participants mp
                    JOIN match_series m ON mp.match_id = m.match_id
                    WHERE m.season = %s
                """, (year,))
                participants_db = set(cur.fetchall())

                cur.execute("SELECT player_id FROM players")
                players_db = {v for (v,) in cur.fetchall()}
                cur.execute("SELECT team_id FROM teams")
                teams_db = {v for (v,) in cur.fetchall()}

                valid = []
                for gid, pid, tid, agent, mid in prepared:
                    db_game = games_db.get(gid)
                    if db_game is None or db_game[0] != mid:
                        raise ValueError(
                            f"Game ID {gid} missing or linked to different Match ID in PostgreSQL"
                        )
                    if pid not in players_db or tid not in teams_db:
                        raise ValueError(f"Missing Player ID {pid} or Team ID {tid} in PostgreSQL")
                    if (mid, tid) not in participants_db:
                        issues.append({
                            "year": year, "file": "database", "row": "",
                            "issue": "missing_validated_match_participation",
                            "match": str(mid), "map": db_game[1],
                            "player": str(pid), "team": str(tid),
                            "detail": f"Match {mid} does not have Team {tid} in match_participants; excluded",
                        })
                        continue
                    valid.append((gid, pid, tid, agent))

                if not valid:
                    raise ValueError("No validated agent selections available for import")

                all_agents = sorted({agent for _, _, _, agent in valid})
                execute_values(
                    cur,
                    "INSERT INTO agents (agent_name) VALUES %s ON CONFLICT DO NOTHING",
                    [(agent,) for agent in all_agents], page_size=250,
                )
                cur.execute("SELECT agent_id, agent_name FROM agents")
                agents_db = {normal(name): aid for aid, name in cur.fetchall()}

                rows = [
                    (gid, pid, tid, agents_db[agent])
                    for gid, pid, tid, agent in valid
                ]

                # Rerunning must not silently change an existing player's pick.
                cur.execute("""
                    SELECT s.game_id, s.player_id, s.team_id, s.agent_id
                    FROM agent_selections s
                    JOIN map_games g ON s.game_id = g.game_id
                    JOIN match_series m ON g.match_id = m.match_id
                    WHERE m.season = %s
                """, (year,))
                current = defaultdict(set)
                for gid, pid, tid, aid in cur.fetchall():
                    current[(gid, pid)].add((tid, aid))
                for gid, pid, tid, aid in rows:
                    existing = current.get((gid, pid))
                    if existing and existing != {(tid, aid)}:
                        raise ValueError(
                            f"Conflicting existing selection for Game {gid}, Player {pid}: "
                            f"stored={existing}, prepared={(tid, aid)}"
                        )

                result = execute_values(
                    cur,
                    "INSERT INTO agent_selections (game_id, player_id, team_id, agent_id) "
                    "VALUES %s ON CONFLICT (game_id, player_id, agent_id) DO NOTHING "
                    "RETURNING game_id",
                    rows, page_size=500, fetch=True,
                )
                return len(result), len(valid), len(all_agents)
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Import validated map-level agent picks")
    parser.add_argument("--year", type=int, choices=range(2021, 2027), default=2023)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reconcile-nrg", action="store_true",
                        help="2025/2026: reconcile verified Mega Minors→NRG score labels")
    args = parser.parse_args()

    prepared, issues, metrics = prepare(args.year, args.reconcile_nrg)
    print(f"Season {args.year}: {metrics['overview_rows']:,} overview rows checked")
    print(f"  Map-level Side=both rows: {metrics['map_both_rows']:,}")
    print(f"  Validated source candidates: {len(prepared):,}")
    print(f"  Diagnostic entries: {len(issues):,}")
    for key, count in sorted(Counter(item['issue'] for item in issues).items()):
        print(f"    {key}: {count:,}")

    try:
        if args.dry_run:
            print("DRY RUN: no PostgreSQL connection or database modifications.")
        else:
            added, accepted, distinct_agents = write_database(args.year, prepared, issues)
            print(f"Import committed: {added:,} new agent_selections")
            print(f"  Verified against match_participants: {accepted:,}")
            print(f"  Distinct agent names in this import: {distinct_agents}")
    finally:
        report = save_report(args.year, issues)
        print(f"Diagnostic report: {report}")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
