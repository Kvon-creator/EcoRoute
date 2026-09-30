# tests/test_solver.py
import pytest
from src.solver.schemas import EnergyCostMatrix
from src.solver.gvrp_solver import solve_gvrp

def test_solver_feasible_output():
    cost_matrix = [
        [0.0, 2.0, 9.0],
        [2.0, 0.0, 3.0],
        [9.0, 3.0, 0.0]
    ]
    cost_data = EnergyCostMatrix(num_locations=3, cost_matrix=cost_matrix)
    demands = [0.0, 10.0, 10.0]
    capacities = [30.0]

    result = solve_gvrp(cost_data, demands, capacities)
    assert result.status == "OPTIMAL_OR_FEASIBLE"
    assert len(result.routes) == 1
    assert result.routes[0].stops[0] == 0
    assert result.routes[0].stops[-1] == 0

def test_solver_capacity_exceeded():
    cost_matrix = [[0.0, 1.0], [1.0, 0.0]]
    cost_data = EnergyCostMatrix(num_locations=2, cost_matrix=cost_matrix)
    demands = [0.0, 500.0]
    capacities = [100.0]  # Demand exceeds vehicle capacity

    result = solve_gvrp(cost_data, demands, capacities)
    assert result.status == "INFEASIBLE"