
"""Audit shared VCT identifiers and relationships across 2021-2026.

Run:
    python scripts/data_cleaning/shared/audit_shared_identifiers.py

Outputs:
    docs/shared/identifier_audit_summary.csv
    docs/shared/identifier_audit_examples.csv
    docs/shared/identifier_cross_season.csv
    docs/shared/identifier_audit_notes.txt

This script does not modify source datasets.
"""

import csv
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "docs" / "shared"

YEARS = range(2021, 2027)
EXAMPLE_LIMIT = 12

GAME_COLS = (
    "Tournament",
    "Tournament ID",
    "Stage",
    "Stage ID",
    "Match Type",
    "Match Name",
    "Match ID",
    "Map",
    "Game ID",
)

HIERARCHY_COLS = (
    "Tournament",
    "Tournament ID",
    "Stage",
    "Stage ID",
    "Match Type",
    "Match Type ID",
)

SUMMARY_COLUMNS = (
    "Year",
    "Record Type",
    "File Present",
    "Rows",
    "Unique IDs",
    "Unique Match IDs",
    "Duplicate Full Rows",
    "Missing IDs",
    "IDs With Multiple Names/Contexts",
    "ID Identity Conflicts",
    "Text Match-Map Keys With Multiple Game IDs",
    "IDs Missing From Global",
    "Records Differing From Global",
    "Global IDs Missing From Season",
    "Game Rows Missing Hierarchy Reference",
    "Notes",
)

EXAMPLE_COLUMNS = (
    "Year", "Record Type", "Issue", "Identifier", "Details"
)

CROSS_COLUMNS = (
    "Record Type",
    "Identifier",
    "Years",
    "Year Count",
    "Distinct Contexts",
    "Details",
)


def load_csv(path, required):
    if not path.is_file():
        return None

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        names = reader.fieldnames or []

        missing = [name for name in required if name not in names]

        if missing:
            raise ValueError(
                f"{path}: missing columns {missing}; found {names}"
            )

        return [
            {
                key: (value or "").strip()
                for key, value in raw.items()
                if key is not None
            }
            for raw in reader
        ]


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def example(examples, caps, year, kind, issue, ident, details):
    bucket = (year, kind, issue)

    if caps[bucket] < EXAMPLE_LIMIT:
        examples.append({
            "Year": year,
            "Record Type": kind,
            "Issue": issue,
            "Identifier": ident,
            "Details": str(details)[:800],
        })

        caps[bucket] += 1


def summary(year, kind, present=True, **kwargs):
    row = dict.fromkeys(SUMMARY_COLUMNS, "")

    row.update({
        "Year": year,
        "Record Type": kind,
        "File Present": "Yes" if present else "NO",
    })

    row.update(kwargs)
    return row


def game_identity(row):
    return tuple(
        row.get(col, "")
        for col in GAME_COLS[:-1]
    )


def match_parent(row):
    return tuple(
        row.get(col, "")
        for col in GAME_COLS[:6]
        if col != "Map"
    )


def text_match_map(row):
    return tuple(
        row.get(col, "")
        for col in (
            "Tournament",
            "Stage",
            "Match Type",
            "Match Name",
            "Map",
        )
    )


def hierarchy_identity(row):
    return tuple(
        row.get(col, "")
        for col in HIERARCHY_COLS
    )


def hierarchy_parent(row):
    return tuple(
        row.get(col, "")
        for col in (
            "Tournament",
            "Tournament ID",
            "Stage",
            "Stage ID",
            "Match Type",
        )
    )


