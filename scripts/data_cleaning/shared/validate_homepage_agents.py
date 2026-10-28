"""Validate Homepage agent candidates against VCT Game IDs (2021-2026).

Run from the repository root:
    python scripts/data_cleaning/shared/validate_homepage_agents.py

Reads raw Game ID mapping, raw map scores, and preliminary cleaned candidate CSVs.
Writes only small diagnostics to docs/shared/; never edits dataset files.
This is a validation tool, NOT a final data import or data cleaner.
"""
from collections import Counter, defaultdict
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "cleaned" / "shared"
REPORTS = ROOT / "docs" / "shared"
REPORTS.mkdir(parents=True, exist_ok=True)

MATCH_FIELDS = ("Tournament", "Stage", "Match Type", "Match Name", "Map")
MAX_EXAMPLES_PER_REASON = 15
ISSUE_FIELDS = [
    "Year", "Issue", "Tournament", "Match Name", "Map", "Team",
    "Player", "Agent", "Game ID", "Detail",
]


def rows(path):
    if not path.is_file():
        raise FileNotFoundError(f"Required input not found: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        yield from csv.DictReader(handle)


def match_key(row):
    """Exact match context; do not silently fuzzy-match different games."""
    return tuple((row.get(field) or "").strip() for field in MATCH_FIELDS)


def tidy(value):
    return (value or "").strip()


summaries = []
issues_path = REPORTS / "agent_validation_examples.csv"
with issues_path.open("w", newline="", encoding="utf-8") as issue_handle:
    issue_writer = csv.DictWriter(issue_handle, fieldnames=ISSUE_FIELDS)
    issue_writer.writeheader()

    for year in range(2021, 2027):
        print(f"Validating {year} ...", flush=True)
        season = RAW / f"vct_{year}"
        game_mapping = defaultdict(set)
        game_id_contexts = defaultdict(set)
        for row in rows(season / "ids" / "tournaments_stages_matches_games_ids.csv"):
            game_id = tidy(row.get("Game ID"))
            if game_id:
                key = match_key(row)
                game_mapping[key].add(game_id)
                game_id_contexts[game_id].add(key)

        # Score record is a useful check, but is not proof that a game finished.
        scored_keys = set()
        for row in rows(season / "matches" / "maps_scores.csv"):
            scored_keys.add(match_key(row))

        metrics = Counter()
        examples = Counter()
        game_players = defaultdict(set)  # game -> unique (team, player) pairs
        player_agents = defaultdict(set)  # (game, team, player) -> agent strings
        seen_exact = set()
        matched_game_ids = set()

        def issue(reason, row, game_id="", detail=""):
            metrics[reason] += 1
            if examples[reason] < MAX_EXAMPLES_PER_REASON:
                examples[reason] += 1
                issue_writer.writerow({
                    "Year": year, "Issue": reason,
                    "Tournament": tidy(row.get("Tournament")),
                    "Match Name": tidy(row.get("Match Name")),
                    "Map": tidy(row.get("Map")),
                    "Team": tidy(row.get("Team")),
                    "Player": tidy(row.get("Player")),
                    "Agent": tidy(row.get("Agent")),
                    "Game ID": game_id, "Detail": detail,
                })

        for row in rows(CLEAN / f"agent_candidates_{year}.csv"):
            metrics["candidate_rows"] += 1
            key = match_key(row)
            ids = game_mapping.get(key, set())
            if not ids:
                issue("no_game_id_match", row)
                continue
            if len(ids) > 1:
                issue("ambiguous_game_id", row, detail=f"Possible IDs: {','.join(sorted(ids))}")
                continue

            game_id = next(iter(ids))
            metrics["matched_rows"] += 1
            matched_game_ids.add(game_id)
            if key not in scored_keys:
                issue("no_matching_map_score", row, game_id)

            player = tidy(row.get("Player"))
            team = tidy(row.get("Team"))
            agent = tidy(row.get("Agent")).casefold()
            if not player or not team:
                issue("blank_player_or_team", row, game_id)
                continue

            # Use game+team+player to distinguish a player from other records.
            # The agent is excluded from this grouping to detect conflicting picks.
            person_key = (game_id, team.casefold(), player.casefold())
            exact_key = (*person_key, agent)
            if exact_key in seen_exact:
                issue("duplicate_same_selection", row, game_id)
            else:
                seen_exact.add(exact_key)
            player_agents[person_key].add(agent)
            game_players[game_id].add((team.casefold(), player.casefold()))

        # One player switching agents, or duplicate/conflicting data? Needs review.
        conflicting = [(key, agents) for key, agents in player_agents.items() if len(agents) > 1]
        metrics["player_game_with_multiple_agents"] = len(conflicting)
        for (game_id, team, player), agents in conflicting[:MAX_EXAMPLES_PER_REASON]:
            issue_writer.writerow({
                "Year": year, "Issue": "player_game_multiple_agents_example",
                "Tournament": "", "Match Name": "", "Map": "",
                "Team": team, "Player": player, "Agent": ", ".join(sorted(agents)),
                "Game ID": game_id, "Detail": "Review player/game agent assignment",
            })

        counts_by_game = Counter({gid: len(players) for gid, players in game_players.items()})
        non_ten = [(gid, count) for gid, count in counts_by_game.items() if count != 10]
        metrics["games_with_candidates"] = len(game_players)
        metrics["games_not_10_players"] = len(non_ten)
        metrics["unique_player_game_team_pairs"] = len(player_agents)
        metrics["game_ids_with_conflicting_contexts"] = sum(
            len(contexts) > 1 for contexts in game_id_contexts.values()
        )
        for gid, count in non_ten[:MAX_EXAMPLES_PER_REASON]:
            issue_writer.writerow({
                "Year": year, "Issue": "game_not_10_players_example",
                "Tournament": "", "Match Name": "", "Map": "",
                "Team": "", "Player": "", "Agent": "", "Game ID": gid,
                "Detail": f"Unique player-team pairs found: {count}",
            })

        summary = {"Year": year, **{name: metrics[name] for name in (
            "candidate_rows", "matched_rows", "no_game_id_match", "ambiguous_game_id",
            "no_matching_map_score", "blank_player_or_team", "duplicate_same_selection",
            "player_game_with_multiple_agents", "games_with_candidates",
            "games_not_10_players", "unique_player_game_team_pairs",
            "game_ids_with_conflicting_contexts",
        )}}
        summaries.append(summary)
        print(
            f"  matched {summary['matched_rows']:,}/{summary['candidate_rows']:,}; "
            f"missing ID {summary['no_game_id_match']:,}; "
            f"ambiguous ID {summary['ambiguous_game_id']:,}; "
            f"duplicates {summary['duplicate_same_selection']:,}; "
            f"games not at 10 players {summary['games_not_10_players']:,}"
        )

summary_path = REPORTS / "agent_validation_summary.csv"
with summary_path.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(summaries[0]))
    writer.writeheader()
    writer.writerows(summaries)

