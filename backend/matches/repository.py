"""Read match results from PostgreSQL using the shared core tables."""

import os
from contextlib import closing
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor


ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = ROOT / "database/postgresql/queries/matches"
load_dotenv(dotenv_path=ROOT / ".env")


def get_connection():
    """Open a read-only connection to the existing Neon database."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is missing from the .env file.")
    conn = psycopg2.connect(database_url, connect_timeout=20)
    conn.set_session(readonly=True)
    return conn


def load_query(filename):
    """Read a query from the Matches SQL folder."""
    return (SQL_DIR / filename).read_text(encoding="utf-8")


def fetch_seasons():
    """Return seasons that have imported match scores."""
    query = """
        SELECT DISTINCT m.season
        FROM match_series m
        JOIN match_scores s ON s.match_id = m.match_id
        ORDER BY m.season DESC;
    """
    with closing(get_connection()) as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)
            return [int(row[0]) for row in cursor.fetchall()]


def fetch_matches(season, tournament_id="", map_name=""):
    """Return match results, optionally filtered by tournament or map.

    Map filters select series containing that map; scores remain the full
    series result. IDs are strings to match the existing frontend format.
    """
    parameters = {
        "season": int(season),
        "tournament_id": int(tournament_id) if tournament_id else None,
        "map_name": map_name or None,
    }
    query = load_query("match_series.sql")
    with closing(get_connection()) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, parameters)
            return [dict(row) for row in cursor.fetchall()]
        
def fetch_match_games(match_id):

    parameters = {
        "match_id": int(match_id)
    }
    query = load_query("match_games.sql")
    with closing(get_connection()) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, parameters)
            return [dict(row) for row in cursor.fetchall()]

def fetch_player_scoreboard(game_id):
    parameters = {
        "game_id": int(game_id)
    }
    query = load_query("players_scoreboards.sql")
    with closing(get_connection()) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, parameters)
            return [dict(row) for row in cursor.fetchall()]
