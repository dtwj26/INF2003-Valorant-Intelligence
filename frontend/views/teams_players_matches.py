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

from services.live_teams_players_service import get_live_records
from components.agent_names import format_agent_name


ROOT = Path(__file__).resolve().parents[1]


def _load_records(view, season, tournament_id='', map_name=''):
    # keep the existing matches service
    if view == 'Matches':
        return service.get_records(
            season,
            tournament_id,
            map_name
        )

    # use PostgreSQL for teams and players
    data = get_live_records(
        season,
        tournament_id,
        map_name
    )

    return {
        **data,
        'matches': []
    }


def _browse_live(view, data):
    if view == "Teams":
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])

        with c1:
            search = st.text_input(
                "Search teams",
                placeholder="Team name",
                key="live_records_search_Teams"
            ).strip().casefold()

        tournament_names = {"": "All tournaments"}
        tournament_names.update({
            t["id"]: t["name"]
            for t in data["tournaments"]
        })

        with c2:
            tournament_id = st.selectbox(
                "Tournament",
                list(tournament_names),
                format_func=lambda x: tournament_names[x],
                key="live_team_tournament"
            )

        with c3:
            map_name = st.selectbox(
                "Map",
                [""] + data["maps"],
                format_func=lambda x: x or "All maps",
                key="live_team_map"
            )

        with c4:
            sort_by = st.selectbox(
                "Sort by",
                ["Name A-Z", "Most map games"],
                key="live_team_sort"
            )

        scoped = _load_records(
            "Teams",
            st.session_state.season,
            tournament_id,
            map_name
        )

        records = [
            t for t in scoped["teams"]
            if search in t["name"].casefold()
        ]

        if sort_by == "Most map games":
            records.sort(
                key=lambda t: (-t["games"], t["name"].casefold())
            )
        else:
            records.sort(key=lambda t: t["name"].casefold())

    else:
        c1, c2, c3, c4 = st.columns(
            [2, 1, 1, 1],
            gap="medium"
        )

        with c1:
            search = st.text_input(
                "Search players",
                placeholder="Player name",
                key="live_records_search_Players"
            ).strip().casefold()

        team_names = sorted({
            p["team_name"]
            for p in data["players"]
            if p.get("team_name")
        })

        with c2:
            selected_team = st.selectbox(
                "Team",
                ["All teams"] + team_names,
                key="live_player_team"
            )

        agent_names = sorted({
            a["name"]
            for p in data["players"]
            for a in p.get("agents", [])
            if a.get("name")
        })

        
        with c3:
            selected_agent = st.selectbox(
                "Agent",
                ["All agents"] + agent_names,
                format_func=format_agent_name,
                key="live_player_agent"
            )


        with c4:
            sort_by = st.selectbox(
                "Sort by",
                ["Name A-Z", "Most map games"],
                key="live_player_sort"
            )

        records = [
            p for p in data["players"]
            if (
                selected_team == "All teams"
                or p["team_name"] == selected_team
            )
            and (
                selected_agent == "All agents"
                or any(
                    a["name"] == selected_agent
                    for a in p.get("agents", [])
                )
            )
            and search in (
                f"{p['name']} {p['team_name']}"
            ).casefold()
        ]

        if sort_by == "Most map games":
            records.sort(
                key=lambda p: (
                    -p["games"],
                    p["name"].casefold()
                )
            )
        else:
            records.sort(
                key=lambda p: p["name"].casefold()
            )


    st.caption(f"{len(records)} {view.lower()} found")
    
    # paginate teams and players
    total_records = len(records)
    page_size = 8
    page_key = f"live_page_{view}"

    total_pages = max(
        1,
        (total_records + page_size - 1) // page_size
    )

    page = max(
        1,
        min(st.session_state.get(page_key, 1), total_pages)
    )

    st.session_state[page_key] = page

    records = records[
        (page - 1) * page_size : page * page_size
    ]




    if view == "Teams":
        rows = [
            {
                "Team": t["name"],
                "Match series": t["matches"],
                "Map games": t["games"],
                "Recorded players": len(t["roster"]),
            }
            for t in records
        ]
    else:
        rows = [
            {
                "Player": p["name"],
                "Team": p["team_name"],
                "Map games": p["games"],
                "Avg. ACS": p["acs"],
                "K/D": f"{p['kd']:.2f}" if p["kd"] is not None else "—",
            }
            for p in records
        ]

    
    
    rich = {}

    
    if view == "Teams":
        rich["Team"] = [
            '<div class="record-name">'
            + _image(get_team_logo(t["id"]), "table-team-logo")
            + _record_link(t["name"], "Teams", t["id"])
            + '</div>'
            for t in records
        ]


    
    else:
        rich["Player"] = [
            _record_link(p["name"], "Players", p["id"])
            for p in records
        ]

        rich["Team"] = [
            '<div class="record-name">'
            + _image(get_team_logo(p["team"]), "table-team-logo")
            + f'<span>{escape(p["team_name"])}</span></div>'
            for p in records
        ]




    
    
    _table(
        rows,
        ids=[r["id"] for r in records],
        view=view,
        name=f"live_records_{view.lower()}",
        action=True,
        rich=rich
    )



    
    # pagination controls
    first_record = (
        (page - 1) * page_size + 1
        if total_records else 0
    )
    last_record = min(page * page_size, total_records)

    footer, previous, next_page = st.columns(
        [5, 1, 1],
        vertical_alignment="center"
    )

    footer.caption(
        f"Showing {first_record}-{last_record} "
        f"of {total_records} / "
        f"Page {page} of {total_pages}"
    )

    if previous.button(
        "Previous",
        disabled=page == 1,
        key=f"live_previous_{view}",
        width="stretch"
    ):
        st.session_state[page_key] = page - 1
        st.rerun()

    if next_page.button(
        "Next",
        disabled=page == total_pages,
        key=f"live_next_{view}",
        width="stretch"
    ):
        st.session_state[page_key] = page + 1
        st.rerun()


