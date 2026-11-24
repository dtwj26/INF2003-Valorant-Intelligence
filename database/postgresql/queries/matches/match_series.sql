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
    s.match_result,
    CASE
        WHEN %(search)s::TEXT IS NULL THEN 0::REAL
        -- Exact text matches should appear before approximate name matches.
        WHEN STRPOS(
            LOWER(ta.team_name || ' ' || tb.team_name || ' ' ||
                  t.tournament_name || ' ' || m.match_id::TEXT),
            %(search)s
        ) > 0 THEN 1::REAL
        ELSE word_similarity(%(search)s, m.match_name)
    END AS search_score
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
  AND (
      %(search)s::TEXT IS NULL
      OR m.match_id IN (
          SELECT search_match.match_id
          FROM match_series search_match
          -- psycopg2 requires a doubled percent sign for the pg_trgm operator.
          WHERE search_match.match_name %%> %(search)s
      )
      -- Keep the existing literal search for team names, tournaments and IDs.
      OR STRPOS(
          LOWER(ta.team_name || ' ' || tb.team_name || ' ' ||
                t.tournament_name || ' ' || m.match_id::TEXT),
          %(search)s
      ) > 0
  )
ORDER BY search_score DESC, m.match_id DESC;
