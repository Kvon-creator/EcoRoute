# EcoRoute: three-person Fairview route comparison

## Scope and current state

Build a local Streamlit app comparing the shortest-distance driving route with the route having the lowest predicted fuel use, for the same origin and destination in a small Fairview study area. Use one fixed vehicle profile and one offline graph. Display both routes, distance in km, estimated fuel in liters, and the difference. Identical routes and zero savings are valid outcomes. Predictions are estimates, not measured savings.

Inspection baseline: Git commit `6db94b0cb8fed7d71283a7278e374648516374df`, cloned from https://github.com/Kvon-creator/EcoRoute on 2026-10-21. No local checkout was present in the chat workspace. This plan preserves all existing source code and tests. Proposed paths below are future work unless listed in the inventory.

Defer fleet optimization, multiple delivery stops, changing payload, time windows, EV charging, traffic prediction, accounts, databases, cloud deployment, and a mobile app. Keep the existing fleet prototype runnable independently.

## Files actually found

| Path | Finding and reuse |
| --- | --- |
| `README.md` | Only `# EcoRoute`; no setup, architecture, or data instructions. |
| `requirements.txt` | Initially OR-Tools, Pydantic, NetworkX, pytest, NumPy, all with lower bounds. Preserve these for the prototype. |
| `main.py` | Console demo: seeded synthetic 6x6 fuel-cost matrix, six stops, two capacity-constrained trucks. Preserve its entry point; it is not a Streamlit app. |
| `src/__init__.py`, `src/solver/__init__.py` | Empty package markers. |
| `src/solver/schemas.py` | Pydantic Waypoint, EnergyCostMatrix, RouteLeg, VehicleRoute, OptimizationResult. Waypoint coordinates and unit conventions are useful references. Fleet result types need not be forced onto point-to-point routes. |
| `src/solver/gvrp_solver.py` | OR-Tools capacity-constrained fleet solver over a supplied cost matrix. Reusable for a later fleet extension; it does not load OSM, learn fuel costs, or find street paths. |
| `tests/test_solver.py` | Two tests: depot return in a feasible case and capacity infeasibility. Keep both. No GIS, ML, or UI tests. |
| `.gitignore` | Broad Python template; already excludes environments, pytest cache, and Streamlit secrets. |
| `EcoRoute.code-workspace` | VS Code workspace targeting the repository root. |
| `data/NLR Delivery Truck Data/data_for_fleet_dna_delivery_trucks.csv` | 553 records, 372 columns, 36 vehicle IDs. Contains daily driving summaries; `fuel_id` is the only column matching fuel/liter/gallon/consumption terms. No measured fuel-volume target found. 6,598 cells are empty or `nan`. |
| `data/NLR Delivery Truck Data/fleet_dna_delivery_trucks_report.pdf` | 47-page Fleet DNA summary report; extracted text describes daily fleet summaries, 36 vehicles and 553 operational days. Useful for context and checking units, not segment-level fuel labels. |
| `data/OpenStreetMap Asheville/Go to this link.txt` | OSM relation URL and a Gemini discussion link. These are references, not a downloaded routable graph. |
| `data/USGS/raw/data.txt` | 16 raster download URLs; no preparation code. |
| `data/USGS/raw/USGS_13_n36w082_20260417.tif` | A 137-byte Git LFS pointer specifying a 481,548,211-byte object. Raster bytes are absent. No tracked `.gitattributes` was found. |

No graph, processed edge table, training script, trained Joblib artifact, Streamlit entry point, dependency lock, CI workflow, or additional application modules were found in the tracked tree.

Existing solver limitations, left unchanged: matrix dimensions, nonnegative finite costs, and vector lengths are not validated; float demands/capacities are truncated to integers; objective costs are truncated after scaling by 1,000; `distance_m` remains the schema default; no time-window dimension is implemented; all no-solution outcomes are called INFEASIBLE, so a timeout cannot be distinguished. Avoid presenting its feasible result as proven optimal.

## Data decisions before implementation

Study-area update: the user selected Fairview using Azalea's existing
coordinates. GIS preparation, dashboard loading, and evaluation now share
`src/study_area.py` and use `data/processed/fairview.graphml`. Original raw
source folders retain their historical filenames. This rename does not create
a graph, validate a raster, or generate fuel predictions.