def audit_games(
    year,
    rows,
    global_game_by_year,
    hierarchy_parents,
    examples,
    caps,
    cross_index,
):
    kind = "Games and matches"

    if rows is None:
        return summary(
            year,
            kind,
            False,
            Notes="Per-season game ID mapping is missing",
        )

    by_game = defaultdict(set)
    by_match = defaultdict(set)
    by_text = defaultdict(set)

    missing_ids = 0
    no_hierarchy = 0

    for row in rows:
        gid = row["Game ID"]
        mid = row["Match ID"]

        if not gid or not mid:
            missing_ids += 1

            example(
                examples, caps, year, kind,
                "Missing Game ID or Match ID",
                gid or mid,
                text_match_map(row),
            )

        if gid:
            by_game[gid].add(game_identity(row))
            by_text[text_match_map(row)].add(gid)

            cross_index[kind][gid][year].add(
                str(game_identity(row))
            )

        if mid:
            by_match[mid].add(match_parent(row))

            cross_index["Matches"][mid][year].add(
                str(match_parent(row))
            )

        if hierarchy_parents is not None:
            if hierarchy_parent(row) not in hierarchy_parents:
                no_hierarchy += 1

                example(
                    examples, caps, year, kind,
                    "Game mapping has no hierarchy row",
                    gid,
                    hierarchy_parent(row),
                )

    conflict_game = {
        gid: contexts
        for gid, contexts in by_game.items()
        if len(contexts) > 1
    }

    conflict_match = {
        mid: contexts
        for mid, contexts in by_match.items()
        if len(contexts) > 1
    }

    for gid, contexts in sorted(conflict_game.items())[:EXAMPLE_LIMIT]:
        example(
            examples, caps, year, kind,
            "Game ID with conflicting context",
            gid,
            sorted(contexts)[:3],
        )

    for mid, contexts in sorted(conflict_match.items())[:EXAMPLE_LIMIT]:
        example(
            examples, caps, year, kind,
            "Match ID with conflicting context",
            mid,
            sorted(contexts)[:3],
        )

    repeated_keys = {
        key: gids
        for key, gids in by_text.items()
        if len(gids) > 1
    }

    for key, gids in sorted(repeated_keys.items())[:EXAMPLE_LIMIT]:
        example(
            examples, caps, year, kind,
            "One text match-map key has multiple Game IDs",
            ", ".join(sorted(gids)),
            key,
        )

    global_for_year = global_game_by_year.get(str(year), {})

    absent_ids = set(by_game) - set(global_for_year)

    differing = {
        gid
        for gid, contexts in by_game.items()
        if gid in global_for_year
        and not contexts.issubset(global_for_year[gid])
    }

    only_global = set(global_for_year) - set(by_game)

    for gid in sorted(absent_ids)[:EXAMPLE_LIMIT]:
        example(
            examples, caps, year, kind,
            "Game ID not found in global mapping",
            gid,
            list(by_game[gid])[:1],
        )

    for gid in sorted(differing)[:EXAMPLE_LIMIT]:
        example(
            examples, caps, year, kind,
            "Game ID context differs from global mapping",
            gid,
            (
                f"season={list(by_game[gid])[:1]}; "
                f"global={list(global_for_year[gid])[:1]}"
            ),
        )

    for gid in sorted(only_global)[:EXAMPLE_LIMIT]:
        example(
            examples, caps, year, kind,
            "Global Game ID missing from season mapping",
            gid,
            list(global_for_year[gid])[:1],
        )

    duplicate_rows = len(rows) - len({
        tuple(sorted(row.items()))
        for row in rows
    })

    return summary(
        year,
        kind,
        Rows=len(rows),
        **{
            "Unique IDs": len(by_game),
            "Unique Match IDs": len(by_match),
            "Duplicate Full Rows": duplicate_rows,
            "Missing IDs": missing_ids,
            "IDs With Multiple Names/Contexts": len(conflict_game),
            "ID Identity Conflicts": (
                f"Game IDs: {len(conflict_game)}; "
                f"Match IDs: {len(conflict_match)}"
            ),
            "Text Match-Map Keys With Multiple Game IDs": len(repeated_keys),
            "IDs Missing From Global": len(absent_ids),
            "Records Differing From Global": len(differing),
            "Global IDs Missing From Season": len(only_global),
            "Game Rows Missing Hierarchy Reference": (
                no_hierarchy
                if hierarchy_parents is not None
                else "Not checked"
            ),
            "Notes": (
                "Repeated maps may be real; "
                "do not deduplicate by match text alone."
            ),
        },
    )


