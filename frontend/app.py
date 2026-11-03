"""Application entry point. Run: python -m streamlit run app.py"""
from pathlib import Path

import streamlit as st

from components.sidebar import render_sidebar
from views.homepage import render as render_homepage
from views.teams_players_matches import render as render_records
from views.live_teams_players import render as render_live_teams_players
from views.competitive_analysis import render as render_analysis

ROOT = Path(__file__).resolve().parent


def main():
    st.set_page_config(page_title="Valorant Competitive Intelligence System", layout="wide")
    st.html(ROOT / "styles.css")
    render_sidebar()

    if st.session_state.get('page', 'home') == 'tp_live':
        with st.container(key='live_teams_players_page'):
            render_live_teams_players()

    elif st.session_state.get('page', 'home') == 'records':

        with st.container(key='records_page'):
            render_records()
    elif st.session_state.get('page') == 'analysis':
        with st.container(key='analysis_page'):
            render_analysis()
    else:
        render_homepage()


if __name__ == "__main__":
    main()
