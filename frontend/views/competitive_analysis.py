"""Competitive Analysis; follows outputs/app-pages-preview/analysis.html.

Keep the four wireframe sections and their information hierarchy. Members 3/4
supply analysis through competitive_analysis_service; this module renders it.
"""
from functools import partial
from datetime import date
from html import escape

import streamlit as st

from services import competitive_analysis_service as service
from components.asset_catalog import get_agent_image, get_agent_role, get_map_image, get_team_logo
from components.record_table import (_table, _image, _record_link, _section, _metrics, _pct,
                                     _RECORD_TABLE, _table_open)

SECTIONS = ['Overview', 'Maps & Agents', 'Rounds & Economy', 'Recommendations']


def _save_draft():
    st.session_state.analysis_draft = dict(team_id=st.session_state.get('analysis_team'),
        tournament_id=st.session_state.get('analysis_tournament', ''),
        map_name=st.session_state.get('analysis_map', ''), season=st.session_state.get('season'))


def _season_changed():
    st.session_state.analysis_team = None
    st.session_state.analysis_tournament = ''
    st.session_state.analysis_map = ''
    st.session_state.analysis_applied = None
    st.session_state.analysis_result = None
    st.session_state.analysis_error = False
    _save_draft()


def _remember_section():
    st.session_state.analysis_section_saved = st.session_state.analysis_section


def _request_analysis():
    _save_draft()
    st.session_state.analysis_pending_request = dict(st.session_state.analysis_draft)


def _retry():
    st.session_state.analysis_pending_request = dict(st.session_state.analysis_failed_request)


def _broaden():
    st.session_state.analysis_tournament = ''
    st.session_state.analysis_map = ''
    _request_analysis()


def _links(content, name):
    key = f'analysis_links_{name}'
    _RECORD_TABLE(data={'html': content}, key=key, on_open_change=partial(_table_open, key))


def _maps(report):
    _table([{'Map': m['name'], 'Games': m['games'], 'Map result': f"{m['wins']}W / {m['losses']}L",
             'Map win rate': _pct(m['win_rate'])} for m in report['maps']],
           rich={'Map': ['<div class="analysis-map-identity">' + _image(get_map_image(m['name']), 'analysis-map-thumbnail')
                         + '<span>'+escape(m['name'])+'</span></div>' for m in report['maps']]}, name='analysis_map_performance')


def _rate_row(label, row):
    return ('<div class="analysis-comparison-row"><span>' + escape(label) + '</span>'
            + f'<div class="bar-track" aria-hidden="true"><div class="bar-fill" style="width:{row["rate"] or 0}%"></div></div>'
            + f'<span class="analysis-rate">{_pct(row["rate"])}<small>{row["wins"]} / {row["total"]} rounds</small></span></div>')


def _supporting_matches(report):
    team_id = report['team_id']
    matches = report['matches']
    rows = []
    for match in matches:
        side = match['team_ids'].index(team_id)
        score = match['score']
        result = 'Win' if score[side] > score[1-side] else 'Loss'
        rows.append({'Date': match['date'], 'Match / tournament': ' vs '.join(match['team_names']),
                     'Full series result': f'{score[side]}–{score[1-side]} / {result}'})
    identity = ['<div class="match-teams">' + _image(get_team_logo(m['team_ids'][0]), 'table-team-logo')
                + _record_link(m['team_names'][0], 'Teams', m['team_ids'][0]) + '<span>vs</span>'
                + _image(get_team_logo(m['team_ids'][1]), 'table-team-logo')
                + _record_link(m['team_names'][1], 'Teams', m['team_ids'][1]) + '</div><small>'
                + escape(m['tournament']) + '</small>' for m in matches]
    results = []
    for row in rows:
        score, result = row['Full series result'].split(' / ')
        results.append('<div class="analysis-series-result"><span class="analysis-series-score">'+escape(score)+'</span>'
                       + f'<span class="analysis-result-badge is-{result.lower()}">{result}</span></div>')
    _table(rows, [m['id'] for m in matches], 'Matches', 'scout_matches',
           rich={'Match / tournament': identity, 'Full series result': results})



