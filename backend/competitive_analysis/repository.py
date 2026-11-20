"""PostgreSQL + MongoDB repository for Competitive Analysis."""

import os
from contextlib import closing
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=ROOT / ".env")


def get_pg_connection():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is missing from .env")
    conn = psycopg2.connect(database_url, connect_timeout=20)
    conn.set_session(readonly=True)
    return conn


def get_mongo_collection():
    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        raise RuntimeError("MONGODB_URI is missing from .env")
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10000)
    return client, client["valorant_intelligence"]["team_game_rounds"]


def fetch_filter_options(season=None):
    with closing(get_pg_connection()) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT DISTINCT season FROM match_series ORDER BY season DESC;")
            seasons = [int(r["season"]) for r in cur.fetchall()]
            if not seasons:
                return {"seasons": [], "teams": [], "tournaments": [], "maps": []}

            selected = int(season) if season in seasons else seasons[0]

            cur.execute("""
                SELECT DISTINCT t.team_id::TEXT AS id, t.team_name AS name
                FROM teams t
                JOIN match_participants mp ON mp.team_id = t.team_id
                JOIN match_series ms ON ms.match_id = mp.match_id
                WHERE ms.season = %s
                ORDER BY t.team_name;
            """, (selected,))
            teams = [dict(r) for r in cur.fetchall()]

            cur.execute("""
                SELECT DISTINCT tr.tournament_id::TEXT AS id, tr.tournament_name AS name
                FROM tournaments tr
                JOIN match_series ms ON ms.tournament_id = tr.tournament_id
                WHERE ms.season = %s
                ORDER BY tr.tournament_name;
            """, (selected,))
            tournaments = [dict(r) for r in cur.fetchall()]

            cur.execute("""
                SELECT DISTINCT mg.map_name
                FROM map_games mg
                JOIN match_series ms ON ms.match_id = mg.match_id
                WHERE ms.season = %s AND mg.map_name IS NOT NULL
                ORDER BY mg.map_name;
            """, (selected,))
            maps = [r["map_name"] for r in cur.fetchall()]

    return {
        "seasons": seasons,
        "teams": teams,
        "tournaments": tournaments,
        "maps": maps,
    }


def fetch_team_games_pg(team_id, season, tournament_id="", map_name=""):
    """Fetch team matches, map scores, and 5-agent compositions from PostgreSQL."""
    params = {
        "team_id": int(team_id),
        "season": int(season),
        "tournament_id": int(tournament_id) if tournament_id else None,
        "map_name": map_name or None,
    }
    with closing(get_pg_connection()) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    ms.match_id::TEXT AS match_id,
                    ms.season,
                    ms.tournament_id::TEXT AS tournament_id,
                    tr.tournament_name AS tournament,
                    pa.team_id::TEXT AS team_a_id,
                    ta.team_name AS team_a_name,
                    pb.team_id::TEXT AS team_b_id,
                    tb.team_name AS team_b_name,
                    COALESCE(msc.team_a_score, 0) AS series_a_score,
                    COALESCE(msc.team_b_score, 0) AS series_b_score,
                    mg.game_id,
                    mg.map_name,
                    gs.team_a_score AS map_a_score,
                    gs.team_b_score AS map_b_score
                FROM match_series ms
                JOIN tournaments tr ON tr.tournament_id = ms.tournament_id
                JOIN match_participants pa ON pa.match_id = ms.match_id AND pa.team_slot = 'A'
                JOIN match_participants pb ON pb.match_id = ms.match_id AND pb.team_slot = 'B'
                JOIN teams ta ON ta.team_id = pa.team_id
                JOIN teams tb ON tb.team_id = pb.team_id
                LEFT JOIN match_scores msc ON msc.match_id = ms.match_id
                JOIN map_games mg ON mg.match_id = ms.match_id
                JOIN map_scores gs ON gs.game_id = mg.game_id
                WHERE ms.season = %(season)s
                  AND (pa.team_id = %(team_id)s OR pb.team_id = %(team_id)s)
                  AND (%(tournament_id)s::BIGINT IS NULL OR ms.tournament_id = %(tournament_id)s)
                  AND (%(map_name)s::TEXT IS NULL OR mg.map_name = %(map_name)s)
                ORDER BY ms.match_id DESC, mg.game_id ASC;
            """, params)
            game_rows = [dict(r) for r in cur.fetchall()]

            if not game_rows:
                return []

            game_ids = [r["game_id"] for r in game_rows]
            cur.execute("""
                SELECT s.game_id, a.agent_name
                FROM agent_selections s
                JOIN agents a ON a.agent_id = s.agent_id
                WHERE s.team_id = %s AND s.game_id = ANY(%s);
            """, (int(team_id), game_ids))

            agents_by_game = {}
            for r in cur.fetchall():
                agents_by_game.setdefault(r["game_id"], []).append(r["agent_name"])

            for r in game_rows:
                r["agents"] = sorted(agents_by_game.get(r["game_id"], []))

    return game_rows


def fetch_round_docs_mongo(team_id, season, game_ids):
    """Fetch round-by-round outcomes and economy from MongoDB team_game_rounds."""
    if not game_ids:
        return {}
    client, collection = get_mongo_collection()
    try:
        cursor = collection.find(
            {
                "season": int(season),
                "team_id": int(team_id),
                "game_id": {"$in": [int(gid) for gid in game_ids]},
            },
            {"_id": 0, "game_id": 1, "rounds": 1, "coverage": 1},
        )
        return {doc["game_id"]: doc for doc in cursor}
    finally:
        client.close()