def _team_detail_live(team, data, season):
    # team identity
    st.html(
        '<div class="record-identity">'
        + _image(get_team_logo(team["id"]), "team-logo")
        + f'<div><h2>{escape(team["name"])}</h2>'
        + f'Season overview / VCT {season} (all tournaments and maps)'
        + '</div></div>'
    )

    # verified PostgreSQL statistics
    _metrics([
        ("Match series", team["matches"], "Recorded series"),
        ("Map games", team["games"], "Recorded map appearances"),
        ("Recorded players", len(team["roster"]), "Players with recorded statistics")
    ])

    # recorded team roster
    _section(
        "Recorded Roster",
        "Players identified from recorded map games."
    )

    roster_ids = set(team["roster"])

    roster = sorted(
        [
            p for p in data["players"]
            if p["id"] in roster_ids
        ],
        key=lambda p: p["name"].casefold()
    )

    roster_rows = [
        {
            "Player": p["name"],
            "Most used agent": format_agent_name(p.get("agent"))
        }
        for p in roster
    ]

    
    _table(
        roster_rows,
        ids=[p["id"] for p in roster],
        view="Players",
        name="live_team_roster",
        action=True,
        rich={
            "Player": [
                _record_link(p["name"], "Players", p["id"])
                for p in roster
            ]
        }
    )


    st.caption(
        "Match results and win rates will be available "
        "after the Matches backend is integrated."
    )


