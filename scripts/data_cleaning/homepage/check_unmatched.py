"""Check which player-map records cannot match a game lookup for all seasons.

Run from the repository root:
    python scripts/data_cleaning/homepage/check_unmatched.py

Read-only diagnostic. 'All Maps' denotes an aggregate, not an individual map.
"""
from pathlib import Path
from collections import Counter
import csv

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
KEYS = ["Tournament", "Stage", "Match Type", "Match Name", "Map"]


def read_csv(path):
    if not path.is_file():
        raise FileNotFoundError(f"Cannot find {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        yield from csv.DictReader(source)


def make_key(row):
    return tuple((row.get(column) or "").strip() for column in KEYS)


for year in range(2021, 2027):  # 2021, ..., 2026
    folder = RAW / f"vct_{year}"
    id_file = folder / "ids" / "tournaments_stages_matches_games_ids.csv"
    overview_file = folder / "matches" / "overview.csv"

    valid_keys = {make_key(row) for row in read_csv(id_file)}
    unmatched_maps = Counter()
    examples = []

    for row in read_csv(overview_file):
        if (row.get("Side") or "").strip().lower() != "both":
            continue
        if make_key(row) not in valid_keys:
            unmatched_maps[(row.get("Map") or "").strip()] += 1
            if len(examples) < 5:
                examples.append({
                    "Tournament": row.get("Tournament", ""),
                    "Match Name": row.get("Match Name", ""),
                    "Map": row.get("Map", ""),
                    "Player": row.get("Player", ""),
                })

    print(f"\nYEAR: {year}")
    print("Unmatched map values:")
    print(unmatched_maps.most_common(10))
    print("Example unmatched records:")
    for example in examples:
        print(example)