1. Use the existing center `(35.5305, -82.4036)` from Azalea for Fairview, NC. Keep the configured 5,000-meter OSMnx bounding-box distance (roughly 10 km across), not a formal municipal boundary. Commit the final bounding box, CRS, download date, OSM attribution, and 5-10 preset locations in a small metadata file. Restrict inputs to those presets initially. Preserve directed roads and parallel edges; this is a study-area comparison, not a claim about routes outside its boundary or full turn-restriction navigation.
2. Download and save one OSMnx drive graph as GraphML. Check connectivity and select preset pairs with directed paths. Record missing speed limits and a consistent road-class speed-imputation rule. Estimated speed is not observed traffic speed.
3. Resolve elevation coverage before adding grade. The GIS code expects `USGS_13_n36w083_20171114.tif`, which is not currently downloaded. Inspect its actual bounds and CRS and verify coverage of the entire Fairview study area. The existing `n36w082` file is a different tile and only a Git LFS pointer. Check nodata, vertical units, and node coverage. Do not download every URL. Prefer a documented GIS export with node elevations if it avoids adding raster tooling to every teammate's environment.
4. Bryce must obtain a documented segment-level fuel target and features available at inference time. The committed daily summaries cannot be joined directly to Fairview OSM edges and do not supply that target. Do not rename `fuel_id`, kinetic intensity, or energy-density statistics as liters consumed.
5. If suitable measured labels cannot be obtained in the first milestone, use a documented fixed-vehicle fuel simulation to create labeled segments and train the model as a simulation surrogate. Label all results and evaluation as simulated. Agree this fallback meets course requirements before treating it as the project outcome. No measured real-world fuel-accuracy claim is justified. If neither path is acceptable, the fuel-prediction milestone is blocked; do not conceal it behind arbitrary weights.

## Simple architecture and shared contracts

Single Python process; offline GIS preparation and model training; file artifacts between teammates. No backend API or separate service. Use Python 3.12 on all three machines. The system `python` inspected here is 3.8.8 and is unsuitable for the proposed modern stack.

Proposed files, not created by this change:

| Future path | Owner and responsibility |
| --- | --- |
| `app.py` | K'von: Streamlit preset selectors, validation, two route layers and metrics. Keep `main.py` as the existing demo. Use Streamlit's bundled PyDeck support for route geometry to avoid another UI dependency. |
| `src/gis.py` | Azalea: prepare/load GraphML, node elevations and directed edge features. Network downloads occur in preparation, not on every UI interaction. |
| `src/ml.py` | Bryce: train a scikit-learn Pipeline and load/predict through Joblib. Use a simple baseline and one RandomForestRegressor; no model search service. |
| `src/routing.py` | K'von: snap approved presets to nodes, calculate both paths with NetworkX, retain selected edge keys, and total route metrics. |
| `data/processed/fairview.graphml` | Azalea's reproducible graph output; ignored generated file. |
| `data/processed/edge_features.csv` | Shared table keyed by `(u, v, key)`; ignored generated file. |
| `models/fuel_model.joblib` | Bryce's complete fitted preprocessing/model Pipeline; ignored generated file. |
| `models/model_metadata.json` | Commit feature order, units, target provenance, vehicle profile, training domain, metrics, seed, package versions and artifact hash. |
| `data/study_area.json` | Commit final area, preset coordinates, graph provenance, download/rebuild instructions and artifact hash. |

Start with edge inputs `length_m`, `speed_kph`, and signed `grade` (rise/run, not percent), for one fixed vehicle. Only include grade if it exists in both training labels/features and GIS inference data. Expand features only with evidence they are available at both stages. Fit all imputation/encoding inside the training Pipeline. Do not use observed end-of-trip values to predict a future route.

Prefer predicting positive fuel rate in liters/km, then set `fuel_liters = predicted_rate * length_m / 1000`. Agree on this target before training; never sum rates directly. Reject missing, infinite, zero/negative rates and unsupported inputs with a clear error rather than silently substituting costs. If a model produces invalid rates, fix or constrain it before release. Version schema and units together.

On graph load, validate that every traversable edge has finite positive length and a valid predicted fuel weight. NetworkX otherwise treats missing named weights as 1, which would corrupt comparisons. Calculate Dijkstra paths once with `length` and once with `fuel_liters` on the same directed MultiDiGraph. Keep `(u, v, key)` edge identities: for each node-pair step, choose the parallel edge minimizing the relevant objective, and use that exact edge for geometry and all totals. Do not accidentally total minimum-length edges on a fuel-minimizing path. Compare both routes using the same model and fixed vehicle profile. Lowest fuel means the minimum additive predicted cost on this graph, not guaranteed real-world minimum consumption.

