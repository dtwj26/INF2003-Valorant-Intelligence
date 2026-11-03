
"""Frontend adapter for live Teams and Players data."""

import sys
from pathlib import Path

# make the project backend importable
ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.teams_players import service as backend_service


def get_live_records(
    season,
    tournament_id="",
    map_name=""
):
    """Retrieve real Teams and Players data from Neon."""

    return backend_service.get_teams_players_data(
        season=int(season),
        tournament_id=tournament_id or None,
        map_name=map_name or None
    )
