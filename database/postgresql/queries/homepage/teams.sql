
-- Homepage: Participating Teams
-- Season is supplied by the Python backend.

WITH selected_season AS (
    SELECT %(season)s::SMALLINT AS season
)

SELECT DISTINCT
    t.team_id::TEXT AS id,
    t.team_name AS name

FROM teams t

JOIN match_participants mp
    ON t.team_id = mp.team_id

JOIN match_series m
    ON mp.match_id = m.match_id

JOIN selected_season s
    ON m.season = s.season

ORDER BY name ASC, id ASC;