Streamlit loads/caches the graph and trusted model once per artifact version. Joblib artifacts must come from the team's training process, and training/inference package versions must match. Include graph/model hashes in the cache key so replacing an artifact invalidates cached results. Missing artifacts should produce preparation instructions, not simulated results presented as real.

## Work split and milestones

| Person | Deliverables | Handoff acceptance |
| --- | --- | --- |
| K'von: routing/UI/integration | Preserve demo, implement route comparison module and Streamlit UI, manage shared schema and integration tests, document setup and demo. | Both routes use the same graph/model; exact edge geometry and totals agree; valid errors for unreachable/same-node/outside-area presets; no network requirement for prepared-demo computation. |
| Bryce: ML | Audit labels and units, resolve measured versus simulated target, establish baseline, fit Pipeline, grouped evaluation, Joblib model and metadata. | Reproducible seed; held-out MAE/RMSE compared with baseline in explicit target units; group by vehicle/trip for measured data or generating scenario for simulated data; no train/test leakage; batch prediction preserves edge order and returns valid rates. Daily summaries do not validate segment accuracy. |
| Azalea: GIS | Confirm small area, prepare directed graph, resolve DEM coverage, derive features and preset coordinates, document attribution/rebuild process. | CRS, units, nodata and one-way checks documented; sample edge grades manually inspected; graph loads offline; no LFS pointer accepted as raster; feature table and graph keys match exactly. |

Milestone 1: agree study bounds, fixed vehicle, feature/target contract and label source. Azalea produces a tiny representative graph/feature sample; Bryce produces a matching prediction contract; K'von defines comparison outputs. Stop scope expansion if labels remain unresolved.

Milestone 2: Azalea delivers graph and reproducible preprocessing; Bryce delivers baseline, fitted Pipeline and evaluation. K'von develops routing against a small deterministic graph fixture, independently of remote downloads. Training is never performed inside the UI.

Milestone 3: integrate artifacts and UI; run the existing tests plus targeted routing and inference tests. Add cases for different shortest/fuel routes, parallel-edge consistency, one-way/unreachable paths, identical routes, bad weights, missing model/features, and prediction round-trip after Joblib loading. On valid fixed-weight fixtures, fuel-route cost must be no greater than shortest-route fuel cost within numeric tolerance.

Milestone 4: freeze dependencies and artifact hashes; verify clean setup on another teammate's machine; deliver a short demo and limitations. Use relative milestones because no deadline or weekly availability was supplied.

## Dependencies and commands

Preserve the original five requirements; add OSMnx 2.x, scikit-learn 1.x, Streamlit 1.x and Joblib 1.x. NetworkX was already declared. No proven package-version conflict was present in the original lower-bound-only manifest, but it was not reproducible. OR-Tools brings numerical/data dependencies; OSMnx brings compiled GIS dependencies. Resolve them together in a clean Python 3.12 environment instead of mixing old global packages. The old NumPy lower bound is not a version pin. After a verified install, record exact resolved versions for the team before exchanging models. Do not force an arbitrary NumPy downgrade.

Rasterio is not added to the shared runtime now: no raster-processing Python code exists. If Azalea chooses Python DEM sampling, add a tested GIS preparation requirement then; otherwise export node elevations through GIS tooling. Do not add unrelated web frameworks or deep-learning packages.

