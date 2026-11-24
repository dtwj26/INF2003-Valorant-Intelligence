"""Frontend adapters for Matches.

get_match_seasons() and get_match_records() supply the live Matches list.
get_match_details() adapts live Matches maps and scoreboards for the frontend.
No Streamlit or database connections belong in this module.
"""

from backend.matches import service as matches_service


class DataServiceError(Exception):
    """Records could not be loaded; the view offers a retry."""


def get_match_seasons():
    """Return seasons with match results in PostgreSQL."""
    try:
        return matches_service.get_seasons()
    except Exception as error:
        raise DataServiceError('Match seasons could not be loaded.') from error


def get_match_records(season, tournament_id='', map_name='', search=''):
    """Return match results and the team/tournament labels used by filters."""
    try:
        matches = matches_service.get_matches(season, tournament_id, map_name, search)
        teams = {}
        tournaments = {}
        for match in matches:
            tournaments[match['tournament_id']] = match['tournament']
            for team_id, team_name in zip(match['team_ids'], match['team_names']):
                teams[team_id] = team_name
        return {
            'matches': matches,
            'teams': [
                {'id': team_id, 'name': name}
                for team_id, name in sorted(teams.items(), key=lambda item: item[1])
            ],
            'tournaments': [
                {'id': tournament_id, 'name': name}
                for tournament_id, name in sorted(tournaments.items(), key=lambda item: item[1])
            ],
            'maps': matches_service.get_season_maps(season),
        }
    except Exception as error:
        raise DataServiceError('Match records could not be loaded.') from error


def get_match_details(match_id):
    """Return one match's maps and scoreboards using frontend field names."""
    try:
        games = []
        for game in matches_service.get_match_details(match_id):
            games.append({
                'id': str(game['game_id']),
                'map': game['map_name'],
                'scores': [game['team_a_score'], game['team_b_score']],
                'players': [
                    {
                        'player_id': str(player['player_id']),
                        'player_name': player['player_name'],
                        'team_id': str(player['team_id']),
                        'team_name': player['team_name'],
                        'agent': player['agent_name'],
                        'acs': float(player['acs']) if player['acs'] is not None else None,
                        'kills': player['kills'],
                        'deaths': player['deaths'],
                        'assists': player['assists'],
                    }
                    for player in game['players']
                ],
            })
        return games
    except Exception as error:
        raise DataServiceError('Match details could not be loaded.') from error