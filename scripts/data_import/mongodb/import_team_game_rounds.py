
import argparse
import csv
import os
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from pymongo import MongoClient, ReplaceOne


ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = ROOT / "data" / "raw"

GAME_FIELDS = (
    "Tournament", "Stage", "Match Type",
    "Match Name", "Map",
)

# only applied to the 2025 economy CSV
TOURNAMENT_ALIASES_2025 = {
    "Champions Tour 2025: Americas Stage 1":
        "VCT 2025: Americas Stage 1",
    "Champions Tour 2025: EMEA Stage 1":
        "VCT 2025: EMEA Stage 1",
    "Champions Tour 2025: Pacific Stage 1":
        "VCT 2025: Pacific Stage 1",
    "Champions Tour 2025: Americas Kickoff":
        "VCT 2025: Americas Kickoff",
    "Champions Tour 2025: EMEA Kickoff":
        "VCT 2025: EMEA Kickoff",
    "Champions Tour 2025: Pacific Kickoff":
        "VCT 2025: Pacific Kickoff",
    "Champions Tour 2025: Masters Bangkok":
        "Valorant Masters Bangkok 2025",
}

NRG_ID = 1034


def clean(value):
    return (value or "").strip()


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        yield from csv.DictReader(file)


def game_key(row, year, economy_source=False):
    values = tuple(clean(row[field]) for field in GAME_FIELDS)

    if year == 2025 and economy_source:
        tournament = TOURNAMENT_ALIASES_2025.get(
            values[0], values[0]
        )
        values = (tournament,) + values[1:]

    return values


def parse_credits(value):
    value = clean(value).lower().replace(",", "")

    if value in ("", "-", "n/a", "na", "null"):
        return None

    if value.endswith("k"):
        return int(Decimal(value[:-1]) * 1000)

    return int(Decimal(value))


