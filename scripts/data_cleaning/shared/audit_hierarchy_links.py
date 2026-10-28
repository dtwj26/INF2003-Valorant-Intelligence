
"""Investigate missing links between games and tournament hierarchy records.

Run:
python scripts/data_cleaning/shared/audit_hierarchy_links.py

Read-only: generates reports in docs/shared.
"""

import csv
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "docs" / "shared"
YEARS = range(2021, 2027)

PARENT_FIELDS = (
    "Tournament", "Tournament ID",
    "Stage", "Stage ID", "Match Type"
)

HIERARCHY_FIELDS = PARENT_FIELDS + ("Match Type ID",)

GAME_FIELDS = PARENT_FIELDS + (
    "Match Name", "Match ID", "Map", "Game ID"
)


def read_csv(path, required):
    if not path.is_file():
        raise FileNotFoundError(f"Missing input file: {path}")

    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = set(required) - set(reader.fieldnames or [])

        if missing:
            raise ValueError(
                f"{path.name} is missing columns: {sorted(missing)}"
            )

        return [
            {
                key: (value or "").strip()
                for key, value in row.items()
                if key
            }
            for row in reader
        ]


def write_csv(name, columns, rows):
    path = OUT / name

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    print(f"  Created: {path}")


def parent_key(row):
    return tuple(row[field] for field in PARENT_FIELDS)


def make_index(rows):
    exact = {parent_key(row) for row in rows}

    stages_by_id = {
        (row["Tournament ID"], row["Stage ID"])
        for row in rows
        if row["Stage ID"]
    }

    tournaments = {
        row["Tournament ID"]
        for row in rows
        if row["Tournament ID"]
    }

    return exact, stages_by_id, tournaments


def classify(key, local_index, global_index):
    local_exact, local_stages, local_tournaments = local_index
    global_exact, global_stages, global_tournaments = global_index

    if key in local_exact:
        return "Exact season match"

    if key in global_exact:
        return "Missing in season; exact match in global"

    tid = key[1]
    sid = key[3]

    if sid and (tid, sid) in local_stages:
        return "Season stage exists; match type/name differs"

    if sid and (tid, sid) in global_stages:
        return "Global stage exists; match type/name differs"

    if tid in local_tournaments or tid in global_tournaments:
        return "Tournament exists; stage does not match"

    return "Tournament ID absent from both hierarchies"


