"""Inventory every VCT CSV and sample Homepage-related files.

Run from the repository root:
    python scripts/data_cleaning/shared/inventory_homepage.py

Writes only to docs/shared/. Original CSV files are not changed.
"""
from pathlib import Path
import csv
import json

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
DOCS = ROOT / "docs" / "shared"
DOCS.mkdir(parents=True, exist_ok=True)

if not RAW.is_dir():
    raise FileNotFoundError(f"Dataset not found: {RAW}")

csv_files = sorted(RAW.rglob("*.csv"))

# PART 1: Inventory ALL seasons and shared ID files.
with (DOCS / "dataset_inventory.csv").open(
    "w", newline="", encoding="utf-8"
) as output:
    writer = csv.writer(output)
    writer.writerow(["season", "file", "size_mb", "column_count", "columns"])

    for path in csv_files:
        relative = path.relative_to(RAW)
        season = relative.parts[0]

        with path.open(
            "r", newline="", encoding="utf-8-sig", errors="replace"
        ) as source:
            columns = next(csv.reader(source), [])

        writer.writerow([
            season,
            str(relative),
            round(path.stat().st_size / (1024 * 1024), 2),
            len(columns),
            " | ".join(columns),
        ])

# PART 2: Two sample rows per relevant CSV in 2023, 2026 and all_ids.
with (DOCS / "homepage_samples.txt").open(
    "w", encoding="utf-8"
) as output:
    for path in csv_files:
        relative = path.relative_to(RAW)
        season = relative.parts[0]
        if season not in ("vct_2023", "vct_2026", "all_ids"):
            continue

        relevant = (
            season == "all_ids"
            or path.parent.name in ("agents", "ids")
            or path.name in ("overview.csv", "maps_played.csv")
        )
        if not relevant:
            continue

        with path.open(
            "r", newline="", encoding="utf-8-sig", errors="replace"
        ) as source:
            reader = csv.DictReader(source)
            output.write(f"\n{'=' * 60}\n")
            output.write(f"FILE: {relative}\n")
            output.write(f"COLUMNS: {reader.fieldnames or []}\n")

            for index, row in enumerate(reader):
                if index >= 2:
                    break
                output.write(json.dumps(row, ensure_ascii=False) + "\n")

print(f"Found {len(csv_files)} CSV files.")
print("Generated:")
print(DOCS / "dataset_inventory.csv")
print(DOCS / "homepage_samples.txt")
