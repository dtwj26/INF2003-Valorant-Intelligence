
"""PostgreSQL repository for Teams & Players."""

from contextlib import closing
from pathlib import Path

import psycopg2
from dotenv import dotenv_values
from psycopg2.extras import RealDictCursor


# project paths
ROOT = Path(__file__).resolve().parents[2]

SQL_DIR = (
    ROOT
    / "database"
    / "postgresql"
    / "queries"
    / "teams_players"
)

DEV_ENV_FILE = (
    ROOT
    / "data"
    / "local"
    / "teams_players"
    / "dev_connection.env"
)


def get_connection():
    """Connect to Neon development database."""

    if not DEV_ENV_FILE.is_file():
        raise FileNotFoundError(
            f"Development connection file missing: {DEV_ENV_FILE}"
        )

    database_url = dotenv_values(
        DEV_ENV_FILE
    ).get("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is missing from dev_connection.env"
        )

    return psycopg2.connect(
        database_url,
        connect_timeout=20
    )



def fetch_player_summaries(
    season,
    limit=None,
    tournament_id=None,
    map_name=None
):
    """Retrieve player performance statistics."""

    # no limit means retrieve all eligible players
    if limit is not None:
        limit = int(limit)

        if not 1 <= limit <= 100000:
            raise ValueError(
                "limit must be between 1 and 100000"
            )

    params = {
        "season": int(season),
        "limit": limit,
        "tournament_id": (
            str(tournament_id).strip()
            if tournament_id not in (None, "")
            else None
        ),
        "map_name": (
            str(map_name).strip()
            if map_name not in (None, "")
            else None
        ),
    }

    query = (
        SQL_DIR / "player_summaries.sql"
    ).read_text(encoding="utf-8")

    with closing(get_connection()) as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            cursor.execute(
                "SET TRANSACTION READ ONLY"
            )

            cursor.execute(query, params)
            rows = cursor.fetchall()

    return [
        {
            "player_id": str(row["player_id"]),
            "player_name": row["player_name"],
            "team_id": str(row["team_id"]),
            "team_name": row["team_name"],
            "map_games": int(row["map_games"]),
            "kills": (
                int(row["kills"])
                if row["kills"] is not None
                else None
            ),
            "deaths": (
                int(row["deaths"])
                if row["deaths"] is not None
                else None
            ),
            "assists": (
                int(row["assists"])
                if row["assists"] is not None
                else None
            ),
            "avg_acs": (
                float(row["avg_acs"])
                if row["avg_acs"] is not None
                else None
            ),
            "kd_ratio": (
                float(row["kd_ratio"])
                if row["kd_ratio"] is not None
                else None
            ),
        }
        for row in rows
    ]



def fetch_team_summaries(
    season,
    tournament_id=None,
    map_name=None
):
    """Retrieve team series and map participation counts."""

    params = {
        "season": int(season),
        "tournament_id": (
            int(tournament_id)
            if tournament_id not in (None, "")
            else None
        ),
        "map_name": (
            str(map_name).strip()
            if map_name not in (None, "")
            else None
        ),
    }

    query = (
        SQL_DIR / "team_summaries.sql"
    ).read_text(encoding="utf-8")

    with closing(get_connection()) as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            cursor.execute(
                "SET TRANSACTION READ ONLY"
            )

            cursor.execute(query, params)
            rows = cursor.fetchall()

    return [
        {
            "team_id": str(row["team_id"]),
            "team_name": row["team_name"],
            "match_series": int(row["match_series"]),
            "map_games": int(row["map_games"]),
        }
        for row in rows
    ]