def audit_entity(
    year,
    kind,
    rows,
    global_rows,
    id_col,
    name_col,
    examples,
    caps,
    cross_index,
):
    if rows is None:
        return summary(
            year,
            kind,
            False,
            Notes=f"Per-season {kind.lower()} ID file is missing",
        )

    by_id = defaultdict(set)
    missing = 0

    for row in rows:
        ident = row[id_col]
        name = row[name_col]

        if not ident:
            missing += 1

            example(
                examples, caps, year, kind,
                "Missing ID",
                name,
                row,
            )
        else:
            by_id[ident].add(name)
            cross_index[kind][ident][year].add(name)

    global_pairs = {
        (row[id_col], row[name_col])
        for row in global_rows
    }

    global_ids = {
        row[id_col]
        for row in global_rows
        if row[id_col]
    }

    absent = set(by_id) - global_ids

    differing = {
        (ident, name)
        for ident, names in by_id.items()
        for name in names
        if ident in global_ids
        and (ident, name) not in global_pairs
    }

    conflict = {
        ident: names
        for ident, names in by_id.items()
        if len(names) > 1
    }

    for ident, names in sorted(conflict.items())[:EXAMPLE_LIMIT]:
        example(
            examples, caps, year, kind,
            "One ID has multiple display names",
            ident,
            sorted(names)[:5],
        )

    for ident in sorted(absent)[:EXAMPLE_LIMIT]:
        example(
            examples, caps, year, kind,
            "ID not found in global mapping",
            ident,
            sorted(by_id[ident])[:5],
        )

    for ident, name in sorted(differing)[:EXAMPLE_LIMIT]:
        example(
            examples, caps, year, kind,
            "ID/name pair differs from global mapping",
            ident,
            name,
        )

    duplicate_rows = len(rows) - len({
        (row[id_col], row[name_col])
        for row in rows
    })

    return summary(
        year,
        kind,
        Rows=len(rows),
        **{
            "Unique IDs": len(by_id),
            "Duplicate Full Rows": duplicate_rows,
            "Missing IDs": missing,
            "IDs With Multiple Names/Contexts": len(conflict),
            "ID Identity Conflicts": len(conflict),
            "IDs Missing From Global": len(absent),
            "Records Differing From Global": len(differing),
            "Notes": (
                "Names can change or repeat; "
                "treat differences as review flags, not deletions."
            ),
        },
    )


