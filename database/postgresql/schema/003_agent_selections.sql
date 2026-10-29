-- 003_agent_selections.sql
-- Stores the agents selected by players in individual map games.

-- Agent identity table
CREATE TABLE IF NOT EXISTS agents (
    agent_id BIGINT GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    agent_name TEXT NOT NULL,

    CONSTRAINT chk_agent_name
        CHECK (LENGTH(TRIM(agent_name)) > 0)
);

-- Prevent duplicate agent names with different capitalization.
CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_name_unique
    ON agents (LOWER(TRIM(agent_name)));


-- Agent selections per player, team and map game.
CREATE TABLE IF NOT EXISTS agent_selections (
    game_id BIGINT NOT NULL,
    player_id BIGINT NOT NULL,
    team_id BIGINT NOT NULL,
    agent_id BIGINT NOT NULL,

    CONSTRAINT pk_agent_selections
        PRIMARY KEY (game_id, player_id, agent_id),

    CONSTRAINT fk_selection_game
        FOREIGN KEY (game_id)
        REFERENCES map_games(game_id),

    CONSTRAINT fk_selection_player
        FOREIGN KEY (player_id)
        REFERENCES players(player_id),

    CONSTRAINT fk_selection_team
        FOREIGN KEY (team_id)
        REFERENCES teams(team_id),

    CONSTRAINT fk_selection_agent
        FOREIGN KEY (agent_id)
        REFERENCES agents(agent_id)
);

CREATE INDEX IF NOT EXISTS idx_selection_agent
    ON agent_selections(agent_id);

CREATE INDEX IF NOT EXISTS idx_selection_team
    ON agent_selections(team_id);
