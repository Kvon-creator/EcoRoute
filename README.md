# EcoRoute

Point-to-point route comparison for a small Fairview study area is under
development. The existing `main.py` remains a separate synthetic fleet-solver
demo. A Streamlit dashboard can review current source data. Fairview route
predictions still require a prepared graph and compatible fuel costs.

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
not measure Fairview fuel savings. The dashboard can load a prepared GraphML
file with precomputed costs; live model inference, feature adapters and coordinate
snapping remain unimplemented. See `PROJECT_PLAN.md` for ownership and data gaps.

## Downloaded fuel-data candidate

The original University of Michigan VED telemetry archives and vehicle
spreadsheets are now available locally under `data/VED/raw/`. One week has been
extracted and inspected. Fuel labels are sparse in that sample; this is a
training-data candidate, not a trained model or Fairview prediction output.
See `data/VED/README.md` for provenance, verified downloads, inspection results,
and reproduction commands.

## Dashboard

The study area is Fairview, NC, centered on Azalea's coordinates
`(35.5305, -82.4036)`. `src/study_area.py` shares the coordinates, graph path,
and 5,000-meter bounding-box distance across GIS preparation and the app.
The requested area is roughly 10 km across; it is not a municipal boundary.
The Fairview GIS graph has been built locally: 779 nodes and 1,652 directed
edges with real sampled elevations and signed grades. The saved graph reloads
and all nodes are covered by the verified USGS raster. The graph currently has
no predicted fuel costs. `data/GIS/fairview_build_report.json` records the
checks, source URLs, units, versions, and artifact hashes.

To reproduce from the repository root:

```powershell
.\.venv\Scripts\python.exe -m scripts.fetch_fairview_dem
.\.venv\Scripts\python.exe -m scripts.build_road_network
.\.venv\Scripts\python.exe -m scripts.inspect_fairview_graph
```

This downloads roads and builds the GIS graph; it does not predict fuel use.
No old Asheville graph is automatically reused under the Fairview name.
The 483 MB USGS raster and generated graph stay local and ignored by Git.
The downloader checks the source MD5 and records SHA-256; USGS metadata in
`data/USGS/fairview_dem_metadata.xml` confirms meters and NAVD88. Its publication
date is 2017-11-14, so elevation is a historical surface rather than a current
survey. Slopes are endpoint rise divided by edge length. Estimated speed
(`speed_kph`) is not yet attached; the ML adapter must establish usable inputs.

Raster sampling rejects out-of-coverage, masked/nodata, and nonfinite samples
without partially changing node elevations. Full turn restrictions are not
modeled. Fresh OSM downloads can change the graph; regenerate the build report
after rebuilding. The GIS report is not `fuel_metadata.json` and must not be
used as a substitute for prediction provenance.

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The Current data tab shows bounded previews of the real VED and Fleet DNA CSVs,
the saved first-week inspection, and missing fuel readings. VED is identified as
Ann Arbor data. Source previews do not produce fuel predictions. No model is
trained and no dataset is downloaded during a UI rerun.

With the GIS graph alone, the Route comparison tab displays the real road
network, node/edge counts, elevation range, and hover details for road length
and signed slope. No model or fuel metadata is required for this GIS preview.
Fuel comparison stays disabled until both of these locally prepared artifacts
exist:

- `data/processed/fairview.graphml`: directed OSMnx MultiDiGraph in EPSG:4326.
  Nodes need numeric longitude `x` and latitude `y`. Every edge needs positive
  `length` in meters and finite nonnegative `fuel_liters` predicted offline with
  one model and vehicle profile. Actual road geometry is used where provided;
  other segments are drawn between endpoints.
- `data/processed/fuel_metadata.json`: JSON object containing `graph_sha256`
  (SHA-256 of the GraphML file), `model_id`, `vehicle_profile`, `fuel_unit`
  (`liters`), and `prediction_source` (`measured-trained` or
  `simulation-trained`). This records team-provided provenance, not independently
  validated accuracy. Do not create metadata to pass off test weights as a model.

The app checks the checksum and caches loading by both artifact content hashes.
Select existing road node IDs and calculate to see a blue shortest route, a
green lowest-predicted-fuel route, metrics, a table and a fuel comparison chart.
Map tiles require internet; prepared routing computation is local. Loading a
Joblib model and converting its predictions onto edges remains a later ML
integration step. Nothing automatically trains or infers from VED files.

## Evaluation preparation

`src/evaluation.py` records successful, identical, and failed route comparisons.
Once the prepared graph and metadata exist, supply a CSV with `origin` and
`destination` columns and 10-20 node-ID pairs:

```powershell
.\.venv\Scripts\python.exe scripts/run_evaluation.py --pairs data/evaluation_pairs.csv
```

The pair CSV must be created from the real graph; none is fabricated in this
change. Output defaults to `data/processed/route_evaluation.csv` and includes
distances, predicted fuel, predicted savings, errors, and artifact provenance.
Missing graph/metadata stops the command without generating benchmark results.
Optimizing and evaluating with the same model does not establish measured
real-world savings.
