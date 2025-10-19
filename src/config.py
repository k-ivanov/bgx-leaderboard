"""Configuration and constants for the BGX Navigation Dashboard."""

from pathlib import Path

# Version
APP_VERSION = "0.0.1"

# Paths
BASE_DIR = Path(__file__).parent.parent
RESULTS_PATH = BASE_DIR / "data" / "bgx-result-2025-full"
DB_PATH = BASE_DIR / "data" / "visits.db"

# Server settings
DEFAULT_PORT = 5001
DEFAULT_HOST = "0.0.0.0"

# Define categories with display names
CATEGORIES = {
    "profi": "Pro",
    "expert": "Expert",
    "standard": "Standard",
    "standard_junior": "Standard Junior",
    "junior": "Junior",
    "women": "Women",
    "seniors_40": "Senior 40+",
    "seniors_50": "Senior 50+"
}

# Define the desired race order
RACE_ORDER = [
    'Race_kyrnare',
    'Race_stara_zagora',
    'Race_buhovo',
    'Race_gorna_malina',
    'Race_alba_damascena',
    'Race_six_days',
    'Race_kirkovo'
]

