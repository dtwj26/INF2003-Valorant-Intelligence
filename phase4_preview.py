
import streamlit as st
from backend.teams_players import service

st.set_page_config(
    page_title="Valorant Teams & Players",
    layout="wide"
)

st.title("Valorant Teams & Players")
st.caption("Live PostgreSQL data - Development preview")

# season filter
season = st.selectbox(
    "Season",
    [2026, 2025, 2024, 2023, 2022, 2021],
    index=1
)

options = service.get_filter_options(season)

# tournament filter
tournament_names = {
    t["id"]: t["name"]
    for t in options["tournaments"]
}

tournament_id = st.selectbox(
    "Tournament",
    [""] + list(tournament_names),
    format_func=lambda value: (
        "All tournaments"
        if not value
        else tournament_names[value]
    )
)

# map filter
map_name = st.selectbox(
    "Map",
    ["All maps"] + options["maps"]
)

selected_map = (
    None if map_name == "All maps" else map_name
)

# retrieve actual PostgreSQL data
with st.spinner("Loading records from Neon..."):
    data = service.get_teams_players_data(
        season,
        tournament_id=tournament_id or None,
        map_name=selected_map
    )

teams = data["teams"]
players = data["players"]

# data coverage
if season == 2021:
    st.warning(
        "2021 player statistics have not been imported yet."
    )
elif season == 2022:
    st.info(
        "2022 player statistics are partially imported. "
        "Unresolved records were excluded."
    )

# summary
col1, col2, col3 = st.columns(3)
col1.metric("Teams", len(teams))
col2.metric("Players", len(players))
col3.metric("Season", season)

# teams
st.subheader("Teams")

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
    use_container_width=True,
    hide_index=True
)

# players
st.subheader("Players")

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
    use_container_width=True,
    hide_index=True
)

st.caption(
    "Player statistics reflect imported records. "
    "Team wins and losses will be integrated "
    "with the Matches backend."
)
