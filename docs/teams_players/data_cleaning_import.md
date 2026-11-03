# Teams & Players – Data Cleaning and Import

## 1. Data Source and Cleaning

Player performance statistics were obtained from the VCT dataset's `matches/overview.csv` files for seasons 2022–2026. Player statistics for 2021 were not imported.

The cleaning process was implemented in `scripts/data_cleaning/teams_players/build_player_map_stats.py`.

Only records where `Side = both` were retained. Rows labelled `All Maps` were excluded because they contain aggregated statistics rather than individual map results.

Each record was matched against the existing database mappings using seven fields: tournament, stage, match type, match name, map, player and team. Text was normalised to handle differences in capitalisation and spacing.

Selected season-specific name mappings were also applied where the source and database names differed. Records with no matching database entry or multiple possible matches were excluded to avoid assigning incorrect IDs.

The script also checks for duplicate `(game_id, player_id)` combinations and invalid statistics. Kills, deaths and assists must be non-negative whole numbers, while ACS and rating must be valid non-negative numbers. Missing numeric values are allowed.

## 2. Cleaning Results

The following player-map records were successfully cleaned and imported into PostgreSQL:

| Season | Imported Records |
|------|--------:|
| 2022 | 86,820 |
| 2023 | 8,300 |
| 2024 | 11,040 |
| 2025 | 12,760 |
| 2026 | 8,860 |
| **Total** | **127,780** |

For 2022, 1,566 candidate records were excluded because their database mappings were unmatched or ambiguous. A partial export was permitted for this season, provided these were the only validation issues.

For the remaining seasons, unresolved validation issues stop the export.

The cleaned records were saved as separate CSV files without modifying the original dataset.

## 3. PostgreSQL Import

The cleaned CSV files were imported using `scripts/data_cleaning/teams_players/import_player_map_stats.py`.

The importer performs the following checks before and during import:

1. Verifies the CSV columns and ensures the file is not empty.
2. Checks the development database connection.
3. Prevents importing a season that already contains player statistics.
4. Inserts the records into `player_map_stats` using PostgreSQL `COPY`.
5. Compares the imported record count against the CSV count and the change in total table records.

The import runs inside a database transaction. If validation fails, the transaction is rolled back.

By default, the script performs a test import and rolls back the changes. The `--commit` option is required to save the imported records.

## 4. Database Validation

After importing the records into the Neon `teams-players-dev` branch, SQL queries were used to check the data.

The validation results showed:

- 0 duplicate `(game_id, player_id)` records
- 0 invalid game references
- 0 invalid player references
- 0 invalid team references
- 0 negative statistics

Some records contained missing performance statistics:

| Statistic | NULL Records |
|-------|-------:|
| Kills | 20 |
| Deaths | 20 |
| Assists | 20 |
| ACS | 193 |
| Rating | 4,879 |

Missing values were stored as `NULL` rather than being replaced with zero.

The table's composite primary key, foreign keys, NOT NULL requirements and non-negative CHECK constraint were also verified against the live PostgreSQL schema.

## 5. Limitations and Handover Notes

The cleaning script currently uses an absolute path to the source dataset, which must be updated when running it on another computer.

Some season-specific name mappings, particularly `Mega Minors` to `NRG Esports`, require supporting evidence before being treated as confirmed corrections.

If a cleaning run fails validation, a previously exported CSV may still exist. The output file should therefore be checked before any future import.

The importer is configured for the development database. Integration into the shared Neon database should be coordinated with the team to avoid conflicting with existing records.