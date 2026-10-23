import networkx as nx
import pytest

from src.road_network import (
    add_edge_grades,
    validate_graph,
)


def make_test_graph():
    """
    Create a small directed graph for testing road grade logic.
    """

    graph = nx.MultiDiGraph()

    #Two nodes with known coordinates and elevations.
    graph.add_node(
        1,
        x=-82.40,
        y=35.53,
        elevation=500.0,
    )

    graph.add_node(
        2,
        x=-82.39,
        y=35.54,
        elevation=512.0,
    )

    #Forward edge is uphill.
    graph.add_edge(
        1,
        2,
        key=0,
        length=200.0,
    )

    #Reverse edge is downhill.
    graph.add_edge(
        2,
        1,
        key=0,
        length=200.0,
    )

    return graph


def test_signed_edge_grades():
    """
    Confirm uphill and downhill directions keep different signs.
    """

    graph = make_test_graph()

    add_edge_grades(graph)

    uphill = graph[1][2][0]["grade"]
    downhill = graph[2][1][0]["grade"]

    #12 meter rise over 200 meters equals a 6 percent grade.
    assert uphill == pytest.approx(0.06)

    #The reverse direction should be the same slope but negative.
    assert downhill == pytest.approx(-0.06)


def test_absolute_grade():
    """
    Confirm grade_abs stores steepness without direction.
    """

    graph = make_test_graph()

    add_edge_grades(graph)

    uphill_abs = graph[1][2][0]["grade_abs"]
    downhill_abs = graph[2][1][0]["grade_abs"]

    assert uphill_abs == pytest.approx(0.06)
    assert downhill_abs == pytest.approx(0.06)


def test_validate_graph():
    """
    Confirm a complete graph passes validation.
    """

    graph = make_test_graph()

    add_edge_grades(graph)

    assert validate_graph(graph) is True


def test_missing_length_rejected():
    """
    Confirm an edge without distance data is rejected.
    """

    graph = nx.MultiDiGraph()

    graph.add_node(
        1,
        x=-82.40,
        y=35.53,
        elevation=500.0,
    )

    graph.add_node(
        2,
        x=-82.39,
        y=35.54,
        elevation=510.0,
    )

    #This edge intentionally has no length.
    graph.add_edge(
        1,
        2,
        key=0,
    )

    with pytest.raises(ValueError):
        add_edge_grades(graph)


def test_invalid_length_rejected():
    """
    Confirm zero or negative road lengths are rejected.
    """

    graph = nx.MultiDiGraph()

    graph.add_node(
        1,
        x=-82.40,
        y=35.53,
        elevation=500.0,
    )

    graph.add_node(
        2,
        x=-82.39,
        y=35.54,
        elevation=510.0,
    )

    #A zero-length road cannot produce a valid grade.
    graph.add_edge(
        1,
        2,
        key=0,
        length=0.0,
    )

    with pytest.raises(ValueError):
        add_edge_grades(graph)