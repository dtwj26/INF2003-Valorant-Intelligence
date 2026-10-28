HOMEPAGE AGENT CANDIDATE VALIDATION
Input: data/cleaned/shared/agent_candidates_YEAR.csv, raw per-year Game IDs and maps_scores.
No raw or cleaned dataset was modified.
Match key: Tournament + Stage + Match Type + Match Name + Map (exact, trimmed).
no_game_id_match = no valid Game ID for the match key.
ambiguous_game_id = multiple Game IDs found for the same match key.
no_matching_map_score = no matching score key; does not prove game incomplete.
duplicate_same_selection = repeated game + team + player + agent entry.
player_game_with_multiple_agents = same game/team/player with different agents; needs review.
games_not_10_players = game has a nonstandard count of unique player/team pairs; flag only, do not automatically discard.
Issue example CSV includes up to 15 examples per issue type per year.
Important: multi-agent and missing-agent records set aside by clean_homepage.py are not validated here; review them separately before finalising pick counts.
Results are diagnostics, NOT final agent picks or completeness guarantees.
