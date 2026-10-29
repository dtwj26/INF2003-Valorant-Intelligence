"""PostgreSQL repository for the Valorant Homepage."""

import os
from pathlib import Path
from contextlib import closing

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv


# Locate the project root
ROOT = Path(__file__).resolve().parents[2]

# Locate our SQL files
SQL_DIR = (
    ROOT
    / "database"
    / "postgresql"
    / "queries"
    / "homepage"
)

# Load Neon credentials from .env
load_dotenv(dotenv_path=ROOT / ".env")


def get_connection():
    """Create a connection to Neon PostgreSQL."""

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is missing from the .env file."
        )

    return psycopg2.connect(
        database_url,
        connect_timeout=20
    )


def load_query(filename):
    """Read an SQL query from the homepage folder."""

    filepath = SQL_DIR / filename

    return filepath.read_text(encoding="utf-8")


def fetch_seasons():
    """Retrieve all available VCT seasons."""

    query = """
        SELECT DISTINCT season
        FROM match_series
        ORDER BY season DESC;
    """

    with closing(get_connection()) as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

    return [int(row[0]) for row in rows]


def fetch_homepage_data(season):
    """Retrieve homepage statistics for a selected season."""

    season = int(season)

    query_files = {
        "summary": "summary.sql",
        "maps": "top_maps.sql",
        "agents": "top_agents.sql",
        "teams": "teams.sql",
    }

    results = {}

    with closing(get_connection()) as conn:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            for section, filename in query_files.items():
                sql = load_query(filename)

                # Safely pass the selected season to PostgreSQL
                cursor.execute(sql, {"season": season})

                results[section] = [
                    dict(row) for row in cursor.fetchall()
                ]

    # Extract summary counts
    summary_row = (
        results["summary"][0]
        if results["summary"]
        else {}
    )

    summary = {
        "tournaments": int(
            summary_row.get("tournaments", 0)
        ),
        "matches": int(
            summary_row.get("matches", 0)
        ),
        "teams": int(
            summary_row.get("teams", 0)
        ),
    }

    return {
        "summary": summary,

        "maps": [
            {
                "name": row["name"],
                "games": int(row["games"]),
            }
            for row in results["maps"]
        ],

        "agents": [
            {
                "name": row["name"],
                "picks": int(row["picks"]),
            }
            for row in results["agents"]
        ],

        "teams": [
            {
                "id": row["id"],
                "name": row["name"],
            }
            for row in results["teams"]
        ],
    }
