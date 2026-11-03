
import argparse
import csv
from pathlib import Path
from urllib.parse import urlsplit

import psycopg

# project paths
ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "local" / "teams_players"

EXPECTED = {
    2022: 86820,
    2023: 8300,
    2024: 11040,
    2025: 12760,
    2026: 8860,
}

COLUMNS = [
    "game_id", "player_id", "team_id",
    "kills", "deaths", "assists", "acs", "rating"
]

# require --commit to save changes
parser = argparse.ArgumentParser()
parser.add_argument("--commit", action="store_true")
args = parser.parse_args()

# read production connection
lines = (ROOT / ".env").read_text(
    encoding="utf-8"
).splitlines()

url = next(
    line.split("=", 1)[1].strip().strip('"').strip("'")
    for line in lines
    if line.strip().startswith("DATABASE_URL=")
)

parsed = urlsplit(url)

# prevent importing into the wrong database
if (
    parsed.hostname !=
    "ep-proud-firefly-a12etnyl.ap-southeast-1.aws.neon.tech"
    or parsed.path.lstrip("/") != "valorant_dev"
):
    raise SystemExit("Wrong database connection. Stopped.")

# validate CSV files before connecting
for season, expected in EXPECTED.items():
    path = DATA / f"player_map_stats_{season}.csv"

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames != COLUMNS:
            raise SystemExit(
                f"{season}: Incorrect CSV columns."
            )

        count = sum(1 for _ in reader)

    if count != expected:
        raise SystemExit(
            f"{season}: Expected {expected}, found {count}."
        )

print("CSV validation passed.")

# import all seasons in one transaction
with psycopg.connect(url, connect_timeout=20) as conn:
    with conn.cursor() as cur:

        cur.execute(
            "SELECT COUNT(*) FROM public.player_map_stats"
        )

        if cur.fetchone()[0] != 0:
            raise RuntimeError(
                "Production table is not empty. Stopped."
            )

        total = 0

        for season, expected in EXPECTED.items():
            path = DATA / f"player_map_stats_{season}.csv"

            copy_sql = """
                COPY public.player_map_stats
                (game_id, player_id, team_id,
                 kills, deaths, assists, acs, rating)
                FROM STDIN
                WITH (FORMAT CSV, HEADER TRUE, NULL '')
            """

            with cur.copy(copy_sql) as copy:
                with path.open("rb") as f:
                    while chunk := f.read(65536):
                        copy.write(chunk)

            cur.execute("""
                SELECT COUNT(*)
                FROM public.player_map_stats s
                JOIN public.map_games mg
                    ON s.game_id = mg.game_id
                JOIN public.match_series ms
                    ON mg.match_id = ms.match_id
                WHERE ms.season = %s
            """, (season,))

            verified = cur.fetchone()[0]

            if verified != expected:
                raise RuntimeError(
                    f"{season}: Verification failed."
                )

            total += verified
            print(f"{season}: {verified} verified")

        cur.execute(
            "SELECT COUNT(*) FROM public.player_map_stats"
        )

        if cur.fetchone()[0] != total:
            raise RuntimeError("Total count mismatch.")

        print("Total verified:", total)

    if args.commit:
        conn.commit()
        print("Production import committed.")
    else:
        conn.rollback()
        print("Dry run passed. All changes rolled back.")
