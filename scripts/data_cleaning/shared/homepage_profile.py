"""Read-only data quality and coverage profile for the INF2003 Homepage.

Save this file as scripts/data_cleaning/shared/homepage_profile.py and run from the
repository root: python scripts/data_cleaning/shared/homepage_profile.py

Outputs a summary CSV and notes TXT inside docs/shared/. Does not modify
original datasets and requires only Python's standard library.
"""
from collections import Counter, defaultdict
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "docs" / "shared"
OUT.mkdir(parents=True, exist_ok=True)

KEY = ("Tournament", "Stage", "Match Type", "Match Name", "Map")


def read_csv(path):
    if not path.is_file():
        raise FileNotFoundError(f"Cannot find {path}")
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
        yield from csv.DictReader(f)


def game_key(row):
    return tuple((row.get(column) or "").strip() for column in KEY)


def safe_id(row, column):
    return (row.get(column) or "").strip()


summary = []
notes = []

for year in range(2021, 2027):
    season = RAW / f"vct_{year}"
    print(f"Profiling {year} ...", flush=True)

    # Match/game IDs: one match series may contain multiple games/maps.
    ids_file = season / "ids" / "tournaments_stages_matches_games_ids.csv"
    matches = set()
    games = set()
    tournaments = set()
    game_ids_by_key = defaultdict(set)
    map_names_by_id = {}
    ids_rows = 0
    blank_id_rows = 0
    repeated_game_id_rows = 0
    for row in read_csv(ids_file):
        ids_rows += 1
        tid = safe_id(row, "Tournament ID")
        mid = safe_id(row, "Match ID")
        gid = safe_id(row, "Game ID")
        if not (tid and mid and gid):
            blank_id_rows += 1
            continue
        tournaments.add(tid)
        matches.add(mid)
        if gid in games:
            repeated_game_id_rows += 1
        games.add(gid)
        game_ids_by_key[game_key(row)].add(gid)
        if gid in map_names_by_id and map_names_by_id[gid] != row.get("Map"):
            notes.append(f"{year}: game ID {gid} has conflicting map names")
        map_names_by_id[gid] = row.get("Map", "")

    # Scores contain participating teams; don't count all teams in all_teams_ids.
    score_rows = 0
    score_match_keys = set()
    team_names = set()
    for row in read_csv(season / "matches" / "scores.csv"):
        score_rows += 1
        score_match_keys.add(tuple((row.get(c) or "").strip() for c in KEY[:-1]))
        for col in ("Team A", "Team B"):
            value = (row.get(col) or "").strip()
            if value:
                team_names.add(value)

    # Map scores are a better candidate for completed games than ID rows alone.
    scored_map_rows = 0
    scored_game_ids = set()
    unmatched_map_scores = 0
    ambiguous_map_scores = 0
    for row in read_csv(season / "matches" / "maps_scores.csv"):
        scored_map_rows += 1
        candidates = game_ids_by_key.get(game_key(row), set())
        if not candidates:
            unmatched_map_scores += 1
        elif len(candidates) > 1:
            ambiguous_map_scores += 1
        else:
            scored_game_ids.update(candidates)

    # A player typically has 'both', 'attack' and 'defend' overview rows.
    overview_rows = 0
    sides = Counter()
    both_rows = 0
    both_missing_game = 0
    both_ambiguous_game = 0
    unique_player_game_agent = set()
    repeated_player_game_agent = 0
    possible_multi_agent = Counter()
    for row in read_csv(season / "matches" / "overview.csv"):
        overview_rows += 1
        side = (row.get("Side") or "").strip().lower()
        sides[side] += 1
        if side != "both":
            continue
        both_rows += 1
        candidates = game_ids_by_key.get(game_key(row), set())
        if not candidates:
            both_missing_game += 1
            continue
        if len(candidates) != 1:
            both_ambiguous_game += 1
            continue
        agent = (row.get("Agents") or "").strip().lower()
        if any(separator in agent for separator in (",", "/", ";", "|")):
            possible_multi_agent[agent] += 1
        gid = next(iter(candidates))
        pkey = (gid, (row.get("Player") or "").strip(),
                (row.get("Team") or "").strip(), agent)
        if pkey in unique_player_game_agent:
            repeated_player_game_agent += 1
        unique_player_game_agent.add(pkey)

    # Pick-rates are percentages, not additive pick counts.
    pick_rate_rows = 0
    all_maps_rows = 0
    for row in read_csv(season / "agents" / "agents_pick_rates.csv"):
        pick_rate_rows += 1
        if (row.get("Map") or "").strip().lower() == "all maps":
            all_maps_rows += 1

    summary.append({
        "year": year,
        "id_rows": ids_rows,
        "tournaments_with_games": len(tournaments),
        "unique_match_ids": len(matches),
        "unique_game_ids": len(games),
        "missing_id_rows": blank_id_rows,
        "repeated_game_id_rows": repeated_game_id_rows,
        "scores_rows": score_rows,
        "distinct_team_names_in_scores": len(team_names),
        "maps_scores_rows": scored_map_rows,
        "matched_scored_game_ids": len(scored_game_ids),
        "maps_scores_unmatched_to_id": unmatched_map_scores,
        "maps_scores_ambiguous_to_id": ambiguous_map_scores,
        "overview_rows": overview_rows,
        "overview_side_both": sides["both"],
        "overview_side_attack": sides["attack"],
        "overview_side_defence": sides["defend"],
        "both_rows_unmatched_to_game_id": both_missing_game,
        "both_rows_ambiguous_to_game_id": both_ambiguous_game,
        "unique_both_player_game_agent_rows": len(unique_player_game_agent),
        "repeated_both_player_game_agent_rows": repeated_player_game_agent,
        "agent_pick_rate_rows": pick_rate_rows,
        "agent_pick_rate_all_maps_rows": all_maps_rows,
    })
    if possible_multi_agent:
        notes.append(f"{year}: candidate multi-agent 'Agents' values: {possible_multi_agent.most_common(8)}")
    notes.append(f"{year}: overview Side distribution: {dict(sides)}")

with (OUT / "homepage_profile.csv").open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(summary[0]))
    writer.writeheader()
    writer.writerows(summary)

(OUT / "homepage_profile_notes.txt").write_text(
    "Homepage data profile notes\n"
    "Counts are diagnostics, not final UI numbers.\n"
    "Team-name counts may include aliases; confirm team IDs before use.\n"
    "A map game is not necessarily completed just because it has a Game ID.\n\n"
    + "\n".join(notes) + "\n", encoding="utf-8"
)
print("Finished. Upload docs/shared/homepage_profile.csv and docs/shared/homepage_profile_notes.txt")
