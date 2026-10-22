import networkx as nx

from src.evaluation import evaluate_pairs


def test_evaluation_retains_failed_identical_and_zero_reference_pairs():
    graph = nx.MultiDiGraph()
    graph.add_edge(1, 2, length=100, fuel_liters=0)
    rows = evaluate_pairs(graph, [(1, 2), (2, 1), (1, 99)])
    assert len(rows) == 3
    assert rows[0]["status"] == "ok"
    assert rows[0]["identical_routes"] is True
    assert rows[0]["predicted_savings_liters"] == 0
    assert rows[0]["predicted_savings_percent"] is None
    assert rows[1]["status"] == "error"
    assert "NetworkXNoPath" in rows[1]["error"]
    assert rows[1]["predicted_savings_liters"] is None
    assert "NodeNotFound" in rows[2]["error"]
