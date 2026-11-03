
-- check agent-selection coverage by season
-- counts teams, players and games represented in agent selections
-- read-only validation query

SELECT
    ms.season,
    COUNT(DISTINCT a.team_id) AS teams,
    COUNT(DISTINCT a.player_id) AS players,
    COUNT(DISTINCT a.game_id) AS map_games,
    COUNT(*) AS agent_selections
FROM agent_selections AS a
JOIN map_games AS mg
    ON a.game_id = mg.game_id
JOIN match_series AS ms
    ON mg.match_id = ms.match_id
GROUP BY ms.season
ORDER BY ms.season;
