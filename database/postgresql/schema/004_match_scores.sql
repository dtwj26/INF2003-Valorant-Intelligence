-- Overall match scores.
CREATE TABLE IF NOT EXISTS match_scores (
    match_id BIGINT PRIMARY KEY
        REFERENCES match_series(match_id),

    team_a_score SMALLINT NOT NULL CHECK (team_a_score >= 0),
    team_b_score SMALLINT NOT NULL CHECK (team_b_score >= 0),

    match_result TEXT
);

-- Individual map scores.
CREATE TABLE IF NOT EXISTS map_scores (
    game_id BIGINT PRIMARY KEY
        REFERENCES map_games(game_id),

    team_a_score SMALLINT NOT NULL CHECK (team_a_score >= 0),
    team_b_score SMALLINT NOT NULL CHECK (team_b_score >= 0)
);