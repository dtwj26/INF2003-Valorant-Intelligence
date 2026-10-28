
"""Read-only audit of gameplay-statistics CSVs for VCT 2021-2026."""

import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "docs" / "shared"

FILES = [
    "matches/overview.csv",
    "matches/maps_played.csv",
    "matches/maps_scores.csv",
    "matches/scores.csv",
    "agents/agents_pick_rates.csv",
    "agents/maps_stats.csv",
    "agents/teams_picked_agents.csv",
]

SUMMARY_HEADERS = [
    "Year", "File", "Status", "Rows", "Columns",
    "Side Values", "Side Both Rows", "All Maps Rows",
    "Blank Map Rows", "Blank Agent Rows", "Multi-Agent Values",
    "Date Columns", "Potentially Useful Columns",
]

COLUMN_HEADERS = [
    "Year", "File", "Column",
    "Nonempty Rows", "Empty Rows", "Example Values"
]


def write_csv(filename, headings, records):
    with (OUT / filename).open(
        "w", encoding="utf-8-sig", newline=""
    ) as output:
        writer = csv.DictWriter(output, fieldnames=headings)
        writer.writeheader()
        writer.writerows(records)


def find_column(columns, name):
    return next(
        (
            col for col in columns
            if col.casefold().strip() == name.casefold()
        ),
        None
    )


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    summaries = []
    columns_out = []
    sample_text = []

    for year in range(2021, 2027):
        for filename in FILES:
            path = RAW / f"vct_{year}" / filename

            if not path.is_file():
                summaries.append({
                    "Year": year,
                    "File": filename,
                    "Status": "MISSING"
                })
                print(f"{year}  {filename}: file not found")
                continue

            with path.open(
                "r", encoding="utf-8-sig", newline=""
            ) as handle:
                reader = csv.DictReader(handle)

                columns = [
                    column
                    for column in (reader.fieldnames or [])
                    if column
                ]

                map_col = find_column(columns, "Map")
                side_col = find_column(columns, "Side")

                agent_col = (
                    find_column(columns, "Agents")
                    or find_column(columns, "Agent")
                )

                count = 0
                both_count = 0
                all_maps = 0
                blank_map = 0
                blank_agent = 0
                multiple_agents = 0

                side_values = Counter()
                nonempty = Counter()

                examples = {
                    column: [] for column in columns
                }

                samples = []

                for row in reader:
                    count += 1

                    for column in columns:
                        value = (
                            row.get(column) or ""
                        ).strip()

                        if value:
                            nonempty[column] += 1

                            if (
                                len(examples[column]) < 3
                                and value not in examples[column]
                            ):
                                examples[column].append(
                                    value[:80]
                                )

                    if side_col:
                        side = (
                            row.get(side_col) or ""
                        ).strip().lower()

                        side_values[
                            side or "<blank>"
                        ] += 1

                        if side == "both":
                            both_count += 1

                    if map_col:
                        map_name = (
                            row.get(map_col) or ""
                        ).strip()

                        if not map_name:
                            blank_map += 1
                        elif map_name.lower() == "all maps":
                            all_maps += 1

                    if agent_col:
                        agent = (
                            row.get(agent_col) or ""
                        ).strip()

                        if not agent:
                            blank_agent += 1
                        elif "," in agent:
                            multiple_agents += 1

                    if len(samples) < 2:
                        samples.append({
                            key: str(
                                row.get(key) or ""
                            )[:120]
                            for key in columns[:14]
                        })

                date_columns = [
                    col for col in columns
                    if (
                        "date" in col.lower()
                        or "time" in col.lower()
                    )
                ]

                key_words = (
                    "team", "player", "map", "agent",
                    "score", "round", "kill", "death",
                    "win", "econom", "date", "time"
                )

                useful_columns = [
                    col for col in columns
                    if any(
                        word in col.lower()
                        for word in key_words
                    )
                ]

                summaries.append({
                    "Year": year,
                    "File": filename,
                    "Status": "OK",
                    "Rows": count,
                    "Columns": len(columns),
                    "Side Values": "; ".join(
                        f"{k}={v}"
                        for k, v in side_values.most_common()
                    ),
                    "Side Both Rows": (
                        both_count if side_col else ""
                    ),
                    "All Maps Rows": (
                        all_maps if map_col else ""
                    ),
                    "Blank Map Rows": (
                        blank_map if map_col else ""
                    ),
                    "Blank Agent Rows": (
                        blank_agent if agent_col else ""
                    ),
                    "Multi-Agent Values": (
                        multiple_agents if agent_col else ""
                    ),
                    "Date Columns": "; ".join(date_columns),
                    "Potentially Useful Columns": "; ".join(
                        useful_columns
                    ),
                })

                for col in columns:
                    columns_out.append({
                        "Year": year,
                        "File": filename,
                        "Column": col,
                        "Nonempty Rows": nonempty[col],
                        "Empty Rows": (
                            count - nonempty[col]
                        ),
                        "Example Values": " | ".join(
                            examples[col]
                        ),
                    })

                sample_text.append(
                    f"\n{'=' * 65}\n"
                    f"YEAR {year}: {filename}\n"
                    f"Rows: {count:,}\n"
                    f"Columns: {', '.join(columns)}\n"
                )

                for i, row in enumerate(samples, start=1):
                    sample_text.append(
                        f"Sample {i}: {row}\n"
                    )

                print(
                    f"{year}  {filename}: "
                    f"{count:,} rows, "
                    f"{len(columns)} columns"
                )

    write_csv(
        "gameplay_statistics_file_audit.csv",
        SUMMARY_HEADERS,
        summaries
    )

    write_csv(
        "gameplay_statistics_columns.csv",
        COLUMN_HEADERS,
        columns_out
    )

    (
        OUT / "gameplay_statistics_samples.txt"
    ).write_text(
        "".join(sample_text),
        encoding="utf-8"
    )

    (
        OUT / "gameplay_statistics_notes.txt"
    ).write_text(
        "Read-only exploratory audit.\n"
        "Counts describe CSV rows, not confirmed "
        "games, matches, or agent picks.\n"
        "'All Maps' rows and Side attack/defend "
        "may be aggregates.\n"
        "Comma-separated agent values require "
        "review, not automatic splitting.\n"
        "Missing fields and duplicated records "
        "need analysis before import.\n",
        encoding="utf-8"
    )

    print(
        "\nFinished. Four reports saved to docs/shared/"
    )


if __name__ == "__main__":
    main()
