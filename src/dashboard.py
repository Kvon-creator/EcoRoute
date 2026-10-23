"""Local artifact loading and presentation helpers for the dashboard.

Prepared route costs are supplied by GIS/ML work; this module never downloads
data, trains a model, or substitutes synthetic costs.
"""

import hashlib
import json
from math import isfinite
from pathlib import Path

import networkx as nx
import osmnx as ox
import pandas as pd
from pyproj import CRS

from src.routing import RouteComparison, RouteResult
from src.road_network import validate_graph


def file_digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_prepared_graph(graph_path: Path, metadata_path: Path):
    """Load costs already predicted onto a graph, with explicit provenance.

    Metadata requires graph_sha256, model_id, vehicle_profile, fuel_unit
    ('liters'), and prediction_source ('measured-trained' or 'simulation-trained').
    Metadata is a team-supplied declaration, not an accuracy certification.
    """
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise ValueError("Fuel metadata must be a JSON object.")
    for field in ("graph_sha256", "model_id", "vehicle_profile"):
        if not isinstance(metadata.get(field), str) or not metadata[field].strip():
            raise ValueError(f"Fuel metadata is missing {field}.")
    if metadata.get("fuel_unit") != "liters":
        raise ValueError("Prepared edge fuel costs must be in liters.")
    if metadata.get("prediction_source") not in ("measured-trained", "simulation-trained"):
        raise ValueError("Metadata must identify measured-trained or simulation-trained predictions.")
    if file_digest(graph_path) != metadata["graph_sha256"]:
        raise ValueError("Road graph does not match the fuel metadata checksum.")
    return load_map_graph(graph_path), metadata


def load_map_graph(graph_path: Path):
    """Load geographic geometry without requiring or inventing fuel costs."""
    graph = ox.load_graphml(graph_path, edge_dtypes={"fuel_liters": float})
    if not isinstance(graph, nx.MultiDiGraph) or not graph.nodes:
        raise ValueError("The road graph must be a nonempty directed MultiDiGraph.")
    if CRS.from_user_input(graph.graph.get("crs")) != CRS.from_epsg(4326):
        raise ValueError("Map display requires an unprojected EPSG:4326 graph.")
    for node, attrs in graph.nodes(data=True):
        try:
            x, y = float(attrs["x"]), float(attrs["y"])
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError(f"Node {node!r} has invalid map coordinates.") from exc
        if not (isfinite(x) and isfinite(y) and -180 <= x <= 180 and -90 <= y <= 90):
            raise ValueError(f"Node {node!r} has invalid map coordinates.")
    return graph


def load_gis_preview(graph_path: Path):
    graph = load_map_graph(graph_path)
    validate_graph(graph)
    edges = ox.graph_to_gdfs(graph, nodes=False)[["length", "grade", "geometry"]].copy()
    edges["grade_percent"] = edges["grade"].astype(float) * 100
    features = json.loads(edges[["length", "grade_percent", "geometry"]].to_json(drop_id=True))
    return graph, features


def comparison_rows(result: RouteComparison) -> list[dict]:
    return [
        {"Route": label, "Distance (km)": route.distance_m / 1000,
         "Predicted fuel (L)": route.fuel_liters}
        for label, route in (("Shortest distance", result.shortest),
                             ("Lowest predicted fuel", result.lowest_fuel))
    ]


def route_paths(graph: nx.MultiDiGraph, route: RouteResult) -> list[list[list[float]]]:
    """Use each selected edge's geometry, falling back to its endpoint line.

    DeckGL renders each segment separately; reversed geometry therefore does
    not introduce a connecting line across unrelated streets.
    """
    paths = []
    for u, v, key in route.edges:
        geometry = graph[u][v][key].get("geometry")
        if geometry is None:
            coords = [(graph.nodes[u]["x"], graph.nodes[u]["y"]),
                      (graph.nodes[v]["x"], graph.nodes[v]["y"])]
        elif getattr(geometry, "geom_type", None) == "LineString":
            coords = list(geometry.coords)
        else:
            raise ValueError(f"Unsupported map geometry on edge {(u, v, key)!r}.")
        path = [[float(point[0]), float(point[1])] for point in coords]
        if len(path) < 2 or any(
            not (isfinite(x) and isfinite(y) and -180 <= x <= 180 and -90 <= y <= 90)
            for x, y in path
        ):
            raise ValueError("A route segment has invalid geographic geometry.")
        paths.append(path)
    return paths


def read_preview(path: Path, limit: int = 1000) -> pd.DataFrame:
    """Bound CSV memory use; missing telemetry values remain missing."""
    if not 1 <= limit <= 10000:
        raise ValueError("CSV preview limit must be between 1 and 10,000 rows.")
    return pd.read_csv(path, nrows=limit)
