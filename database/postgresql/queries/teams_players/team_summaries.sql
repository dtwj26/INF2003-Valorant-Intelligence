
-- retrieve team appearances for a selected season

SELECT
    t.team_id,
    t.team_name,
    COUNT(DISTINCT mp.match_id) AS match_series,
    COUNT(DISTINCT mg.game_id) AS map_games
FROM match_participants AS mp
JOIN teams AS t
    ON t.team_id = mp.team_id
JOIN match_series AS ms
    ON ms.match_id = mp.match_id
JOIN map_games AS mg
    ON mg.match_id = ms.match_id
WHERE ms.season = %(season)s
    AND (
        %(tournament_id)s IS NULL
        OR ms.tournament_id = %(tournament_id)s
    )
    AND (
        %(map_name)s IS NULL
        OR mg.map_name = %(map_name)s
    )
GROUP BY
    t.team_id,
    t.team_name
ORDER BY
    map_games DESC,
    t.team_name,
    t.team_id;
