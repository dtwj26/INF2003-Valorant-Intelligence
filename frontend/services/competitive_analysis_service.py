"""Members 3/4: connect your analysis backend at get_filters() and get_analysis().

These functions return plain dictionaries; Streamlit and database code stay separate.
Current records come from the supplied Champions 2023 CSV extracts in data/.
Attack/defence exclude overtime. Economy categories retain the source definitions.
"""
import json
from collections import Counter
from pathlib import Path

from services import teams_players_matches_service as records

DETAILS_FILE = Path(__file__).resolve().parents[1] / 'data' / 'competitive_analysis.json'


class DataServiceError(Exception):
    """The view can show a retry when analysis records are unavailable."""


def get_filters(season=None):
    """Return seasons, teams, tournaments and maps for the scouting controls."""
    try:
        seasons = records.get_seasons()
        selected = season if season in seasons else (seasons[0] if seasons else None)
        data = records.get_records(selected) if selected is not None else dict(teams=[], tournaments=[], maps=[])
        return dict(seasons=seasons, teams=sorted(data['teams'], key=lambda t: t['name']),
                    tournaments=data['tournaments'], maps=data['maps'])
    except records.DataServiceError as error:
        raise DataServiceError('Scouting filters could not be loaded.') from error


def _rate(wins, total):
    return round(100 * wins / total, 1) if total else None


def get_analysis(team_id, season, tournament_id='', map_name=''):
    """Return one applied-scope report for all four analysis sections.

    A map filter narrows map/round statistics; supporting series retain full scores.
    Pistol and economy denominators include only recorded opportunities. Missing
    round records are disclosed in coverage rather than replaced with zero wins.
    Recommendations describe the evidence; they do not predict a counter-strategy.
    """
    try:
        # CONNECTION POINT: replace these reads with Members 3/4's backend calls.
        data = records.get_records(season, tournament_id, map_name)
        details = json.loads(DETAILS_FILE.read_text(encoding='utf-8-sig'))['games']
    except (records.DataServiceError, OSError, ValueError) as error:
        raise DataServiceError('Opponent analysis could not be loaded.') from error
    team = next((t for t in data['teams'] if t['id'] == team_id), None)
    matches = [m for m in data['matches'] if team_id in m['team_ids']]
    games = []
    for match in matches:
        side = match['team_ids'].index(team_id)
        for game in match['games']:
            if map_name and game['map'] != map_name:
                continue
            games.append(dict(id=game['id'], map=game['map'], match=match,
                              won=game['scores'][side], lost=game['scores'][1-side],
                              composition=sorted(p['agent'] for p in game['players'] if p['team_id'] == team_id),
                              detail=details.get(game['id'], {}).get('sides', {}).get(team_id, {})))
    round_total = sum(g['won'] + g['lost'] for g in games)
    round_wins = sum(g['won'] for g in games)
    side_stats = {}
    for side in ('attack', 'defence'):
        won = sum(g['detail'].get(side+'_wins', 0) for g in games)
        total = sum(g['detail'].get(side+'_total', 0) for g in games)
        side_stats[side] = dict(wins=won, total=total, rate=_rate(won, total))
    overtime = sum(g['detail'].get('overtime_total', 0) for g in games)
    maps = []
    for name in sorted({g['map'] for g in games}):
        group = [g for g in games if g['map'] == name]
        wins = sum(g['won'] > g['lost'] for g in group)
        maps.append(dict(name=name, games=len(group), wins=wins, losses=len(group)-wins,
                         win_rate=_rate(wins, len(group))))
    agents = Counter(agent for g in games for agent in g['composition'])
    compositions = {}
    for game in games:
        key = tuple(game['composition'])
        row = compositions.setdefault(key, dict(agents=list(key), games=0, wins=0))
        row['games'] += 1
        row['wins'] += game['won'] > game['lost']
    composition_rows = sorted(compositions.values(), key=lambda c: (-c['games'], c['agents']))
    for row in composition_rows:
        row.update(usage=_rate(row['games'], len(games)), win_rate=_rate(row['wins'], row['games']))
    trends = []
    for match in sorted(matches, key=lambda m: (m['date'], int(m['id']))):
        group = [g for g in games if g['match']['id'] == match['id']]
        total = sum(g['won'] + g['lost'] for g in group)
        won = sum(g['won'] for g in group)
        trends.append(dict(match_id=match['id'], date=match['date'], rounds=total, wins=won, rate=_rate(won, total)))
    pistol_wins = pistol_total = conversion_wins = conversion_total = recovery_wins = recovery_total = 0
    economy = {}
    recorded_rounds = 0
    complete_maps = 0
    for game in games:
        rounds = game['detail'].get('rounds', [])
        recorded_rounds += len(rounds)
        complete_maps += len(rounds) == game['won'] + game['lost']
        by_number = {r['number']: r for r in rounds}
        for number in (1, 13):
            pistol = by_number.get(number)
            following = by_number.get(number+1)
            if pistol:
                pistol_total += 1
                pistol_wins += pistol['won']
                if following:
                    if pistol['won']:
                        conversion_total += 1
                        conversion_wins += following['won']
                    else:
                        recovery_total += 1
                        recovery_wins += following['won']
        for row in rounds:
            group = economy.setdefault(row['category'] or 'Unclassified', dict(rounds=0, wins=0))
            group['rounds'] += 1
            group['wins'] += row['won']
    economy_rows = [dict(category=label, **values, rate=_rate(values['wins'], values['rounds'])) for label, values in economy.items()]
    economy_rows.sort(key=lambda r: (not r['category'].startswith('Full buy'), r['category']))
    summary = dict(matches=len(matches), games=len(games), map_wins=sum(g['won'] > g['lost'] for g in games),
                   map_win_rate=_rate(sum(g['won'] > g['lost'] for g in games), len(games)),
                   rounds=round_total, round_wins=round_wins, round_win_rate=_rate(round_wins, round_total),
                   series_wins=team['wins'] if team else 0)
    report = dict(team_id=team_id, team_name=team['name'] if team else '', season=season,
                  tournament_id=tournament_id, map_name=map_name, summary=summary,
                  maps=maps, sides=side_stats, overtime_rounds=overtime,
                  agents=[dict(name=name, picks=count, share=_rate(count, len(games)))
                          for name, count in sorted(agents.items(), key=lambda item: (-item[1], item[0]))],
                  compositions=composition_rows, trends=trends,
                  pistol=[dict(label=label, wins=won, total=total, rate=_rate(won, total)) for label, won, total in [
                      ('Pistol rounds', pistol_wins, pistol_total),
                      ('Next round after pistol win', conversion_wins, conversion_total),
                      ('Next round after pistol loss', recovery_wins, recovery_total)]],
                  economy=economy_rows, matches=matches,
                  coverage=dict(recorded_rounds=recorded_rounds, expected_rounds=round_total,
                                complete_maps=complete_maps, total_maps=len(games)))
    report['recommendations'] = _recommendations(report, games)
    return report


