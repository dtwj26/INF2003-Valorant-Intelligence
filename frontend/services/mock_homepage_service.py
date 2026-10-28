"""Temporary JSON backend. Member 1 integrates through services/homepage_service.py instead.

This file contains fixture validation/calculations, never database or UI code.
"""
import json
from collections import Counter
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "mock_data.json"


class MockDataError(Exception):
    """Recoverable source or validation failure."""


def _load_data(path=None):
    try:
        data = json.loads(Path(path or DATA_PATH).read_text(encoding="utf-8-sig"))
        if data["is_mock"] is not True:
            raise ValueError("Source must be labelled as mock data.")
        seasons = data["seasons"]
        if not seasons or any(type(year) is not int for year in seasons) or len(seasons) != len(set(seasons)):
            raise ValueError("Seasons must be a nonempty unique list.")
        indexes = {}
        for name in ("teams", "tournaments", "maps", "agents"):
            indexes[name] = {item["id"]: item for item in data[name]}
            if len(indexes[name]) != len(data[name]):
                raise ValueError(f"Duplicate IDs in {name}.")
            if any(not isinstance(item["name"], str) for item in data[name]):
                raise ValueError(f"Invalid names in {name}.")
        seen_matches, seen_games = set(), set()
        for match in data["matches"]:
            if match["id"] in seen_matches or match["season"] not in seasons:
                raise ValueError("Duplicate match ID or unknown season.")
            seen_matches.add(match["id"])
            if match["tournament_id"] not in indexes["tournaments"]:
                raise ValueError("Unknown tournament.")
            teams = match["team_ids"]
            if len(teams) != 2 or len(set(teams)) != 2:
                raise ValueError("A match needs two different teams.")
            if any(team not in indexes["teams"] for team in teams):
                raise ValueError("Unknown team.")
            if not match["map_games"]:
                raise ValueError("A completed match needs a map game.")
            for game in match["map_games"]:
                if game["id"] in seen_games or game["map_id"] not in indexes["maps"]:
                    raise ValueError("Duplicate game ID or unknown map.")
                seen_games.add(game["id"])
                if set(game["agent_picks"]) != set(teams):
                    raise ValueError("Agent picks must belong to both match teams.")
                for picks in game["agent_picks"].values():
                    if len(picks) != 5 or len(set(picks)) != 5:
                        raise ValueError("Each team needs five distinct selections.")
                    if any(agent not in indexes["agents"] for agent in picks):
                        raise ValueError("Unknown agent.")
        return data
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        raise MockDataError("The mock data file is missing, unreadable or invalid.") from error


def get_seasons():
    """Demo seasons newest first, including the empty example."""
    return sorted(_load_data()["seasons"], reverse=True)


def get_homepage_data(season):
    """One consistent season snapshot, counting completed series only.

    Map games count once; agent picks once per player per map, never per round.
    An empty season returns zeros and empty lists, not an error.
    """
    data = _load_data()
    if season not in data["seasons"]:
        raise MockDataError("Choose a season available in the demo source.")
    matches = [match for match in data["matches"] if match["season"] == season]
    games = [game for match in matches for game in match["map_games"]]
    teams = {team for match in matches for team in match["team_ids"]}
    maps = {item["id"]: item for item in data["maps"]}
    agents = {item["id"]: item for item in data["agents"]}
    map_counts = Counter(game["map_id"] for game in games)
    pick_counts = Counter(agent for game in games
                          for picks in game["agent_picks"].values() for agent in picks)
    return {
        "summary": {
            "tournaments": len({match["tournament_id"] for match in matches}),
            "matches": len(matches), "teams": len(teams),
        },
        "maps": sorted([{"name": maps[key]["name"], "games": count} for key, count in map_counts.items()],
                       key=lambda row: (-row["games"], row["name"])),
        "agents": sorted([{"name": agents[key]["name"], "picks": count} for key, count in pick_counts.items()],
                         key=lambda row: (-row["picks"], row["name"])),
        "teams": sorted([dict(team) for team in data["teams"] if team["id"] in teams],
                        key=lambda team: team["name"]),
    }
