"""Investigate ambiguous VCT Game IDs without changing any dataset.

Run from the repository root:
    python scripts/data_cleaning/shared/diagnose_ambiguous_game_ids.py

Reads:
    data/raw/vct_YEAR/ids/tournaments_stages_matches_games_ids.csv
    data/raw/vct_YEAR/matches/maps_scores.csv
    data/raw/vct_YEAR/matches/maps_played.csv
    data/cleaned/shared/agent_candidates_YEAR.csv

Writes:
    docs/shared/ambiguous_game_id_summary.csv
    docs/shared/ambiguous_game_id_evidence.csv
    docs/shared/ambiguous_game_id_notes.txt

Only the years 2021 and 2022 are checked, where the previous validation
found ambiguous candidate-to-Game-ID joins.
"""

import csv
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "cleaned" / "shared"
REPORTS = ROOT / "docs" / "shared"
REPORTS.mkdir(parents=True, exist_ok=True)

YEARS = (2021, 2022)
KEY_FIELDS = ("Tournament", "Stage", "Match Type", "Match Name", "Map")
SUMMARY_FILE = REPORTS / "ambiguous_game_id_summary.csv"
EVIDENCE_FILE = REPORTS / "ambiguous_game_id_evidence.csv"
NOTES_FILE = REPORTS / "ambiguous_game_id_notes.txt"

SUMMARY_FIELDS = [
    "Year", *KEY_FIELDS, "Distinct Game IDs", "Game IDs", "Distinct Match IDs",
    "Match IDs", "Mapping Rows", "Candidate Rows", "Unique Team-Player Pairs",
    "Unique Teams", "Score Rows", "Distinct Scorelines", "Maps Played Rows",
    "Possible Explanation",
]
EVIDENCE_FIELDS = [
    "Year", "Evidence Type", *KEY_FIELDS, "Match ID", "Game ID",
    "Team", "Player", "Agent", "Team A", "Team A Score", "Team B",
    "Team B Score", "Duration", "Comment",
]