def main():
    global_path = (
        RAW / "all_ids" /
        "all_tournaments_stages_match_types_ids.csv"
    )

    global_rows = read_csv(
        global_path,
        HIERARCHY_FIELDS + ("Year",)
    )

    global_by_year = defaultdict(list)

    for row in global_rows:
        global_by_year[row["Year"]].append(row)

    summary = []
    issues = []
    id_examples = []

    for year in YEARS:
        folder = RAW / f"vct_{year}" / "ids"

        games = read_csv(
            folder / "tournaments_stages_matches_games_ids.csv",
            GAME_FIELDS
        )

        season_hierarchy = read_csv(
            folder / "tournaments_stages_match_types_ids.csv",
            HIERARCHY_FIELDS
        )

        global_hierarchy = global_by_year[str(year)]

        local_index = make_index(season_hierarchy)
        global_index = make_index(global_hierarchy)

        issue_groups = defaultdict(
            lambda: {
                "games": 0,
                "matches": set(),
                "game_examples": []
            }
        )

        counts = Counter()

        # Check every game against the hierarchy mappings.
        for game in games:
            key = parent_key(game)

            category = classify(
                key,
                local_index,
                global_index
            )

            counts[category] += 1

            if category == "Exact season match":
                continue

            group_key = (category,) + key
            group = issue_groups[group_key]

            group["games"] += 1

            if game["Match ID"]:
                group["matches"].add(game["Match ID"])

            if len(group["game_examples"]) < 5:
                group["game_examples"].append(
                    game["Game ID"] or "<blank>"
                )

        # Group issues by tournament, stage and match type.
        for (category, *parts), result in sorted(
            issue_groups.items()
        ):
            info = dict(zip(PARENT_FIELDS, parts))

            issues.append({
                "Year": year,
                "Classification": category,
                **info,
                "Game Rows": result["games"],
                "Distinct Match IDs": len(result["matches"]),
                "Example Game IDs": ", ".join(
                    result["game_examples"]
                )
            })

        # Examine blank hierarchy IDs separately.
        aggregate_count = 0
        other_blank_count = 0

        for source, rows in (
            ("Season", season_hierarchy),
            ("Global", global_hierarchy)
        ):
            for row in rows:
                missing = [
                    field
                    for field in (
                        "Tournament ID",
                        "Stage ID",
                        "Match Type ID"
                    )
                    if not row[field]
                ]

                if not missing:
                    continue

                is_aggregate = (
                    row["Stage"] == "All Stages"
                    and row["Match Type"] == "All Match Types"
                    and not row["Stage ID"]
                    and not row["Match Type ID"]
                )

                if source == "Season":
                    if is_aggregate:
                        aggregate_count += 1
                    else:
                        other_blank_count += 1

                existing_examples = sum(
                    1
                    for item in id_examples
                    if item["Year"] == year
                    and item["Source"] == source
                )

                if existing_examples < 15:
                    id_examples.append({
                        "Year": year,
                        "Source": source,
                        "Category": (
                            "Aggregate label with blank IDs"
                            if is_aggregate
                            else "Other blank ID(s)"
                        ),
                        **{
                            field: row[field]
                            for field in HIERARCHY_FIELDS
                        },
                        "Missing Fields": ", ".join(missing)
                    })

        summary.append({
            "Year": year,
            "Total Game Rows": len(games),
            "Exact Season Hierarchy Matches":
                counts["Exact season match"],
            "Missing Season, Present Global":
                counts["Missing in season; exact match in global"],
            "Season Stage / Type Mismatch":
                counts["Season stage exists; match type/name differs"],
            "Global Stage / Type Mismatch":
                counts["Global stage exists; match type/name differs"],
            "Tournament Found, Stage Mismatch":
                counts["Tournament exists; stage does not match"],
            "Tournament ID Missing Everywhere":
                counts["Tournament ID absent from both hierarchies"],
            "Season Hierarchy Rows": len(season_hierarchy),
            "Global Hierarchy Rows": len(global_hierarchy),
            "Season Aggregate Rows With Blank IDs":
                aggregate_count,
            "Season Other Rows With Blank IDs":
                other_blank_count
        })

        matched_season = counts["Exact season match"]

        matched_global = counts[
            "Missing in season; exact match in global"
        ]

        unresolved = (
            len(games) - matched_season - matched_global
        )

        print(
            f"{year}: {len(games):,} game rows; "
            f"{matched_season:,} matched season; "
            f"{matched_global:,} matched global only; "
            f"{unresolved:,} unresolved"
        )

    OUT.mkdir(parents=True, exist_ok=True)

    write_csv(
        "hierarchy_relationship_summary.csv",
        list(summary[0]),
        summary
    )

    write_csv(
        "hierarchy_relationship_issues.csv",
        [
            "Year",
            "Classification",
            *PARENT_FIELDS,
            "Game Rows",
            "Distinct Match IDs",
            "Example Game IDs"
        ],
        issues
    )

    write_csv(
        "hierarchy_missing_id_examples.csv",
        [
            "Year",
            "Source",
            "Category",
            *HIERARCHY_FIELDS,
            "Missing Fields"
        ],
        id_examples
    )

    notes = """HIERARCHY RELATIONSHIP AUDIT (2021-2026)

Input: per-season game and hierarchy mappings plus global hierarchy mappings.

Exact matches require:
Tournament, Tournament ID, Stage, Stage ID, Match Type.

Match Type ID is unavailable in the game mapping,
so it is not used as a join key.

The global hierarchy is filtered to the game's year.

Counts refer to game rows, not necessarily completed games.

'Missing in season; exact match in global' suggests
the global mapping has additional hierarchy coverage.

Other mismatch classifications are diagnostic hints,
not automatic corrections.

'All Stages' / 'All Match Types' with blank IDs
are treated as aggregate-level labels.

Other blank Match Type IDs are flagged but are not
automatically treated as errors.

No raw or cleaned dataset is modified.

Do not import mismatched foreign key references blindly.
"""

    notes_path = OUT / "hierarchy_relationship_notes.txt"

    notes_path.write_text(notes, encoding="utf-8")

    print(f"  Created: {notes_path}")


if __name__ == "__main__":
    main()
