-- Homepage: Summary Statistics
-- Change the year here to test another season.

WITH selected_season AS (
    SELECT %(season)s::SMALLINT AS season
)

SELECT
    s.season,

    -- Count distinct tournaments
    (
        SELECT COUNT(DISTINCT m.tournament_id)
        FROM match_series m
        WHERE m.season = s.season
    ) AS tournaments,

    -- Count match series
    (
        SELECT COUNT(*)
        FROM match_series m
        WHERE m.season = s.season
    ) AS matches,

    -- Count teams that actually participated
    (
        SELECT COUNT(DISTINCT mp.team_id)
        FROM match_participants mp
        JOIN match_series m
            ON mp.match_id = m.match_id
        WHERE m.season = s.season
    ) AS teams

FROM selected_season s;
