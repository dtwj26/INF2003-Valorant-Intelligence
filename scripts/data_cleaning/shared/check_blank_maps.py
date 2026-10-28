"""Inspect player records with blank map names across VCT 2021-2026.

Run from the repository root:
    python scripts/data_cleaning/shared/check_blank_maps.py

Read-only: does not modify any CSVs.
"""
from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
DISPLAY_FIELDS = [
    "Tournament", "Stage", "Match Type", "Match Name",
    "Player", "Team", "Agents", "Map", "Side",
]

for year in range(2021, 2027):
    path = RAW / f"vct_{year}" / "matches" / "overview.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Cannot find {path}")

    count = 0
    examples = []
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            if (
                (row.get("Side") or "").strip().lower() == "both"
                and not (row.get("Map") or "").strip()
            ):
                count += 1
                if len(examples) < 5:
                    examples.append(row)

    print(f"\nYEAR {year}: {count} blank-map 'both' records")
    for row in examples:
        for column in DISPLAY_FIELDS:
            print(f"{column}: {row.get(column, '')}")
        print("-" * 50)
