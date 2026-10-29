-- Final PostgreSQL Import Validation
-- VCT 2021-2026

WITH match_stats AS (
    SELECT
        season,
        COUNT(*) AS total_matches,
        COUNT(DISTINCT tournament_id) AS tournaments
    FROM match_series
    GROUP BY season
),

game_stats AS (
    SELECT
        m.season,
        COUNT(*) AS total_games
    FROM map_games g
    JOIN match_series m ON g.match_id = m.match_id
    GROUP BY m.season
),

match_coverage AS (
    SELECT
        m.season,
        m.match_id,
        COUNT(mp.team_id) AS team_count
    FROM match_series m
    LEFT JOIN match_participants mp
        ON m.match_id = mp.match_id
    GROUP BY m.season, m.match_id
),

participant_stats AS (
    SELECT
        season,
        COUNT(*) FILTER (
            WHERE team_count = 2
        ) AS complete_matches
    FROM match_coverage
    GROUP BY season
),

agent_stats AS (
    SELECT
        m.season,
        COUNT(*) AS agent_selections,
        COUNT(DISTINCT s.game_id) AS games_with_agents
    FROM agent_selections s
    JOIN map_games g ON s.game_id = g.game_id
    JOIN match_series m ON g.match_id = m.match_id
    GROUP BY m.season
)

SELECT
    ms.season,
    ms.tournaments,
    ms.total_matches,
    gs.total_games,

    ps.complete_matches,

    ms.total_matches - ps.complete_matches
        AS incomplete_matches,

    COALESCE(a.agent_selections, 0)
        AS agent_selections,

    COALESCE(a.games_with_agents, 0)
        AS games_with_agents,

    gs.total_games - COALESCE(a.games_with_agents, 0)
        AS games_without_agents

FROM match_stats ms
JOIN game_stats gs ON ms.season = gs.season
JOIN participant_stats ps ON ms.season = ps.season
LEFT JOIN agent_stats a ON ms.season = a.season

ORDER BY ms.season;