def _player_detail_live(player, data, season):
    # player identity
    st.html(
        f'<h2 class="record-detail-title">'
        f'{escape(player["name"])}</h2>'
    )


    st.caption(
        f'Season overview / VCT {season} (all tournaments and maps) / '
        f'{player.get("team_name") or "Team not recorded"}'
    )


    # verified performance statistics
    acs = player.get("acs")
    kd = player.get("kd")

    _metrics([
        (
            "Avg. ACS",
            f"{acs:.2f}" if acs is not None else "—",
            "Average combat score"
        ),
        (
            "K/D",
            f"{kd:.2f}" if kd is not None else "—",
            "Kills divided by deaths"
        ),
        (
            "Map games",
            player["games"],
            "Recorded player-map appearances"
        )
    ])

    _section(
        "Performance Statistics",
        "Aggregated statistics from recorded map games."
    )

    _table([
        {"Measure": "Kills", "Value": player.get("kills")},
        {"Measure": "Deaths", "Value": player.get("deaths")},
        {"Measure": "Assists", "Value": player.get("assists")}
    ], name="live_player_performance", action=False)

    _section(
        "Agent Usage",
        "Agents recorded across the player's map games."
    )

    agents = player.get("agents", [])

    agent_rows = [
        {
            "Agent": format_agent_name(a["name"]),
            "Map picks": a["picks"],
            "Usage share (%)": a["share"]
        }
        for a in agents
    ]

    _table(
        agent_rows,
        name="live_player_agents",
        action=False,
        rich={
            "Agent": [
                '<div class="roster-agent">'
                + _image(get_agent_image(a["name"]), "table-agent-image")
                + escape(format_agent_name(a["name"]))
                + '</div>'
                for a in agents
            ]
        }
    )

    st.caption(
        "Match-level results will be connected when "
        "the Matches backend is integrated."
    )

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
        
        active_view = st.session_state.get(
            "record_view",
            st.session_state.get("record_view_saved", "Teams")
        )

        if active_view == "Matches":
            seasons = service.get_seasons()
        else:
            seasons = [2026, 2025, 2024, 2023, 2022, 2021]

        if not seasons:
            st.info('No seasons are available yet. Refresh after records have been added.')
            st.button('Refresh records')
            return
        if st.session_state.get('season') not in seasons:
            st.session_state.season = seasons[0]
            _reset_scope()
        text, selector = st.columns([3, 1], vertical_alignment='center')
        text.write('Explore the records. Follow teams and players into their matches.')
        
        if active_view == "Matches":
            text.caption(
                "Coverage: Valorant Champions 2023 (existing JSON preview data)."
            )
        else:
            text.caption(
                f"Coverage: VCT {st.session_state.season} records from PostgreSQL. "
                "Statistics reflect recorded tournaments in the selected season."
            )

        with selector:
            st.selectbox('Season', seasons, key='season', on_change=_reset_scope)
        if 'record_view' not in st.session_state:
            st.session_state.record_view = st.session_state.get('record_view_saved', 'Teams')
        with st.container(key='record_tabs'):
            view = st.radio('Record type', ['Teams', 'Players', 'Matches'], horizontal=True,
                            key='record_view', label_visibility='collapsed', on_change=_back)
        season = st.session_state.season
        # clear selected profile when season changes
        previous_season = st.session_state.get(
            "records_last_season"
        )

        if (
            previous_season is not None
            and previous_season != season
        ):
            st.session_state.records_detail = None
            st.session_state.records_revision = (
                st.session_state.get("records_revision", 0) + 1
            )

        st.session_state.records_last_season = season
        with st.spinner('Loading records…'):
            data = _load_records(view, season)
        
        records_by_view = {
            'Teams': data.get('teams', []),
            'Players': data.get('players', []),
            'Matches': data.get('matches', []),
        }

        
        if view == "Players" and season == 2021:
            st.warning(
                "2021 player-performance statistics have not "
                "been imported into PostgreSQL. "
                "Team and match records may still be available."
            )
            return


        if not records_by_view[view]:
            st.info(
                f'No {view.lower()} records are available for {season}. '
                'Choose another season to continue.'
            )
            return

        
        # explain incomplete 2022 player statistics
        if view == "Players" and season == 2022:
            st.info(
                "2022 player statistics have partial coverage. "
                "Some unmatched or ambiguous source records "
                "were excluded during validation to maintain "
                "data accuracy."
            )

        detail = st.session_state.get('records_detail')
        if detail:
            st.button(f'Back to {view.lower()}', on_click=_back)
            
            record = next(
                (
                    row for row in data[view.lower()]
                    if str(row["id"]) == str(detail)
                ),
                None
            )

            if record is None:
                st.warning('This record is no longer available. Return to the list and choose another record.')
            elif view == 'Teams':
                _team_detail_live(record, data, season)
            elif view == 'Players':
                _player_detail_live(record, data, season)
            else:
                _match_detail(record, data)
        else:
            if view in ("Teams", "Players"):
                _browse_live(view, data)
            else:
                _browse(view, data, season)
    except service.DataServiceError:
        st.error('Records could not be loaded. Your selections are kept. Retry loading to continue.')
        st.button('Retry loading', type='primary')
