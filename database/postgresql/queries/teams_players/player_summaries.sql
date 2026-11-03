
-- player statistics by season, tournament and map
-- keep players from different teams separate

SELECT
    p.player_id,
    p.player_name,
    t.team_id,
    t.team_name,
    COUNT(*) AS map_games,
    SUM(s.kills) AS kills,
    SUM(s.deaths) AS deaths,
    SUM(s.assists) AS assists,
    ROUND(AVG(s.acs), 2) AS avg_acs,
    ROUND(
        SUM(s.kills)::numeric /
        NULLIF(SUM(s.deaths), 0),
        2
    ) AS kd_ratio

FROM player_map_stats AS s

JOIN players AS p
    ON p.player_id = s.player_id

JOIN teams AS t
    ON t.team_id = s.team_id

JOIN map_games AS mg
    ON mg.game_id = s.game_id

JOIN match_series AS ms
    ON ms.match_id = mg.match_id

WHERE ms.season = %(season)s

    AND (
        %(tournament_id)s IS NULL
        OR ms.tournament_id::text = %(tournament_id)s
    )

    AND (
        %(map_name)s IS NULL
        OR mg.map_name = %(map_name)s
    )

GROUP BY
    p.player_id,
    p.player_name,
    t.team_id,
    t.team_name

ORDER BY
    map_games DESC,
    p.player_name,
    t.team_name,
    p.player_id,
    t.team_id

LIMIT %(limit)s;
