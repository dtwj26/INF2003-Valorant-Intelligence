
-- 002_match_participants.sql
-- Links each match series to its participating teams.
-- A match has up to two participating teams: A and B.

CREATE TABLE IF NOT EXISTS match_participants (
    match_id BIGINT NOT NULL,
    team_id BIGINT NOT NULL,
    team_slot CHAR(1) NOT NULL,

    CONSTRAINT pk_match_participants
        PRIMARY KEY (match_id, team_id),

    CONSTRAINT fk_participant_match
        FOREIGN KEY (match_id)
        REFERENCES match_series(match_id),

    CONSTRAINT fk_participant_team
        FOREIGN KEY (team_id)
        REFERENCES teams(team_id),

    CONSTRAINT chk_team_slot
        CHECK (team_slot IN ('A', 'B')),

    CONSTRAINT uq_match_team_slot
        UNIQUE (match_id, team_slot)
);

CREATE INDEX IF NOT EXISTS idx_participant_team
    ON match_participants(team_id);
