# EcoRoute

Point-to-point route comparison for a small Asheville study area is under
development. The existing `main.py` remains a separate synthetic fleet-solver
demo. No Asheville fuel predictions or dashboard are available yet.

## Setup and checks

Use Python 3.12. From the repository root in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe main.py
```

## Routing module

`src.routing.compare_routes(graph, origin, destination)` accepts a directed
NetworkX `MultiDiGraph` and existing node IDs. Every edge must contain numeric
`length` in meters (positive) and `fuel_liters` (nonnegative and finite). The
caller must prepare fuel costs using the same model and vehicle profile for
both objectives. Rates in liters/km must be converted to segment liters before
calling this function. Missing costs are rejected rather than defaulted.

The returned `RouteComparison` contains:

- `shortest` and `lowest_fuel`, each with `nodes`, exact `(u, v, key)` `edges`,
  `distance_m`, and `fuel_liters`.
- `fuel_saved_liters` and `fuel_saved_percent`, relative to the shortest route.
  Percentage savings is `None` if the reference fuel total is zero.

Both paths use Dijkstra. Parallel edges are chosen separately for each
objective and their exact IDs are retained for future map rendering. A trip
from a node to itself has no edges and zero totals. An unreachable trip raises
`networkx.NetworkXNoPath`; an absent endpoint raises `networkx.NodeNotFound`.
Invalid weights raise `ValueError`, and unsupported graph types raise
`TypeError`. The input graph is not modified.

Run only the independent routing tests with:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_routing.py -q
```

The tests use artificial graphs and costs to verify routing behavior. They do
not measure Asheville fuel savings. Real graph/model loading, feature adapters,
coordinate snapping, and the Streamlit UI remain unimplemented. See
`PROJECT_PLAN.md` for ownership and data gaps.

## Downloaded fuel-data candidate

The original University of Michigan VED telemetry archives and vehicle
spreadsheets are now available locally under `data/VED/raw/`. One week has been
extracted and inspected. Fuel labels are sparse in that sample; this is a
training-data candidate, not a trained model or Asheville prediction output.
See `data/VED/README.md` for provenance, verified downloads, inspection results,
and reproduction commands.