def _overview(report):
    summary = report['summary']
    _metrics([('Match series', summary['matches'], 'Containing the selected map scope'),
              ('Map win rate', _pct(summary['map_win_rate']), f"{summary['map_wins']} wins / {summary['games']} map games"),
              ('Round win rate', _pct(summary['round_win_rate']), f"{summary['round_wins']} wins / {summary['rounds']} rounds")])
    performance, sides = st.columns([1.3, 1], gap='large')
    with performance:
        _section('Team & map performance', 'Map outcomes for '+report['team_name'])
        _maps(report)
    with sides:
        _section('Attack / defence', 'Round wins / completed regulation rounds, 0–100% scale')
        st.html(_rate_row('Attack', report['sides']['attack']) + _rate_row('Defence', report['sides']['defence']))
        st.caption('Side totals cover regulation rounds. Overall round win rate also includes overtime.'
                   + (f" This scope contains {report['overtime_rounds']} overtime rounds." if report['overtime_rounds'] else ''))
    st.html('<div class="analysis-evidence-summary"><strong>What this scope contains</strong>'
            + f'<p>{summary["games"]} map games across {summary["matches"]} match series. Series counts include matches containing the chosen map; map and round rates use only the selected games. '
            + f'{escape(report["team_name"])} won {summary["series_wins"]} of these full series.</p></div>')
    _section('Supporting match records', 'Inspect the evidence before reading a recommendation. Scores are shown from '+report['team_name']+'’s perspective.')
    _supporting_matches(report)


def _maps_agents(report):
    total = report['summary']['games']
    st.caption('Agent pick share uses team-map games as its denominator. A five-agent composition is counted once per team per map game.')
    picks, compositions = st.columns([1.3, 1], gap='large')
    with picks:
        _section('Agent picks', f'{total} team-map games / {total*5} player-map selections')
        _table([{'Agent': a['name'], 'Selections': a['picks'], 'Team-map pick share': _pct(a['share'])} for a in report['agents']],
               rich={'Agent': ['<div class="roster-agent">' + _image(get_agent_image(a['name']), 'table-agent-image')
                      + '<span>' + escape(a['name']) + '<small>' + escape(get_agent_role(a['name'])) + '</small></span></div>'
                      for a in report['agents']]}, name='analysis_agent_picks')
        st.caption('Shares can exceed 100% when added because each team uses five agents.')
    with compositions:
        _section('Agent compositions', 'Usage is descriptive; observed wins do not prove a lineup is optimal.')
        rows = []
        for composition in report['compositions']:
            chips = ''.join('<span class="analysis-agent-chip">' + _image(get_agent_image(a), 'table-agent-image')
                            + escape(a) + '</span>' for a in composition['agents'])
            rows.append('<div class="analysis-composition-row"><div class="analysis-composition-agents">'+chips+'</div>'
                        + f'<p><strong>{composition["games"]} / {total} games ({_pct(composition["usage"])} usage)</strong><br>'
                        + f'{composition["wins"]} wins / {composition["games"]} games ({_pct(composition["win_rate"])} observed win rate)</p></div>')
        st.html(''.join(rows))
    _map_context(report)


def _map_context(report):
    """Reference-image layout: distribution, image highlights and per-map outcomes."""
    maps = report['maps']
    total = report['summary']['games']
    breakdown, highlights = st.columns([1, 1], gap='large')
    with breakdown:
        _section('Map breakdown', f'Distribution of played maps / {total} completed map games')
        ordered = sorted(maps, key=lambda m: (-m['games'], m['name']))
        maximum = max((m['games'] for m in ordered), default=1)
        st.html('<div class="analysis-map-breakdown">'+''.join(
            '<div class="analysis-map-distribution-row"><span>'+escape(m['name'])+'</span>'
            + f'<div class="analysis-map-distribution-track" aria-hidden="true"><div style="width:{m["games"]/maximum*100:.3f}%"></div></div>'
            + f'<strong>{m["games"]}<span class="sr-only"> map games</span></strong></div>' for m in ordered)+'</div>')
    with highlights:
        _section('Map highlight', 'Ranked by observed map win rate; game counts remain visible.')
        ordered = sorted(maps, key=lambda m: (-m['win_rate'], -m['games'], m['name']))
        st.html('<div class="analysis-map-highlights">'+''.join(
            '<div class="analysis-map-highlight">'+_image(get_map_image(m['name']), 'analysis-map-banner-image')
            + '<div class="analysis-map-highlight-content"><strong>'+escape(m['name'])+f' / {_pct(m["win_rate"])}</strong>'
            + f'<span>{m["wins"]}W / {m["losses"]}L · {m["games"]} '+('game' if m['games']==1 else 'games')
            + (' · Limited sample' if m['games'] <= 2 else '')+'</span></div></div>' for m in ordered)+'</div>')
    _section('Map overview', 'Map outcomes in the applied team, tournament and map scope.')
    cards = []
    for m in sorted(maps, key=lambda m: (-m['games'], m['name'])):
        wins_label = str(m['wins']) + (' win' if m['wins'] == 1 else ' wins')
        losses_label = str(m['losses']) + (' loss' if m['losses'] == 1 else ' losses')
        cards.append('<article class="analysis-map-overview"><header>'+_image(get_map_image(m['name']), 'analysis-map-banner-image')
                     + '<h3>'+escape(m['name'])+'</h3></header><dl>'
                     + f'<div><dt>Games played</dt><dd>{m["games"]}</dd></div>'
                     + f'<div><dt>Wins / losses</dt><dd><span class="analysis-map-wins">{wins_label}</span> / '
                     + f'<span class="analysis-map-losses">{losses_label}</span></dd></div>'
                     + f'<div><dt>Win rate</dt><dd>{_pct(m["win_rate"])}</dd></div></dl></article>')
    st.html('<div class="analysis-map-overview-grid">'+''.join(cards)+'</div>')


