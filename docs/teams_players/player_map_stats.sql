
-- member 2: player-map performance table
-- schema reference for the teams and players backend
-- review existing database schema before executing

CREATE TABLE player_map_stats (
    game_id BIGINT NOT NULL,
    player_id BIGINT NOT NULL,
    team_id BIGINT,

    kills INTEGER,
    deaths INTEGER,
    assists INTEGER,
    acs NUMERIC(7,2),
    rating NUMERIC(6,3),

    CONSTRAINT pk_player_map_stats
        PRIMARY KEY (game_id, player_id),

    CONSTRAINT fk_stats_game
        FOREIGN KEY (game_id)
        REFERENCES map_games(game_id),

    CONSTRAINT fk_stats_player
        FOREIGN KEY (player_id)
        REFERENCES players(player_id),

    CONSTRAINT fk_stats_team
        FOREIGN KEY (team_id)
        REFERENCES teams(team_id),

    CONSTRAINT chk_stats_nonnegative
        CHECK (
            (kills IS NULL OR kills >= 0)
            AND (deaths IS NULL OR deaths >= 0)
            AND (assists IS NULL OR assists >= 0)
            AND (acs IS NULL OR acs >= 0)
            AND (rating IS NULL OR rating >= 0)
        )
);
