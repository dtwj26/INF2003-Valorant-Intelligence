
"""Explore remaining VCT CSV datasets across 2021-2026.

Reads CSV files without modifying them.

Outputs:
docs/shared/remaining_dataset_file_audit.csv
docs/shared/remaining_dataset_column_audit.csv
docs/shared/remaining_dataset_schema_changes.csv
docs/shared/remaining_dataset_samples.txt
"""

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "docs" / "shared"

YEARS = range(2021, 2027)

# Already examined in our gameplay statistics investigation.
EXAMINED = {
    "matches/overview.csv",
    "matches/maps_played.csv",
    "matches/maps_scores.csv",
    "matches/scores.csv",
    "agents/agents_pick_rates.csv",
    "agents/maps_stats.csv",
    "agents/teams_picked_agents.csv",
}

FILE_HEADERS = [
    "Year", "File", "Category", "Rows", "Columns",
    "File Size MB", "ID Columns", "Potential Date Columns",
]

COLUMN_HEADERS = [
    "Year", "File", "Column",
    "Nonempty Rows", "Empty Rows", "Example Values",
]

SCHEMA_HEADERS = [
    "File", "Years Present", "Missing Years",
    "Columns Differ Across Years",
    "Differences",
]


def save_csv(filename, headers, rows):
    path = OUT / filename

    with path.open(
        "w", encoding="utf-8-sig", newline=""
    ) as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Created: {path}")


def possible_date_column(name):
    # Avoid treating 'Overtime Score' as a date/time.
    words = set(
        re.findall(r"[a-z0-9]+", name.lower())
    )

    return bool(
        words.intersection({
            "date", "datetime", "timestamp"
        })
        or (
            "time" in words
            and words.intersection({
                "start", "end", "match", "event"
            })
        )
    )


def possible_id_column(name):
    name = name.strip().lower()

    return (
        name.endswith(" id")
        or name.endswith("_id")
        or name in {
            "gameid", "matchid", "playerid",
            "teamid", "tournamentid"
        }
    )


def categorize(relative_path):
    name = relative_path.lower()

    if any(
        keyword in name
        for keyword in (
            "round", "econom", "kill",
            "weapon", "damage", "event"
        )
    ):
        return "Potential detailed gameplay / MongoDB"

    if "ids/" in name or name.startswith("ids/"):
        return "Identifier mappings"

    if "player" in name or "team" in name:
        return "Player / team data"

    return "Other dataset"


def inspect_file(path, year, relative_path):
    counts = Counter()
    examples = {}
    samples = []
    row_count = 0

    with path.open(
        "r", encoding="utf-8-sig", newline=""
    ) as file:
        reader = csv.DictReader(file)

        columns = [
            col for col in (reader.fieldnames or [])
            if col
        ]

        examples = {
            col: [] for col in columns
        }

        for row in reader:
            row_count += 1

            for col in columns:
                value = str(
                    row.get(col) or ""
                ).strip()

                if value:
                    counts[col] += 1

                    if (
                        len(examples[col]) < 3
                        and value not in examples[col]
                    ):
                        examples[col].append(
                            value[:100]
                        )

            if len(samples) < 2:
                samples.append({
                    col: str(row.get(col) or "")[:100]
                    for col in columns
                })

    id_columns = [
        col for col in columns
        if possible_id_column(col)
    ]

    date_columns = [
        col for col in columns
        if possible_date_column(col)
    ]

    file_info = {
        "Year": year,
        "File": relative_path,
        "Category": categorize(relative_path),
        "Rows": row_count,
        "Columns": len(columns),
        "File Size MB": round(
            path.stat().st_size / (1024 * 1024), 2
        ),
        "ID Columns": "; ".join(id_columns),
        "Potential Date Columns": "; ".join(
            date_columns
        ),
    }

    column_info = []

    for col in columns:
        column_info.append({
            "Year": year,
            "File": relative_path,
            "Column": col,
            "Nonempty Rows": counts[col],
            "Empty Rows": row_count - counts[col],
            "Example Values": " | ".join(
                examples[col]
            ),
        })

    sample_info = [
        f"\n{'=' * 65}",
        f"YEAR: {year}",
        f"FILE: {relative_path}",
        f"CATEGORY: {categorize(relative_path)}",
        f"ROWS: {row_count:,}",
        f"COLUMNS: {', '.join(columns)}",
        f"ID COLUMNS: {', '.join(id_columns) or 'None'}",
        f"POTENTIAL DATE COLUMNS: "
        f"{', '.join(date_columns) or 'None'}",
    ]

    for number, row in enumerate(samples, start=1):
        sample_info.append(
            f"\nSample {number}:\n{row}"
        )

    return file_info, column_info, sample_info, columns


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    file_results = []
    column_results = []
    sample_results = []

    # Relative filename -> year -> column list.
    schemas = defaultdict(dict)

    for year in YEARS:
        folder = RAW / f"vct_{year}"

        if not folder.is_dir():
            print(f"WARNING: Missing {folder}")
            continue

        print(f"\nExamining {year} ...")

        for path in sorted(folder.rglob("*.csv")):
            relative_path = path.relative_to(
                folder
            ).as_posix()

            if relative_path.lower() in EXAMINED:
                continue

            (
                file_info,
                column_info,
                sample_info,
                columns,
            ) = inspect_file(
                path, year, relative_path
            )

            file_results.append(file_info)
            column_results.extend(column_info)
            sample_results.extend(sample_info)

            schemas[relative_path][year] = columns

            print(
                f"  {relative_path}: "
                f"{file_info['Rows']:,} rows, "
                f"{file_info['Columns']} columns"
            )

    schema_results = []

    for filename, years_data in sorted(
        schemas.items()
    ):
        available_years = sorted(years_data)
        missing_years = [
            year for year in YEARS
            if year not in years_data
        ]

        baseline_year = available_years[0]
        baseline = set(
            years_data[baseline_year]
        )

        differences = []

        for year in available_years[1:]:
            current = set(
                years_data[year]
            )

            added = sorted(current - baseline)
            removed = sorted(baseline - current)

            if added or removed:
                differences.append(
                    f"{year}: added={added}; "
                    f"missing={removed}"
                )

        schema_results.append({
            "File": filename,
            "Years Present": ", ".join(
                map(str, available_years)
            ),
            "Missing Years": ", ".join(
                map(str, missing_years)
            ),
            "Columns Differ Across Years":
                "Yes" if differences else "No",
            "Differences": " | ".join(
                differences
            ),
        })

    save_csv(
        "remaining_dataset_file_audit.csv",
        FILE_HEADERS,
        file_results
    )

    save_csv(
        "remaining_dataset_column_audit.csv",
        COLUMN_HEADERS,
        column_results
    )

    save_csv(
        "remaining_dataset_schema_changes.csv",
        SCHEMA_HEADERS,
        schema_results
    )

    (
        OUT / "remaining_dataset_samples.txt"
    ).write_text(
        "\n".join(sample_results),
        encoding="utf-8"
    )

    print("\nInvestigation completed.")
    print(
        f"Files examined: {len(file_results)}"
    )
    print(
        f"Different file types: {len(schemas)}"
    )
    print(
        "Reports generated in docs/shared/"
    )
    print(
        "\nNOTE: These are descriptive findings. "
        "They do not prove record accuracy, "
        "unique keys or join compatibility."
    )


if __name__ == "__main__":
    main()
