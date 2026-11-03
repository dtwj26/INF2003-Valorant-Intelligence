import csv
import sys
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

# choose the season to process
season = int(sys.argv[1]) if len(sys.argv) > 1 else 2023

ROOT = Path(__file__).resolve().parents[3]
LOCAL = ROOT / "data" / "local" / "teams_players"

SOURCE_ROOT = Path(
    r"C:\Users\user\Documents\uni\year2\tri1\INF2003 - Database\archive"
)

source_file = SOURCE_ROOT / f"vct_{season}" / "matches" / "overview.csv"
mapping_file = LOCAL / f"{season}_player_mappings.csv"
tournament_file = LOCAL / f"{season}_tournaments.csv"
output_file = LOCAL / f"player_map_stats_{season}.csv"


def read_csv(path):
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def clean(value):
    return " ".join((value or "").strip().casefold().split())


def valid_number(value, whole=False):
    if not value:
        return True

    try:
        number = Decimal(value)
        return (
            number.is_finite()
            and number >= 0
            and (not whole or number == number.to_integral_value())
        )
    except InvalidOperation:
        return False


# load source data and database mappings
source = read_csv(source_file)
mappings = read_csv(mapping_file)
tournaments = read_csv(tournament_file)

tournament_names = {
    row["tournament_id"]: row["tournament_name"]
    for row in tournaments
}


# build database lookup using full match identity
lookup = defaultdict(set)

for row in mappings:
    tournament_name = tournament_names[row["tournament_id"]]

    key = tuple(clean(value) for value in (
        tournament_name,
        row["stage_name"],
        row["match_type"],
        row["match_name"],
        row["map_name"],
        row["player_name"],
        row["team_name"],
    ))

    lookup[key].add((
        row["game_id"],
        row["player_id"],
        row["team_id"],
    ))


# known 2025 team-name differences
TEAM_NAMES_2025 = {
    "Mega Minors": "NRG Esports",
    "TALON": "Talon Esports",
}

# 2026 source/database team-name differences
TEAM_NAMES_2026 = {
    "Mega Minors": "NRG Esports",
    "KIWOOM DRX": "DRX",
}

# 2025 player-name candidates from mapping investigation
PLAYER_NAMES_2025 = {
    ("Gentle Mates", "Kada"): "K4DAVRA",
    ("TYLOO", "zjc"): "hfmi0dzjc9z7",
    ("EDward Gaming", "zjc"): "hfmi0dzjc9z7",
}


# process player performance records
results = []
issues = Counter()
alias_counts = Counter()
seen = set()
candidate_count = 0
unmatched_rows = []

for row in source:

    # keep full-map statistics only
    if clean(row["Side"]) != "both":
        continue

    if clean(row["Map"]) == "all maps":
        continue

    candidate_count += 1

    source_team = row["Team"].strip()
    source_player = row["Player"].strip()

    db_team = source_team
    db_player = source_player

    # apply season-specific naming differences
    if season == 2022:
        if (
            source_team == "Alter Ego"
            and source_player == "Kush"
            and row["Match Name"].strip() in {
                "CERBERUS Esports vs Alter Ego",
                "BLEED vs Alter Ego",
                "Alter Ego vs Made in Thailand",
            }
        ):
            db_player = "Kushy"

    elif season == 2025:
        db_team = TEAM_NAMES_2025.get(
            source_team,
            source_team
        )
        db_player = PLAYER_NAMES_2025.get(
            (source_team, source_player),
            source_player
        )

    elif season == 2026:
        db_team = TEAM_NAMES_2026.get(
            source_team,
            source_team
        )

    # match using tournament, match, map, player and team
    key = tuple(clean(value) for value in (
        row["Tournament"],
        row["Stage"],
        row["Match Type"],
        row["Match Name"],
        row["Map"],
        db_player,
        db_team,
    ))

    matches = lookup.get(key, set())

    # reject records without a database match
    if not matches:
        issues["unmatched"] += 1
        unmatched_rows.append(row)
        continue

    # reject ambiguous matches
    if len(matches) > 1:
        issues["ambiguous"] += 1
        continue

    game_id, player_id, team_id = next(iter(matches))

    # prevent duplicate player-map records
    if (game_id, player_id) in seen:
        issues["duplicate_player_game"] += 1
        continue

    # extract performance statistics
    fields = {
        "kills": "Kills",
        "deaths": "Deaths",
        "assists": "Assists",
        "acs": "Average Combat Score",
        "rating": "Rating",
    }

    stats = {
        name: row[column].strip()
        for name, column in fields.items()
    }

    # validate numeric statistics
    if any(
        not valid_number(
            value,
            name in ("kills", "deaths", "assists")
        )
        for name, value in stats.items()
    ):
        issues["invalid_statistics"] += 1
        continue

    seen.add((game_id, player_id))

    # count naming differences that matched successfully
    if db_team != source_team:
        alias_counts[
            f"Team: {source_team} -> {db_team}"
        ] += 1

    if db_player != source_player:
        alias_counts[
            f"Player: {source_player} -> {db_player}"
        ] += 1

    results.append({
        "game_id": game_id,
        "player_id": player_id,
        "team_id": team_id,
        **stats,
    })


