"""Tiny real GeoTIFF fixtures verify coverage and missing-data handling."""

import networkx as nx
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from src.road_network import add_node_elevations, add_edge_grades, validate_graph, save_graph, load_graph


@pytest.fixture
def raster(tmp_path):
    path = tmp_path / "dem.tif"
    with rasterio.open(path, "w", driver="GTiff", width=2, height=2, count=1,
                       dtype="float32", crs="EPSG:4326", nodata=-9999,
                       transform=from_origin(-83, 36, 0.5, 0.5)) as dataset:
        dataset.write(np.array([[600, 650], [500, -9999]], dtype="float32"), 1)
    return path


def graph_with_nodes(second=(-82.25, 35.75)):
    graph = nx.MultiDiGraph(crs="EPSG:4326")
    graph.add_node(1, x=-82.75, y=35.75)
    graph.add_node(2, x=second[0], y=second[1])
    graph.add_edge(1, 2, length=1000)
    return graph


def test_raster_sampling_and_graphml_roundtrip(raster, tmp_path):
    graph = graph_with_nodes()
    add_node_elevations(graph, raster)
    assert graph.nodes[1]["elevation"] == 600
    assert graph.nodes[2]["elevation"] == 650
    add_edge_grades(graph)
    assert graph[1][2][0]["grade"] == pytest.approx(0.05)
    path = save_graph(graph, tmp_path / "fairview.graphml")
    restored = load_graph(path)
    assert validate_graph(restored)
    assert restored[1][2][0]["grade"] == pytest.approx(0.05)
    assert restored.number_of_edges() == 1


@pytest.mark.parametrize("coordinate,message", [
    ((-81, 35.75), "does not cover"),
    ((-82.25, 35.25), "Missing elevation"),
    ((float("nan"), 35.75), "nonfinite coordinates"),
])
def test_invalid_samples_do_not_partially_mutate_graph(raster, coordinate, message):
    graph = graph_with_nodes(coordinate)
    with pytest.raises(ValueError, match=message):
        add_node_elevations(graph, raster)
    assert all("elevation" not in node for _, node in graph.nodes(data=True))


def test_grade_rejects_nonfinite_elevation():
    graph = graph_with_nodes()
    nx.set_node_attributes(graph, {1: 600, 2: float("nan")}, "elevation")
    with pytest.raises(ValueError, match="nonfinite endpoint elevations"):
        add_edge_grades(graph)


def test_validation_rejects_inconsistent_grade():
    graph = graph_with_nodes()
    nx.set_node_attributes(graph, 600, "elevation")
    add_edge_grades(graph)
    graph[1][2][0]["grade_abs"] = 1
    with pytest.raises(ValueError, match="Inconsistent"):
        validate_graph(graph)


def test_validation_rejects_empty_graph():
    with pytest.raises(ValueError, match="must contain"):
        validate_graph(nx.MultiDiGraph())
