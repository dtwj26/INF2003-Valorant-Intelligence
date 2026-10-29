-- =================================================
-- INF2003 Valorant Competitive Intelligence System
-- Shared PostgreSQL Core Schema - Version 001
-- ==================================================

-- 1. TOURNAMENTS
CREATE TABLE IF NOT EXISTS tournaments (
    tournament_id BIGINT PRIMARY KEY,
    tournament_name TEXT NOT NULL,

    CONSTRAINT chk_tournament_name
        CHECK (LENGTH(TRIM(tournament_name)) > 0)
);


-- 2. TEAMS
CREATE TABLE IF NOT EXISTS teams (
    team_id BIGINT PRIMARY KEY,
    team_name TEXT NOT NULL,

    CONSTRAINT chk_team_name
        CHECK (LENGTH(TRIM(team_name)) > 0)
);


-- 3. PLAYERS
CREATE TABLE IF NOT EXISTS players (
    player_id BIGINT PRIMARY KEY,
    player_name TEXT NOT NULL,

    CONSTRAINT chk_player_name
        CHECK (LENGTH(TRIM(player_name)) > 0)
);


-- 4. MATCH SERIES
CREATE TABLE IF NOT EXISTS match_series (
    match_id BIGINT PRIMARY KEY,

    tournament_id BIGINT NOT NULL,

    season SMALLINT NOT NULL,

    match_name TEXT NOT NULL,

    stage_name TEXT,
    source_stage_id BIGINT,
    match_type TEXT,

    CONSTRAINT fk_match_tournament
        FOREIGN KEY (tournament_id)
        REFERENCES tournaments(tournament_id),

    CONSTRAINT chk_match_season
        CHECK (season BETWEEN 2021 AND 2100),

    CONSTRAINT chk_match_name
        CHECK (LENGTH(TRIM(match_name)) > 0)
);


-- 5. MAP GAMES
CREATE TABLE IF NOT EXISTS map_games (
    game_id BIGINT PRIMARY KEY,

    match_id BIGINT NOT NULL,

    map_name TEXT NOT NULL,

    CONSTRAINT fk_game_match
        FOREIGN KEY (match_id)
        REFERENCES match_series(match_id),

    CONSTRAINT chk_real_map
        CHECK (
            LENGTH(TRIM(map_name)) > 0
            AND LOWER(TRIM(map_name)) <> 'all maps'
        )
);


-- Basic indexes on frequently used relationships
CREATE INDEX IF NOT EXISTS idx_match_season
    ON match_series(season);

CREATE INDEX IF NOT EXISTS idx_match_tournament
    ON match_series(tournament_id);

CREATE INDEX IF NOT EXISTS idx_game_match
    ON map_games(match_id);
