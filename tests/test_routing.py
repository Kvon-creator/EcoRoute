"""Artificial graph weights verify algorithms, not Fairview fuel savings."""

from copy import deepcopy

import networkx as nx
import pytest

from src.routing import compare_routes


def test_distance_and_fuel_take_different_paths_without_mutation():
    graph = nx.MultiDiGraph()
    graph.add_edge(1, 2, length=100, fuel_liters=0.4)
    graph.add_edge(2, 4, length=100, fuel_liters=0.4)
    graph.add_edge(1, 3, length=150, fuel_liters=0.1)
    graph.add_edge(3, 4, length=150, fuel_liters=0.1)
    original = deepcopy(graph)

    result = compare_routes(graph, 1, 4)

    assert result.shortest.nodes == (1, 2, 4)
    assert result.lowest_fuel.nodes == (1, 3, 4)
    assert result.shortest.distance_m == 200
    assert result.lowest_fuel.distance_m == 300
    assert result.shortest.fuel_liters == pytest.approx(0.8)
    assert result.lowest_fuel.fuel_liters == pytest.approx(0.2)
    assert result.fuel_saved_liters == pytest.approx(0.6)
    assert result.fuel_saved_percent == pytest.approx(75)
    assert nx.utils.graphs_equal(graph, original)


def test_parallel_edges_keep_correct_identity_and_metrics():
    graph = nx.MultiDiGraph()
    graph.add_edge("A", "B", key="short", length=100, fuel_liters=0.5)
    graph.add_edge("A", "B", key="eco", length=130, fuel_liters=0.2)
    graph.add_edge("B", "C", key=7, length=50, fuel_liters=0.1)

    result = compare_routes(graph, "A", "C")

    assert result.shortest.edges == (("A", "B", "short"), ("B", "C", 7))
    assert result.lowest_fuel.edges == (("A", "B", "eco"), ("B", "C", 7))
    assert result.shortest.distance_m == 150
    assert result.lowest_fuel.distance_m == 180
    assert result.shortest.fuel_liters == pytest.approx(0.6)
    assert result.lowest_fuel.fuel_liters == pytest.approx(0.3)


def test_one_way_and_disconnected_nodes():
    graph = nx.MultiDiGraph()
    graph.add_edge(1, 2, length=100, fuel_liters=0.1)
    graph.add_node(3)
    assert compare_routes(graph, 1, 2).shortest.nodes == (1, 2)
    for origin, destination in [(2, 1), (1, 3)]:
        with pytest.raises(nx.NetworkXNoPath):
            compare_routes(graph, origin, destination)


@pytest.mark.parametrize("origin,destination", [(9, 1), (1, 9)])
def test_missing_endpoints(origin, destination):
    graph = nx.MultiDiGraph()
    graph.add_node(1)
    with pytest.raises(nx.NodeNotFound):
        compare_routes(graph, origin, destination)


@pytest.mark.parametrize("attribute,bad_value", [
    ("length", None), ("length", 0), ("length", -1),
    ("length", float("nan")), ("length", float("inf")),
    ("length", "100"), ("length", True),
    ("fuel_liters", None), ("fuel_liters", -0.1),
    ("fuel_liters", float("nan")), ("fuel_liters", float("inf")),
    ("fuel_liters", "0.1"), ("fuel_liters", False),
])
def test_invalid_weights_are_rejected_even_on_unused_edges(attribute, bad_value):
    graph = nx.MultiDiGraph()
    graph.add_edge(1, 2, length=10, fuel_liters=0.1)
    graph.add_edge(3, 4, length=10, fuel_liters=0.1)
    if bad_value is None:
        del graph[3][4][0][attribute]
    else:
        graph[3][4][0][attribute] = bad_value
    with pytest.raises(ValueError, match=attribute):
        compare_routes(graph, 1, 2)


def test_identical_routes_have_zero_savings():
    graph = nx.MultiDiGraph()
    graph.add_edge(1, 2, length=100, fuel_liters=0.2)
    result = compare_routes(graph, 1, 2)
    assert result.shortest == result.lowest_fuel
    assert result.fuel_saved_liters == 0
    assert result.fuel_saved_percent == 0


def test_zero_fuel_is_allowed_and_percentage_is_undefined():
    graph = nx.MultiDiGraph()
    graph.add_edge(1, 2, length=100, fuel_liters=0)
    result = compare_routes(graph, 1, 2)
    assert result.shortest.fuel_liters == 0
    assert result.fuel_saved_liters == 0
    assert result.fuel_saved_percent is None


def test_same_node_returns_empty_trip():
    graph = nx.MultiDiGraph()
    graph.add_node(1)
    result = compare_routes(graph, 1, 1)
    assert result.shortest.nodes == (1,)
    assert result.shortest.edges == ()
    assert result.shortest.distance_m == 0
    assert result.shortest.fuel_liters == 0
    assert result.lowest_fuel == result.shortest
    assert result.fuel_saved_percent is None


@pytest.mark.parametrize("graph", [nx.Graph(), nx.DiGraph(), nx.MultiGraph()])
def test_unsupported_graph_type(graph):
    with pytest.raises(TypeError, match="MultiDiGraph"):
        compare_routes(graph, 1, 2)
