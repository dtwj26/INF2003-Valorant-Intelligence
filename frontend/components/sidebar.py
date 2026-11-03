"""Shared application navigation."""
import streamlit as st


def _navigate(page):
    st.session_state.page = page


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
        st.button(
            "Teams & Players (Live Test)",
            key="live_tp_nav",
            width="stretch",
            type="primary" if page == "tp_live" else "secondary",
            on_click=_navigate,
            args=("tp_live",)
        )