# display validation results
print("Season:", season)
print("Candidate records:", candidate_count)
print("Verified records:", len(results))
print("Issues:", dict(issues))

# show applied naming differences
if alias_counts:
    print("\nApplied naming differences:")

    for name, count in alias_counts.most_common():
        print(f"{name}: {count}")


# investigate unmatched records
if unmatched_rows:
    print("\nUnmatched records by tournament:")

    tournament_counts = Counter(
        row["Tournament"] for row in unmatched_rows
    )

    for name, count in tournament_counts.most_common(10):
        print(f"{name}: {count}")

    print("\nUnmatched records by team:")

    team_counts = Counter(
        row["Team"] for row in unmatched_rows
    )

    for name, count in team_counts.most_common(10):
        print(f"{name}: {count}")

    print("\nFirst 5 unmatched records:")

    for row in unmatched_rows[:5]:
        print({
            field: row[field]
            for field in (
                "Tournament",
                "Stage",
                "Match Type",
                "Match Name",
                "Map",
                "Player",
                "Team",
            )
        })


# check 2026 team-name differences
if season == 2026 and unmatched_rows:
    without_team = defaultdict(set)

    for item in mappings:
        key = tuple(clean(value) for value in (
            tournament_names[item["tournament_id"]],
            item["stage_name"],
            item["match_type"],
            item["match_name"],
            item["map_name"],
            item["player_name"],
        ))

        without_team[key].add((
            item["team_name"],
            item["game_id"],
            item["player_id"],
        ))

    differences = Counter()
    no_match = 0
    ambiguous = 0

    for item in unmatched_rows:
        key = tuple(clean(item[field]) for field in (
            "Tournament",
            "Stage",
            "Match Type",
            "Match Name",
            "Map",
            "Player",
        ))

        possible = without_team.get(key, set())

        if len(possible) == 1:
            db_team, game_id, player_id = next(iter(possible))
            differences[(item["Team"], db_team)] += 1
        elif len(possible) == 0:
            no_match += 1
        else:
            ambiguous += 1

    print("\n2026 possible team-name differences:")

    for (source_team, db_team), count in differences.most_common():
        print(f"{source_team} -> {db_team}: {count}")

    print("No match without team:", no_match)
    print("Ambiguous matches:", ambiguous)




# allow verified 2022 records to be exported separately
unresolved = candidate_count - len(results)

if issues or unresolved:
    allowed_issues = {"unmatched", "ambiguous"}

    if (
        season == 2022
        and set(issues).issubset(allowed_issues)
        and sum(issues.values()) == unresolved
    ):
        print("\n2022 partial export:")
        print("Verified records:", len(results))
        print("Excluded records:", unresolved)
        print("Reason:", dict(issues))
    else:
        raise SystemExit(
            "Validation failed. No import file created."
        )


# export validated records
columns = [
    "game_id",
    "player_id",
    "team_id",
    "kills",
    "deaths",
    "assists",
    "acs",
    "rating",
]

with output_file.open(
    "w",
    encoding="utf-8",
    newline=""
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=columns
    )

    writer.writeheader()
    writer.writerows(results)


print("\nExported:", output_file)