def load_rows(path):
    if not path.is_file():
        raise FileNotFoundError(f"Required CSV not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        yield from csv.DictReader(file)


def tidy(value):
    return (value or "").strip()


def get_key(row):
    return tuple(tidy(row.get(field)) for field in KEY_FIELDS)


def sorted_ids(items):
    return sorted(items, key=lambda s: (0, int(s)) if s.isdecimal() else (1, s))


def explain(match_ids, scorelines, score_rows):
    if len(match_ids) > 1:
        return "Different Match IDs share this same text key; key is not unique"
    if len(scorelines) > 1:
        return "Multiple distinct scorelines; check for repeated map games"
    if score_rows > 1:
        return "Multiple score rows; check for repeated map games or duplicated rows"
    return "Multiple Game IDs share this key; raw data cannot uniquely assign candidates"


summary_rows = []
evidence_rows = []
for year in YEARS:
    season = RAW / f"vct_{year}"
    mapping = defaultdict(list)
    for row in load_rows(season / "ids" / "tournaments_stages_matches_games_ids.csv"):
        game_id = tidy(row.get("Game ID"))
        if game_id:
            mapping[get_key(row)].append(row)

    ambiguous_keys = {
        key for key, rows in mapping.items()
        if len({tidy(row.get("Game ID")) for row in rows}) > 1
    }

    # Only retain candidate rows for ambiguous keys; no broad datasets are rewritten.
    candidates = defaultdict(list)
    for row in load_rows(CLEAN / f"agent_candidates_{year}.csv"):
        key = get_key(row)
        if key in ambiguous_keys:
            candidates[key].append(row)

    # Filter to ambiguities that actually affect candidate rows.
    affected_keys = set(candidates)
    scores = defaultdict(list)
    for row in load_rows(season / "matches" / "maps_scores.csv"):
        key = get_key(row)
        if key in affected_keys:
            scores[key].append(row)

    maps_played = Counter()
    for row in load_rows(season / "matches" / "maps_played.csv"):
        key = get_key(row)
        if key in affected_keys:
            maps_played[key] += 1

    for key in sorted(affected_keys):
        context = dict(zip(KEY_FIELDS, key))
        ids = {tidy(row.get("Game ID")) for row in mapping[key]}
        match_ids = {tidy(row.get("Match ID")) for row in mapping[key]}
        scorelines = {
            (tidy(row.get("Team A")), tidy(row.get("Team A Score")),
             tidy(row.get("Team B")), tidy(row.get("Team B Score")))
            for row in scores[key]
        }
        players = {
            (tidy(row.get("Team")).casefold(), tidy(row.get("Player")).casefold())
            for row in candidates[key]
        }
        teams = {tidy(row.get("Team")) for row in candidates[key]}

        summary_rows.append({
            "Year": year, **context,
            "Distinct Game IDs": len(ids), "Game IDs": ", ".join(sorted_ids(ids)),
            "Distinct Match IDs": len(match_ids),
            "Match IDs": ", ".join(sorted_ids(match_ids)),
            "Mapping Rows": len(mapping[key]),
            "Candidate Rows": len(candidates[key]),
            "Unique Team-Player Pairs": len(players),
            "Unique Teams": len(teams),
            "Score Rows": len(scores[key]),
            "Distinct Scorelines": len(scorelines),
            "Maps Played Rows": maps_played[key],
            "Possible Explanation": explain(match_ids, scorelines, len(scores[key])),
        })

        for row in mapping[key]:
            evidence_rows.append({
                "Year": year, "Evidence Type": "GAME_ID_MAPPING", **context,
                "Match ID": tidy(row.get("Match ID")),
                "Game ID": tidy(row.get("Game ID")),
                "Comment": "Raw per-season IDs mapping",
            })

        for row in scores[key]:
            evidence_rows.append({
                "Year": year, "Evidence Type": "MAP_SCORE", **context,
                "Team A": tidy(row.get("Team A")),
                "Team A Score": tidy(row.get("Team A Score")),
                "Team B": tidy(row.get("Team B")),
                "Team B Score": tidy(row.get("Team B Score")),
                "Duration": tidy(row.get("Duration")),
                "Comment": "Score row has no Game ID; not a verified ID-to-score match",
            })

        for row in candidates[key]:
            evidence_rows.append({
                "Year": year, "Evidence Type": "AGENT_CANDIDATE", **context,
                "Team": tidy(row.get("Team")),
                "Player": tidy(row.get("Player")),
                "Agent": tidy(row.get("Agent")),
                "Comment": "Candidate lacks Game ID; cannot choose between multiple IDs",
            })

    affected_row_count = sum(len(v) for v in candidates.values())
    print(
        f"{year}: {len(affected_keys)} ambiguous match-map groups; "
        f"{affected_row_count} affected agent candidate rows"
    )

with SUMMARY_FILE.open("w", encoding="utf-8-sig", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=SUMMARY_FIELDS)
    writer.writeheader()
    writer.writerows(summary_rows)

with EVIDENCE_FILE.open("w", encoding="utf-8-sig", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=EVIDENCE_FIELDS)
    writer.writeheader()
    writer.writerows(evidence_rows)

NOTES_FILE.write_text(
    "AMBIGUOUS GAME ID INVESTIGATION (2021-2022)\n"
    "Raw data and cleaned candidates were NOT modified.\n\n"
    "Key: Tournament + Stage + Match Type + Match Name + Map.\n"
    "Each summary row is a key with multiple distinct Game IDs and at least "
    "one agent candidate row.\n"
    "GAME_ID_MAPPING evidence shows the actual candidate Game IDs and Match IDs.\n"
    "MAP_SCORE evidence shows available score rows, which do NOT contain Game ID.\n"
    "AGENT_CANDIDATE evidence shows player/agent records with no Game ID.\n"
    "Possible Explanation is a diagnostic hint, NOT a proven cause.\n"
    "Never arbitrarily choose a Game ID or duplicate one candidate across all IDs.\n"
    "Further identity data or a deterministic source key may be required.\n",
    encoding="utf-8",
)

print("\nReports created:")
print(" -", SUMMARY_FILE)
print(" -", EVIDENCE_FILE)
print(" -", NOTES_FILE)
