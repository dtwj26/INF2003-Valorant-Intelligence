
"""Import VCT core entities into the shared PostgreSQL starter schema.

From the repository root:
    python scripts/data_import/postgresql/import_core.py --year 2023 --dry-run
    python scripts/data_import/postgresql/import_core.py --year 2023

Requires database/postgresql/schema/001_core_tables.sql to have been executed.
Reads only the selected season's ID mapping CSVs. No raw data is modified.
"""

import argparse
import csv
import getpass
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
REPORTS = ROOT / "docs" / "shared"

# Insertion order matters: matches reference tournaments; games reference matches.
TABLES = {
    "tournaments": ("tournament_id", "tournament_name"),
    "teams": ("team_id", "team_name"),
    "players": ("player_id", "player_name"),
    "match_series": (
        "match_id", "tournament_id", "season", "match_name",
        "stage_name", "source_stage_id", "match_type",
    ),
    "map_games": ("game_id", "match_id", "map_name"),
}

ISSUE_FIELDS = ("year", "file", "row", "table", "issue", "identifier", "detail")


def read_csv(path, required):
    if not path.is_file():
        raise FileNotFoundError(f"Required input is missing: {path}")

    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = set(required) - set(reader.fieldnames or ())

        if missing:
            raise ValueError(
                f"{path} is missing columns: {sorted(missing)}"
            )

        for line, raw_row in enumerate(reader, start=2):
            yield line, {
                k: (v or "").strip()
                for k, v in raw_row.items()
                if k is not None
            }


def add_issue(issues, year, path, line, table, issue, identifier, detail):
    issues.append({
        "year": year,
        "file": path.name,
        "row": line,
        "table": table,
        "issue": issue,
        "identifier": identifier,
        "detail": str(detail)[:500],
    })


def valid_id(raw):
    try:
        value = int(raw)
        return value if value > 0 else None
    except (ValueError, TypeError):
        return None


def optional_stage_id(raw, issues, year, path, line):
    if not raw:
        return None

    try:
        value = int(raw)

        if value >= 0:
            # Preserve source Stage ID 0.
            # Its meaning is not yet confirmed.
            return value
    except ValueError:
        pass

    add_issue(
        issues, year, path, line, "match_series",
        "invalid_stage_id", raw,
        "Keeping stage name; storing source_stage_id as NULL"
    )
    return None


def add_record(data, table, record, issues, fatal, year, path, line):
    ident = record[0]
    previous = data[table].get(ident)

    if previous is None:
        data[table][ident] = record

    elif previous == record:
        # Identical ID and values: no need to add another record.
        return

    elif table in ("tournaments", "teams", "players"):
        # Preserve first name and flag the alternative for review.
        add_issue(
            issues, year, path, line, table,
            "name_variation", ident,
            f"First name={previous[1]!r}; "
            f"additional name={record[1]!r}; first kept"
        )

    else:
        # A Match ID / Game ID must not describe conflicting records.
        add_issue(
            issues, year, path, line, table,
            "conflicting_id", ident,
            f"First={previous!r}; later={record!r}"
        )
        fatal.append((table, ident))


def build_data(year):
    folder = RAW / f"vct_{year}" / "ids"

    games_file = (
        folder / "tournaments_stages_matches_games_ids.csv"
    )
    teams_file = folder / "teams_ids.csv"
    players_file = folder / "players_ids.csv"

    data = {table: {} for table in TABLES}
    issues = []
    fatal = []
    counts = {"mapping_rows": 0}

    # 1. Read team and player identity mappings.
    for table, path, name_col, id_col in (
        ("teams", teams_file, "Team", "Team ID"),
        ("players", players_file, "Player", "Player ID"),
    ):
        for line, row in read_csv(path, (name_col, id_col)):
            ident = valid_id(row[id_col])
            name = row[name_col]

            if ident is None or not name:
                add_issue(
                    issues, year, path, line, table,
                    "invalid_identity", row[id_col],
                    f"Name={name!r}; skipped"
                )
                continue

            add_record(
                data, table, (ident, name),
                issues, fatal, year, path, line
            )

    # 2. Read tournaments, match series and map games.
    required = (
        "Tournament", "Tournament ID",
        "Stage", "Stage ID", "Match Type",
        "Match Name", "Match ID", "Map", "Game ID",
    )

    for line, row in read_csv(games_file, required):
        counts["mapping_rows"] += 1

        tid = valid_id(row["Tournament ID"])
        mid = valid_id(row["Match ID"])
        gid = valid_id(row["Game ID"])

        tournament_name = row["Tournament"]
        match_name = row["Match Name"]
        map_name = row["Map"]

        # TOURNAMENT
        if tid is None or not tournament_name:
            add_issue(
                issues, year, games_file, line,
                "tournaments", "invalid_identity",
                row["Tournament ID"],
                "Missing valid tournament ID or name; dependent row skipped"
            )
            continue

        add_record(
            data, "tournaments", (tid, tournament_name),
            issues, fatal, year, games_file, line
        )

        # MATCH SERIES
        if mid is None or not match_name:
            add_issue(
                issues, year, games_file, line,
                "match_series", "invalid_identity",
                row["Match ID"],
                "Missing valid match ID or name; game skipped"
            )
            continue

        stage_id = optional_stage_id(
            row["Stage ID"], issues, year, games_file, line
        )

        match = (
            mid,
            tid,
            year,
            match_name,
            row["Stage"] or None,
            stage_id,
            row["Match Type"] or None,
        )

        add_record(
            data, "match_series", match,
            issues, fatal, year, games_file, line
        )

        # MAP GAME
        if (
            gid is None
            or not map_name
            or map_name.casefold() == "all maps"
        ):
            add_issue(
                issues, year, games_file, line,
                "map_games", "invalid_game",
                row["Game ID"],
                f"Map={map_name!r}; game skipped"
            )
            continue

        add_record(
            data, "map_games", (gid, mid, map_name),
            issues, fatal, year, games_file, line
        )

    return data, issues, fatal, counts


