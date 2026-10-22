"""Batch comparison using prepared costs; results are model estimates only."""

from collections.abc import Iterable

import networkx as nx

from src.routing import compare_routes


def evaluate_pairs(graph: nx.MultiDiGraph, pairs: Iterable[tuple]) -> list[dict]:
    """Retain failed pairs and identical routes rather than filtering results."""
    rows = []
    for origin, destination in pairs:
        row = {"origin": origin, "destination": destination, "status": "error",
               "shortest_distance_km": None, "lowest_fuel_distance_km": None,
               "shortest_predicted_fuel_liters": None, "lowest_predicted_fuel_liters": None,
               "predicted_savings_liters": None, "predicted_savings_percent": None,
               "identical_routes": None, "error": ""}
        try:
            comparison = compare_routes(graph, origin, destination)
            row.update(
                status="ok", shortest_distance_km=comparison.shortest.distance_m / 1000,
                lowest_fuel_distance_km=comparison.lowest_fuel.distance_m / 1000,
                shortest_predicted_fuel_liters=comparison.shortest.fuel_liters,
                lowest_predicted_fuel_liters=comparison.lowest_fuel.fuel_liters,
                predicted_savings_liters=comparison.fuel_saved_liters,
                predicted_savings_percent=comparison.fuel_saved_percent,
                identical_routes=comparison.shortest.edges == comparison.lowest_fuel.edges,
            )
        except (nx.NodeNotFound, nx.NetworkXNoPath, TypeError, ValueError) as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)
    return rows
