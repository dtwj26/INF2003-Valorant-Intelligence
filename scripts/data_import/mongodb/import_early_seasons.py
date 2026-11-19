
import argparse
import csv
import os
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from pymongo import MongoClient, ReplaceOne


ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = ROOT / "data" / "raw"
AUDIT_DIR = ROOT / "docs" / "shared"

FIELDS = (
    "Tournament", "Stage", "Match Type",
    "Match Name", "Map",
)


def clean(value):
    return (value or "").strip()


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        yield from csv.DictReader(file)


def game_key(row):
    return tuple(clean(row[field]) for field in FIELDS)


def parse_credits(value):
    value = clean(value).lower().replace(",", "")

    if value in ("", "-", "n/a", "na", "null"):
        return None

    if value.endswith("k"):
        return int(Decimal(value[:-1]) * 1000)

    return int(Decimal(value))


def load_postgresql(year):
    with psycopg2.connect(
        os.environ["DATABASE_URL"], connect_timeout=10
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT g.game_id, g.match_id,
                       p.team_id, t.team_name
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

            pg = defaultdict(dict)
            for game_id, match_id, team_id, name in cur:
                pg[(game_id, match_id)][team_id] = name

    return pg


def prepare(year):
    base = DATA_ROOT / f"vct_{year}"

    team_ids = defaultdict(set)
    for row in rows(base / "ids" / "teams_ids.csv"):
        name = clean(row["Team"])
        value = clean(row["Team ID"])
        if value:
            team_ids[name].add(int(value))

    game_refs = defaultdict(set)
    for row in rows(
        base / "ids" / "tournaments_stages_matches_games_ids.csv"
    ):
        values = (
            clean(row["Game ID"]),
            clean(row["Match ID"]),
            clean(row["Tournament ID"]),
        )
        if all(values):
            game_refs[game_key(row)].add(
                tuple(map(int, values))
            )

    outcome_file = (
        base / "matches" / "win_loss_methods_round_number.csv"
    )
    economy_file = base / "matches" / "eco_rounds.csv"

    pg = load_postgresql(year)

    game_teams = defaultdict(set)
    game_counts = Counter()

    for row in rows(outcome_file):
        key = game_key(row)
        game_teams[key].add(clean(row["Team"]))
        game_counts[key] += 1

    approved = {}
    excluded = {}

    # validate one game ID and two PostgreSQL teams
    for key, names in game_teams.items():
        refs = game_refs.get(key, set())

        if not refs:
            excluded[key] = "missing game ID"
            continue

        if len(refs) != 1:
            excluded[key] = "ambiguous game ID"
            continue

        if len(names) != 2:
            excluded[key] = "invalid team count"
            continue

        resolved = {}
        for name in names:
            ids = team_ids.get(name, set())
            if len(ids) != 1:
                break
            resolved[name] = next(iter(ids))

        if len(resolved) != 2:
            excluded[key] = "missing or ambiguous team ID"
            continue

        game_id, match_id, tournament_id = next(iter(refs))
        participants = pg.get((game_id, match_id), {})

        if (
            len(participants) != 2
            or set(resolved.values()) != set(participants)
        ):
            excluded[key] = "PostgreSQL participant mismatch"
            continue

        approved[key] = (
            game_id, match_id, tournament_id, resolved,
            participants,
        )

    # prevent two different source keys from using one game ID
    claimed = {}
    for key, info in approved.items():
        game_id = info[0]
        if game_id in claimed:
            excluded[key] = "duplicate game ID across source keys"
            excluded[claimed[game_id]] = (
                "duplicate game ID across source keys"
            )
        else:
            claimed[game_id] = key

    approved = {
        key: value for key, value in approved.items()
        if key not in excluded
    }

    documents = {}
    round_states = defaultdict(
        lambda: [0, 0, 0, set()]
    )
    bad_games = set()

    # build documents from verified round outcomes
    for row in rows(outcome_file):
        key = game_key(row)

        if key not in approved:
            continue

        game_id, match_id, tournament_id, names, pg_names = (
            approved[key]
        )

        team_name = clean(row["Team"])
        outcome = clean(row["Outcome"])

        try:
            number = int(clean(row["Round Number"]))
        except ValueError:
            bad_games.add(key)
            continue

        if (
            team_name not in names
            or outcome not in ("Win", "Loss")
            or number < 1
        ):
            bad_games.add(key)
            continue

        team_id = names[team_name]
        document_key = (game_id, team_id)

        if document_key not in documents:
            documents[document_key] = {
                "season": year,
                "tournament_id": tournament_id,
                "match_id": match_id,
                "game_id": game_id,
                "team_id": team_id,
                "team_name": pg_names[team_id],
                "source_team_name": team_name,
                "map_name": clean(row["Map"]),
                "source": f"vct_{year}",
                "rounds": [],
                "_source_key": key,
            }

        documents[document_key]["rounds"].append({
            "number": number,
            "outcome": outcome,
            "won": outcome == "Win",
            "method": clean(row["Method"]) or None,
            "economy": None,
        })

        state = round_states[(key, number)]
        state[0] += 1
        state[1] += outcome == "Win"
        state[2] += outcome == "Loss"
        state[3].add(team_id)

    # exclude entire games containing inconsistent rounds
    for (key, number), state in round_states.items():
        count, wins, losses, teams = state
        if (
            count != 2
            or wins != 1
            or losses != 1
            or len(teams) != 2
        ):
            bad_games.add(key)

    for key in bad_games:
        excluded[key] = "invalid or duplicate round outcomes"

    approved = {
        key: info for key, info in approved.items()
        if key not in bad_games
    }

    documents = {
        key: doc for key, doc in documents.items()
        if doc["_source_key"] in approved
    }

    # link valid rounds to their economy observations
    round_lookup = {}
    for document in documents.values():
        for item in document["rounds"]:
            round_lookup[(
                document["game_id"],
                document["team_id"],
                item["number"],
            )] = item

    seen_economy = set()
    duplicate_economy = set()
    unmatched_economy = 0
    skipped_economy = 0

    for row in rows(economy_file):
        key = game_key(row)

        if key not in approved:
            skipped_economy += 1
            continue

        game_id, _, _, names, _ = approved[key]
        team_name = clean(row["Team"])

        try:
            number = int(clean(row["Round Number"]))
            team_id = names[team_name]
        except (ValueError, KeyError):
            unmatched_economy += 1
            continue

        identity = (game_id, team_id, number)
        target = round_lookup.get(identity)

        if target is None:
            unmatched_economy += 1
            continue

        if identity in seen_economy:
            duplicate_economy.add(identity)
            target["economy"] = None
            continue

        seen_economy.add(identity)

        try:
            target["economy"] = {
                "category": clean(row["Type"]) or None,
                "loadout_value": parse_credits(
                    row["Loadout Value"]
                ),
                "remaining_credits": parse_credits(
                    row["Remaining Credits"]
                ),
            }
        except (ValueError, ArithmeticError):
            unmatched_economy += 1
            target["economy"] = None

    # duplicate economy observations are not trusted
    for identity in duplicate_economy:
        round_lookup[identity]["economy"] = None

    no_economy_games = set()
    partial_economy_games = set()
    total_rounds = total_economy = 0

    for document in documents.values():
        document.pop("_source_key")
        document["rounds"].sort(
            key=lambda item: item["number"]
        )

        count = len(document["rounds"])
        economy_count = sum(
            item["economy"] is not None
            for item in document["rounds"]
        )

        document["coverage"] = {
            "recorded_rounds": count,
            "economy_rounds": economy_count,
            "economy_available": economy_count > 0,
        }

        total_rounds += count
        total_economy += economy_count

        if economy_count == 0:
            no_economy_games.add(document["game_id"])
        elif economy_count < count:
            partial_economy_games.add(document["game_id"])

    stats = {
        "source_games": len(game_counts),
        "included_games": len(approved),
        "excluded_games": len(excluded),
        "excluded_outcome_rows": sum(
            game_counts[key] for key in excluded
        ),
        "documents": len(documents),
        "round_rows": total_rounds,
        "economy_rows": total_economy,
        "games_without_economy": len(no_economy_games),
        "games_with_partial_economy": len(
            partial_economy_games
        ),
        "unmatched_economy": unmatched_economy,
        "skipped_economy": skipped_economy,
        "duplicate_economy": len(duplicate_economy),
    }

    return documents, excluded, game_counts, stats


def save_audit(year, excluded, game_counts):
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    path = AUDIT_DIR / f"mongodb_import_issues_{year}.csv"

    with path.open(
        "w", newline="", encoding="utf-8-sig"
    ) as file:
        writer = csv.writer(file)
        writer.writerow([
            "season", "tournament", "stage",
            "match_type", "match_name", "map",
            "reason", "excluded_outcome_rows",
        ])

        for key, reason in sorted(excluded.items()):
            writer.writerow([
                year, *key, reason, game_counts[key]
            ])

    print("Audit report:", path)


def import_documents(year, documents):
    uri = os.environ["MONGODB_URI"]

    with MongoClient(
        uri, serverSelectionTimeoutMS=10000
    ) as client:
        client.admin.command("ping")

        collection = client[
            "valorant_intelligence"
        ]["team_game_rounds"]

        collection.create_index(
            [("game_id", 1), ("team_id", 1)],
            unique=True,
            name="uq_game_team",
        )

        collection.create_index(
            [("season", 1), ("team_id", 1), ("map_name", 1)],
            name="idx_season_team_map",
        )

        game_ids = {
            key[0] for key in documents
        }

        # never replace a different season's records
        for record in collection.find(
            {"game_id": {"$in": list(game_ids)}},
            {"game_id": 1, "season": 1},
        ):
            if record["season"] != year:
                raise ValueError(
                    f"Cross-season ID collision: "
                    f"{record['game_id']}"
                )

        keys = sorted(documents)
        upserted = matched = modified = 0

        for start in range(0, len(keys), 300):
            batch = keys[start:start + 300]

            operations = [
                ReplaceOne(
                    {"game_id": gid, "team_id": tid},
                    documents[(gid, tid)],
                    upsert=True,
                )
                for gid, tid in batch
            ]

            result = collection.bulk_write(
                operations, ordered=False
            )

            upserted += result.upserted_count
            matched += result.matched_count
            modified += result.modified_count

        count = collection.count_documents(
            {"season": year}
        )

        print("\nMongoDB import")
        print("Upserted:", upserted)
        print("Matched:", matched)
        print("Modified:", modified)
        print("Documents for season:", count)

        if count != len(documents):
            raise ValueError(
                "Imported count does not match prepared count"
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--year", type=int,
        choices=(2021, 2022), required=True
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")

    print(f"\nPreparing VCT {args.year}")

    documents, excluded, counts, stats = prepare(args.year)

    print("\nValidation results")
    for label, value in stats.items():
        print(f"{label}: {value}")

    reasons = Counter(excluded.values())
    print("\nExclusion reasons")
    for reason, count in sorted(reasons.items()):
        print(f"{reason}: {count} games")

    save_audit(args.year, excluded, counts)

    if not documents:
        raise ValueError("No valid documents prepared")

    if not args.apply:
        print("\nDRY RUN PASSED - No database changes made")
        return

    import_documents(args.year, documents)
    print("\nIMPORT COMPLETE")


if __name__ == "__main__":
    main()
