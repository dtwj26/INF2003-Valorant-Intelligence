"""Matches service called by frontend adapters."""

from . import repository


def get_seasons():
    """Return seasons with imported match results."""
    return repository.fetch_seasons()


def get_matches(season, tournament_id="", map_name=""):
    """Return overall match results for the selected scope."""
    return repository.fetch_matches(season, tournament_id, map_name)

def get_match_games(match_id):
    return repository.fetch_match_games(match_id)

def get_player_scoreboard(game_id):
    return repository.fetch_player_scoreboard(game_id)


def get_match_details(match_id):
    """Return one match's maps with each map's player scoreboard."""
    games = get_match_games(match_id)
    for game in games:
        game["players"] = get_player_scoreboard(game["game_id"])
    return games
