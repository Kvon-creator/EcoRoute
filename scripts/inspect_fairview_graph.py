"""Reload and verify the prepared GIS graph, recording source provenance.

This does not create fuel_metadata.json or attach fuel costs.
"""

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path

import networkx as nx
import numpy as np
import rasterio
from pyproj import Transformer
from osmnx.utils_geo import bbox_from_point

from src.road_network import DEFAULT_DEM_PATH, add_node_elevations, load_graph, validate_graph
from src.study_area import DEFAULT_GRAPH_PATH, FAIRVIEW_CENTER, DEFAULT_DISTANCE_METERS

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    graph_path, dem_path = ROOT / DEFAULT_GRAPH_PATH, ROOT / DEFAULT_DEM_PATH
    graph = load_graph(graph_path)
    validate_graph(graph)
    stored = {node: float(attrs["elevation"]) for node, attrs in graph.nodes(data=True)}
    add_node_elevations(graph, dem_path)
    if any(not np.isclose(stored[node], attrs["elevation"]) for node, attrs in graph.nodes(data=True)):
        raise ValueError("Saved node elevations disagree with the current raster.")
    for u, v, key, attrs in graph.edges(keys=True, data=True):
        expected = (stored[v] - stored[u]) / float(attrs["length"])
        if not np.isclose(float(attrs["grade"]), expected):
            raise ValueError(f"Saved grade disagrees with sampled elevations on {(u,v,key)}")
    bbox = tuple(float(x) for x in bbox_from_point(FAIRVIEW_CENTER, dist=DEFAULT_DISTANCE_METERS))
    with rasterio.open(dem_path) as dem:
        transformer = Transformer.from_crs("EPSG:4326", dem.crs, always_xy=True)
        corners = [transformer.transform(x,y) for x in (bbox[0],bbox[2]) for y in (bbox[1],bbox[3])]
        if not all(dem.bounds.left <= x < dem.bounds.right and dem.bounds.bottom < y <= dem.bounds.top for x,y in corners):
            raise ValueError("Raster does not cover the complete requested study box.")
        raster_details = {"crs": str(dem.crs), "bounds": list(dem.bounds),
                          "pixel_size_degrees": list(dem.res), "nodata": dem.nodata}
    source_path = ROOT / "data/USGS/fairview_dem_source.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    if digest(dem_path) != source["sha256"]:
        raise ValueError("Raster checksum no longer matches its source manifest.")
    grades = [float(attrs["grade"]) for *_, attrs in graph.edges(data=True)]
    report = {
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "study_area": "Fairview, NC", "center_lat_lon": list(FAIRVIEW_CENTER),
        "distance_m": DEFAULT_DISTANCE_METERS, "bbox_wgs84_west_south_east_north": bbox,
        "graph_path": DEFAULT_GRAPH_PATH.as_posix(), "graph_sha256": digest(graph_path),
        "graph_size_bytes": graph_path.stat().st_size, "graph_crs": str(graph.graph["crs"]),
        "osm_graph_created_date": graph.graph.get("created_date"),
        "osm_source": "https://overpass-api.de/api", "osm_attribution": "OpenStreetMap contributors, ODbL",
        "nodes": graph.number_of_nodes(), "directed_edges": graph.number_of_edges(),
        "weak_components": nx.number_weakly_connected_components(graph),
        "strong_components": nx.number_strongly_connected_components(graph),
        "oneway_edges": sum(bool(attrs.get("oneway", False)) for *_, attrs in graph.edges(data=True)),
        "elevation_range_m": [min(stored.values()), max(stored.values())],
        "signed_grade_range": [min(grades), max(grades)],
        "absolute_grade_percentiles_50_95_99_100": np.percentile(np.abs(grades), [50,95,99,100]).tolist(),
        "edges_with_speed_kph": sum("speed_kph" in attrs for *_, attrs in graph.edges(data=True)),
        "edges_with_fuel_liters": sum("fuel_liters" in attrs for *_, attrs in graph.edges(data=True)),
        "raster": raster_details, "raster_source": source,
        "units": {"length": "meters", "elevation": "meters (USGS product metadata)", "grade": "rise/run"},
        "checks": {"all_nodes_covered_and_sampled": True, "study_box_covered": True,
                   "saved_grades_match_elevations": True, "graphml_reload": True},
        "versions": {name: importlib.metadata.version(name) for name in ("osmnx","networkx","rasterio","pyproj")},
        "limitations": ["Historical elevation raster; source publication date recorded in manifest.",
                        "Grade is endpoint rise divided by edge length, not a full road elevation profile.",
                        "One-way topology is retained; complete turn restrictions are not modeled.",
                        "GIS artifact only; no model, fuel predictions, or fuel metadata created."],
    }
    destination = ROOT / "data/GIS/fairview_build_report.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
