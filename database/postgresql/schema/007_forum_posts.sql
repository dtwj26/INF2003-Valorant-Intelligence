-- =================================================
-- INF2003 Valorant Competitive Intelligence System
-- Forums Polyglot Feature Schema - Version 007
-- =================================================

CREATE TABLE IF NOT EXISTS forum_posts (
    post_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    title TEXT NOT NULL,
    category TEXT NOT NULL,
    author_name TEXT NOT NULL,
    body TEXT NOT NULL,

    -- Optional relational links to existing VCT entities
    season SMALLINT NULL,
    team_id BIGINT NULL REFERENCES teams(team_id) ON DELETE SET NULL,
    match_id BIGINT NULL REFERENCES match_series(match_id) ON DELETE SET NULL,
    map_name TEXT NULL,
    agent_name TEXT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_forum_title
        CHECK (LENGTH(TRIM(title)) > 0),

    CONSTRAINT chk_forum_author
        CHECK (LENGTH(TRIM(author_name)) > 0),

    CONSTRAINT chk_forum_body
        CHECK (LENGTH(TRIM(body)) > 0),

    CONSTRAINT chk_forum_category
        CHECK (
            category IN (
                'Matchup Discussion',
                'Tactical Breakdown',
                'Scouting Brief',
                'Agent & Map Meta',
                'General'
            )
        ),

    CONSTRAINT chk_forum_season
        CHECK (season IS NULL OR season BETWEEN 2021 AND 2100)
);

CREATE INDEX IF NOT EXISTS idx_forum_posts_created_at
    ON forum_posts(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_forum_posts_category
    ON forum_posts(category);

CREATE INDEX IF NOT EXISTS idx_forum_posts_team_id
    ON forum_posts(team_id);

CREATE INDEX IF NOT EXISTS idx_forum_posts_match_id
    ON forum_posts(match_id);