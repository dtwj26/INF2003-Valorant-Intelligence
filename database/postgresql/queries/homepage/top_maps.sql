-- Homepage: Top 5 Most Played Maps
-- Change the year to test another season.

WITH selected_season AS (
    SELECT %(season)s::SMALLINT AS season
)

SELECT
    g.map_name AS name,
    COUNT(DISTINCT g.game_id) AS games

FROM map_games g

JOIN match_series m
    ON g.match_id = m.match_id

JOIN selected_season s
    ON m.season = s.season

GROUP BY g.map_name

ORDER BY games DESC, name ASC

LIMIT 5;
