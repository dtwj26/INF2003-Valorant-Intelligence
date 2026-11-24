"""Shared application navigation."""
import streamlit as st


def _reset_page_state(page):
    """Clear sub-views, open detail screens, filters, and transient UI flags for the target tab."""
    if page == 'home':
        st.session_state.pop('opponent', None)
        st.session_state.pop('scouting_context', None)
        st.session_state.pop('season', None)
    elif page == 'records':
        st.session_state.pop('season', None)
        st.session_state.record_view = 'Teams'
        st.session_state.record_view_saved = 'Teams'
        st.session_state.records_detail = None
        st.session_state.records_preferences = {}
        st.session_state.records_revision = st.session_state.get('records_revision', 0) + 1
        for key in list(st.session_state):
            if key.startswith(('_records_', 'live_records_search_', 'live_page_', 'live_team_', 'live_player_')):
                del st.session_state[key]
    elif page == 'analysis':
        st.session_state.pop('season', None)
        st.session_state.analysis_applied = None
        st.session_state.analysis_result = None
        st.session_state.analysis_error = False
        st.session_state.analysis_section = 'Overview'
        st.session_state.analysis_section_saved = 'Overview'
        st.session_state.pop('analysis_draft', None)
        st.session_state.pop('analysis_team', None)
        st.session_state.pop('analysis_tournament', None)
        st.session_state.pop('analysis_map', None)
    elif page == 'forums':
        st.session_state.forum_selected_post_id = None
        st.session_state.forum_show_create = False
        st.session_state.forum_editing_post = False
        st.session_state.forum_editing_comment_id = None
        st.session_state.forum_confirm_delete_post = False
        st.session_state.forum_search_input = ''
        st.session_state.forum_applied_search = ''
        st.session_state.forum_filter_category = ''
        st.session_state.forum_sort = 'Newest first'
        st.session_state.forum_page = 1


def _navigate(page):
    st.session_state.page = page
    st.session_state.nav_revision = st.session_state.get('nav_revision', 0) + 1
    _reset_page_state(page)


def open_analysis(team_id, season, tournament_id=''):
    st.session_state.analysis_handoff = dict(team_id=team_id, season=season, tournament_id=tournament_id, map_name='')
    st.session_state.page = 'analysis'


def render_sidebar():
    page = st.session_state.get('page', 'home')
    with st.sidebar:
        st.html('<div class="brand"><div class="project-mark">VCI</div>'
                '<p>Valorant Competitive<br>Intelligence System</p></div>')
        st.button('Homepage', key='home_nav', width='stretch',
                  type='primary' if page == 'home' else 'secondary', on_click=_navigate, args=('home',))
        st.button('Teams / Players / Matches', key='records_nav', width='stretch',
                  type='primary' if page == 'records' else 'secondary', on_click=_navigate, args=('records',))
        st.button('Competitive Analysis', key='analysis_nav', width='stretch',
                  type='primary' if page == 'analysis' else 'secondary', on_click=_navigate, args=('analysis',))
        st.button('Forums', key='forums_nav', width='stretch',
                  type='primary' if page == 'forums' else 'secondary', on_click=_navigate, args=('forums',))