def load_postgresql(year):
    uri = os.getenv("DATABASE_URL")

    if not uri:
        raise ValueError("DATABASE_URL missing from .env")

    conn = psycopg2.connect(uri, connect_timeout=10)

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    g.game_id,
                    g.match_id,
                    p.team_id,
                    t.team_name
                FROM map_games g
                JOIN match_series m
                    ON m.match_id = g.match_id
                JOIN match_participants p
                    ON p.match_id = g.match_id
                JOIN teams t
                    ON t.team_id = p.team_id
                WHERE m.season = %s
                """,
                (year,),
            )

            return {
                (game_id, match_id, team_id): team_name
                for game_id, match_id, team_id, team_name
                in cur.fetchall()
            }
    finally:
        conn.close()


def prepare_documents(year, pg_records):
    base = DATA_ROOT / f"vct_{year}"

    if not base.is_dir():
        raise FileNotFoundError(f"Dataset not found: {base}")

    # load team IDs
    team_ids = {}

    for row in read_csv(base / "ids" / "teams_ids.csv"):
        name = clean(row["Team"])
        team_id = int(row["Team ID"])

        if name in team_ids and team_ids[name] != team_id:
            raise ValueError(f"Ambiguous team ID: {name}")

        team_ids[name] = team_id

    # load game and match IDs
    games = {}

    for row in read_csv(
        base / "ids" / "tournaments_stages_matches_games_ids.csv"
    ):
        key = game_key(row, year)

        info = {
            "game_id": int(row["Game ID"]),
            "match_id": int(row["Match ID"]),
            "tournament_id": int(row["Tournament ID"]),
        }

        if key in games and games[key] != info:
            raise ValueError(f"Ambiguous game mapping: {key}")

        games[key] = info

    nrg_alias_games = set()
    tournament_alias_games = set()

    def resolve_team(row, economy_source=False):
        key = game_key(row, year, economy_source)

        if key not in games:
            raise ValueError(f"Unmapped game: {key}")

        info = games[key]
        game_id = info["game_id"]
        match_id = info["match_id"]
        source_name = clean(row["Team"])

        if (
            economy_source
            and year == 2025
            and clean(row["Tournament"]) in TOURNAMENT_ALIASES_2025
        ):
            tournament_alias_games.add(game_id)

        # the Mega Minors alias is accepted only
        # when PostgreSQL confirms NRG in that game
        if year in (2025, 2026) and source_name == "Mega Minors":
            team_id = NRG_ID

            if (game_id, match_id, team_id) not in pg_records:
                raise ValueError(
                    f"Unverified Mega Minors alias: {game_id}"
                )

            nrg_alias_games.add(game_id)

        elif source_name in team_ids:
            team_id = team_ids[source_name]

        else:
            raise ValueError(
                f"Team could not be mapped: {source_name}"
            )

        identity = (game_id, match_id, team_id)

        if identity not in pg_records:
            raise ValueError(
                f"PostgreSQL participant mismatch: {identity}"
            )

        return info, team_id, pg_records[identity], source_name

    # load economy records, normalizing 2025 tournament names
    economy = {}

    for row in read_csv(base / "matches" / "eco_rounds.csv"):
        info, team_id, _, _ = resolve_team(
            row, economy_source=True
        )

        key = (
            info["game_id"],
            team_id,
            int(row["Round Number"]),
        )

        if key in economy:
            raise ValueError(f"Duplicate economy record: {key}")

        economy[key] = {
            "category": clean(row["Type"]) or None,
            "loadout_value": parse_credits(row["Loadout Value"]),
            "remaining_credits": parse_credits(
                row["Remaining Credits"]
            ),
        }

    documents = {}
    outcome_keys = set()
    game_teams = defaultdict(set)
    game_rounds = defaultdict(list)
    outcome_count = 0

    # combine round outcomes with economy details
    for row in read_csv(
        base / "matches" / "win_loss_methods_round_number.csv"
    ):
        info, team_id, team_name, source_name = resolve_team(row)

        game_id = info["game_id"]
        match_id = info["match_id"]
        number = int(row["Round Number"])
        outcome = clean(row["Outcome"])

        if outcome not in ("Win", "Loss"):
            raise ValueError(f"Invalid round outcome: {outcome}")

        round_key = (game_id, team_id, number)

        if round_key in outcome_keys:
            raise ValueError(
                f"Duplicate round outcome: {round_key}"
            )

        outcome_keys.add(round_key)
        outcome_count += 1

        document_key = (game_id, team_id)

        if document_key not in documents:
            documents[document_key] = {
                "season": year,
                "tournament_id": info["tournament_id"],
                "match_id": match_id,
                "game_id": game_id,
                "team_id": team_id,
                "team_name": team_name,
                "source_team_name": source_name,
                "map_name": clean(row["Map"]),
                "source": f"vct_{year}",
                "rounds": [],
            }

        document = documents[document_key]

        if (
            document["match_id"] != match_id
            or document["map_name"] != clean(row["Map"])
            or document["source_team_name"] != source_name
        ):
            raise ValueError(
                f"Inconsistent game data: {document_key}"
            )

        document["rounds"].append({
            "number": number,
            "outcome": outcome,
            "won": outcome == "Win",
            "method": clean(row["Method"]) or None,
            "economy": economy.get(round_key),
        })

        game_teams[game_id].add(team_id)
        game_rounds[(game_id, number)].append(
            (team_id, outcome)
        )

    # economy records must match actual round outcomes
    unmatched_economy = set(economy) - outcome_keys

    if unmatched_economy:
        raise ValueError(
            f"{len(unmatched_economy)} unmatched economy records"
        )

    # each recorded game must have exactly two teams
    invalid_games = [
        game_id
        for game_id, team_set in game_teams.items()
        if len(team_set) != 2
    ]

    if invalid_games:
        raise ValueError(
            f"Games without two teams: {invalid_games[:5]}"
        )

    # every recorded round must have one winner and loser
    invalid_rounds = []

    for key, records in game_rounds.items():
        teams = {team_id for team_id, _ in records}
        outcomes = sorted(outcome for _, outcome in records)

        if (
            len(records) != 2
            or len(teams) != 2
            or outcomes != ["Loss", "Win"]
        ):
            invalid_rounds.append(key)

    if invalid_rounds:
        raise ValueError(
            f"Invalid round pairs: {invalid_rounds[:5]}"
        )

    games_without_economy = set()
    games_with_partial_economy = set()

    for document in documents.values():
        rounds = document["rounds"]
        rounds.sort(key=lambda item: item["number"])

        economy_count = sum(
            item["economy"] is not None for item in rounds
        )

        document["coverage"] = {
            "recorded_rounds": len(rounds),
            "economy_rounds": economy_count,
            "economy_available": economy_count > 0,
        }

        if economy_count == 0:
            games_without_economy.add(document["game_id"])
        elif economy_count < len(rounds):
            games_with_partial_economy.add(
                document["game_id"]
            )

    source_mappings = {
        (
            document["game_id"],
            document["match_id"],
            document["team_id"],
        )
        for document in documents.values()
    }

    missing_pg = source_mappings - set(pg_records)
    extra_pg = set(pg_records) - source_mappings

    if missing_pg:
        raise ValueError(
            f"Missing PostgreSQL mappings: "
            f"{sorted(missing_pg)[:5]}"
        )

    if not documents:
        raise ValueError("No valid documents prepared")

    stats = {
        "reference_games": len(games),
        "recorded_games": len(game_teams),
        "documents": len(documents),
        "round_outcomes": outcome_count,
        "economy_records": len(economy),
        "rounds_without_economy": outcome_count - len(economy),
        "games_without_economy": len(games_without_economy),
        "partial_economy_games": len(games_with_partial_economy),
        "nrg_alias_games": len(nrg_alias_games),
        "tournament_alias_games": len(tournament_alias_games),
        "missing_pg": len(missing_pg),
        "extra_pg": len(extra_pg),
    }

    return documents, stats


def import_mongodb(year, documents):
    uri = os.getenv("MONGODB_URI")

    if not uri:
        raise ValueError("MONGODB_URI missing from .env")

    with MongoClient(
        uri, serverSelectionTimeoutMS=10000
    ) as client:
        client.admin.command("ping")

        collection = client[
            "valorant_intelligence"
        ]["team_game_rounds"]

        # unique identifier for each team-game document
        collection.create_index(
            [("game_id", 1), ("team_id", 1)],
            unique=True,
            name="uq_game_team",
        )

        # supports season, team and map filters
        collection.create_index(
            [
                ("season", 1),
                ("team_id", 1),
                ("map_name", 1),
            ],
            name="idx_season_team_map",
        )

        game_ids = sorted({game_id for game_id, _ in documents})

        # refuse to overwrite another season's games
        existing = collection.find(
            {"game_id": {"$in": game_ids}},
            {"_id": 0, "game_id": 1, "season": 1},
        )

        for row in existing:
            if row.get("season") != year:
                raise ValueError(
                    f"Game {row['game_id']} belongs "
                    "to another season"
                )

        keys = sorted(documents)
        upserted = modified = matched = 0

        for start in range(0, len(keys), 500):
            batch = keys[start:start + 500]

            operations = [
                ReplaceOne(
                    {"game_id": game_id, "team_id": team_id},
                    documents[(game_id, team_id)],
                    upsert=True,
                )
                for game_id, team_id in batch
            ]

            result = collection.bulk_write(
                operations, ordered=False
            )

            upserted += result.upserted_count
            modified += result.modified_count
            matched += result.matched_count

        final_count = collection.count_documents(
            {"season": year}
        )

        print("\nMongoDB import")
        print("Upserted:", upserted)
        print("Matched:", matched)
        print("Modified:", modified)
        print("Documents for season:", final_count)

        if final_count != len(documents):
            raise ValueError(
                "Imported count differs from prepared documents"
            )

        print("\nIMPORT COMPLETE")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--year",
        type=int,
        choices=range(2021, 2027),
        default=2023,
    )
    parser.add_argument("--apply", action="store_true")

    args = parser.parse_args()

    load_dotenv(ROOT / ".env")

    print(f"\nPreparing VCT {args.year}")

    pg_records = load_postgresql(args.year)
    documents, stats = prepare_documents(args.year, pg_records)

    print("\nSource validation")
    print("Reference games:", stats["reference_games"])
    print("Games with round data:", stats["recorded_games"])
    print("Team-game documents:", stats["documents"])
    print("Round outcome records:", stats["round_outcomes"])
    print("Economy records:", stats["economy_records"])
    print(
        "Rounds without economy:",
        stats["rounds_without_economy"],
    )
    print(
        "Games without economy:",
        stats["games_without_economy"],
    )
    print(
        "Games with partial economy:",
        stats["partial_economy_games"],
    )
    print(
        "Verified Mega Minors alias games:",
        stats["nrg_alias_games"],
    )
    print(
        "Normalized tournament-name games:",
        stats["tournament_alias_games"],
    )

    print("\nPostgreSQL validation")
    print("Missing mappings:", stats["missing_pg"])
    print("Additional mappings:", stats["extra_pg"])
    print("PostgreSQL identifier validation: PASSED")

    if stats["reference_games"] != stats["recorded_games"]:
        print(
            "WARNING: Some reference games have "
            "no round outcomes"
        )

    if not args.apply:
        print("\nDRY RUN PASSED - No database changes made")
        return

    import_mongodb(args.year, documents)


if __name__ == "__main__":
    main()
