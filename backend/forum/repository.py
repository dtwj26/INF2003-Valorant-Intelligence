"""PostgreSQL + MongoDB repository for the Forums feature."""

import os
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=ROOT / ".env")

CATEGORIES = (
    "Matchup Discussion",
    "Tactical Breakdown",
    "Scouting Brief",
    "Agent & Map Meta",
    "General",
)

_MONGO_INDEX_READY = False
_UNSET = object()


def get_pg_connection(readonly=False):
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is missing from .env")
    conn = psycopg2.connect(database_url, connect_timeout=20)
    if readonly:
        conn.set_session(readonly=True)
    return conn


def get_mongo_collection():
    global _MONGO_INDEX_READY
    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        raise RuntimeError("MONGODB_URI is missing from .env")
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10000)
    collection = client["valorant_intelligence"]["forum_threads"]
    if not _MONGO_INDEX_READY:
        collection.create_index([("post_id", 1)], unique=True, name="uq_forum_post_id")
        collection.create_index([("tags", 1)], name="idx_forum_tags")
        _MONGO_INDEX_READY = True
    return client, collection


def _utc_now():
    return datetime.now(timezone.utc)


def _normalize_tags(tags):
    cleaned = []
    seen = set()
    for raw in tags or []:
        tag = " ".join(str(raw).strip().lower().split())
        if tag and tag not in seen:
            seen.add(tag)
            cleaned.append(tag)
    return cleaned


# ---------------------------------------------------------------------------
# PostgreSQL + MongoDB CRUD: Posts
# ---------------------------------------------------------------------------

def count_posts():
    with closing(get_pg_connection(readonly=True)) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM forum_posts;")
            return int(cur.fetchone()[0])


def fetch_all_posts():
    """Fetch all forum posts from PostgreSQL merged with tags/comments from MongoDB."""
    with closing(get_pg_connection(readonly=True)) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    fp.post_id,
                    fp.title,
                    fp.category,
                    fp.author_name,
                    fp.body,
                    fp.season,
                    fp.team_id::TEXT AS team_id,
                    t.team_name,
                    fp.match_id::TEXT AS match_id,
                    ms.match_name,
                    tr.tournament_name AS match_tournament,
                    fp.map_name,
                    fp.agent_name,
                    fp.created_at,
                    fp.updated_at
                FROM forum_posts fp
                LEFT JOIN teams t ON t.team_id = fp.team_id
                LEFT JOIN match_series ms ON ms.match_id = fp.match_id
                LEFT JOIN tournaments tr ON tr.tournament_id = ms.tournament_id
                ORDER BY fp.created_at DESC, fp.post_id DESC;
                """
            )
            pg_rows = [dict(r) for r in cur.fetchall()]

    if not pg_rows:
        return []

    post_ids = [int(r["post_id"]) for r in pg_rows]
    client, collection = get_mongo_collection()
    try:
        mongo_docs = {
            int(doc["post_id"]): doc
            for doc in collection.find(
                {"post_id": {"$in": post_ids}},
                {"_id": 0, "post_id": 1, "tags": 1, "comments": 1},
            )
        }
    finally:
        client.close()

    merged = []
    for row in pg_rows:
        pid = int(row["post_id"])
        doc = mongo_docs.get(pid, {})
        comments = doc.get("comments") or []
        merged.append(
            {
                **row,
                "post_id": pid,
                "tags": doc.get("tags") or [],
                "comments": comments,
                "comment_count": len(comments),
            }
        )
    return merged


def fetch_post_by_id(post_id):
    """Fetch one post from PostgreSQL merged with its MongoDB companion document."""
    pid = int(post_id)
    with closing(get_pg_connection(readonly=True)) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    fp.post_id,
                    fp.title,
                    fp.category,
                    fp.author_name,
                    fp.body,
                    fp.season,
                    fp.team_id::TEXT AS team_id,
                    t.team_name,
                    fp.match_id::TEXT AS match_id,
                    ms.match_name,
                    tr.tournament_name AS match_tournament,
                    fp.map_name,
                    fp.agent_name,
                    fp.created_at,
                    fp.updated_at
                FROM forum_posts fp
                LEFT JOIN teams t ON t.team_id = fp.team_id
                LEFT JOIN match_series ms ON ms.match_id = fp.match_id
                LEFT JOIN tournaments tr ON tr.tournament_id = ms.tournament_id
                WHERE fp.post_id = %s;
                """,
                (pid,),
            )
            row = cur.fetchone()

    if not row:
        return None

    post = dict(row)
    post["post_id"] = int(post["post_id"])

    client, collection = get_mongo_collection()
    try:
        doc = collection.find_one(
            {"post_id": pid},
            {"_id": 0, "post_id": 1, "tags": 1, "comments": 1},
        ) or {}
    finally:
        client.close()

    comments = doc.get("comments") or []
    post["tags"] = doc.get("tags") or []
    post["comments"] = comments
    post["comment_count"] = len(comments)
    return post


