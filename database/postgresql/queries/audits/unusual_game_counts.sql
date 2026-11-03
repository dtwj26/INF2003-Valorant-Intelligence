

-- investigate unusual agent-selection counts in 2021 and 2022
-- group games by selection count and distinct player count
-- diagnostic only; unusual counts do not necessarily mean invalid data
-- read-only validation query


WITH game_counts AS (
    SELECT
        ms.season,
        mg.game_id,
        COUNT(a.game_id) AS selections,
        COUNT(DISTINCT a.player_id) AS players
    FROM map_games mg
    JOIN match_series ms
        ON mg.match_id = ms.match_id
    LEFT JOIN agent_selections a
        ON mg.game_id = a.game_id
    WHERE ms.season IN (2021, 2022)
    GROUP BY ms.season, mg.game_id
)
SELECT
    season,
    selections,
    players,
    COUNT(*) AS game_count
FROM game_counts
WHERE selections <> 10
   OR players <> 10
GROUP BY season, selections, players
ORDER BY season, game_count DESC;
