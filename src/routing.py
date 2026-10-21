"""Compare point-to-point routes on a graph with prepared edge fuel costs.

No downloads, training, or model loading happen here. The caller supplies one
directed MultiDiGraph whose edges have `length` in meters and `fuel_liters`
predicted by the same model and vehicle profile for both route objectives.
"""

from dataclasses import dataclass
from math import fsum, isfinite
from numbers import Real
from typing import Hashable

import networkx as nx


EdgeId = tuple[Hashable, Hashable, Hashable]


@dataclass(frozen=True)
class RouteResult:
    """Exact original edge IDs allow the UI to retrieve the correct geometry."""

    nodes: tuple[Hashable, ...]
    edges: tuple[EdgeId, ...]
    distance_m: float
    fuel_liters: float


@dataclass(frozen=True)
class RouteComparison:
    shortest: RouteResult
    lowest_fuel: RouteResult
    fuel_saved_liters: float
    fuel_saved_percent: float | None


def _cost(value: object, attribute: str, edge: EdgeId) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"Edge {edge!r}: {attribute} must be a finite number.")
    cost = float(value)
    if not isfinite(cost) or cost < 0 or (attribute == "length" and cost == 0):
        rule = "positive" if attribute == "length" else "nonnegative"
        raise ValueError(f"Edge {edge!r}: {attribute} must be finite and {rule}.")
    return cost


def _route(graph: nx.DiGraph, origin: Hashable, destination: Hashable) -> RouteResult:
    nodes = tuple(nx.dijkstra_path(graph, origin, destination, weight="weight"))
    steps = [graph[u][v] for u, v in zip(nodes, nodes[1:])]
    return RouteResult(
        nodes=nodes,
        edges=tuple(step["edge_id"] for step in steps),
        distance_m=fsum(step["length"] for step in steps),
        fuel_liters=fsum(step["fuel_liters"] for step in steps),
    )


def compare_routes(
    graph: nx.MultiDiGraph, origin: Hashable, destination: Hashable
) -> RouteComparison:
    """Find distance-minimizing and predicted-fuel-minimizing directed routes.

    Validate *all* edges to prevent NetworkX's missing-weight default of 1.
    Lengths must be positive; fuel costs may be zero but must be nonnegative.
    Never convert liters/km to liters implicitly: that belongs in the model
    adapter. This function cannot verify the provenance of supplied costs.

    Parallel edges are selected separately for each objective; ties retain the
    first inserted edge. Metrics use those exact selected edges. Input graph
    attributes and topology remain unchanged.

    Raises TypeError for an unsupported graph, ValueError for invalid costs,
    nx.NodeNotFound for absent endpoints, and nx.NetworkXNoPath if unreachable.
    A valid same-node trip has no edges and zero totals. Percentage savings is
    None when the shortest route's fuel total is zero (undefined denominator).
    """
    if not isinstance(graph, nx.MultiDiGraph):
        raise TypeError("Expected a directed NetworkX MultiDiGraph.")
    for label, node in (("Origin", origin), ("Destination", destination)):
        if node not in graph:
            raise nx.NodeNotFound(f"{label} node {node!r} is not in the graph.")

    distance_graph = nx.DiGraph()
    fuel_graph = nx.DiGraph()
    distance_graph.add_nodes_from(graph)
    fuel_graph.add_nodes_from(graph)

    for u, v, key, attributes in graph.edges(keys=True, data=True):
        edge_id = (u, v, key)
        length = _cost(attributes.get("length"), "length", edge_id)
        fuel = _cost(attributes.get("fuel_liters"), "fuel_liters", edge_id)
        for target, weight in ((distance_graph, length), (fuel_graph, fuel)):
            if not target.has_edge(u, v) or weight < target[u][v]["weight"]:
                target.add_edge(
                    u, v, weight=weight, edge_id=edge_id,
                    length=length, fuel_liters=fuel,
                )

    shortest = _route(distance_graph, origin, destination)
    lowest_fuel = _route(fuel_graph, origin, destination)
    saved = shortest.fuel_liters - lowest_fuel.fuel_liters
    percent = (
        saved / shortest.fuel_liters * 100
        if shortest.fuel_liters > 0 else None
    )
    return RouteComparison(shortest, lowest_fuel, saved, percent)