def create_post(
    title,
    category,
    author_name,
    body,
    tags=None,
    season=None,
    team_id=None,
    match_id=None,
    map_name=None,
    agent_name=None,
    initial_comments=None,
):
    """Insert post metadata into PostgreSQL and companion thread doc into MongoDB."""
    clean_tags = _normalize_tags(tags)
    now = _utc_now()
    comments_payload = []
    for item in initial_comments or []:
        c_time = item.get("created_at") or now
        comments_payload.append(
            {
                "comment_id": item.get("comment_id") or str(uuid.uuid4()),
                "author_name": str(item["author_name"]).strip(),
                "body": str(item["body"]).strip(),
                "created_at": c_time,
                "updated_at": item.get("updated_at") or c_time,
            }
        )

    with closing(get_pg_connection(readonly=False)) as conn:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO forum_posts (
                        title, category, author_name, body,
                        season, team_id, match_id, map_name, agent_name
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING post_id;
                    """,
                    (
                        title.strip(),
                        category,
                        author_name.strip(),
                        body.strip(),
                        int(season) if season not in (None, "") else None,
                        int(team_id) if team_id not in (None, "") else None,
                        int(match_id) if match_id not in (None, "") else None,
                        map_name.strip() if map_name else None,
                        agent_name.strip() if agent_name else None,
                    ),
                )
                post_id = int(cur.fetchone()[0])

            # Insert into MongoDB before PG commits so any Mongo error rolls back PG
            client, collection = get_mongo_collection()
            try:
                collection.insert_one(
                    {
                        "post_id": post_id,
                        "tags": clean_tags,
                        "comments": comments_payload,
                    }
                )
            finally:
                client.close()

    return post_id


def update_post(
    post_id,
    title,
    category,
    author_name,
    body,
    tags=None,
    season=_UNSET,
    team_id=_UNSET,
    match_id=_UNSET,
    map_name=_UNSET,
    agent_name=_UNSET,
):
    """Update post row in PostgreSQL and tags array in MongoDB."""
    pid = int(post_id)
    clean_tags = _normalize_tags(tags)

    set_clauses = [
        "title = %s",
        "category = %s",
        "author_name = %s",
        "body = %s",
    ]
    values = [
        title.strip(),
        category,
        author_name.strip(),
        body.strip(),
    ]

    if season is not _UNSET:
        set_clauses.append("season = %s")
        values.append(int(season) if season not in (None, "") else None)
    if team_id is not _UNSET:
        set_clauses.append("team_id = %s")
        values.append(int(team_id) if team_id not in (None, "") else None)
    if match_id is not _UNSET:
        set_clauses.append("match_id = %s")
        values.append(int(match_id) if match_id not in (None, "") else None)
    if map_name is not _UNSET:
        set_clauses.append("map_name = %s")
        values.append(map_name.strip() if map_name else None)
    if agent_name is not _UNSET:
        set_clauses.append("agent_name = %s")
        values.append(agent_name.strip() if agent_name else None)

    set_clauses.append("updated_at = NOW()")
    values.append(pid)

    with closing(get_pg_connection(readonly=False)) as conn:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE forum_posts SET {', '.join(set_clauses)} WHERE post_id = %s;",
                    tuple(values),
                )
                if cur.rowcount == 0:
                    raise ValueError(f"Post #{pid} was not found.")

            client, collection = get_mongo_collection()
            try:
                collection.update_one(
                    {"post_id": pid},
                    {
                        "$set": {"tags": clean_tags},
                        "$setOnInsert": {"comments": []},
                    },
                    upsert=True,
                )
            finally:
                client.close()


def delete_post(post_id):
    """Delete post from both PostgreSQL and MongoDB."""
    pid = int(post_id)
    with closing(get_pg_connection(readonly=False)) as conn:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM forum_posts WHERE post_id = %s;", (pid,))

            client, collection = get_mongo_collection()
            try:
                collection.delete_one({"post_id": pid})
            finally:
                client.close()


# ---------------------------------------------------------------------------
# MongoDB CRUD: Flat Embedded Comments
# ---------------------------------------------------------------------------

def add_comment(post_id, author_name, body):
    """Append a flat comment to MongoDB forum_threads.comments via $push."""
    pid = int(post_id)
    with closing(get_pg_connection(readonly=True)) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM forum_posts WHERE post_id = %s;", (pid,))
            if cur.fetchone() is None:
                raise ValueError(f"Post #{pid} was not found.")

    now = _utc_now()
    comment = {
        "comment_id": str(uuid.uuid4()),
        "author_name": author_name.strip(),
        "body": body.strip(),
        "created_at": now,
        "updated_at": now,
    }
    client, collection = get_mongo_collection()
    try:
        collection.update_one(
            {"post_id": pid},
            {
                "$push": {"comments": comment},
                "$setOnInsert": {"tags": []},
            },
            upsert=True,
        )
    finally:
        client.close()
    return comment


def update_comment(post_id, comment_id, body):
    """Edit an embedded comment body using MongoDB's positional $ operator."""
    pid = int(post_id)
    now = _utc_now()
    client, collection = get_mongo_collection()
    try:
        result = collection.update_one(
            {"post_id": pid, "comments.comment_id": str(comment_id)},
            {
                "$set": {
                    "comments.$.body": body.strip(),
                    "comments.$.updated_at": now,
                }
            },
        )
        if result.matched_count == 0:
            raise ValueError("Comment could not be found.")
    finally:
        client.close()


def delete_comment(post_id, comment_id):
    """Remove an embedded comment from MongoDB via $pull."""
    pid = int(post_id)
    client, collection = get_mongo_collection()
    try:
        collection.update_one(
            {"post_id": pid},
            {"$pull": {"comments": {"comment_id": str(comment_id)}}},
        )
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Idempotent Starter Data Lookup Helpers
# ---------------------------------------------------------------------------

def find_team_and_match_by_name(team_name_pattern, season=None):
    """Look up a real team_id and optional match_id from PostgreSQL for seeding."""
    with closing(get_pg_connection(readonly=True)) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    t.team_id,
                    t.team_name,
                    ms.match_id,
                    ms.season
                FROM teams t
                LEFT JOIN match_participants mp ON mp.team_id = t.team_id
                LEFT JOIN match_series ms ON ms.match_id = mp.match_id
                    AND (%s::SMALLINT IS NULL OR ms.season = %s)
                WHERE LOWER(t.team_name) LIKE LOWER(%s)
                ORDER BY ms.season DESC NULLS LAST, ms.match_id DESC NULLS LAST
                LIMIT 1;
                """,
                (season, season, team_name_pattern),
            )
            row = cur.fetchone()
            return dict(row) if row else None