"""Homepage layout. Backend integration lives in services/homepage_service.py."""
from html import escape
from pathlib import Path
import streamlit as st
from services import homepage_service, competitive_analysis_service
from components.sidebar import open_analysis
from components.asset_catalog import get_agent_image, get_agent_role, get_map_image

ROOT = Path(__file__).resolve().parents[1]

def html(text):
    st.html(text)


def reset_season():
    st.session_state.pop("opponent", None)
    st.session_state.pop("scouting_context", None)


def change_season(year):
    st.session_state.season = year
    reset_season()


def asset_image(filename, class_name):
    if filename and (ROOT / "static" / filename).is_file():
        return f'<img class="{class_name}" src="app/static/{escape(filename, quote=True)}" alt="">'
    return f'<span class="{class_name}" aria-hidden="true"></span>'


def render():
    """Render the homepage using its two service calls."""
    st.title("Valorant Competitive Intelligence System")

    # BACKEND CALL 1: season-selector options.
    try:
        seasons = homepage_service.get_seasons()
    except homepage_service.DataServiceError:
        st.error("Season data could not be loaded. Please retry.")
        if st.button("Retry loading", type="primary"):
            st.rerun()
        st.stop()

    if not seasons:
        st.info("No seasons are available yet. Try again after season records have been added.")
        if st.button("Refresh seasons"):
            st.rerun()
        st.stop()

    if st.session_state.get("season") not in seasons:
        reset_season()
        st.session_state.season = seasons[0]

    with st.container(key="heading"):
        title, season_control = st.columns([3, 1], vertical_alignment="center")
        with title:
            st.write("Explore the season. Find the context for your next matchup.")
        with season_control:
            st.selectbox("Season", seasons, key="season", on_change=reset_season,
                         format_func=str,
                         help="Choose the season to explore.")

    season = st.session_state.season

    # BACKEND CALL 2: one snapshot for every homepage section.
    try:
        with st.spinner("Loading season statistics…"):
            snapshot = homepage_service.get_homepage_data(season)
    except homepage_service.DataServiceError:
        st.error("Season statistics could not be loaded. Please retry. Your season is kept.")
        if st.button("Retry loading", type="primary"):
            st.rerun()
        st.stop()

    summary = snapshot["summary"]
    html('<dl class="coverage-strip" aria-label="Season statistics">' + "".join(
        f'<div class="metric"><dt>{label}</dt><dd>{summary[key]:,}</dd><p>{note}</p></div>'
        for key, label, note in [
            ("tournaments", "Tournaments", "Distinct events"),
            ("matches", "Matches", "Match series, not maps"),
            ("teams", "Teams", "Distinct participants"),
        ]
    ) + '</dl>')

    if not summary["matches"]:
        st.info(f"No records for {season}. Choose another season to continue.")
        other_seasons = [year for year in seasons if year != season]
        if other_seasons:
            year = other_seasons[0]
            st.button(f"View {year} season", on_click=change_season, args=(year,))
    else:
        with st.container(key="patterns"):
            map_column, agent_column = st.columns([1.45, 1], gap="large")
            with map_column:
                html('<div class="section-heading"><h2>Most played maps</h2>'
                     '<p>Completed map games</p></div>')
                top_maps = snapshot["maps"][:5]
                maximum = max((row["games"] for row in top_maps), default=1) or 1
                rows = []
                for row in top_maps:
                    rows.append(
                        '<li class="map-row"><div class="map-identity">'
                        + asset_image(get_map_image(row["name"]), "map-image")
                        + f'<span>{escape(row["name"])}</span></div>'
                        + f'<div class="bar-track" aria-hidden="true"><div class="bar-fill" '
                        + f'style="width:{row["games"] / maximum * 100:.3f}%"></div></div>'
                        + f'<span class="map-value">{row["games"]}<span class="sr-only"> map games</span></span></li>'
                    )
                html('<ul class="map-list" aria-label="Map games, descending">' + "".join(rows) + '</ul>')
                if not top_maps:
                    st.info("No map statistics are available for this season.")
                st.caption("Each map game is counted once across both teams. Top five shown.")
            with agent_column:
                html('<div class="section-heading"><h2>Most picked agents</h2>'
                     '<p>Player-map selections</p></div>')
                rows = []
                for row in snapshot["agents"][:5]:
                    rows.append(
                        '<li class="agent-row">' + asset_image(get_agent_image(row["name"]), "agent-image")
                        + f'<div><strong>{escape(row["name"])}</strong>'
                        + f'<span class="agent-role">{escape(get_agent_role(row["name"]))}</span></div>'
                        + f'<span class="agent-value">{row["picks"]:,}<small>picks</small></span></li>'
                    )
                html('<ul class="agent-list" aria-label="Agent picks, descending">' + "".join(rows) + '</ul>')
                if not snapshot["agents"]:
                    st.info("No agent statistics are available for this season.")
                st.caption("One selection per player per map game. Top five shown.")

    with st.container(key="scout"):
        text, controls = st.columns([1, 1.2], gap="large", vertical_alignment="center")
        with text:
            st.subheader("Prepare for an opponent")
            st.write("Take this season into Competitive Analysis. Start with the team you want to understand.")
        with controls:
            try:
                scouting = competitive_analysis_service.get_filters(season)
                teams = {team["id"]: team["name"] for team in scouting["teams"]} if season in scouting["seasons"] else {}
            except competitive_analysis_service.DataServiceError:
                teams = {}
                st.error("Scouting teams could not be loaded. Please refresh to retry.")
            if st.session_state.get("opponent") not in teams:
                st.session_state.pop("opponent", None)
                st.session_state.pop("scouting_context", None)
            st.selectbox("Opponent team (required)", list(teams), index=None, key="opponent",
                         format_func=lambda team_id: teams[team_id], placeholder="Select a team",
                         disabled=not teams,
                         help="Choose an opponent to open Competitive Analysis.")
            chosen = st.session_state.get("opponent")
            st.button("Start scouting", type="primary", disabled=chosen is None, width="stretch",
                      on_click=open_analysis, args=(chosen, season))

    st.caption(f"Season {season} / All tournaments")
