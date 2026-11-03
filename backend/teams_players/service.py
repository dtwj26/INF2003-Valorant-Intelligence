
"""Service layer for Teams and Players."""

from . import repository


def get_team_summaries(
    season,
    tournament_id=None,
    map_name=None
):
    """Return team participation statistics."""

    return repository.fetch_team_summaries(
        season,
        tournament_id,
        map_name
    )



def get_player_summaries(
    season,
    limit=None,
    tournament_id=None,
    map_name=None
):
    """Return player performance statistics."""

    return repository.fetch_player_summaries(
        season=season,
        limit=limit,
        tournament_id=tournament_id,
        map_name=map_name
    )



def get_player_agent_usage(
    season,
    tournament_id=None,
    map_name=None
):
    """Return player agent usage statistics."""

    return repository.fetch_player_agent_usage(
        season,
        tournament_id,
        map_name
    )



def get_player_directory(
    season,
    tournament_id=None,
    map_name=None
):
    """Return unique player profiles."""

    return repository.fetch_player_directory(
        season=season,
        tournament_id=tournament_id,
        map_name=map_name
    )


def get_player_profiles(
    season,
    tournament_id=None,
    map_name=None
):
    """Combine player statistics with agent usage."""

    players = get_player_directory(
        season,
        tournament_id,
        map_name
    )

    usage = get_player_agent_usage(
        season,
        tournament_id,
        map_name
    )

    # group agent picks by player
    usage_by_player = {}

    for row in usage:
        player_id = row["player_id"]
        agent_name = row["agent_name"]

        if player_id not in usage_by_player:
            usage_by_player[player_id] = {}

        agent_counts = usage_by_player[player_id]

        agent_counts[agent_name] = (
            agent_counts.get(agent_name, 0)
            + row["map_picks"]
        )

    # attach agent information to player profiles
    for player in players:
        agent_counts = usage_by_player.get(
            player["id"], {}
        )

        total_picks = sum(agent_counts.values())

        sorted_agents = sorted(
            agent_counts.items(),
            key=lambda item: (-item[1], item[0])
        )

        player["agents"] = [
            {
                "name": name,
                "picks": picks,
                "share": round(
                    picks / total_picks * 100, 1
                ) if total_picks else None,
            }
            for name, picks in sorted_agents
        ]

        # most frequently selected agent
        player["agent"] = (
            player["agents"][0]["name"]
            if player["agents"]

            else None
        )

        # role is not available in the current database
        player["role"] = "Not recorded"


    return players


def get_team_profiles(
    season,
    tournament_id=None,
    map_name=None
):
    """Combine team information with recorded player rosters."""

    teams = get_team_summaries(
        season,
        tournament_id,
        map_name
    )

    players = get_player_profiles(
        season,
        tournament_id,
        map_name
    )

    # group players by every team they represented
    rosters = {}

    for player in players:
        for team_id in player["team_ids"]:
            rosters.setdefault(team_id, set()).add(
                player["id"]
            )

    # prepare frontend-friendly team records
    results = []

    for team in teams:
        team_id = team["team_id"]

        results.append({
            "id": team_id,
            "name": team["team_name"],
            "matches": team["match_series"],
            "games": team["map_games"],
            "roster": sorted(rosters.get(team_id, set())),
        })

    return results



def get_teams_players_data(
    season,
    tournament_id=None,
    map_name=None
):
    """Return Teams and Players data with filter options."""

    players = get_player_profiles(
        season,
        tournament_id,
        map_name
    )

    teams = get_team_summaries(
        season,
        tournament_id,
        map_name
    )

    filters = get_filter_options(season)

    # build historical rosters
    rosters = {}

    for player in players:
        for team_id in player["team_ids"]:
            rosters.setdefault(team_id, set()).add(
                player["id"]
            )

    team_profiles = []

    for team in teams:
        team_id = team["team_id"]

        team_profiles.append({
            "id": team_id,
            "name": team["team_name"],
            "matches": team["match_series"],
            "games": team["map_games"],
            "roster": sorted(
                rosters.get(team_id, set())
            ),
        })

    return {
        "teams": team_profiles,
        "players": players,
        "tournaments": filters["tournaments"],
        "maps": filters["maps"],
    }


def get_filter_options(season):
    """Return tournament and map filter options."""

    return repository.fetch_filter_options(season)
