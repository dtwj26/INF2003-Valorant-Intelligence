SELECT g.game_id, g.map_name, s.team_a_score, s.team_b_score, g.match_id
FROM map_games g
JOIN map_scores s ON g.game_id = s.game_id
WHERE g.match_id = %(match_id)s;