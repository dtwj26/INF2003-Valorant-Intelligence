"""Homepage service for the Valorant Intelligence System."""

from . import repository


def get_seasons():
    """Return available VCT seasons."""
    return repository.fetch_seasons()


def get_homepage_data(season):
    """Return homepage data for the selected season."""
    return repository.fetch_homepage_data(season)
