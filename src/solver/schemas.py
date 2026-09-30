# src/solver/schemas.py
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

class Waypoint(BaseModel):
    id: int
    name: str
    lat: float
    lon: float
    demand_kg: float = 0.0  # Cargo payload drop-off

class EnergyCostMatrix(BaseModel):
    num_locations: int
    # Matrix of predicted fuel/energy burn (Liters or kWh) between all node pairs
    cost_matrix: List[List[float]]
    # Optional travel duration matrix (seconds) for time windows
    time_matrix: Optional[List[List[float]]] = None

class RouteLeg(BaseModel):
    from_node: int
    to_node: int
    energy_consumed: float
    distance_m: Optional[float] = 0.0

class VehicleRoute(BaseModel):
    vehicle_id: int
    stops: List[int]
    total_energy: float
    legs: List[RouteLeg]

class OptimizationResult(BaseModel):
    status: str
    total_fleet_energy: float
    routes: List[VehicleRoute]