def fetch_player_agent_usage(
    season,
    tournament_id=None,
    map_name=None
):
    """Retrieve player agent usage from PostgreSQL."""

    params = {
        "season": int(season),
        "tournament_id": (
            int(tournament_id)
            if tournament_id not in (None, "")
            else None
        ),
        "map_name": (
            str(map_name).strip()
            if map_name not in (None, "")
            else None
        ),
    }

    query = """
        SELECT
            p.player_id,
            p.player_name,
            t.team_id,
            t.team_name,
            ag.agent_name,
            COUNT(DISTINCT a.game_id) AS map_picks

        FROM agent_selections AS a

        JOIN players AS p
            ON p.player_id = a.player_id

        JOIN teams AS t
            ON t.team_id = a.team_id

        JOIN agents AS ag
            ON ag.agent_id = a.agent_id

        JOIN map_games AS mg
            ON mg.game_id = a.game_id

        JOIN match_series AS ms
            ON ms.match_id = mg.match_id

        WHERE ms.season = %(season)s

            AND (
                %(tournament_id)s IS NULL
                OR ms.tournament_id = %(tournament_id)s
            )

            AND (
                %(map_name)s IS NULL
                OR mg.map_name = %(map_name)s
            )

        GROUP BY
            p.player_id,
            p.player_name,
            t.team_id,
            t.team_name,
            ag.agent_id,
            ag.agent_name

        ORDER BY
            map_picks DESC,
            p.player_name,
            t.team_name,
            ag.agent_name;
    """

    with closing(get_connection()) as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            cursor.execute(
                "SET TRANSACTION READ ONLY"
            )

            cursor.execute(query, params)
            rows = cursor.fetchall()

    return [
        {
            "player_id": str(row["player_id"]),
            "player_name": row["player_name"],
            "team_id": str(row["team_id"]),
            "team_name": row["team_name"],
            "agent_name": row["agent_name"],
            "map_picks": int(row["map_picks"]),
        }
        for row in rows
    ]


def fetch_player_directory(
    season,
    tournament_id=None,
    map_name=None
):
    """Retrieve unique player profiles across teams."""

    params = {
        "season": int(season),
        "tournament_id": (
            str(tournament_id).strip()
            if tournament_id not in (None, "")
            else None
        ),
        "map_name": (
            str(map_name).strip()
            if map_name not in (None, "")
            else None
        ),
    }

    query = (
        SQL_DIR / "player_directory.sql"
    ).read_text(encoding="utf-8")

    with closing(get_connection()) as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(query, params)
            rows = cursor.fetchall()

    return [
        {
            "id": str(row["player_id"]),
            "name": row["player_name"],
            "team": str(row["team_id"]),
            "team_name": row["team_name"],
            "team_ids": [
                str(team_id)
                for team_id in row["team_ids"]
            ],
            "games": int(row["map_games"]),
            "kills": (
                int(row["kills"])
                if row["kills"] is not None
                else None
            ),
            "deaths": (
                int(row["deaths"])
                if row["deaths"] is not None
                else None
            ),
            "assists": (
                int(row["assists"])
                if row["assists"] is not None
                else None
            ),
            "acs": (
                float(row["avg_acs"])
                if row["avg_acs"] is not None
                else None
            ),
            "kd": (
                float(row["kd_ratio"])
                if row["kd_ratio"] is not None
                else None
            ),
        }
        for row in rows
    ]


def fetch_filter_options(season):
    """Retrieve tournament and map options for a season."""

    season = int(season)

    with closing(get_connection()) as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            cursor.execute("SET TRANSACTION READ ONLY")

            # tournaments available in the selected season
            cursor.execute("""
                SELECT DISTINCT
                    t.tournament_id,
                    t.tournament_name
                FROM tournaments t
                JOIN match_series ms
                    ON ms.tournament_id = t.tournament_id
                WHERE ms.season = %s
                ORDER BY t.tournament_name, t.tournament_id
            """, (season,))

            tournaments = [
                {
                    "id": str(row["tournament_id"]),
                    "name": row["tournament_name"],
                }
                for row in cursor.fetchall()
            ]

            # maps available in the selected season
            cursor.execute("""
                SELECT DISTINCT mg.map_name
                FROM map_games mg
                JOIN match_series ms
                    ON ms.match_id = mg.match_id
                WHERE ms.season = %s
                  AND mg.map_name IS NOT NULL
                ORDER BY mg.map_name
            """, (season,))

            maps = [
                row["map_name"]
                for row in cursor.fetchall()
            ]

    return {
        "tournaments": tournaments,
        "maps": maps,
    }