notes_path = REPORTS / "agent_validation_readme.txt"
notes_path.write_text(
    "HOMEPAGE AGENT CANDIDATE VALIDATION\n"
    "Input: data/cleaned/shared/agent_candidates_YEAR.csv, raw per-year Game IDs and maps_scores.\n"
    "No raw or cleaned dataset was modified.\n"
    "Match key: Tournament + Stage + Match Type + Match Name + Map (exact, trimmed).\n"
    "no_game_id_match = no valid Game ID for the match key.\n"
    "ambiguous_game_id = multiple Game IDs found for the same match key.\n"
    "no_matching_map_score = no matching score key; does not prove game incomplete.\n"
    "duplicate_same_selection = repeated game + team + player + agent entry.\n"
    "player_game_with_multiple_agents = same game/team/player with different agents; needs review.\n"
    "games_not_10_players = game has a nonstandard count of unique player/team pairs; "
    "flag only, do not automatically discard.\n"
    "Issue example CSV includes up to 15 examples per issue type per year.\n"
    "Important: multi-agent and missing-agent records set aside by clean_homepage.py "
    "are not validated here; review them separately before finalising pick counts.\n"
    "Results are diagnostics, NOT final agent picks or completeness guarantees.\n",
    encoding="utf-8",
)
print("\nReports created:")
print(" -", summary_path)
print(" -", issues_path)
print(" -", notes_path)
