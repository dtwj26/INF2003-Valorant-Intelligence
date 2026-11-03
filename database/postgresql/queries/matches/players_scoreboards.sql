SELECT
    s.player_id,
    s.team_id,
    s.agent_id,
    p.player_name,
    t.team_name,
    a.agent_name,
    ps.acs,
    ps.kills,
    ps.deaths,
    ps.assists,
    s.game_id
FROM agent_selections s
JOIN players p
    ON s.player_id = p.player_id
JOIN teams t
    ON s.team_id = t.team_id
JOIN agents a
    ON s.agent_id = a.agent_id
LEFT JOIN player_map_stats ps
    ON s.game_id = ps.game_id
    AND s.player_id = ps.player_id
WHERE s.game_id = %(game_id)s;