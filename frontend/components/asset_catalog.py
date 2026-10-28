"""Local image lookup by dataset ID or agent/map name. No registry or network needed."""
import unicodedata
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / 'static'
TEAM_LOGO_FALLBACK = 'team_logos/valorant.webp'

# Labels used by the homepage; image paths come directly from names below.
AGENT_ROLES = {'astra': 'Controller', 'breach': 'Initiator', 'brimstone': 'Controller', 'chamber': 'Sentinel', 'clove': 'Controller', 'cypher': 'Sentinel', 'deadlock': 'Sentinel', 'fade': 'Initiator', 'gekko': 'Initiator', 'harbor': 'Controller', 'iso': 'Duelist', 'jett': 'Duelist', 'kayo': 'Initiator', 'killjoy': 'Sentinel', 'miks': 'Controller', 'neon': 'Duelist', 'omen': 'Controller', 'phoenix': 'Duelist', 'raze': 'Duelist', 'reyna': 'Duelist', 'sage': 'Sentinel', 'skye': 'Initiator', 'sova': 'Initiator', 'tejo': 'Initiator', 'veto': 'Sentinel', 'viper': 'Controller', 'vyse': 'Sentinel', 'waylay': 'Duelist', 'yoru': 'Duelist'}


def _name_key(name):
    return ''.join(c for c in unicodedata.normalize('NFKC', str(name)).casefold() if c.isalnum())


def _existing(relative_path):
    return relative_path if (STATIC / relative_path).is_file() else None


def get_agent_image(name):
    return _existing(f'agents/{_name_key(name)}.webp')


def get_agent_role(name):
    return AGENT_ROLES.get(_name_key(name), '')


def get_map_image(name):
    return _existing(f'maps/{_name_key(name)}.webp')


def get_map_minimap(name):
    return _existing(f'maps/{_name_key(name)}_minimap.webp')


def get_team_logo(team_id=None):
    """Use the dataset's numeric VLR team ID; unknown IDs get the Valorant logo."""
    key = str(team_id).strip()
    if key.isascii() and key.isdecimal():
        logo = _existing(f'team_logos/{key}.webp')
        if logo:
            return logo
    return TEAM_LOGO_FALLBACK
