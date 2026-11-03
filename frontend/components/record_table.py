"""Shared broadcast tables and record links used by browsing and scouting."""
from functools import partial
from html import escape
import streamlit as st
import streamlit.components.v2 as components

def _open(view, record_id, game_id=None):
    st.session_state.page = 'records'
    st.session_state.record_view = view
    st.session_state.record_view_saved = view
    st.session_state.records_detail = record_id
    if game_id is not None:
        st.session_state[f'map_game_{record_id}'] = game_id
    st.session_state.records_revision = st.session_state.get('records_revision', 0) + 1



_RECORD_TABLE = components.component(
    'record_rows',
    html='<div class="vci-record-table-root"></div>',
    isolate_styles=False,
    js="""export default function(component) {
        const {data, parentElement, setTriggerValue} = component;
        const root = parentElement.querySelector('.vci-record-table-root');
        root.innerHTML = data.html;
        const open = event => {
            const row = event.target.closest('[data-record]');
            if (!row) return;
            event.preventDefault();
            setTriggerValue('open', {view: row.dataset.view, id: row.dataset.record, game: row.dataset.game || null});
        };
        root.onclick = open;
        root.onkeydown = event => {
            if (event.target.matches('[data-record]:not(button)') && (event.key === 'Enter' || event.key === ' ')) open(event);
        };
        return () => { root.onclick = null; root.onkeydown = null; };
    }
    """,
)



def _table_open(key):
    record = st.session_state[key].get('open')
    if record:
        _open(record['view'], record['id'], record.get('game'))



def _record_link(text, view, record_id, game_id=None):
    game_attribute = f' data-game="{escape(str(game_id), quote=True)}"' if game_id is not None else ''
    return (f'<button class="record-link" type="button" data-record="{escape(str(record_id), quote=True)}" '
            f'data-view="{escape(view, quote=True)}"{game_attribute}>{escape(str(text))}</button>')



def _image(filename, css_class):
    if not filename:
        return ''
    return f'<img class="{css_class}" src="app/static/{escape(filename, quote=True)}" alt="">'



def _section(title, note=''):
    st.html(f'<div class="section-heading records-section"><h2>{escape(title)}</h2>'
            f'<p>{escape(note)}</p></div>')



def _metrics(items):
    st.html('<dl class="coverage-strip">' + ''.join(
        f'<div class="metric"><dt>{escape(label)}</dt><dd>{escape(str(value if value is not None else '—'))}</dd>'
        f'<p>{escape(note)}</p></div>' for label, value, note in items) + '</dl>')



def _pct(value):
    return f'{value:.1f}%' if value is not None else '—'



def _table(rows, ids=None, view=None, name='records', rich=None, action=True):
    if not rows:
        st.info('No records are available in this scope.')
        return
    rich = rich or {}
    headers = list(rows[0])
    content = '<div class="record-table-wrap"><table class="record-table">'
    caption = {'browse_teams': 'Team records', 'browse_players': 'Individual performance', 'browse_matches': 'Match series'}.get(name)
    if caption:
        content += f'<caption>{caption} / Valorant Champions 2023</caption>'
    content += '<thead><tr>'
    for label in headers:    
        team_stat = (
            (
                view == "Teams"
                and label in ("Match series", "Map games", "Recorded players")
            )
            or (
                view == "Players"
                and label in ("Map games", "Avg. ACS", "K/D")
            )
        )
        align = ' style="text-align: center !important;"' if team_stat else ""
        content += f'<th scope="col"{align}>{escape(label)}</th>'

    if ids is not None and action:
        content += '<th scope="col">' + ('Details' if view == 'Matches' else 'Profile') + '</th>'
    content += '</tr></thead><tbody>'
    for index, row in enumerate(rows):
        attrs = (f' data-record="{escape(str(ids[index]), quote=True)}" data-view="{view}" tabindex="0"'
                 if ids is not None else '')
        content += f'<tr{attrs}>'
        for label, value in row.items():
            cell = rich[label][index] if label in rich else escape(str(value if value is not None else '—'))
            numeric = isinstance(value, (int, float)) or label in ('K/D', 'Win rate', 'Score', 'Series score', 'Result')
                
            team_stat = (
                (
                    view == "Teams"
                    and label in ("Match series", "Map games", "Recorded players")
                )
                or (
                    view == "Players"
                    and label in ("Map games", "Avg. ACS", "K/D")
                )
            )

            cell_class = "" if team_stat else ("numeric" if numeric else "")
            cell_style = ' style="text-align: center !important;"' if team_stat else ""
            content += f'<td class="{cell_class}"{cell_style}>{cell}</td>'


        if ids is not None and action:
            action_label = {'Teams': 'View team', 'Players': 'View player', 'Matches': 'View match'}[view]
            content += '<td>' + _record_link(action_label, view, ids[index]) + '</td>'
        content += '</tr>'
    content += '</tbody></table></div>'
    if ids is None and not rich:
        st.html(content)
    else:
        key = f'{name}_{st.session_state.get("records_revision", 0)}'
        _RECORD_TABLE(data={'html': content}, key=key, on_open_change=partial(_table_open, key))

