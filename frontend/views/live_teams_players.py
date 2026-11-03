
"""Development view for live Teams and Players data."""

import streamlit as st

from services.live_teams_players_service import get_live_records
from backend.teams_players.service import get_filter_options


def render():
    st.title("Teams & Players — Live Data")
    st.caption(
        "Development preview using Neon PostgreSQL. "
        "Match results will be integrated separately."
    )

    season = st.selectbox(
        "Season",
        [2026, 2025, 2024, 2023, 2022, 2021],
        index=1,
        key="live_tp_season"
    )

    options = get_filter_options(season)

    tournament_names = {
        "": "All tournaments"
    }

    tournament_names.update({
        t["id"]: t["name"]
        for t in options["tournaments"]
    })

    col1, col2 = st.columns(2)

    with col1:
        tournament_id = st.selectbox(
            "Tournament",
            list(tournament_names),
            format_func=lambda x: tournament_names[x],
            key="live_tp_tournament"
        )

    with col2:
        map_name = st.selectbox(
            "Map",
            [""] + options["maps"],
            format_func=lambda x: x or "All maps",
            key="live_tp_map"
        )

    with st.spinner("Loading PostgreSQL records..."):
        data = get_live_records(
            season,
            tournament_id,
            map_name
        )

    teams = data["teams"]
    players = data["players"]

    if season == 2021:
        st.warning(
            "2021 player-performance statistics "
            "have not been imported."
        )
    elif season == 2022:
        st.info(
            "2022 statistics have partial coverage. "
            "Unresolved records were excluded."
        )

    c1, c2, c3 = st.columns(3)

    c1.metric("Teams", len(teams))
    c2.metric("Players", len(players))
    c3.metric("Season", season)

    tab1, tab2 = st.tabs(["Teams", "Players"])

    with tab1:
        st.subheader("Team Directory")

        st.dataframe(
            [
                {
                    "Team": t["name"],
                    "Match Series": t["matches"],
                    "Map Games": t["games"],
                    "Recorded Players": len(t["roster"]),
                }
                for t in teams
            ],
            width="stretch",
            hide_index=True
        )

    with tab2:
        st.subheader("Player Directory")

        st.dataframe(
            [
                {
                    "Player": p["name"],
                    "Team": p["team_name"],
                    "Map Games": p["games"],
                    "Kills": p["kills"],
                    "Deaths": p["deaths"],
                    "Assists": p["assists"],
                    "Avg ACS": p["acs"],
                    "K/D": p["kd"],
                    "Most Used Agent": p["agent"],
                }
                for p in players
            ],
            width="stretch",
            hide_index=True
        )
