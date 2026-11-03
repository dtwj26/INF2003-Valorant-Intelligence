# Teams & Players – Database Schema Design

## 1. Overview

The Teams & Players backend uses PostgreSQL to retrieve team, player and match-related data.

The `player_map_stats` table was added to store individual player performance statistics for each map game. It connects to the existing `map_games`, `players` and `teams` tables through foreign keys.

This document covers the additional table and its constraints, rather than the group's complete database schema.

## 2. Table Structure and Relationships

The `player_map_stats` table contains eight columns:

| Column | Data Type | Description |
|--------|-----------|-------------|
| game_id | BIGINT | References the map game |
| player_id | BIGINT | References the player |
| team_id | BIGINT | References the team |
| kills | INTEGER | Total kills |
| deaths | INTEGER | Total deaths |
| assists | INTEGER | Total assists |
| acs | NUMERIC(7,2) | Average Combat Score |
| rating | NUMERIC(6,3) | Player rating |

The composite primary key `(game_id, player_id)` prevents the same player from having multiple statistics records for a single map game.

Three foreign keys connect the table to the existing database:

- `fk_stats_game`: `game_id` → `map_games(game_id)`
- `fk_stats_player`: `player_id` → `players(player_id)`
- `fk_stats_team`: `team_id` → `teams(team_id)`

Each map game can have multiple player statistics records, while a player can have records across different map games.

## 3. Database Constraints

The table includes the following constraints:

- `game_id` and `player_id` cannot be NULL.
- The composite primary key prevents duplicate player-map records.
- Foreign keys prevent references to non-existent games, players and teams.
- `chk_stats_nonnegative` prevents negative kills, deaths, assists, ACS and rating values.

The performance statistics columns allow NULL values because some statistics are missing from the source dataset. The `team_id` column is also nullable.

The schema definition is available in `docs/teams_players/player_map_stats.sql`.

## 4. Schema and Data Validation

The table structure was checked against the live PostgreSQL database on the Neon `teams-players-dev` branch.

All eight columns matched the SQL schema reference, including their data types and NULL settings.

Additional SQL checks confirmed:

- No duplicate `(game_id, player_id)` records
- No invalid game, player or team references
- No negative performance statistics
- Primary key, foreign keys and CHECK constraint present

The table contains 127,780 imported player-map statistics records across seasons 2022–2026.

The cleaning and import process is documented separately in `data_cleaning_import.md`.

## 5. Query Performance

The 2022 player statistics aggregation query was tested using `EXPLAIN (ANALYZE, BUFFERS)`.

The query processed 86,820 player-map records and returned 8,670 player-team summaries, with an execution time of approximately 132 ms.

PostgreSQL used hash joins and the existing `idx_match_season` index to retrieve and combine the records. An intermediate sorting operation used temporary disk storage.

No additional indexes were introduced after this initial test because the measured execution time was acceptable for the current implementation. Further testing may be needed if the dataset or query workload increases.