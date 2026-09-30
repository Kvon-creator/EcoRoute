# main.py
import numpy as np
from src.solver.schemas import EnergyCostMatrix
from src.solver.gvrp_solver import solve_gvrp

def run_solver_demo():
    print("=== EcoRoute: GVRP Solver Prototype ===")
    
    # Generate a synthetic 6x6 energy cost matrix (liters of fuel burned)
    np.random.seed(42)
    locations = 6
    synthetic_matrix = np.random.uniform(1.2, 5.8, size=(locations, locations))
    np.fill_diagonal(synthetic_matrix, 0.0)

    cost_data = EnergyCostMatrix(
        num_locations=locations,
        cost_matrix=synthetic_matrix.tolist()
    )

    # Depot at index 0, delivery demands in kg
    demands = [0.0, 150.0, 200.0, 100.0, 300.0, 120.0]
    vehicle_capacities = [500.0, 500.0]  # Two delivery trucks

    result = solve_gvrp(cost_data, demands, vehicle_capacities)

    print(f"Status: {result.status}")
    print(f"Total Predicted Fleet Fuel Burn: {result.total_fleet_energy:.2f} L")
    for r in result.routes:
        print(f" • Vehicle {r.vehicle_id}: Stops {r.stops} | Energy: {r.total_energy:.2f} L")

if __name__ == "__main__":
    run_solver_demo()