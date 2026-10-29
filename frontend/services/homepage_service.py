"""
views/homepage.py calls only the two functions below. Replace the backend calls or adapt
field names here; no Streamlit layout changes are needed.
"""

# CONNECTION POINT: replace this import with your real backend module when ready.
# Keep it while developing against the existing JSON file.
from backend.homepage import service as backend


class DataServiceError(Exception):
    """Backend failure that the homepage can display with a retry action."""


def get_seasons():
    """Return integer years, newest first. [] means no seasons yet."""
    try:
        # MEMBER 1: call your available-seasons function here.
        return sorted(set(backend.get_seasons()), reverse=True)
    except Exception as error:
        raise DataServiceError("Available seasons could not be loaded.") from error


def get_homepage_data(season):
    """Return one snapshot for the selected integer year.

    summary: {"tournaments": int, "matches": int, "teams": int}
    maps:    [{"name": str, "games": int}]
    agents:  [{"name": str, "picks": int}]
    teams:   [{"id": str, "name": str}]

    The backend calculates counts. This adapter maps fields and orders rows.
    Empty seasons return zero counts and empty lists. Images/roles belong to UI.
    """
    try:
        # MEMBER 1: call your season-statistics function here.
        result = backend.get_homepage_data(season)

        # FIELD MAPPING: adapt the right-hand expressions to your backend.
        # Preserve these output keys so views/homepage.py does not need editing.
        return {
            "summary": {
                "tournaments": result["summary"]["tournaments"],
                "matches": result["summary"]["matches"],
                "teams": result["summary"]["teams"],
            },
            "maps": sorted(result["maps"], key=lambda row: (-row["games"], row["name"])),
            "agents": sorted(result["agents"], key=lambda row: (-row["picks"], row["name"])),
            "teams": sorted(result["teams"], key=lambda row: row["name"]),
        }
    except Exception as error:
        raise DataServiceError("Season statistics could not be loaded.") from error
