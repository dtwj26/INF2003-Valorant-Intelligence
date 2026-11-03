
-- one player profile per season and selected scope
-- combine statistics across teams

WITH scoped AS (
    SELECT
        s.player_id,
        s.team_id,
        s.kills,
        s.deaths,
        s.assists,
        s.acs
    FROM player_map_stats s
    JOIN map_games mg
        ON mg.game_id = s.game_id
    JOIN match_series ms
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
),
totals AS (
    SELECT
        player_id,
        COUNT(*) AS map_games,
        SUM(kills) AS kills,
        SUM(deaths) AS deaths,
        SUM(assists) AS assists,
        ROUND(AVG(acs), 2) AS avg_acs,
        ROUND(
            SUM(kills)::numeric /
            NULLIF(SUM(deaths), 0),
            2
        ) AS kd_ratio
    FROM scoped
    GROUP BY player_id
),
team_counts AS (
    SELECT
        player_id,
        team_id,
        COUNT(*) AS team_maps
    FROM scoped
    GROUP BY player_id, team_id
),
ranked_teams AS (
    SELECT
        player_id,
        team_id,
        ROW_NUMBER() OVER (
            PARTITION BY player_id
            ORDER BY team_maps DESC, team_id
        ) AS team_rank
    FROM team_counts
)
SELECT
    p.player_id,
    p.player_name,
    t.team_id,
    t.team_name,
    totals.map_games,
    totals.kills,
    totals.deaths,
    totals.assists,
    totals.avg_acs,
    totals.kd_ratio,
    ARRAY(
        SELECT tc.team_id::text
        FROM team_counts tc
        WHERE tc.player_id = totals.player_id
        ORDER BY tc.team_maps DESC, tc.team_id
    ) AS team_ids
FROM totals
JOIN players p
    ON p.player_id = totals.player_id
JOIN ranked_teams rt
    ON rt.player_id = totals.player_id
    AND rt.team_rank = 1
JOIN teams t
    ON t.team_id = rt.team_id
ORDER BY
    totals.map_games DESC,
    p.player_name,
    p.player_id;