PowerShell, from the repository root, with Python 3.12 installed:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe main.py
```

`main.py` currently runs only the synthetic fleet demo. After `app.py` is implemented and prepared graph/model artifacts exist, the planned UI command is:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

There is no runnable GIS preparation or ML training command yet; add those commands alongside the implementation rather than documenting nonexistent scripts as usable.

Changes in this planning pass: create this plan; add the four requested missing dependencies; ignore only OSMnx's root cache, processed GIS outputs and generated Joblib models. Keep raw source data, metadata and all working code tracked. Verification outcomes are recorded below after execution.

## Verification performed

In a fresh local Python 3.12.14 virtual environment, the updated requirements installed together successfully. `pip check` reported no broken requirements. Imports of OSMnx, NetworkX, scikit-learn, Streamlit and Joblib succeeded. Resolved direct versions: OR-Tools 9.15.6755, Pydantic 2.14.1, NetworkX 3.7, pytest 9.1.1, NumPy 2.5.4, OSMnx 2.1.1, scikit-learn 1.9.1, Streamlit 1.66.1 and Joblib 1.6.0. These observations establish compatibility in this environment, not a cross-platform lock.

`python -m pytest -q`: 2 passed in 10.66 seconds, with three third-party SWIG deprecation warnings. `python main.py`: completed with OPTIMAL_OR_FEASIBLE and synthetic fleet cost 15.73 L. The console bullet rendered incorrectly in captured output; numeric output completed successfully and source was left unchanged.

`git diff --check` passed. Ignore checks confirmed generated graph/cache/model paths are ignored while proposed metadata paths remain trackable. Source, tests, README and raw data match the baseline. No street graph was downloaded, raster retrieved, model trained, or UI implemented. Data findings above came from the CSV, pointer text, reference text files and PDF text extraction; the report's graphical layout and raster contents were not validated.

## Dashboard implementation progress

The earlier inventory is the audit baseline. Subsequent work added and tested
`src/routing.py`, then transferred the work and VED downloads to the OneDrive
VS Code checkout. The existing solver remains unchanged.

`app.py` now provides source-data review plus route-comparison controls. Actual
CSV previews and saved inspection counts are available immediately. Missing
Fairview artifacts disable routing rather than generating fake results.
`src/dashboard.py` supports prepared GraphML with precomputed fuel weights,
checksum/provenance metadata, and exact selected-edge geometry. This avoids
depending on an unfinished Joblib feature adapter. No live model inference,
coordinate snapping, address lookup, or model training has been implemented.

`src/evaluation.py` and `scripts/run_evaluation.py` prepare the 10-20-pair
evaluation workflow and retain failures. No actual Fairview benchmark was run
because the prepared graph, prediction metadata, and real node pairs are absent.
See README.md for the implemented file contract and commands.

Validation of this stage: a new `.venv` in the VS Code checkout uses Python
3.12.14; declared requirements installed successfully and `pip check` passed.
The complete suite passed 37 tests, with three existing third-party SWIG
deprecation warnings. Streamlit AppTest verified the actual local VED and Fleet
DNA previews. Fixture tests exercised route rendering, missing artifacts,
checksum errors, and unreachable nodes. A running local Streamlit server
returned HTTP 200 from its health endpoint. Browser visual inspection was not
available; interactive map appearance still needs a manual check with real
artifacts. Invoking evaluation with current files failed as expected on missing
fuel metadata and produced no benchmark CSV. No source dataset, solver code,
requirements, or ignore rules were changed in this stage.

## Fairview GIS preparation

Work on `feat/fairview-gis-data` downloaded and source-MD5-verified the USGS
`n36w083` raster already referenced by the project. Its bounds cover the whole
study box. The local graph now contains 779 nodes and 1,652 directed edges,
with one strongly connected component. Saved GraphML was reloaded, all node
elevations resampled and compared, and signed grades checked against their
endpoint elevations. The report is `data/GIS/fairview_build_report.json`.
The raw raster and generated graph are ignored local artifacts; fetch/build/
inspection scripts and source manifests make the preparation reviewable.

No fuel costs or `fuel_metadata.json` were created. Existing blockers now concern
ML inputs and predictions, not the basic GIS graph. Historical elevation and
endpoint-average grades should be considered when interpreting a future model.

Validation: 50 tests passed (three existing SWIG deprecation warnings). The
initial run hit permissions on the system pytest temporary directory; rerunning
with a fresh temporary directory inside the writable Codex workspace passed.
The live graph also passed raster resampling, full-box coverage, saved-grade
consistency, and GraphML reload checks.

## API references

- [OSMnx user reference](https://osmnx.readthedocs.io/en/stable/user-reference.html): graph acquisition, GraphML IO, nearest nodes, speed/elevation attributes.
- [NetworkX shortest paths](https://networkx.org/documentation/stable/reference/algorithms/shortest_paths.html): weighted directed routes and missing-weight behavior.
- [scikit-learn model persistence](https://scikit-learn.org/stable/model_persistence.html): Joblib persistence and matching training/inference environments.