def save_issues(year, issues):
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"core_import_issues_{year}.csv"

    with path.open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle, fieldnames=ISSUE_FIELDS
        )
        writer.writeheader()
        writer.writerows(issues)

    return path


def import_postgresql(data, year, issues, fatal):
    try:
        import psycopg2
        from psycopg2 import sql
        from psycopg2.extras import execute_values
    except ImportError as exc:
        raise RuntimeError(
            "Install the driver: python -m pip install psycopg2-binary"
        ) from exc

    # Database connection settings.
    host = os.getenv("PGHOST", "localhost")
    port = int(os.getenv("PGPORT", "5432"))
    dbname = os.getenv("PGDATABASE", "valorant_dev")
    user = os.getenv("PGUSER", "postgres")
    password = os.getenv("PGPASSWORD")

    print(
        f"\nConnecting to {dbname} at {host}:{port} as {user}"
    )

    if password is None:
        password = getpass.getpass(
            "PostgreSQL password (hidden): "
        )

    connection = psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
        connect_timeout=10,
    )

    inserted = {}

    try:
        # Transaction: COMMIT on success, ROLLBACK on failure.
        with connection:
            with connection.cursor() as cursor:

                # Check existing database records before inserting.
                for table, columns in TABLES.items():
                    records = data[table]

                    if not records:
                        inserted[table] = 0
                        continue

                    query = sql.SQL(
                        "SELECT {} FROM {} WHERE {} = ANY(%s)"
                    ).format(
                        sql.SQL(", ").join(
                            map(sql.Identifier, columns)
                        ),
                        sql.Identifier(table),
                        sql.Identifier(columns[0]),
                    )

                    cursor.execute(
                        query, (list(records.keys()),)
                    )

                    for old in cursor.fetchall():
                        current = records[old[0]]

                        if old == current:
                            continue

                        if table in (
                            "tournaments", "teams", "players"
                        ):
                            add_issue(
                                issues, year,
                                Path("database"), 0, table,
                                "existing_name_variation", old[0],
                                f"Stored={old[1]!r}; "
                                f"source={current[1]!r}; "
                                "stored name kept"
                            )

                        else:
                            add_issue(
                                issues, year,
                                Path("database"), 0, table,
                                "existing_id_conflict", old[0],
                                f"Stored={old!r}; source={current!r}"
                            )
                            fatal.append((table, old[0]))

                if fatal:
                    raise ValueError(
                        f"Found {len(fatal)} conflicting "
                        "match/game identities. "
                        "Import cancelled; see issue report."
                    )

                # Insert in foreign-key dependency order.
                for table, columns in TABLES.items():
                    rows = list(data[table].values())

                    if not rows:
                        inserted[table] = 0
                        continue

                    statement = sql.SQL(
                        "INSERT INTO {} ({}) VALUES %s "
                        "ON CONFLICT ({}) DO NOTHING "
                        "RETURNING {}"
                    ).format(
                        sql.Identifier(table),
                        sql.SQL(", ").join(
                            map(sql.Identifier, columns)
                        ),
                        sql.Identifier(columns[0]),
                        sql.Identifier(columns[0]),
                    )

                    added = execute_values(
                        cursor,
                        statement.as_string(connection),
                        rows,
                        page_size=500,
                        fetch=True,
                    )

                    inserted[table] = len(added)

    finally:
        connection.close()

    return inserted


def main():
    parser = argparse.ArgumentParser(
        description="Load a season's core VCT IDs into PostgreSQL"
    )

    parser.add_argument(
        "--year",
        type=int,
        choices=range(2021, 2027),
        default=2023,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate CSVs without connecting to PostgreSQL",
    )

    args = parser.parse_args()

    data, issues, fatal, counts = build_data(args.year)

    print(
        f"\nSeason {args.year}: read "
        f"{counts['mapping_rows']:,} game mapping rows"
    )

    for table in TABLES:
        print(
            f"  {table:14s}: "
            f"{len(data[table]):,} distinct IDs prepared"
        )

    print(
        f"  diagnostic notes: {len(issues):,}; "
        f"fatal conflicts: {len(fatal):,}"
    )

    try:
        if fatal:
            raise ValueError(
                "Conflicting IDs within source CSVs; import stopped"
            )

        if args.dry_run:
            print(
                "\nDRY RUN: no database connection and no inserts."
            )

        else:
            inserted = import_postgresql(
                data, args.year, issues, fatal
            )

            print(
                "\nImport committed successfully "
                "(newly inserted rows):"
            )

            for table, count in inserted.items():
                print(f"  {table:14s}: {count:,}")

    finally:
        report = save_issues(args.year, issues)
        print(f"\nDiagnostic report: {report}")


if __name__ == "__main__":
    try:
        main()
    except (
        FileNotFoundError,
        ValueError,
        RuntimeError,
    ) as error:
        raise SystemExit(f"ERROR: {error}") from error
