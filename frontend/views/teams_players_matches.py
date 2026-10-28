"""Teams, Players & Matches; data access stays in the service module.

Layout authority: outputs/app-pages-preview/directory.html in the design workspace.
Preserve its columns, hierarchy and detail layouts; do not substitute data grids.
"""
from functools import partial
from html import escape
from pathlib import Path

import streamlit as st

from components.asset_catalog import get_agent_image, get_map_image, get_team_logo
from services import teams_players_matches_service as service
from components.record_table import _RECORD_TABLE, _table_open, _record_link, _image, _section, _metrics, _pct, _table, _open
from components.sidebar import open_analysis

ROOT = Path(__file__).resolve().parents[1]


def _back():
    st.session_state.record_view_saved = st.session_state.get('record_view', 'Teams')
    st.session_state.records_detail = None
    st.session_state.records_revision = st.session_state.get('records_revision', 0) + 1


# Small native Streamlit component: HTML rows behave like the approved wireframe.
# It only reports a record ID; all navigation and data stay in Python.


def _page(view, step, maximum):
    prefs = st.session_state.setdefault('records_preferences', {}).setdefault(view, {})
    prefs['page'] = max(1, min(maximum, prefs.get('page', 1) + step))


def _reset_scope():
    _back()
    st.session_state.records_preferences = {}
    for key in list(st.session_state):
        if key.startswith('_records_'):
            del st.session_state[key]
    st.session_state.pop('opponent', None)
    st.session_state.pop('scouting_context', None)


def _remember(view, field, key):
    prefs = st.session_state.setdefault('records_preferences', {})
    prefs.setdefault(view, {})[field] = st.session_state[key]
    # A changed filter returns the list to its first page.
    if field != 'page':
        prefs[view]['page'] = 1
        st.session_state.pop(f'_records_{view}_page', None)


def _filter(view, field, label, options=None, placeholder=None):
    key = f'_records_{view}_{field}'
    saved = st.session_state.get('records_preferences', {}).get(view, {}).get(field)
    if key not in st.session_state:
        st.session_state[key] = saved if saved is not None else (options[0] if options else '')
    if options and st.session_state[key] not in options:
        st.session_state[key] = options[0]
    kwargs = dict(key=key, on_change=_remember, args=(view, field, key))
    if options:
        return st.selectbox(label, options, **kwargs)
    return st.text_input(label, placeholder=placeholder, **kwargs)


def _clear(view):
    st.session_state.setdefault('records_preferences', {})[view] = {}
    for key in list(st.session_state):
        if key.startswith(f'_records_{view}_'):
            del st.session_state[key]
    _back()


def _match_table(matches, team_id=None, name='match_history'):
    rows = []
    for match in matches:
        side = match['team_ids'].index(team_id) if team_id else 0
        score = match['score']
        row = {'Date': match['date'], 'Match / tournament': ' vs '.join(match['team_names']), 'Series score': f'{score[side]}–{score[1-side]}'}
        if team_id:
            row['Result'] = 'Win' if score[side] > score[1-side] else 'Loss'
        rows.append(row)
    identity = ['<div class="match-teams">' + _image(get_team_logo(m['team_ids'][0]), 'table-team-logo')
                + _record_link(m['team_names'][0], 'Teams', m['team_ids'][0]) + '<span>vs</span>'
                + _image(get_team_logo(m['team_ids'][1]), 'table-team-logo')
                + _record_link(m['team_names'][1], 'Teams', m['team_ids'][1]) + '</div><small>' + escape(m['tournament']) + '</small>' for m in matches]
    _table(rows, [m['id'] for m in matches], 'Matches', name, rich={'Match / tournament': identity})


