-- Read overall match results in the A/B order stored in match_participants.
-- Python supplies the season and optional filters as query parameters.
SELECT
    m.match_id::TEXT AS id,
    m.season,
    m.match_name,
    m.stage_name AS stage,
    m.match_type,
    m.tournament_id::TEXT AS tournament_id,
    t.tournament_name AS tournament,
    ARRAY[pa.team_id::TEXT, pb.team_id::TEXT] AS team_ids,
    ARRAY[ta.team_name, tb.team_name] AS team_names,
    ARRAY[s.team_a_score, s.team_b_score] AS score,
    s.match_result
FROM match_series m
JOIN match_scores s ON s.match_id = m.match_id
JOIN tournaments t ON t.tournament_id = m.tournament_id
JOIN match_participants pa ON pa.match_id = m.match_id AND pa.team_slot = 'A'
JOIN match_participants pb ON pb.match_id = m.match_id AND pb.team_slot = 'B'
JOIN teams ta ON ta.team_id = pa.team_id
JOIN teams tb ON tb.team_id = pb.team_id
WHERE m.season = %(season)s
  AND (%(tournament_id)s::BIGINT IS NULL OR m.tournament_id = %(tournament_id)s)
  AND (
      %(map_name)s::TEXT IS NULL
      OR EXISTS (
          SELECT 1
          FROM map_games g
          WHERE g.match_id = m.match_id AND g.map_name = %(map_name)s
      )
  )
ORDER BY m.match_id DESC;
