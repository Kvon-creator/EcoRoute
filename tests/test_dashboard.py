"""Artifact and UI checks; prepared graphs here are synthetic test fixtures."""

import json
from pathlib import Path
import shutil

import networkx as nx
import osmnx as ox
import pytest
from shapely.geometry import LineString
from streamlit.testing.v1 import AppTest

from src.dashboard import file_digest, load_prepared_graph, read_preview, route_paths
from src.routing import compare_routes


@pytest.fixture
def prepared(tmp_path):
    graph = nx.MultiDiGraph(crs="EPSG:4326")
    graph.add_node(1, x=-82.55, y=35.59)
    graph.add_node(2, x=-82.54, y=35.59)
    graph.add_node(3, x=-82.545, y=35.60)
    graph.add_edge(1, 2, key=0, length=100, fuel_liters=0.5)
    graph.add_edge(1, 3, key=0, length=80, fuel_liters=0.1)
    graph.add_edge(3, 2, key=0, length=80, fuel_liters=0.1)
    folder = tmp_path / "data/processed"
    folder.mkdir(parents=True)
    graph_path = folder / "fairview.graphml"
    ox.save_graphml(graph, graph_path)
    metadata = {"graph_sha256": file_digest(graph_path), "model_id": "TEST-FIXTURE",
                "vehicle_profile": "TEST-ONLY", "fuel_unit": "liters",
                "prediction_source": "simulation-trained"}
    metadata_path = folder / "fuel_metadata.json"
    metadata_path.write_text(json.dumps(metadata))
    return graph, graph_path, metadata_path


def test_prepared_graph_preserves_numeric_fuel_costs(prepared):
    _, graph_path, metadata_path = prepared
    graph, metadata = load_prepared_graph(graph_path, metadata_path)
    assert graph[1][2][0]["fuel_liters"] == 0.5
    assert compare_routes(graph, 1, 2).fuel_saved_liters == pytest.approx(0.3)
    assert metadata["model_id"] == "TEST-FIXTURE"


@pytest.mark.parametrize("field,value", [
    ("fuel_unit", "liters/km"), ("model_id", ""),
    ("prediction_source", "unknown"), ("graph_sha256", "bad-hash"),
])
def test_rejects_incompatible_or_mismatched_metadata(prepared, field, value):
    _, graph_path, metadata_path = prepared
    metadata = json.loads(metadata_path.read_text())
    metadata[field] = value
    metadata_path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError):
        load_prepared_graph(graph_path, metadata_path)


def test_map_uses_selected_parallel_edge_geometry():
    graph = nx.MultiDiGraph()
    graph.add_node(1, x=-82.55, y=35.59)
    graph.add_node(2, x=-82.54, y=35.59)
    graph.add_edge(1, 2, key="short", length=100, fuel_liters=0.5)
    coords = [(-82.55, 35.59), (-82.545, 35.60), (-82.54, 35.59)]
    graph.add_edge(1, 2, key="eco", length=150, fuel_liters=0.1,
                   geometry=LineString(coords))
    result = compare_routes(graph, 1, 2)
    assert route_paths(graph, result.lowest_fuel) == [[list(p) for p in coords]]
    assert route_paths(graph, result.shortest) == [[[-82.55, 35.59], [-82.54, 35.59]]]


def test_preview_is_bounded_and_does_not_fill_missing_fuel(tmp_path):
    path = tmp_path / "sample.csv"
    path.write_text("Fuel Rate[L/hr],VehId\nNaN,1\n0,1\n2,2\n")
    preview = read_preview(path, limit=2)
    assert len(preview) == 2
    assert preview["Fuel Rate[L/hr]"].isna().sum() == 1
    assert preview["Fuel Rate[L/hr]"].iloc[1] == 0


def copy_app(folder):
    destination = folder / "app.py"
    shutil.copy2(Path(__file__).resolve().parents[1] / "app.py", destination)
    return destination


def test_ui_missing_artifacts_disables_routes_without_fabricated_metrics(tmp_path):
    app = AppTest.from_file(str(copy_app(tmp_path))).run(timeout=30)
    assert not app.exception
    assert app.button[0].disabled
    assert len(app.metric) == 0
    assert any("waiting for a prepared road graph" in item.value for item in app.info)
    assert any("Fairview" in item.value for item in app.info)
    assert any("Study area: Fairview, NC" in item.value for item in app.caption)


def test_ui_renders_computed_routes_and_handles_unreachable_pair(prepared):
    _, graph_path, _ = prepared
    root = graph_path.parents[2]
    app = AppTest.from_file(str(copy_app(root))).run(timeout=30)
    assert not app.exception
    app.button[0].click().run()
    assert not app.exception
    assert app.metric[0].value == "0.3000 L"
    assert app.metric[1].value == "60.00%"
    assert app.dataframe[0].value["Distance (km)"].tolist() == [0.1, 0.16]
    app.selectbox(key="origin").select(2)
    app.selectbox(key="destination").select(1)
    app.button[0].click().run()
    assert not app.exception
    assert any("No driving route" in item.value for item in app.error)
    assert len(app.metric) == 0


def test_ui_bad_checksum_shows_error(prepared):
    _, graph_path, metadata_path = prepared
    graph_path.write_text("not a valid prepared graph")
    app = AppTest.from_file(str(copy_app(graph_path.parents[2]))).run(timeout=30)
    assert not app.exception
    assert any("checksum" in item.value for item in app.error)
