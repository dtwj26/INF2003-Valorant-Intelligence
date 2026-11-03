
import argparse
import csv
from pathlib import Path
from urllib.parse import urlsplit

import psycopg

# select the season
parser = argparse.ArgumentParser()
parser.add_argument(
    "season",
    type=int,
    choices=range(2021, 2027)
)
parser.add_argument("--commit", action="store_true")
args = parser.parse_args()

# project paths
ROOT = Path(__file__).resolve().parents[3]
LOCAL = ROOT / "data" / "local" / "teams_players"

CSV_FILE = LOCAL / f"player_map_stats_{args.season}.csv"
ENV_FILE = LOCAL / "dev_connection.env"

COLUMNS = [
    "game_id", "player_id", "team_id",
    "kills", "deaths", "assists", "acs", "rating"
]


def read_database_url(path):
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise ValueError("DATABASE_URL not found")


# load development connection
database_url = read_database_url(ENV_FILE)

dev_host = urlsplit(database_url).hostname
database_name = urlsplit(database_url).path.lstrip("/")

if database_name != "valorant_dev" or not dev_host:
    raise SystemExit("Unexpected database connection")

# check against the project's production connection
production_env = ROOT / ".env"

if production_env.is_file():
    production_url = read_database_url(production_env)
    production_host = urlsplit(production_url).hostname

    if dev_host == production_host:
        raise SystemExit(
            "Development host matches project connection. Stopped."
        )

# check the CSV before importing
with CSV_FILE.open("r", encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)

    if reader.fieldnames != COLUMNS:
        raise SystemExit("Unexpected CSV columns")

    record_count = sum(1 for _ in reader)

if record_count == 0:
    raise SystemExit("CSV is empty. Import stopped.")

print("Season:", args.season)
print("CSV records:", record_count)
print("Database:", database_name)

# use a transaction for safe importing
with psycopg.connect(database_url, connect_timeout=20) as conn:
    with conn.cursor() as cur:

        # check whether this season already has data
        cur.execute("""
            SELECT COUNT(*)
            FROM player_map_stats p
            JOIN map_games mg ON p.game_id = mg.game_id
            JOIN match_series ms ON mg.match_id = ms.match_id
            WHERE ms.season = %s
        """, (args.season,))

        existing = cur.fetchone()[0]

        if existing:
            raise RuntimeError(
                f"Season {args.season} already has "
                f"{existing} records. Import stopped."
            )

        # record total before import
        cur.execute("SELECT COUNT(*) FROM player_map_stats")
        total_before = cur.fetchone()[0]

        # insert CSV into PostgreSQL
        copy_sql = """
            COPY player_map_stats
            (game_id, player_id, team_id,
             kills, deaths, assists, acs, rating)
            FROM STDIN
            WITH (FORMAT CSV, HEADER TRUE, NULL '')
        """

        with cur.copy(copy_sql) as copy:
            with CSV_FILE.open("rb") as f:
                while chunk := f.read(65536):
                    copy.write(chunk)

        # validate the imported records
        cur.execute("""
            SELECT COUNT(*)
            FROM player_map_stats p
            JOIN map_games mg ON p.game_id = mg.game_id
            JOIN match_series ms ON mg.match_id = ms.match_id
            WHERE ms.season = %s
        """, (args.season,))

        verified = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM player_map_stats")
        total_after = cur.fetchone()[0]

        print("Verified season rows:", verified)

        if (
            verified != record_count
            or total_after - total_before != record_count
        ):
            raise RuntimeError(
                "Import verification failed. Transaction rolled back."
            )

    if args.commit:
        conn.commit()
        print("Import committed successfully.")
    else:
        conn.rollback()
        print("Test passed. Changes rolled back.")

print("Finished.")
