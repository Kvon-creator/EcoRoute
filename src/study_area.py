"""Shared Fairview defaults; artifact paths are relative to the project root."""

from pathlib import Path

STUDY_AREA_LABEL = "Fairview, NC"
FAIRVIEW_CENTER = (35.5305, -82.4036)  # Latitude, longitude from Azalea's setup.
DEFAULT_DISTANCE_METERS = 5000  # OSMnx bbox distance; roughly 10 km across.
DEFAULT_GRAPH_PATH = Path("data/processed/fairview.graphml")
