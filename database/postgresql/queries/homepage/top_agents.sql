-- Homepage: Top 5 Most Picked Agents

WITH selected_season AS (
    SELECT %(season)s::SMALLINT AS season
)

SELECT
    a.agent_name AS name,
    COUNT(*) AS picks

FROM agent_selections s

JOIN agents a
    ON s.agent_id = a.agent_id

JOIN map_games g
    ON s.game_id = g.game_id

JOIN match_series m
    ON g.match_id = m.match_id

JOIN selected_season ss
    ON m.season = ss.season

GROUP BY a.agent_id, a.agent_name

ORDER BY picks DESC, name ASC

LIMIT 5;