def audit_hierarchy(
    year,
    rows,
    global_hierarchy_by_year,
    examples,
    caps,
    cross_index,
):
    kind = "Tournament/stage/match-type IDs"

    if rows is None:
        return summary(
            year,
            kind,
            False,
            Notes="Per-season tournament hierarchy is missing",
        )

    by_tournament = defaultdict(set)
    by_stage = defaultdict(set)
    by_type = defaultdict(set)

    missing = 0

    for row in rows:
        tid = row["Tournament ID"]
        sid = row["Stage ID"]
        mtid = row["Match Type ID"]

        if not all((tid, sid, mtid)):
            missing += 1

            example(
                examples, caps, year, kind,
                "Missing hierarchy ID",
                "/".join((tid, sid, mtid)),
                row,
            )

        if tid:
            by_tournament[tid].add(row["Tournament"])

            cross_index["Tournaments"][tid][year].add(
                row["Tournament"]
            )

        if sid:
            ctx = (
                tid,
                row["Tournament"],
                row["Stage"],
            )

            by_stage[sid].add(ctx)

            cross_index["Stages"][sid][year].add(
                str(ctx)
            )

        if mtid:
            ctx = (
                tid,
                sid,
                row["Match Type"],
            )

            by_type[mtid].add(ctx)

            cross_index["Match Types"][mtid][year].add(
                str(ctx)
            )

    tournament_conflicts = {
        ident: names
        for ident, names in by_tournament.items()
        if len(names) > 1
    }

    stage_reuse = {
        ident: values
        for ident, values in by_stage.items()
        if len(values) > 1
    }

    type_reuse = {
        ident: values
        for ident, values in by_type.items()
        if len(values) > 1
    }

    checks = (
        ("Tournament ID with multiple names", tournament_conflicts),
        ("Stage ID reused across contexts", stage_reuse),
        ("Match Type ID reused across contexts", type_reuse),
    )

    for issue, mapping in checks:
        for ident, contexts in sorted(mapping.items())[:EXAMPLE_LIMIT]:
            example(
                examples, caps, year, kind,
                issue,
                ident,
                sorted(contexts)[:5],
            )

    global_rows = global_hierarchy_by_year.get(str(year), set())

    local_rows = {
        hierarchy_identity(row)
        for row in rows
    }

    missing_from_global = local_rows - global_rows
    only_global = global_rows - local_rows

    for values in sorted(missing_from_global)[:EXAMPLE_LIMIT]:
        example(
            examples, caps, year, kind,
            "Hierarchy record absent from global file",
            "/".join((values[1], values[3], values[5])),
            values,
        )

    for values in sorted(only_global)[:EXAMPLE_LIMIT]:
        example(
            examples, caps, year, kind,
            "Global hierarchy record absent from season",
            "/".join((values[1], values[3], values[5])),
            values,
        )

    return summary(
        year,
        kind,
        Rows=len(rows),
        **{
            "Unique IDs": len(by_tournament),
            "Duplicate Full Rows": len(rows) - len(local_rows),
            "Missing IDs": missing,
            "IDs With Multiple Names/Contexts": (
                f"Tournament: {len(tournament_conflicts)}; "
                f"Stage: {len(stage_reuse)}; "
                f"Match type: {len(type_reuse)}"
            ),
            "ID Identity Conflicts": len(tournament_conflicts),
            "Records Differing From Global": len(missing_from_global),
            "Global IDs Missing From Season": len(only_global),
            "Notes": (
                "Unique IDs = tournament IDs. "
                "Other IDs may be scoped to parents; "
                "investigate reuse."
            ),
        },
    )


def cross_season_report(cross_index):
    output = []

    for kind, by_id in sorted(cross_index.items()):
        for ident, per_year in sorted(by_id.items()):
            if len(per_year) < 2:
                continue

            contexts = {
                context
                for values in per_year.values()
                for context in values
            }

            output.append({
                "Record Type": kind,
                "Identifier": ident,
                "Years": ", ".join(
                    map(str, sorted(per_year))
                ),
                "Year Count": len(per_year),
                "Distinct Contexts": len(contexts),
                "Details": " | ".join(
                    sorted(contexts)[:3]
                )[:600],
            })

    return output


