"""Member 2: replace the JSON read with your backend when it is ready.

get_seasons() supplies the selector; get_records() supplies the three views.
A tournament extract from the supplied CSV dataset is kept in data/teams_players_matches.json.
No Streamlit or database connections belong in this module.
"""
import json
from collections import Counter
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parents[1] / 'data' / 'teams_players_matches.json'


class DataServiceError(Exception):
    """Records could not be loaded; the view offers a retry."""


def _read():
    # CONNECTION POINT: replace this read with Member 2's backend call.
    try:
        return json.loads(DATA_FILE.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as error:
        raise DataServiceError('Records could not be loaded.') from error


def get_seasons():
    return sorted(set(_read()['seasons']), reverse=True)


def _rate(wins, total):
    return round(wins / total * 100, 1) if total else None


def get_records(season, tournament_id='', map_name=''):
    """Return teams, players and matches for a season and optional scope.

    Team fields include roster IDs, series/map totals and per-map performance.
    Player fields include totals, ACS, K/D and agent usage.
    Match fields include the full series score and per-map player scoreboards.
    A map filter restricts map statistics, but never rewrites a series result.
    The frontend uses these dictionaries regardless of the database technology.
    """
    data = _read()
    teams = {t['id']: dict(t) for t in data['teams']}
    tournaments = {t['id']: t['name'] for t in data['tournaments']}
    matches = []
    for source in data['matches']:
        if source['season'] != season or (tournament_id and source['tournament_id'] != tournament_id):
            continue
        if map_name and not any(g['map'] == map_name for g in source['games']):
            continue
        match = dict(source)
        match['team_names'] = [teams[t]['name'] for t in match['team_ids']]
        match['tournament'] = tournaments[match['tournament_id']]
        match['score'] = [sum(g['scores'][side] > g['scores'][1-side] for g in match['games']) for side in (0, 1)]
        matches.append(match)
    matches.sort(key=lambda m: m['date'], reverse=True)

    players = []
    for source in data['players']:
        appearances = [p for m in matches for g in m['games'] if not map_name or g['map'] == map_name
                       for p in g['players'] if p['player_id'] == source['id']]
        if not appearances:
            continue
        player = dict(source)
        player['team_name'] = teams[player['team']]['name']
        player['games'] = len(appearances)
        for field in ('kills', 'deaths', 'assists'):
            player[field] = sum(p[field] for p in appearances)
        acs_values = [p['acs'] for p in appearances if p['acs'] is not None]
        player['acs'] = round(sum(acs_values) / len(acs_values)) if len(acs_values) == len(appearances) else None
        player['kd'] = round(player['kills'] / player['deaths'], 2) if player['deaths'] else None
        player['agents'] = [dict(name=name, picks=count, share=_rate(count, len(appearances)))
                            for name, count in Counter(p['agent'] for p in appearances).most_common()]
        players.append(player)

    team_rows = []
    for team_id, team in teams.items():
        history = [m for m in matches if team_id in m['team_ids']]
        if not history:
            continue
        outcomes = []
        series_wins = 0
        for match in history:
            side = match['team_ids'].index(team_id)
            series_wins += match['score'][side] > match['score'][1-side]
            outcomes.extend((g['map'], g['scores'][side] > g['scores'][1-side]) for g in match['games']
                            if not map_name or g['map'] == map_name)
        team.update(matches=len(history), wins=series_wins, losses=len(history)-series_wins,
                    games=len(outcomes), map_wins=sum(w for _, w in outcomes),
                    win_rate=_rate(sum(w for _, w in outcomes), len(outcomes)),
                    roster=[p['id'] for p in players if p['team'] == team_id])
        team['maps'] = []
        for name in sorted({name for name, _ in outcomes}):
            wins = [w for n, w in outcomes if n == name]
            team['maps'].append(dict(name=name, games=len(wins), wins=sum(wins), losses=len(wins)-sum(wins),
                                     win_rate=_rate(sum(wins), len(wins))))
        team_rows.append(team)
    season_matches = [m for m in data['matches'] if m['season'] == season]
    return dict(teams=team_rows, players=players, matches=matches,
                tournaments=[t for t in data['tournaments'] if any(m['tournament_id'] == t['id'] for m in season_matches)],
                maps=sorted({g['map'] for m in season_matches for g in m['games']}))