def _recommendations(report, games):
    if not games:
        return []
    strongest = max(report['maps'], key=lambda m: (m['win_rate'], m['games']))
    weakest = min(report['maps'], key=lambda m: (m['win_rate'], -m['games']))
    composition = report['compositions'][0]
    agent = report['agents'][0]

    def evidence(selected):
        return [dict(match_id=g['match']['id'], map=g['map']) for g in selected[:3]]

    return [dict(title=f"Review {strongest['name']} as a map candidate",
                 body=f"{report['team_name']} has {strongest['wins']} wins from {strongest['games']} {strongest['name']} games ({strongest['win_rate']:.1f}%) in this scope. Inspect these matches before deciding how to prepare.",
                 note='An observed win rate does not establish a reliable ban or pick prediction.',
                 value=f"{strongest['wins']} / {strongest['games']} map wins", detail=strongest['name']+' / current applied scope',
                 evidence=evidence([g for g in games if g['map'] == strongest['name']])),
            dict(title='Prepare against the most-used composition',
                 body=f"{', '.join(composition['agents'])} appears in {composition['games']} of {len(games)} games ({composition['usage']:.1f}% usage). {agent['name']} is the most-used individual agent ({agent['picks']} / {len(games)} games). Review the map context before choosing a practice focus.",
                 note='Usage indicates what to review; it does not establish the best counter-composition.',
                 value=f"{agent['picks']} / {len(games)} games", detail=agent['name']+' selections / team-map denominator',
                 evidence=evidence([g for g in games if g['composition'] == composition['agents']])),
            dict(title=f"Review the lower-performing {weakest['name']} games" if len(report['maps']) > 1 else f"Review the {weakest['name']} round evidence",
                 body=f"{weakest['name']} shows {weakest['wins']} wins in {weakest['games']} games ({weakest['win_rate']:.1f}%). Compare the round, pistol and economy evidence with the source scoreboards before deciding what to practise.",
                 note='Opponent strength, small samples and missing records can affect these observations.',
                 value=f"{weakest['games']} map games", detail='Limited scope / no confidence interval inferred',
                 evidence=evidence([g for g in games if g['map'] == weakest['name']]))]