def _round_chart(report):
    """Observed match rates on a fixed scale; dates use actual elapsed spacing."""
    rows = report['trends']
    if not rows:
        return
    matches = {m['id']: m for m in report['matches']}
    width, height, left, right, top, bottom = 1000, 320, 64, 60, 38, 58
    dates = [date.fromisoformat(r['date']).toordinal() for r in rows]
    first, last = min(dates), max(dates)
    span = last-first
    baseline = height-bottom
    plot_height = baseline-top
    points = [(left+(n-first)/span*(width-left-right) if span else width/2,
               baseline-(r['rate'] or 0)/100*plot_height) for n,r in zip(dates, rows)]
    svg = '<div class="analysis-connected-chart"><svg viewBox="0 0 1000 320" role="group" aria-label="Round win rate by match">'
    svg += '<title>Round win rate by match</title><desc>Completed series on a fixed 0 to 100 percent scale. Exact match names and round counts are listed below. Select a point to open the match.</desc>'
    for value in range(0, 101, 25):
        y = baseline-value/100*plot_height
        dash = ' stroke-dasharray="5 5"' if value==50 else ''
        color = '#8290a0' if value==50 else '#e5eaf0'
        svg += f'<line x1="{left}" y1="{y}" x2="{width-right}" y2="{y}" stroke="{color}"{dash}/>'
        svg += f'<text x="{left-14}" y="{y+4}" text-anchor="end" class="chart-axis-label">{value}%</text>'
    coords = ' '.join(f'{x:.2f},{y:.2f}' for x,y in points)
    svg += f'<polyline points="{coords}" fill="none" stroke="#8290a0" stroke-width="2"/>'
    for row,(x,y) in zip(rows, points):
        match = matches[row['match_id']]
        label = ' vs '.join(match['team_names'])
        day = date.fromisoformat(row['date']).strftime('%d %b')
        aria = f'{label}, {day}, {_pct(row["rate"])}, {row["wins"]} of {row["rounds"]} rounds. Open match.'
        svg += f'<g class="analysis-chart-point" data-record="{escape(match["id"], quote=True)}" data-view="Matches" tabindex="0" role="link" aria-label="{escape(aria, quote=True)}">'
        svg += f'<circle class="chart-point-hit" cx="{x}" cy="{y}" r="16" fill="transparent"/>'
        svg += f'<circle class="chart-point-dot" cx="{x}" cy="{y}" r="6" fill="#17212d" stroke="#fff" stroke-width="2"/>'
        svg += f'<text x="{x}" y="{y-17}" text-anchor="middle" class="chart-value-label">{_pct(row["rate"])}</text>'
        svg += f'<text x="{x}" y="{baseline+28}" text-anchor="middle" class="chart-axis-label">{day}</text></g>'
    _links(svg+'</svg></div>', 'connected_chart')


