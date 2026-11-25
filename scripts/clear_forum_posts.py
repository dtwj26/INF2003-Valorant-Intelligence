"""CLI-only script to delete all forum threads from PostgreSQL and MongoDB.

Usage (from repository root):
    python scripts/clear_forum_posts.py
    python scripts/clear_forum_posts.py --yes
"""

import argparse
from contextlib import closing
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.forum import repository  # noqa: E402


def main():
    parser = argparse.ArgumentParser(
        description="Delete all forum posts and comments from PostgreSQL and MongoDB."
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip interactive confirmation prompt.",
    )
    args = parser.parse_args()

    pg_count = repository.count_posts()
    client, collection = repository.get_mongo_collection()
    try:
        mongo_count = collection.count_documents({})
    finally:
        client.close()

    if pg_count == 0 and mongo_count == 0:
        print("Forum is already empty (0 posts in PostgreSQL, 0 threads in MongoDB).")
        return

    if not args.yes:
        reply = input(
            f"This will permanently delete {pg_count} post(s) from PostgreSQL and "
            f"{mongo_count} thread document(s) from MongoDB. Continue? [y/N]: "
        ).strip().lower()
        if reply not in ("y", "yes"):
            print("Aborted. No records were deleted.")
            return

    with closing(repository.get_pg_connection(readonly=False)) as conn:
        with conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE forum_posts RESTART IDENTITY;")

            client, collection = repository.get_mongo_collection()
            try:
                mongo_result = collection.delete_many({})
            finally:
                client.close()

    print(
        f"Cleared all forum data: deleted {pg_count} PostgreSQL row(s) (identity reset) "
        f"and {mongo_result.deleted_count} MongoDB document(s)."
    )


if __name__ == "__main__":
    main()