def _browse(view, data, season):
    is_players, is_matches = view == 'Players', view == 'Matches'
    with st.container(key='record_filters'):
        columns = st.columns([1.5, 1, 1, 1, 1] if is_matches else [2, 1, 1, 1], gap='medium')
        with columns[0]:
            search = _filter(view, 'search', f'Search {view.lower()}',
                             placeholder='Player or team name' if is_players else ('Team, tournament or match ID' if is_matches else 'Team name')).strip().casefold()
        with columns[1]:
            first = _filter(view, 'first', 'Team' if is_players else 'Tournament',
                            ['All teams'] + [t['name'] for t in data['teams']] if is_players
                            else ['All tournaments'] + [t['name'] for t in data['tournaments']])
        with columns[2]:
            second = _filter(view, 'second', 'Agent' if is_players else 'Map',
                             ['All agents'] + sorted({a['name'] for p in data['players'] for a in p['agents']})
                             if is_players else ['All maps'] + data['maps'])
        if is_matches:
            with columns[3]:
                team_filter = _filter(view, 'team', 'Team', ['All teams'] + [t['name'] for t in data['teams']])
        with columns[-1]:
            order = _filter(view, 'sort', 'Sort by', ['Newest first', 'Oldest first'] if is_matches
                            else ['Name A–Z', 'Most map games'])
    scoped = data
    if not is_players:
        event_id = next((t['id'] for t in data['tournaments'] if t['name'] == first), '')
        scoped = service.get_records(season, event_id, '' if second == 'All maps' else second)
    rows = scoped[view.lower()]
    if is_players:
        rows = [p for p in rows if (first == 'All teams' or p['team_name'] == first)
                and (second == 'All agents' or any(a['name'] == second for a in p['agents']))
                and search in f"{p['name']} {p['team_name']}".casefold()]
    elif is_matches:
        rows = [m for m in rows if (team_filter == 'All teams' or team_filter in m['team_names'])
                and search in (' '.join(m['team_names']) + ' ' + m['tournament'] + ' ' + m['id']).casefold()]
    else:
        rows = [t for t in rows if search in t['name'].casefold()]
    rows = sorted(rows, key=(lambda r: r['date']) if is_matches else
                  ((lambda r: (-r['games'], r['name'])) if order == 'Most map games' else lambda r: r['name']),
                  reverse=is_matches and order == 'Newest first')
    if is_matches:
        active = [label for label in [
            f'Team: {team_filter}' if team_filter != 'All teams' else '',
            f'Tournament: {first}' if first != 'All tournaments' else '',
            f'Map: {second}' if second != 'All maps' else '',
            f'Search: {search}' if search else ''] if label]
        if active:
            st.caption('Active filters: ' + ' / '.join(active) + '. Clear filters to see every team’s matches.')
        else:
            st.caption(f'Search any team across all {len(data["matches"])} matches. The list starts with the newest results.')
    count, clear = st.columns([4, 1], vertical_alignment='center')
    count.caption(f'{len(rows)} {view.lower()} found')
    with clear:
        with st.container(key='record_clear'):
            st.button('Clear filters', on_click=_clear, args=(view,), width='stretch')
    if not rows:
        st.info('No records match your filters. Try another name or clear the filters.')
        return
    total_pages = max(1, (len(rows) + 7) // 8)
    saved_page = st.session_state.get('records_preferences', {}).get(view, {}).get('page', 1)
    page = min(saved_page, total_pages)
    visible = rows[(page-1)*8:page*8]
    if is_matches:
        st.caption('Map filters find series containing that map; scores show the full series.')
        _match_table(visible, name='browse_matches')
    elif is_players:
        _table([{'Player': p['name'], 'Team': p['team_name'], 'Map games': p['games'],
                 'Avg. ACS': p['acs'], 'K/D': f"{p['kd']:.2f}" if p['kd'] is not None else '—'} for p in visible],
               [p['id'] for p in visible], view, 'browse_players', rich={
                   'Player': [_record_link(p['name'], 'Players', p['id']) for p in visible],
                   'Team': ['<div class="record-name">' + _image(get_team_logo(p['team']), 'table-team-logo')
                            + _record_link(p['team_name'], 'Teams', p['team']) + '</div>' for p in visible]})
        st.caption('ACS: average combat score. K/D: total kills divided by total deaths.')
    else:
        _table([{'Team': t['name'], 'Match series': t['matches'],
                 'Series record': f"{t['wins']}W / {t['losses']}L", 'Map games': t['games']} for t in visible],
               [t['id'] for t in visible], view, 'browse_teams', rich={
                   'Team': ['<div class="record-name">' + _image(get_team_logo(t['id']), 'table-team-logo')
                            + _record_link(t['name'], 'Teams', t['id']) + '</div>' for t in visible]})
    footer, previous, next_page = st.columns([5, 1, 1], vertical_alignment='center')
    footer.caption(f'Showing {(page-1)*8+1}–{min(page*8, len(rows))} of {len(rows)} / Page {page} of {total_pages}')
    previous.button('Previous', disabled=page == 1, on_click=_page, args=(view, -1, total_pages), width='stretch')
    next_page.button('Next', disabled=page == total_pages, on_click=_page, args=(view, 1, total_pages), width='stretch')


def _browse_team_matches(team_name):
    _back()
    st.session_state.record_view = 'Matches'
    st.session_state.record_view_saved = 'Matches'
    prefs = st.session_state.setdefault('records_preferences', {})
    prefs['Matches'] = {'team': team_name, 'first': prefs.get('Teams', {}).get('first', 'All tournaments')}
    for key in list(st.session_state):
        if key.startswith('_records_Matches_'):
            del st.session_state[key]


def _team_detail(team, data, season):
    prefs = st.session_state.get('records_preferences', {}).get('Teams', {})
    event_name = prefs.get('first', 'All tournaments')
    event_id = next((t['id'] for t in data['tournaments'] if t['name'] == event_name), '')
    scoped = service.get_records(season, event_id)
    team = next((t for t in scoped['teams'] if t['id'] == team['id']), team)
    identity, actions = st.columns([1.4, 1], vertical_alignment='center')
    with identity:
        st.html('<div class="record-identity">' + _image(get_team_logo(team['id']), 'team-logo')
                + f'<div><h2>{escape(team["name"])}</h2><p>Team profile / {escape(event_name)} / all maps</p></div></div>')
    with actions:
        scout, browse = st.columns([1, 1.4])
        scout.button('Scout this team', type='primary', width='stretch', on_click=open_analysis, args=(team['id'], season, event_id))
        browse.button('Browse team matches', on_click=_browse_team_matches, args=(team['name'],), width='stretch')
    _metrics([('Match series', team['matches'], f"{team['wins']} wins / {team['losses']} losses"),
              ('Map games', team['games'], f"{team['map_wins']} wins / {team['games']-team['map_wins']} losses"),
              ('Map win rate', _pct(team['win_rate']), 'Map games, not series')])
    roster_col, maps_col = st.columns([1.3, 1], gap='large')
    with roster_col:
        _section('Roster', 'Open a player to inspect their performance.')
        roster = [p for p in data['players'] if p['id'] in team['roster']]
        _table([{'Player': p['name'], 'Primary role': p['role']} for p in roster],
               [p['id'] for p in roster], 'Players', 'team_roster', rich={
                   'Primary role': ['<div class="roster-agent">' + _image(get_agent_image(p['agent']), 'table-agent-image')
                                    + '<span>' + escape(p['role']) + '<small>' + escape(p['agent']) + '</small></span></div>' for p in roster]})
    with maps_col:
        _section('Map performance', 'Outcomes across all maps in the tournament scope.')
        _table([{'Map': m['name'], 'Games': m['games'], 'Record': f"{m['wins']}W / {m['losses']}L",
                 'Win rate': _pct(m['win_rate'])} for m in team['maps']])
    _section('Match history', 'Series scores are shown from this team’s perspective.')
    _match_table([m for m in scoped['matches'] if team['id'] in m['team_ids']], team['id'])


def _player_detail(player, data):
    heading, action = st.columns([3, 1], vertical_alignment='center')
    with heading:
        st.html(f'<h2 class="record-detail-title">{escape(player["name"])}</h2>')
        st.caption(f"Player profile / {player['team_name']}")
    action.button('View team', on_click=_open, args=('Teams', player['team']), width='stretch')
    _metrics([('Avg. ACS', player['acs'], 'Average combat score'),
              ('K/D', f"{player['kd']:.2f}" if player['kd'] is not None else '—', f"{player['kills']} kills / {player['deaths']} deaths"),
              ('Map games', player['games'], 'One player record per map game')])
    performance, agents = st.columns([1, 1], gap='large')
    with performance:
        _section('Performance statistics', 'Totals within the selected tournament.')
        _table([{'Measure': label, 'Value': value} for label, value in [
            ('Kills', player['kills']), ('Deaths', player['deaths']), ('Assists', player['assists']),
            ('Average kills per map', round(player['kills']/player['games'], 1))]])
    with agents:
        _section('Agent usage', 'Selections across the player’s map games.')
        st.html('<ul class="agent-list">' + ''.join('<li class="agent-row">'
            + _image(get_agent_image(a['name']), 'agent-image')
            + f'<div><strong>{escape(a["name"])}</strong><span class="agent-role">{a["picks"]} map games</span></div>'
            + f'<span class="agent-value">{_pct(a["share"])}</span></li>' for a in player['agents']) + '</ul>')
    _section('Match appearances', 'Open a match to inspect its map scoreboard.')
    _match_table([m for m in data['matches'] if any(p['player_id'] == player['id']
                  for g in m['games'] for p in g['players'])], player['team'], 'player_history')


def _match_detail(match, data):
    st.html(f'<h2 class="record-detail-title">Match {escape(match["id"])}</h2>')
    st.caption(f"{match['tournament']} / {match['date']} / Completed")
    identity = ('<div class="match-scoreline">'
                + _record_link(match['team_names'][0], 'Teams', match['team_ids'][0])
                + f'<span>{match["score"][0]}–{match["score"][1]}</span>'
                + _record_link(match['team_names'][1], 'Teams', match['team_ids'][1]) + '</div>')
    key = f'match_identity_{match["id"]}'
    _RECORD_TABLE(data={'html': identity}, key=key, on_open_change=partial(_table_open, key))
    games = {g['id']: g for g in match['games']}
    st.caption('Choose a map game to see its score and player records.')
    with st.container(key='record_map_tabs'):
        game_id = st.radio('Map game', list(games), horizontal=True, key=f'map_game_{match["id"]}',
                       format_func=lambda key: f"{games[key]['map']}  {games[key]['scores'][0]}–{games[key]['scores'][1]}")
    game = games[game_id]
    _section(f"{game['map']} scoreboard", f"{match['team_names'][0]} {game['scores'][0]}–{game['scores'][1]} {match['team_names'][1]} / {sum(game['scores'])} rounds")
    players = {p['id']: p for p in data['players']}
    records = game['players']
    team_names = dict(zip(match['team_ids'], match['team_names']))
    _table([{'Player / team': players[p['player_id']]['name'], 'Agent': p['agent'], 'ACS': p['acs'],
             'Kills': p['kills'], 'Deaths': p['deaths'], 'Assists': p['assists'],
             'K/D': f"{p['kills']/p['deaths']:.2f}" if p['deaths'] else '—'} for p in records],
           [p['player_id'] for p in records], 'Players', f'scoreboard_{game_id}', action=False, rich={
               'Player / team': [_record_link(players[p['player_id']]['name'], 'Players', p['player_id'])
                                 + '<small>' + _record_link(team_names[p['team_id']], 'Teams', p['team_id']) + '</small>' for p in records],
               'Agent': ['<div class="roster-agent">' + _image(get_agent_image(p['agent']), 'table-agent-image')
                         + escape(p['agent']) + '</div>' for p in records]})
    st.caption('ACS: average combat score. A dash indicates a value missing from the imported records.')
    with st.container(key='record_match_scout'):
        description, actions = st.columns([1.2, 1], vertical_alignment='center')
        description.subheader('Take this match into scouting')
        description.write('Explore patterns across this team’s records, beyond a single result.')
        with actions:
            first, second = st.columns(2)
            for side, column in enumerate((first, second)):
                column.button(f"Scout {match['team_names'][side]}", width='stretch', on_click=open_analysis,
                              args=(match['team_ids'][side], match['season'], match['tournament_id']))


def render():
    st.title('Teams, Players & Matches')
    try:
        seasons = service.get_seasons()
        if not seasons:
            st.info('No seasons are available yet. Refresh after records have been added.')
            st.button('Refresh records')
            return
        if st.session_state.get('season') not in seasons:
            st.session_state.season = seasons[0]
            _reset_scope()
        text, selector = st.columns([3, 1], vertical_alignment='center')
        text.write('Explore the records. Follow teams and players into their matches.')
        text.caption('Coverage: Valorant Champions 2023. Statistics reflect this tournament.')
        with selector:
            st.selectbox('Season', seasons, key='season', on_change=_reset_scope)
        if 'record_view' not in st.session_state:
            st.session_state.record_view = st.session_state.get('record_view_saved', 'Teams')
        with st.container(key='record_tabs'):
            view = st.radio('Record type', ['Teams', 'Players', 'Matches'], horizontal=True,
                            key='record_view', label_visibility='collapsed', on_change=_back)
        season = st.session_state.season
        with st.spinner('Loading records…'):
            data = service.get_records(season)
        if not data['matches']:
            st.info(f'No records are available for {season}. Choose another season to continue.')
            return
        detail = st.session_state.get('records_detail')
        if detail:
            st.button(f'Back to {view.lower()}', on_click=_back)
            record = next((row for row in data[view.lower()] if row['id'] == detail), None)
            if record is None:
                st.warning('This record is no longer available. Return to the list and choose another record.')
            elif view == 'Teams':
                _team_detail(record, data, season)
            elif view == 'Players':
                _player_detail(record, data)
            else:
                _match_detail(record, data)
        else:
            _browse(view, data, season)
    except service.DataServiceError:
        st.error('Records could not be loaded. Your selections are kept. Retry loading to continue.')
        st.button('Retry loading', type='primary')