def _rounds_economy(report):
    coverage = report['coverage']
    st.caption(f"Round outcomes, pistol conversions and loadout categories use the same {report['summary']['games']}-game scope.")
    if coverage['complete_maps'] < coverage['total_maps']:
        st.warning(f"Round-level records cover {coverage['complete_maps']} of {coverage['total_maps']} map games "
                   f"({coverage['recorded_rounds']} of {coverage['expected_rounds']} rounds). Missing rounds are excluded from pistol and economy denominators.")
    _section('Round win rate by match', 'Completed series, oldest to newest / selected maps / fixed 0–100% scale')
    _round_chart(report)
    trends, pistol = st.columns([1.3, 1], gap='large')
    with trends:
        _section('Match records', 'Open a matchup to inspect its map scoreboards.')
        matches = {m['id']: m for m in report['matches']}
        rows = []
        for row in report['trends']:
            match = matches[row['match_id']]
            side = match['team_ids'].index(report['team_id'])
            score = match['score']
            outcome = 'Win' if score[side] > score[1-side] else 'Loss'
            scope = report['map_name']+' only' if report['map_name'] else str(len(match['games']))+' maps'
            rows.append(f'<button type="button" class="analysis-trend-match" data-record="{escape(match["id"], quote=True)}" data-view="Matches">'
                        + '<span><strong>'+escape(' vs '.join(match['team_names']))+'</strong><small>'
                        + escape(date.fromisoformat(match['date']).strftime('%d %b %Y'))+' / '+escape(scope)+'</small></span>'
                        + f'<span class="analysis-trend-outcome"><span class="analysis-result-badge is-{outcome.lower()}">{outcome}</span>'
                        + f'<span>{score[side]}–{score[1-side]}</span><small>'+escape(report['team_name'])+' series result</small></span>'
                        + f'<span class="analysis-trend-rate"><strong>{_pct(row["rate"])}</strong><small>{row["wins"]} / {row["rounds"]} rounds</small></span></button>')
        _links('<div class="analysis-trend-matches">'+''.join(rows)+'</div>', 'trend_matches')
        st.caption('Series results are shown from '+report['team_name']+'’s perspective. Round rates use only the selected map scope.')
    with pistol:
        _section('Pistol-round analysis', 'First round of each regulation half; rounds 1 and 13.')
        _table([{'Measure': p['label'], 'Wins / opportunities': f"{p['wins']} / {p['total']}", 'Rate': _pct(p['rate'])}
                for p in report['pistol']])
        st.caption('Conversion rates use only recorded pistol rounds with a recorded following round.')
    _section('Economy analysis', 'Round wins by the team’s loadout category.')
    _table([{'Purchase category': r['category'], 'Rounds': r['rounds'], 'Rounds won': r['wins'],
             'Win rate': _pct(r['rate'])} for r in report['economy']])
    st.caption('Categories retain the dataset’s team loadout-value bands. Pistol and overtime rounds are included; loadout value is not round spending.')


def _recommendations(report):
    st.caption('These scouting suggestions describe the observed records in this scope. Review the evidence before deciding how to prepare; small samples are not reliable predictions.')
    for index, item in enumerate(report['recommendations']):
        with st.container(key=f'analysis_recommendation_{index}'):
            description, evidence = st.columns([2.6, 1], gap='large')
            with description:
                st.html(f'<div class="analysis-recommendation-text"><h2>{escape(item["title"])}</h2>'
                        + f'<p>{escape(item["body"])}</p><p class="analysis-muted">{escape(item["note"])}</p></div>')
                matches = {m['id']: m for m in report['matches']}
                links = []
                for row in item['evidence']:
                    match = matches[row['match_id']]
                    game = next(g for g in match['games'] if g['map'] == row['map'])
                    label = ' vs '.join(match['team_names']) + ' · ' + row['map']
                    links.append('<div class="analysis-evidence-match">'
                                 + _record_link(label, 'Matches', match['id'], game_id=game['id'])
                                 + '<small>'+escape(match['date'])+' / '+escape(match['tournament'])+'</small></div>')
                links = ''.join(links)
                _links('<div class="analysis-evidence-links">'+links+'</div>', f'evidence_{index}')
            with evidence:
                st.html(f'<aside class="analysis-evidence-block"><strong>{escape(item["value"])}</strong>'
                        + f'<p>{escape(item["detail"])}</p><p>Derived from the applied scope</p></aside>')


