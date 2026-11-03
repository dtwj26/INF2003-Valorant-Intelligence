
import csv
from pathlib import Path

# source dataset
csv_path = Path(
    r"C:\Users\user\Documents\uni\year2\tri1\INF2003 - Database\archive\vct_2023\matches\overview.csv"
)

if not csv_path.is_file():
    raise FileNotFoundError(f"CSV not found: {csv_path}")

# read original csv
with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
    reader = csv.DictReader(file)
    columns = reader.fieldnames
    rows = list(reader)

print("Total source rows:", len(rows))
print("Columns:", columns)

# keep full-map player statistics only
player_rows = [
    row for row in rows
    if row["Side"].strip().lower() == "both"
    and row["Map"].strip().lower() != "all maps"
]

print("Candidate player-map rows:", len(player_rows))
print("Excluded rows:", len(rows) - len(player_rows))


# check duplicate player-map records
from collections import Counter

key_fields = (
    "Tournament",
    "Stage",
    "Match Type",
    "Match Name",
    "Map",
    "Player",
    "Team",
)

keys = [
    tuple(row[field].strip() for field in key_fields)
    for row in player_rows
]

counts = Counter(keys)

duplicate_groups = sum(
    1 for count in counts.values() if count > 1
)

print("Unique player-map descriptions:", len(counts))
print("Duplicate player-map groups:", duplicate_groups)

# check missing performance values
for field in ("Kills", "Deaths", "Assists",
              "Average Combat Score", "Rating"):
    missing = sum(
        1 for row in player_rows
        if not row[field].strip()
    )
    print(f"Missing {field}: {missing}")
