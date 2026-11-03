

-- audit agent-selection completeness by map game
-- flag games with missing or unusual selection/player counts
-- results require investigation; unusual counts do not prove invalid data
-- read-only validation query


WITH selections_per_game AS (
    SELECT
        game_id,
        COUNT(*) AS selection_rows,
        COUNT(DISTINCT player_id) AS distinct_players
    FROM agent_selections
    GROUP BY game_id
)
SELECT
    ms.season,
    COUNT(*) AS total_map_games,
    COUNT(*) FILTER (
        WHERE spg.game_id IS NULL
    ) AS games_without_selections,
    COUNT(*) FILTER (
        WHERE spg.game_id IS NOT NULL
          AND spg.selection_rows <> 10
    ) AS games_with_unusual_selections,
    COUNT(*) FILTER (
        WHERE spg.game_id IS NOT NULL
          AND spg.distinct_players <> 10
    ) AS games_with_unusual_player_counts
FROM map_games mg
JOIN match_series ms
    ON mg.match_id = ms.match_id
LEFT JOIN selections_per_game spg
    ON mg.game_id = spg.game_id
GROUP BY ms.season
ORDER BY ms.season;
