"""Prepare candidate player-map agent observations for each VCT season.

Run from repository root:
    python scripts/data_cleaning/shared/clean_homepage.py

Outputs in data/cleaned/shared/. This is preliminary preparation, NOT
completed validation or database import. Raw files remain unchanged.
"""
from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
OUTPUT = ROOT / "data" / "cleaned" / "shared"
OUTPUT.mkdir(parents=True, exist_ok=True)

FIELDS = [
    "Year", "Tournament", "Stage", "Match Type",
    "Match Name", "Map", "Player", "Team", "Agent",
]

for year in range(2021, 2027):
    source = RAW / f"vct_{year}" / "matches" / "overview.csv"
    if not source.is_file():
        raise FileNotFoundError(f"Cannot find {source}")

    clean_file = OUTPUT / f"agent_candidates_{year}.csv"
    review_file = OUTPUT / f"agent_review_{year}.csv"
    counts = {
        "valid_candidates": 0,
        "all_maps": 0,
        "blank_maps": 0,
        "side_specific": 0,
        "multiple_agents": 0,
        "missing_agents": 0,
    }

    with (
        source.open("r", encoding="utf-8-sig", newline="") as src,
        clean_file.open("w", encoding="utf-8", newline="") as dst,
        review_file.open("w", encoding="utf-8", newline="") as rev,
    ):
        reader = csv.DictReader(src)
        clean_writer = csv.DictWriter(dst, fieldnames=FIELDS)
        review_writer = csv.DictWriter(rev, fieldnames=FIELDS + ["Reason"])
        clean_writer.writeheader()
        review_writer.writeheader()

        for row in reader:
            side = (row.get("Side") or "").strip().lower()
            map_name = (row.get("Map") or "").strip()
            agent = (row.get("Agents") or "").strip().lower()

            if side != "both":
                counts["side_specific"] += 1
                continue
            if map_name.lower() == "all maps":
                counts["all_maps"] += 1
                continue

            record = {
                "Year": year,
                "Tournament": (row.get("Tournament") or "").strip(),
                "Stage": (row.get("Stage") or "").strip(),
                "Match Type": (row.get("Match Type") or "").strip(),
                "Match Name": (row.get("Match Name") or "").strip(),
                "Map": map_name,
                "Player": (row.get("Player") or "").strip(),
                "Team": (row.get("Team") or "").strip(),
                "Agent": agent,
            }

            reason = None
            if not map_name:
                reason = "blank_maps"
            elif not agent:
                reason = "missing_agents"
            elif any(separator in agent for separator in (",", "/", ";", "|")):
                reason = "multiple_agents"

            if reason:
                counts[reason] += 1
                review_writer.writerow({**record, "Reason": reason})
            else:
                clean_writer.writerow(record)
                counts["valid_candidates"] += 1

    print(f"\nYEAR {year}")
    for key, count in counts.items():
        print(f"{key}: {count:,}")

print("\nDone! Files saved to:", OUTPUT)
