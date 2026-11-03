-- One player's statistics for one map game.
-- Missing statistics remain NULL.

CREATE TABLE IF NOT EXISTS player_game_stats (
    game_id BIGINT NOT NULL,
    player_id BIGINT NOT NULL,

    acs NUMERIC(8, 2) CHECK (acs >= 0),
    kills SMALLINT CHECK (kills >= 0),
    deaths SMALLINT CHECK (deaths >= 0),
    assists SMALLINT CHECK (assists >= 0),

    CONSTRAINT pk_player_game_stats
        PRIMARY KEY (game_id, player_id),

    CONSTRAINT fk_player_stats_game
        FOREIGN KEY (game_id)
        REFERENCES map_games(game_id),

    CONSTRAINT fk_player_stats_player
        FOREIGN KEY (player_id)
        REFERENCES players(player_id)
);

-- Helps retrieve a player's statistics across multiple games.
CREATE INDEX IF NOT EXISTS idx_player_game_stats_player
    ON player_game_stats(player_id);