def render():
    st.title('Competitive Analysis')
    try:
        options = service.get_filters(st.session_state.get('season'))
    except service.DataServiceError:
        st.error('Scouting filters could not be loaded. Refresh to retry.')
        st.button('Retry loading filters')
        return
    if not options['seasons']:
        st.info('No seasons are available for analysis yet.')
        return
    if st.session_state.get('season') not in options['seasons']:
        st.session_state.season = options['seasons'][0]
        _season_changed()
    handoff = st.session_state.pop('analysis_handoff', None)
    if handoff:
        st.session_state.season = handoff['season'] if handoff['season'] in options['seasons'] else options['seasons'][0]
        for field, key in [('team_id', 'analysis_team'), ('tournament_id', 'analysis_tournament'), ('map_name', 'analysis_map')]:
            st.session_state[key] = handoff.get(field) or (None if field == 'team_id' else '')
        st.session_state.analysis_applied = None
        st.session_state.analysis_result = None
        st.session_state.analysis_error = False
        st.session_state.analysis_section = 'Overview'
        st.session_state.analysis_section_saved = 'Overview'
        _save_draft()
    teams = {t['id']: t['name'] for t in options['teams']}
    tournaments = {'': 'All tournaments', **{t['id']: t['name'] for t in options['tournaments']}}
    saved = st.session_state.get('analysis_draft', {})
    for field, key, valid, default in [
        ('team_id', 'analysis_team', teams, next(iter(teams), None)),
        ('tournament_id', 'analysis_tournament', tournaments, ''),
        ('map_name', 'analysis_map', ['', *options['maps']], '')]:
        if key not in st.session_state:
            st.session_state[key] = saved.get(field, default)
        if st.session_state[key] not in valid and st.session_state[key] is not None:
            st.session_state[key] = default
    heading, season = st.columns([3, 1], vertical_alignment='center')
    heading.write('Prepare an opponent brief. Follow each observation back to its evidence.')
    heading.caption('Coverage: Valorant Champions 2023. Statistics reflect this tournament.')
    with season:
        st.selectbox('Season', options['seasons'], key='season', on_change=_season_changed)
    with st.container(key='analysis_filters'):
        opponent, tournament, map_control, analyse = st.columns([1.3, 1.3, 1, 1], gap='medium')
        with opponent:
            st.selectbox('Opponent team (required)', list(teams), key='analysis_team', index=None,
                         format_func=teams.get, placeholder='Select opponent', on_change=_save_draft)
        with tournament:
            st.selectbox('Tournament', list(tournaments), key='analysis_tournament', format_func=tournaments.get, on_change=_save_draft)
        with map_control:
            st.selectbox('Map', ['', *options['maps']], key='analysis_map', format_func=lambda m: m or 'All maps', on_change=_save_draft)
        with analyse:
            with st.container(key='analyse_action'):
                st.button('Analyse Opponent', type='primary', disabled=not st.session_state.analysis_team,
                          on_click=_request_analysis, width='stretch')
    _save_draft()
    request = st.session_state.pop('analysis_pending_request', None)
    if request:
        try:
            with st.spinner('Analysing opponent…'):
                result = service.get_analysis(**request)
            st.session_state.analysis_result = result
            st.session_state.analysis_applied = request
            st.session_state.analysis_error = False
        except service.DataServiceError:
            st.session_state.analysis_error = True
            st.session_state.analysis_failed_request = request
    report = st.session_state.get('analysis_result')
    applied = st.session_state.get('analysis_applied')
    dirty = bool(applied and applied != st.session_state.analysis_draft)
    if dirty:
        st.html('<p class="analysis-pending" role="status">Filters changed. Analyse Opponent to update the results below.</p>')
    if applied and report:
        applied_name = teams.get(applied['team_id'], report['team_name'])
        tournament_label = tournaments.get(applied['tournament_id'], 'All tournaments')
        if not applied['tournament_id'] and len(options['tournaments']) == 1:
            tournament_label = options['tournaments'][0]['name']
        scope = f"{tournament_label} / Season {applied['season']} / {applied['map_name'] or 'All maps'}"
        status = 'Previous applied scope' if dirty else 'Applied results'
        st.html('<section class="analysis-applied-identity" aria-label="Applied analysis identity">'
                + _image(get_team_logo(applied['team_id']), 'analysis-opponent-logo')
                + '<div class="analysis-applied-name"><span>Applied opponent</span><h2>'+escape(applied_name)+'</h2><p>'
                + escape(scope)+'</p></div><span class="analysis-identity-status">'+status+'</span></section>')
    if 'analysis_section' not in st.session_state:
        st.session_state.analysis_section = st.session_state.get('analysis_section_saved', 'Overview')
    with st.container(key='analysis_tabs'):
        section = st.radio('Scouting section', SECTIONS, horizontal=True, key='analysis_section', label_visibility='collapsed', on_change=_remember_section)
    if st.session_state.get('analysis_error'):
        st.error('Analysis could not be loaded. Your selections are kept. Retry to load the requested scope.')
        st.button('Retry analysis', on_click=_retry)
    if not report:
        st.html('<section class="analysis-state"><h2>Ready to build your scouting brief</h2>'
                '<p>Check the prefilled opponent and season, then select Analyse Opponent. All sections will use that applied scope.</p></section>')
        return
    if not report['summary']['games']:
        st.html('<section class="analysis-state"><h2>No matching map games</h2>'
                '<p>There are no records for this opponent, tournament and map combination. Try all tournaments and all maps.</p></section>')
        st.button('Analyse a broader scope', on_click=_broaden)
        return
    {'Overview': _overview, 'Maps & Agents': _maps_agents, 'Rounds & Economy': _rounds_economy,
     'Recommendations': _recommendations}[section](report)