def main():
    all_games = load_csv(
        RAW / "all_ids" / "all_matches_games_ids.csv",
        (*GAME_COLS, "Year"),
    )

    all_players = load_csv(
        RAW / "all_ids" / "all_players_ids.csv",
        ("Player", "Player ID"),
    )

    all_teams = load_csv(
        RAW / "all_ids" / "all_teams_ids.csv",
        ("Team", "Team ID"),
    )

    all_hierarchy = load_csv(
        RAW / "all_ids" /
        "all_tournaments_stages_match_types_ids.csv",
        (*HIERARCHY_COLS, "Year"),
    )

    required_files = (
        ("all_matches_games_ids.csv", all_games),
        ("all_players_ids.csv", all_players),
        ("all_teams_ids.csv", all_teams),
        (
            "all_tournaments_stages_match_types_ids.csv",
            all_hierarchy,
        ),
    )

    for filename, records in required_files:
        if records is None:
            raise FileNotFoundError(
                f"Required data/raw/all_ids/{filename} is missing"
            )

    global_games = defaultdict(
        lambda: defaultdict(set)
    )

    global_hierarchy = defaultdict(set)

    for row in all_games:
        if row["Year"] and row["Game ID"]:
            global_games[row["Year"]][row["Game ID"]].add(
                game_identity(row)
            )

    for row in all_hierarchy:
        if row["Year"]:
            global_hierarchy[row["Year"]].add(
                hierarchy_identity(row)
            )

    findings = []
    examples = []
    caps = Counter()

    cross_index = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(set)
        )
    )

    for year in YEARS:
        ids = RAW / f"vct_{year}" / "ids"

        games = load_csv(
            ids / "tournaments_stages_matches_games_ids.csv",
            GAME_COLS,
        )

        players = load_csv(
            ids / "players_ids.csv",
            ("Player", "Player ID"),
        )

        teams = load_csv(
            ids / "teams_ids.csv",
            ("Team", "Team ID"),
        )

        hierarchy = load_csv(
            ids / "tournaments_stages_match_types_ids.csv",
            HIERARCHY_COLS,
        )

        parents = (
            {
                hierarchy_parent(row)
                for row in hierarchy
            }
            if hierarchy is not None
            else None
        )

        game_result = audit_games(
            year,
            games,
            global_games,
            parents,
            examples,
            caps,
            cross_index,
        )

        findings.append(game_result)

        findings.append(
            audit_entity(
                year,
                "Players",
                players,
                all_players,
                "Player ID",
                "Player",
                examples,
                caps,
                cross_index,
            )
        )

        findings.append(
            audit_entity(
                year,
                "Teams",
                teams,
                all_teams,
                "Team ID",
                "Team",
                examples,
                caps,
                cross_index,
            )
        )

        findings.append(
            audit_hierarchy(
                year,
                hierarchy,
                global_hierarchy,
                examples,
                caps,
                cross_index,
            )
        )

        print(
            f"{year}: "
            f"{game_result['Unique IDs']} games, "
            f"{game_result['Unique Match IDs']} matches; "
            f"repeated text match-map keys: "
            f"{game_result['Text Match-Map Keys With Multiple Game IDs']}; "
            f"game context mismatches vs global: "
            f"{game_result['Records Differing From Global']}; "
            f"unmatched hierarchy rows: "
            f"{game_result['Game Rows Missing Hierarchy Reference']}"
        )

    cross = cross_season_report(cross_index)

    OUT.mkdir(parents=True, exist_ok=True)

    write_csv(
        OUT / "identifier_audit_summary.csv",
        SUMMARY_COLUMNS,
        findings,
    )

    write_csv(
        OUT / "identifier_audit_examples.csv",
        EXAMPLE_COLUMNS,
        examples,
    )

    write_csv(
        OUT / "identifier_cross_season.csv",
        CROSS_COLUMNS,
        cross,
    )

    notes = (
        "SHARED IDENTIFIER AUDIT - 2021 THROUGH 2026\n"
        "Read-only: no raw or cleaned dataset was changed.\n\n"
        "Summary has four rows per season:\n"
        "Games/matches, Players, Teams, "
        "Tournament/stage/match-type IDs.\n\n"
        "Global comparison uses data/raw/all_ids "
        "and the same Year for year-specific tables.\n"
        "Game ID = one map game.\n"
        "Match ID = one match series, potentially several games.\n"
        "Game mappings are checked against tournament hierarchy rows.\n"
        "Repeated match-map text is NOT proof of duplication.\n"
        "Multiple display names for one ID may indicate "
        "renaming or a data issue.\n"
        "Cross-season reused IDs are reported "
        "but are NOT automatically treated as wrong.\n"
        "Missing mapping records and conflicting contexts "
        "are investigation flags only.\n"
        "Per-season player/team ID files are checked "
        "when available.\n"
        f"At most {EXAMPLE_LIMIT} examples per year, "
        "entity type and issue are included.\n"
        "This audit does not check score, kills, "
        "economy or full player statistics.\n"
        "Text comparisons are exact except "
        "for trimming surrounding whitespace.\n"
    )

    (OUT / "identifier_audit_notes.txt").write_text(
        notes,
        encoding="utf-8",
    )

    print("\nReports saved to docs/shared/:")
    print(" - identifier_audit_summary.csv")
    print(" - identifier_audit_examples.csv")
    print(" - identifier_cross_season.csv")
    print(" - identifier_audit_notes.txt")

    print(
        f"\nCross-season reuse rows: {len(cross):,} "
        "(not automatically errors)"
    )


if __name__ == "__main__":
    main()
