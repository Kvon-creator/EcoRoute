# src/solver/gvrp_solver.py
from typing import List, Dict
import numpy as np
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from src.solver.schemas import EnergyCostMatrix, OptimizationResult, VehicleRoute, RouteLeg

def solve_gvrp(
    cost_data: EnergyCostMatrix,
    demands: List[float],
    vehicle_capacities: List[float],
    depot_index: int = 0,
    time_limit_seconds: int = 10
) -> OptimizationResult:
    """
    Solves the Green Vehicle Routing Problem (GVRP) using custom predicted energy costs.
    """
    num_vehicles = len(vehicle_capacities)
    manager = pywrapcp.RoutingIndexManager(cost_data.num_locations, num_vehicles, depot_index)
    routing = pywrapcp.RoutingModel(manager)

    # Scale float costs to integers for OR-Tools solver (e.g., milli-liters or watt-hours)
    SCALE_FACTOR = 1000
    int_cost_matrix = [
        [int(cost * SCALE_FACTOR) for cost in row]
        for row in cost_data.cost_matrix
    ]

    def energy_callback(from_index: int, to_index: int) -> int:
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int_cost_matrix[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(energy_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Add Capacity Constraints
    def demand_callback(from_index: int) -> int:
        from_node = manager.IndexToNode(from_index)
        return int(demands[from_node])

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,  # null capacity slack
        [int(c) for c in vehicle_capacities],
        True,  # start cumul to zero
        "Capacity"
    )

    # Search parameters
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.seconds = time_limit_seconds

    solution = routing.SolveWithParameters(search_parameters)

    if not solution:
        return OptimizationResult(status="INFEASIBLE", total_fleet_energy=0.0, routes=[])

    routes: List[VehicleRoute] = []
    total_fleet_energy = 0.0

    for vehicle_id in range(num_vehicles):
        index = routing.Start(vehicle_id)
        stops = []
        legs = []
        route_energy = 0.0

        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            stops.append(node)
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            next_node = manager.IndexToNode(index)

            step_energy = cost_data.cost_matrix[node][next_node]
            route_energy += step_energy
            legs.append(RouteLeg(from_node=node, to_node=next_node, energy_consumed=step_energy))

        stops.append(manager.IndexToNode(index))
        total_fleet_energy += route_energy
        routes.append(VehicleRoute(
            vehicle_id=vehicle_id,
            stops=stops,
            total_energy=route_energy,
            legs=legs
        ))

    return OptimizationResult(
        status="OPTIMAL_OR_FEASIBLE",
        total_fleet_energy=total_fleet_energy,
        routes=routes
    )